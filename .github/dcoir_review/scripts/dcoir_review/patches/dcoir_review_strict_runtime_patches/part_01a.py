

def _candidate_kind(candidate: Any) -> str:
    text = str(getattr(candidate, "text", "") or "")
    path = str(getattr(candidate, "path", "") or "")
    normalized = _normalize(text)
    if "pull_request_target" in normalized:
        return "yaml_pull_request_target"
    if GH_WRITE_PERMISSION_RE.search(text):
        return "yaml_broad_write"
    if "github.event.pull_request.head" in normalized or "github.head_ref" in normalized:
        return "yaml_untrusted_checkout"
    if CURL_SHELL_RE.search(text):
        return "yaml_shell_pipe"
    if "extractall" in normalized:
        return "python_archive_extract"
    return _semantic_kind({"path": path, "title": normalized, "body": normalized})


def _is_natural_language(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    first = next((line.strip() for line in stripped.splitlines() if line.strip()), "")
    if NATURAL_LANGUAGE_START_RE.match(first):
        return True
    return len(first.split()) >= 5 and bool(NATURAL_LANGUAGE_WORD_RE.search(first))


def _python_is_code(value: str) -> bool:
    try:
        ast.parse(textwrap.dedent(value).strip() + "\n")
        return True
    except SyntaxError:
        return False


def _powershell_is_code(value: str) -> bool:
    lines = [line for line in value.splitlines() if line.strip()]
    return bool(lines) and all(POWERSHELL_CODE_RE.match(line) or line.strip() in {"}", "};"} for line in lines)


def _yaml_is_code(value: str) -> bool:
    lines = [line for line in value.splitlines() if line.strip()]
    return bool(lines) and any(YAML_CODE_RE.match(line) for line in lines) and not _is_natural_language(value)


def _js_ts_is_code(value: str) -> bool:
    lines = [line for line in value.splitlines() if line.strip()]
    return bool(lines) and any(JS_TS_CODE_RE.match(line) for line in lines) and not _is_natural_language(value)


def _strict_code_value_is_valid(value: Any, language: str) -> bool:
    text = _strip_fences(value)
    if not text or _is_natural_language(text):
        return False
    language = str(language or "").lower()
    if language == "python":
        return _python_is_code(text)
    if language == "powershell":
        return _powershell_is_code(text)
    if language in {"yaml", "json"}:
        return _yaml_is_code(text)
    if language in {"typescript", "javascript"}:
        return _js_ts_is_code(text)
    return not _is_natural_language(text) and any(signal in text for signal in ("=", "$", ":", "(", "{", "|", ";"))


def _code_field_invalid(result: dict[str, Any], path: str) -> bool:
    language = str(result.get("language") or _language_hint(path)).lower()
    for key in ("remove_code", "replace_code", "add_code"):
        value = _strip_fences(result.get(key, ""))
        if value and not _strict_code_value_is_valid(value, language):
            return True
    return False


def _strict_fix_guidance(result: dict[str, Any], finding: dict[str, Any], path: str) -> dict[str, str]:
    language = str(result.get("language") or _language_hint(path)).lower()
    guidance: dict[str, str] = {"language": language}
    notes: list[str] = []
    for result_key, guidance_key in (
        ("remove_code", "remove"),
        ("replace_code", "replace"),
        ("add_code", "add"),
        ("remove", "remove"),
        ("replace", "replace"),
        ("add", "add"),
    ):
        value = _strip_fences(result.get(result_key, ""))
        if not value:
            continue
        if _strict_code_value_is_valid(value, language):
            guidance[guidance_key] = value
        else:
            notes.append(value)
    raw_notes = _clean_public_text(str(result.get("notes", "") or ""))
    if raw_notes:
        notes.append(raw_notes)
    kind = _semantic_kind({**finding, "path": path})
    if kind == "python_ssrf":
        notes = [
            re.sub(r"\bhardcoded secret\b", "secret or token value", note, flags=re.IGNORECASE)
            for note in notes
            if "syntax error" not in note.lower()
        ]
    cleaned_notes: list[str] = []
    seen: set[str] = set()
    for note in notes:
        cleaned = _clean_public_text(note)
        key = _normalize(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            cleaned_notes.append(cleaned)
    if cleaned_notes:
        guidance["notes"] = "\n\n".join(cleaned_notes)
    return guidance if any(key in guidance for key in ("remove", "replace", "add", "notes")) else {}


def _normalize_existing_fix_guidance(finding: dict[str, Any]) -> dict[str, str]:
    path = str(finding.get("path", "") or "")
    raw = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    if not raw:
        return {}
    language = str(raw.get("language") or _language_hint(path)).lower()
    synthetic = {
        "language": language,
        "remove_code": raw.get("remove", ""),
        "replace_code": raw.get("replace", ""),
        "add_code": raw.get("add", ""),
        "notes": raw.get("notes", ""),
    }
    return _strict_fix_guidance(synthetic, finding, path)


def _build_strict_fix_synthesis_prompt(
    base: Any,
    finding: dict[str, Any],
    path: str,
    line: int,
    line_text: str,
    file_text: str,
    config: Any,
) -> str:
    max_file_chars = max(0, int(getattr(config, "per_file_review_max_file_chars", getattr(config, "deep_review_max_file_chars", 12000))))
    visible_text = base.sanitize_text(file_text, config)
    if len(visible_text) > max_file_chars:
        visible_text = f"{visible_text[:max_file_chars]}\n\n[full-file context truncated for fix synthesis]"
    language = _language_hint(path)
    finding_payload = json.dumps(
        {
            "title": finding.get("title", ""),
            "severity": finding.get("severity", ""),
            "confidence": finding.get("confidence", 0),
            "path": path,
            "line": line,
            "body": finding.get("body", ""),
            "validation": finding.get("validation", ""),
        },
        ensure_ascii=False,
        indent=2,
    )
    prompt = f"""
Strict fix synthesis pass for one already-detected DCOIR Review finding.

Return JSON matching the schema exactly. Do not return Markdown.

Field rules:
- suggested_replacement: exact single-line replacement code for the anchored GitHub review line only, or empty.
- remove_code: exact code/config text copied from this file that should be removed, or empty.
- replace_code: exact replacement code/config only, or empty.
- add_code: exact code/config to add only, or empty.
- notes: all prose guidance, caveats, rationale, multi-line conceptual repair steps, and any explanation.
- validation: exact validation command(s) only.
- language: the code fence language for exact code/config fields.
- start_line/end_line: the affected file line range when known; otherwise both equal the anchored line.

Hard constraints:
- Never put English sentences, labels, "the entire function", "if a governed parser...", or conceptual repair text in remove_code, replace_code, add_code, or suggested_replacement.
- If the repair is conceptual, broad, multi-file, or not exact, leave code fields empty and put the explanation in notes.
- For remove_code, prefer copying the exact anchored line text when that line is the code to remove.
- Do not invent facts not supported by the file. If a token is read from os.environ, do not call it a hardcoded secret. Do not claim syntax errors unless the shown file text is syntactically invalid.
- Do not recommend eval, exec, or dynamic execution.

File: `{path}`
Language: {language}
Anchored line: {line}
Current anchored line text:
```text
{base.sanitize_text(line_text, config)}
```

Finding:
```json
{base.sanitize_text(finding_payload, config)}
```

Full head-file context:
```{language}
{visible_text}
```
""".strip()
    prompt = base.sanitize_text(prompt, config)
    max_prompt = int(getattr(config, "max_prompt_chars", len(prompt)))
    return prompt[:max_prompt]
