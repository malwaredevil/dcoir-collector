def _normalize_comment_finding(finding: dict[str, Any]) -> dict[str, Any]:
    item = v4._normalize_comment_finding(finding)
    if finding.get("_anchored_line_text") and not item.get("_anchored_line_text"):
        item["_anchored_line_text"] = finding.get("_anchored_line_text")
    kind = _semantic_kind(item)
    path = str(item.get("path", "") or "")
    line_text = str(item.get("_anchored_line_text", "") or "")
    if kind in REQUIRED_KIND_TITLES:
        item.update(_template_fields(kind, path, line_text))
    if _is_env_kind(kind):
        item["title"] = "Environment token forwarded to request-controlled callback"
        item["body"] = "Environment token read from env and forwarded to request-controlled callback. Keep collector tokens server-side and allowlist outbound destinations before sending authorization headers."
        item["suggested_replacement"] = ""
        item["fix_guidance"] = {
            "language": v4._language_hint(path),
            "notes": "Keep the token on the trusted side of the boundary and validate the callback destination against an allowlist before any request is made.",
        }
    return item


def _coverage_line(kind: str, finding_line: int, sentinel_line: int) -> bool:
    if finding_line <= 0 or sentinel_line <= 0:
        return False
    if kind == v4.PS_ACL:
        return abs(finding_line - sentinel_line) <= 4
    return finding_line == sentinel_line


def finding_covers_sentinel(finding: dict[str, Any], sentinel: Any, original_covers: Any | None = None) -> bool:
    kind = _sentinel_kind(sentinel)
    normalized = _normalize_comment_finding(finding)
    if kind in REQUIRED_KIND_TITLES:
        return (
            str(normalized.get("path", "") or "") == str(getattr(sentinel, "path", "") or "")
            and _semantic_kind(normalized) == kind
            and _coverage_line(kind, _finding_line(normalized), _sentinel_line(sentinel))
        )
    if callable(original_covers):
        return bool(original_covers(finding, sentinel))
    return False


def _dedupe_key(finding: dict[str, Any]) -> tuple[str, int, str, str]:
    normalized = _normalize_comment_finding(finding)
    kind = _semantic_kind(normalized)
    return (
        str(normalized.get("path", "") or ""),
        _finding_line(normalized),
        kind or str(normalized.get("title", "") or ""),
        _normalize(normalized.get("_anchored_line_text", "")),
    )


def _dedupe_findings(hardened: Any, findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str, int, str, str], dict[str, Any]] = {}
    order: list[tuple[str, int, str, str]] = []
    for finding in findings:
        normalized = _normalize_comment_finding(finding)
        key = _dedupe_key(normalized)
        if key not in by_key:
            by_key[key] = normalized
            order.append(key)
            continue
        if hasattr(hardened, "severity_sort_key"):
            by_key[key] = normalized
    return [by_key[key] for key in order]


def _rank_findings(module: Any, hardened: Any, original_rank: Any, findings: list[dict[str, Any]], config: Any) -> list[dict[str, Any]]:
    max_inline = max(0, int(getattr(config, "max_inline_comments", 12)))
    ranked_source = _dedupe_findings(hardened, findings)
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str, str]] = set()

    def add(finding: dict[str, Any]) -> None:
        key = _dedupe_key(finding)
        if key not in seen and len(selected) < max_inline:
            seen.add(key)
            selected.append(finding)

    for kind in RANK_KIND_ORDER:
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
        add(_normalize_comment_finding(finding))
    return selected[:max_inline]


def _required_sentinels(original_required: Any, sentinels: list[Any]) -> list[Any]:
    combined = list(original_required(sentinels)) if callable(original_required) else []
    combined.extend(sentinel for sentinel in sentinels if _sentinel_kind(sentinel) in REQUIRED_KIND_TITLES)
    seen: set[tuple[str, int, str]] = set()
    result: list[Any] = []
    for sentinel in combined:
        key = (str(getattr(sentinel, "path", "") or ""), _sentinel_line(sentinel), _sentinel_kind(sentinel))
        if key in seen:
            continue
        seen.add(key)
        result.append(sentinel)
    return result


def _fallback_finding(sentinel: Any, config: Any, original_fallback: Any | None = None) -> dict[str, Any]:
    kind = _sentinel_kind(sentinel)
    if kind in REQUIRED_KIND_TITLES:
        path = str(getattr(sentinel, "path", "") or "")
        line_text = str(getattr(sentinel, "text", "") or "")
        finding = {
            "severity": "critical" if kind in {v4.YAML_PULL_REQUEST_TARGET, v4.YAML_SHELL_PIPE, v4.PS_PROCESS_LAUNCH, PYTHON_YAML_LOAD, PYTHON_SHELL_EXEC} else "high",
            "confidence": 0.99,
            "path": path,
            "line": _sentinel_line(sentinel),
            "_anchored_line_text": line_text,
        }
        finding.update(_template_fields(kind, path, line_text))
        return finding
    if callable(original_fallback):
        result = original_fallback(sentinel, config)
        return result if isinstance(result, dict) else {}
    return {}


def add_risk_sentinel_fallback_findings(hardened: Any, original_rank: Any, original_covers: Any, original_fallback: Any, findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    required_sentinels = hardened.required_risk_sentinels(risk_sentinels)
    normalized_findings = _dedupe_findings(hardened, findings)
    coverage_pool = [*normalized_findings, *(_dedupe_findings(hardened, unanchored_findings or []) if unanchored_findings else [])]
    uncovered = [
        sentinel
        for sentinel in required_sentinels
        if not any(finding_covers_sentinel(finding, sentinel, original_covers) for finding in coverage_pool)
    ]
    fallbacks = [_fallback_finding(sentinel, config, original_fallback) for sentinel in uncovered]
    fallbacks = [finding for finding in fallbacks if finding]
    inline_limit = max(0, int(getattr(config, "max_inline_comments", 12)))
    existing_budget = max(0, inline_limit - len(fallbacks))
    existing = _rank_findings(None, hardened, original_rank, normalized_findings, config)[:existing_budget]
    return _rank_findings(None, hardened, None, [*existing, *fallbacks], config)[:inline_limit]


def final_rendered_scrub(comment: str, finding: dict[str, Any]) -> str:
    text = v4._final_rendered_scrub(comment, finding)
    if _is_env_kind(_semantic_kind(finding)):
        text = TOKEN_BAD_RE.sub("environment token", text)
        text = text.replace("environment token value", "environment token")
    return text
