

def _semantic_kind(finding: dict[str, Any]) -> str:
    path = str(finding.get("path", "") or "").strip().lower()
    text = _finding_text(finding)
    suffix = Path(path).suffix
    if suffix == ".py":
        if "pickle.loads" in text or "pickle.load" in text or ("pickle" in text and "deserial" in text):
            return "python_pickle"
        if "yaml.load" in text or "yaml.loader" in text or "loader=yaml.loader" in text:
            return "python_yaml_load"
        if "requests.get" in text or "requests.post" in text or "requests.request" in text or "ssrf" in text:
            return "python_ssrf"
        if PYTHON_DYNAMIC_EXEC_CALL_RE.search(text):
            return "python_dynamic_exec"
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if "convertto-securestring" in text and "asplaintext" in text:
            return "ps_securestring"
        if "start-process" in text:
            return "ps_start_process"
        if "currentversion\\run" in text or "run key" in text or ("set-itemproperty" in text and "\\run" in text):
            return "ps_run_key"
    if suffix in {".yml", ".yaml"}:
        if "pull_request_target" in text:
            return "yaml_pull_request_target"
        if "github.head_ref" in text or "github.event.pull_request.head" in text or ("untrusted" in text and "checkout" in text):
            return "yaml_untrusted_checkout"
        if ("curl" in text or "wget" in text) and ("|" in text or "pipe" in text) and ("bash" in text or " sh" in text):
            return "yaml_shell_pipe"
        if "write-all" in text or "broad write" in text or ("permissions" in text and "write" in text):
            return "yaml_broad_write"
    return ""


def _github_actions_kinds_from_text(text: str) -> set[str]:
    kinds: set[str] = set()
    if "pull_request_target" in text:
        kinds.add("yaml_pull_request_target")
    if "write-all" in text or "broad write" in text or ("permissions" in text and "write" in text):
        kinds.add("yaml_broad_write")
    if (
        "github.head_ref" in text
        or "github.event.pull_request.head" in text
        or ("untrusted" in text and "checkout" in text)
        or "head ref" in text
        or "head sha" in text
    ):
        kinds.add("yaml_untrusted_checkout")
    if ("curl" in text or "wget" in text) and ("bash" in text or " sh" in text) and ("pipe" in text or "|" in text):
        kinds.add("yaml_shell_pipe")
    return kinds


def _finding_anchor_kinds(finding: dict[str, Any]) -> set[str]:
    title_kinds = _github_actions_kinds_from_text(_finding_text(finding, "title"))
    body_kinds = _github_actions_kinds_from_text(_finding_text(finding))
    return title_kinds or body_kinds


def _candidate_anchor_kind(candidate: Any) -> str:
    raw_text = str(getattr(candidate, "text", ""))
    text = _normalize(raw_text)
    if "pull_request_target" in text:
        return "yaml_pull_request_target"
    if "github.head_ref" in text or "github.event.pull_request.head" in text:
        return "yaml_untrusted_checkout"
    if CURL_BASH_RE.search(raw_text):
        return "yaml_shell_pipe"
    if GH_WRITE_PERMISSION_RE.search(raw_text):
        return "yaml_broad_write"
    return ""


def _sentinel_anchor_kind(sentinel: Any) -> str:
    text = _normalize(
        "\n".join(
            [
                str(getattr(sentinel, "label", "") or ""),
                str(getattr(sentinel, "detail", "") or ""),
                str(getattr(sentinel, "text", "") or ""),
            ]
        )
    )
    kinds = _github_actions_kinds_from_text(text)
    return sorted(kinds)[0] if kinds else ""


def _language_hint_for_path(path: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    return {
        ".bash": "bash",
        ".cjs": "javascript",
        ".js": "javascript",
        ".json": "json",
        ".mjs": "javascript",
        ".ps1": "powershell",
        ".psd1": "powershell",
        ".psm1": "powershell",
        ".py": "python",
        ".sh": "bash",
        ".ts": "typescript",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix, "text")


def _clean_language(language: Any, fallback: str) -> str:
    text = str(language or "").strip().lower()
    return text if re.fullmatch(r"[a-z0-9_+.-]{1,32}", text) else fallback


def _extract_code_candidate(value: str, language: str) -> str:
    cleaned = _strip_markdown_fence_lines(value)
    first = _first_nonempty_line(cleaned)
    if not first:
        return ""
    if PROSE_GUIDANCE_START_RE.match(first):
        colon_tail = first.split(":", 1)[1].strip() if ":" in first else ""
        if colon_tail and patched_guidance_value_looks_like_code(colon_tail, language):
            return colon_tail
        candidate_lines: list[str] = []
        for line in cleaned.splitlines()[1:]:
            if not line.strip():
                continue
            if _guidance_value_is_prose(line, language):
                return ""
            if _line_looks_like_code(line, language):
                candidate_lines.append(line.rstrip())
        candidate = "\n".join(candidate_lines).strip()
        if candidate and patched_guidance_value_looks_like_code(candidate, language):
            return candidate
    for match in INLINE_CODE_RE.finditer(cleaned):
        candidate = match.group(1).strip()
        if len(candidate) > 12 and patched_guidance_value_looks_like_code(candidate, language):
            return candidate
    return ""


def _is_mismatched_python_dynamic_guidance(kind: str, value: str) -> bool:
    return kind in {"python_pickle", "python_yaml_load", "python_ssrf"} and bool(MISMATCHED_DYNAMIC_RE.search(value or ""))


def _normalize_fix_guidance(finding: dict[str, Any]) -> dict[str, str]:
    path = str(finding.get("path", "") or "")
    kind = _semantic_kind(finding)
    raw_guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    if not raw_guidance:
        return {}
    fallback_language = _language_hint_for_path(path)
    language = _clean_language(raw_guidance.get("language", ""), fallback_language)
    normalized: dict[str, str] = {"language": language}
    notes: list[str] = []

    for key in ("remove", "replace", "add"):
        raw_value = _strip_markdown_fence_lines(str(raw_guidance.get(key, "") or ""))
        if not raw_value:
            continue
        candidate = _extract_code_candidate(raw_value, language)
        if _is_mismatched_python_dynamic_guidance(kind, raw_value):
            if key == "remove" and candidate:
                normalized[key] = candidate
            continue
        if patched_guidance_value_looks_like_code(raw_value, language):
            normalized[key] = raw_value
        elif candidate:
            normalized[key] = candidate
            if key != "remove":
                notes.append(raw_value)
        else:
            notes.append(raw_value)

    raw_notes = _strip_markdown_fence_lines(str(raw_guidance.get("notes", "") or ""))
    if raw_notes and not _is_mismatched_python_dynamic_guidance(kind, raw_notes):
        notes.append(raw_notes)
    default_note = _KIND_DEFAULT_NOTES.get(kind, "")
    if default_note and (not notes or any(_is_mismatched_python_dynamic_guidance(kind, item) for item in notes)):
        notes = [item for item in notes if not _is_mismatched_python_dynamic_guidance(kind, item)]
        notes.insert(0, default_note)
    cleaned_notes: list[str] = []
    seen_notes: set[str] = set()
    for note in notes:
        cleaned = _clean_user_text(note)
        if not cleaned:
            continue
        key = _normalize(cleaned)
        if key in seen_notes:
            continue
        seen_notes.add(key)
        cleaned_notes.append(cleaned)
    if cleaned_notes:
        normalized["notes"] = "\n\n".join(cleaned_notes)
    return normalized if any(key in normalized for key in ("remove", "replace", "add", "notes")) else {}
