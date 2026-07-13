

def _validation_needs_replacement(validation: str, path: str, kind: str) -> bool:
    if not str(validation or "").strip():
        return True
    if path.lower().endswith((".yml", ".yaml")) and ("<<'PY'" in validation or "\n" in validation):
        return True
    return required._validation_needs_replacement(validation, path)


def _token_forwarding_context(finding: dict[str, Any]) -> bool:
    haystack = "\n".join(
        str(value or "")
        for value in (
            finding.get("title"),
            finding.get("body"),
            finding.get("validation"),
            finding.get("_anchored_line_text"),
        )
    )
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    haystack += "\n" + "\n".join(str(guidance.get(key, "") or "") for key in ("remove", "replace", "add", "notes"))
    kind = _semantic_kind(finding)
    return (kind in {"python_ssrf", "ps_outbound_token"} and TOKEN_FORWARDING_RE.search(haystack) is not None) or (
        ENV_TOKEN_RE.search(haystack) is not None and TOKEN_FORWARDING_RE.search(haystack) is not None
    )


def _normalize_token_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("shorn", "should")
    text = BRACKETED_REDACTION_RE.sub("environment token value", text)
    text = HARDCODED_BEARER_RE.sub("environment token", text)
    text = LITERAL_BEARER_VALUE_RE.sub("environment Bearer token value", text)
    text = HARDCODED_TOKEN_RE.sub("environment token value", text)
    text = re.sub(r"\bliteral\s+Bearer\s+token\b", "environment Bearer token", text, flags=re.IGNORECASE)
    lines = [line for line in text.splitlines() if "syntax error" not in line.lower()]
    return "\n".join(lines).strip()


def _language_hint(path: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    return {
        ".cjs": "javascript",
        ".js": "javascript",
        ".mjs": "javascript",
        ".ps1": "powershell",
        ".psd1": "powershell",
        ".psm1": "powershell",
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix, "text")


def _strip_fences(value: Any) -> str:
    lines = []
    for line in str(value or "").splitlines():
        if line.strip().startswith(("```", "~~~")):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


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
        ast.parse(value.strip() + "\n")
        return True
    except SyntaxError:
        return False


def _looks_like_code(value: str, language: str) -> bool:
    text = _strip_fences(value)
    if not text or _is_natural_language(text):
        return False
    language = str(language or "").lower()
    if language == "python":
        return _python_is_code(text)
    if language == "powershell":
        lines = [line for line in text.splitlines() if line.strip()]
        return bool(lines) and all(POWERSHELL_CODE_RE.match(line) or line.strip() in {"}", "};"} for line in lines)
    if language in {"yaml", "json"}:
        return bool(YAML_CODE_RE.search(text))
    if language in {"typescript", "javascript"}:
        lines = [line for line in text.splitlines() if line.strip()]
        return bool(lines) and any(JS_TS_CODE_RE.match(line) for line in lines)
    return any(signal in text for signal in ("=", "$", ":", "(", "{", "|", ";"))


def _sanitize_fix_guidance(finding: dict[str, Any]) -> dict[str, Any]:
    raw = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    if not raw:
        return {}
    path = str(finding.get("path", "") or "")
    language = str(raw.get("language") or _language_hint(path)).lower()
    cleaned: dict[str, Any] = {"language": language}
    notes: list[str] = []
    for key in ("remove", "replace", "add"):
        value = _strip_fences(raw.get(key, ""))
        if not value:
            continue
        value = _normalize_token_text(value) if _token_forwarding_context(finding) else value.replace("shorn", "should")
        if _looks_like_code(value, language):
            cleaned[key] = value
        else:
            notes.append(value)
    raw_notes = str(raw.get("notes", "") or "").strip()
    if raw_notes:
        notes.append(raw_notes)
    if notes:
        normalized_notes: list[str] = []
        seen: set[str] = set()
        for note in notes:
            note = _normalize_token_text(note) if _token_forwarding_context(finding) else note.replace("shorn", "should")
            note = required._clean_public_text(note)
            key = _normalize(note)
            if note and key not in seen:
                seen.add(key)
                normalized_notes.append(note)
        if normalized_notes:
            cleaned["notes"] = "\n\n".join(normalized_notes)
    return cleaned if any(key in cleaned for key in ("remove", "replace", "add", "notes")) else {}


def _normalize_comment_finding(finding: dict[str, Any]) -> dict[str, Any]:
    item = required._normalize_comment_finding(finding)
    kind = _semantic_kind(item)
    if kind in HARD_REQUIRED_KIND_TITLES:
        item["title"] = HARD_REQUIRED_KIND_TITLES[kind]
    token_context = _token_forwarding_context(item)
    if token_context:
        if kind in {"python_ssrf", "ps_outbound_token"}:
            item["title"] = "Environment token forwarded to request-controlled callback"
        else:
            item["title"] = _normalize_token_text(item.get("title", ""))
        item["body"] = _normalize_token_text(item.get("body", ""))
    else:
        item["title"] = str(item.get("title", "") or "Finding").replace("shorn", "should")
        item["body"] = str(item.get("body", "") or "").replace("shorn", "should")
    path = str(item.get("path", "") or "")
    validation = str(item.get("validation", "") or "")
    if _validation_needs_replacement(validation, path, kind):
        validation = _validation_for_path(path, kind)
    item["validation"] = validation.replace("shorn", "should")
    guidance = _sanitize_fix_guidance(item)
    if guidance:
        item["fix_guidance"] = guidance
    else:
        item.pop("fix_guidance", None)
    return item


def _dedupe_line_key(kind: str, finding: dict[str, Any]) -> str:
    if kind in {"python_ssrf", PS_ACL_KIND}:
        return ""
    return str(finding.get("line", "") or "").strip()


def _dedupe_key(finding: dict[str, Any]) -> tuple[str, str, str, str]:
    kind = _semantic_kind(finding)
    path = str(finding.get("path", "") or "").strip()
    if kind:
        return path, _dedupe_line_key(kind, finding), kind, ""
    return required._dedupe_key(finding)


def _dedupe_findings(hardened: Any, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str, str]] = []
    for finding in findings:
        key = _dedupe_key(finding)
        if key not in by_key:
            by_key[key] = finding
            order.append(key)
            continue
        if required._finding_quality_score(hardened, finding) >= required._finding_quality_score(hardened, by_key[key]):
            by_key[key] = finding
    return [by_key[key] for key in order]
