def _strict_rank_findings(module: Any, hardened: Any, original_rank: Any, findings: list[dict[str, Any]], config: Any) -> list[dict[str, Any]]:
    max_inline = max(0, int(getattr(config, "max_inline_comments", 12)))
    ranked_source = _dedupe_findings(hardened, findings)
    severity_sort = getattr(hardened, "severity_sort_key", None)
    if callable(severity_sort):
        ranked_source = sorted(ranked_source, key=severity_sort)
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add(finding: dict[str, Any]) -> None:
        key = _dedupe_key(finding)
        if key not in seen and len(selected) < max_inline:
            seen.add(key)
            selected.append(finding)

    for kind in YAML_REQUIRED_KIND_TITLES:
        for finding in ranked_source:
            if _semantic_kind(finding) == kind:
                add(finding)
                break
    remainder = [finding for finding in ranked_source if _dedupe_key(finding) not in seen]
    if callable(original_rank):
        try:
            remainder = original_rank(remainder, config)
        except TypeError:
            remainder = original_rank(remainder)
    for finding in remainder:
        add(finding)
    return selected[:max_inline]


def _finding_covers_sentinel(finding: dict[str, Any], sentinel: Any) -> bool:
    sentinel_kind = _sentinel_kind(sentinel)
    if sentinel_kind in YAML_REQUIRED_KIND_TITLES:
        try:
            return (
                str(finding.get("path", "") or "") == str(getattr(sentinel, "path", "") or "")
                and int(finding.get("line", 0) or 0) == int(getattr(sentinel, "line", 0) or 0)
                and _semantic_kind({**finding, "_anchored_line_text": str(getattr(sentinel, "text", "") or "")}) == sentinel_kind
            )
        except (TypeError, ValueError):
            return False
    return False


def _required_sentinels(original_required: Any, sentinels: list[Any]) -> list[Any]:
    required: list[Any] = []
    for sentinel in sentinels:
        if _sentinel_kind(sentinel) in YAML_REQUIRED_KIND_TITLES:
            required.append(sentinel)
        elif callable(original_required) and sentinel in original_required([sentinel]):
            required.append(sentinel)
    return _dedupe_sentinels(required)


def _risk_sentinel_fallback_finding(hardened: Any, original_fallback: Any, sentinel: Any, config: Any) -> dict[str, Any]:
    kind = _sentinel_kind(sentinel)
    if kind in YAML_REQUIRED_KIND_TITLES:
        return {
            "title": YAML_REQUIRED_KIND_TITLES[kind],
            "severity": "high",
            "confidence": 0.99,
            "path": str(getattr(sentinel, "path", "") or ""),
            "line": int(getattr(sentinel, "line", 0) or 0),
            "body": _yaml_fallback_body(kind, sentinel),
            "suggested_replacement": "",
            "validation": _validation_for_path(str(getattr(sentinel, "path", "") or ""), kind),
            "_anchored_line_text": str(getattr(sentinel, "text", "") or ""),
        }
    if callable(original_fallback):
        return original_fallback(sentinel, config)
    return {}


def _strict_suggestion_is_safe(suggestion: str, file_text: str, line: int, path: str, finding: dict[str, Any]) -> bool:
    suggestion = str(suggestion or "").rstrip()
    if not suggestion or "\n" in suggestion or "```" in suggestion or "~~~" in suggestion:
        return False
    original_lines = file_text.splitlines()
    if line <= 0 or line > len(original_lines):
        return False
    kind = _semantic_kind({**finding, "path": path, "_anchored_line_text": original_lines[line - 1]})
    lowered = suggestion.lower()
    if kind in {"python_shell_exec", "python_dynamic_exec"}:
        if "shell=true" in lowered or "eval(" in lowered or "exec(" in lowered or "shlex.split" in lowered:
            return False
        if re.search(r"\bsubprocess\.\w+\s*\(", suggestion) and re.search(r"\b(command|cmd)\b", suggestion) and "allow" not in lowered:
            return False
    if path.lower().endswith(".py"):
        if "shlex." in suggestion and not re.search(r"(?m)^\s*(?:import\s+shlex|from\s+shlex\s+import\b)", file_text):
            return False
        updated = list(original_lines)
        updated[line - 1] = suggestion
        try:
            ast.parse("\n".join(updated) + "\n")
        except SyntaxError:
            return False
    if path.lower().endswith((".yml", ".yaml")):
        if _line_semantic_kind(path, suggestion) in YAML_REQUIRED_KIND_TITLES:
            return False
    if path.lower().endswith((".ps1", ".psm1", ".psd1")):
        if "invoke-expression" in lowered:
            return False
    return True
