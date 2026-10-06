def _normalize_comment_finding(finding: dict[str, Any]) -> dict[str, Any]:
    raw_kind = _semantic_kind(finding)
    item = v3._normalize_comment_finding(finding)
    if finding.get("_anchored_line_text") and not item.get("_anchored_line_text"):
        item["_anchored_line_text"] = finding.get("_anchored_line_text")
    # Preserve the semantic classification from the anchored source finding.
    # Earlier normalization can rewrite the title/body, which must not change
    # a process-launch finding into a different required-risk family.
    kind = raw_kind or _semantic_kind(item)
    path = str(item.get("path", "") or "")
    line_text = str(item.get("_anchored_line_text", "") or "")
    if _is_env_token_callback({**item, "_anchored_line_text": line_text}):
        item.update(_env_token_fields(path))
        return item
    if kind in HARD_REQUIRED_KIND_TITLES or kind == YAML_METADATA_SHELL:
        item.update(_template_fields(kind, path, line_text))
        return item
    item["title"] = required._clean_public_text(str(item.get("title", "") or "Finding").replace("validatation", "validation"))
    item["body"] = required._clean_public_text(str(item.get("body", "") or "").replace("validatation", "validation"))
    item["validation"] = _clean_validation(item.get("validation", ""), path, kind)
    guidance = _sanitize_fix_guidance(item)
    if guidance:
        item["fix_guidance"] = guidance
    else:
        item.pop("fix_guidance", None)
    return item


def _render_deterministic_comment(finding: dict[str, Any], model_used: str) -> str:
    title = str(finding.get("title", "") or "Finding")
    body = str(finding.get("body", "") or "").strip()
    validation = str(finding.get("validation", "") or "").strip()
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    notes = _format_notes(guidance.get("notes", ""), str(finding.get("path", "") or "")) if guidance else ""
    parts = [f"**{title}**"]
    if body:
        parts.extend(["", body])
    if notes:
        parts.extend(["", "**Suggested fix:**", "", notes])
    if validation:
        parts.extend(["", "**Validation:**", "", "```bash", validation, "```"])
    if model_used:
        parts.extend(["", f"_Reviewed with {model_used}._"])
    return _final_rendered_scrub("\n".join(parts), finding)


def _final_rendered_scrub(comment: str, finding: dict[str, Any]) -> str:
    text = str(comment or "").replace("validatation", "validation")
    text = text.replace("environment token value value", "environment token")
    if _is_env_token_callback(finding):
        text = BANNED_ENV_PROSE_RE.sub("environment token", text)
        text = text.replace("environment token value", "environment token")
    if _semantic_kind(finding) == YAML_SHELL_PIPE and "https://" in str(finding.get("_anchored_line_text", "") or "").lower():
        text = re.sub(r"\bplain HTTP\b", "network-fetched content", text, flags=re.IGNORECASE)
    return DUPLICATE_WHITESPACE_RE.sub("\n\n", text).strip()


def _dedupe_key(finding: dict[str, Any]) -> tuple[str, int, str, str]:
    kind = _semantic_kind(finding)
    path = str(finding.get("path", "") or "")
    line = _finding_line(finding)
    sink = _normalize(finding.get("_anchored_line_text", ""))
    if kind:
        return path, line, kind, sink
    return path, line, str(finding.get("title", "") or ""), sink


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
        if required._finding_quality_score(hardened, normalized) >= required._finding_quality_score(hardened, by_key[key]):
            by_key[key] = normalized
    return [by_key[key] for key in order]


def _rank_findings(module: Any, hardened: Any, original_rank: Any, findings: list[dict[str, Any]], config: Any) -> list[dict[str, Any]]:
    max_inline = max(0, int(getattr(config, "max_inline_comments", 12)))
    ranked_source = _dedupe_findings(hardened, findings)
    severity_sort = getattr(hardened, "severity_sort_key", None)
    if callable(severity_sort):
        ranked_source = sorted(ranked_source, key=severity_sort)
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


def _sentinel_key(sentinel: Any) -> tuple[str, int, str]:
    return str(getattr(sentinel, "path", "") or ""), _sentinel_line(sentinel), _sentinel_kind(sentinel)


def _dedupe_sentinels(sentinels: list[Any]) -> list[Any]:
    seen: set[tuple[str, int, str]] = set()
    result: list[Any] = []
    for sentinel in sentinels:
        key = _sentinel_key(sentinel)
        if key in seen:
            continue
        seen.add(key)
        result.append(sentinel)
    return result


def _required_sentinels(original_required: Any, sentinels: list[Any]) -> list[Any]:
    existing = original_required(sentinels) if callable(original_required) else []
    required_items = [sentinel for sentinel in sentinels if _sentinel_kind(sentinel) in HARD_REQUIRED_KIND_TITLES]
    return _dedupe_sentinels([*existing, *required_items])


def _finding_covers_sentinel(finding: dict[str, Any], sentinel: Any) -> bool:
    kind = _sentinel_kind(sentinel)
    if kind not in HARD_REQUIRED_KIND_TITLES:
        return False
    if str(finding.get("path", "") or "") != str(getattr(sentinel, "path", "") or ""):
        return False
    if _semantic_kind(finding) != kind:
        return False
    finding_line = _finding_line(finding)
    sentinel_line = _sentinel_line(sentinel)
    if kind == PS_ACL:
        return finding_line > 0 and sentinel_line > 0 and abs(finding_line - sentinel_line) <= 4
    return finding_line == sentinel_line


def _fallback_finding(sentinel: Any, config: Any) -> dict[str, Any]:
    kind = _sentinel_kind(sentinel)
    path = str(getattr(sentinel, "path", "") or "")
    line_text = str(getattr(sentinel, "text", "") or "")
    if kind in HARD_REQUIRED_KIND_TITLES:
        finding = {
            "severity": "critical" if kind in {YAML_PULL_REQUEST_TARGET, YAML_SHELL_PIPE, PS_PROCESS_LAUNCH} else "high",
            "confidence": 0.99,
            "path": path,
            "line": _sentinel_line(sentinel),
            "_anchored_line_text": line_text,
        }
        finding.update(_template_fields(kind, path, line_text))
        return finding
    return {}


def _add_risk_sentinel_fallback_findings(hardened: Any, original_rank: Any, findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    required_sentinels = hardened.required_risk_sentinels(risk_sentinels)
    normalized_findings = _dedupe_findings(hardened, findings)
    uncovered = [
        sentinel
        for sentinel in required_sentinels
        if not any(_finding_covers_sentinel(finding, sentinel) for finding in normalized_findings)
    ]
    fallback_findings = [_fallback_finding(sentinel, config) for sentinel in uncovered]
    fallback_findings = [finding for finding in fallback_findings if finding]
    inline_limit = max(0, int(getattr(config, "max_inline_comments", 12)))
    if fallback_findings:
        try:
            message = "; ".join(f"{finding.get('path')}:{finding.get('line')} {_semantic_kind(finding)}" for finding in fallback_findings)
            base = getattr(hardened, "base", None)
            if base is not None and callable(getattr(base, "emit_status", None)):
                base.emit_status("required-v4-fallback-inserted", message)
        except Exception:
            pass
    existing_budget = max(0, inline_limit - len(fallback_findings))
    existing = _rank_findings(None, hardened, original_rank, normalized_findings, config)[:existing_budget]
    return _rank_findings(None, hardened, None, [*existing, *fallback_findings], config)[:inline_limit]


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return

    original_required = getattr(hardened, "_dcoir_required_v4_original_required_risk_sentinels", None)
    if original_required is None:
        original_required = getattr(hardened, "required_risk_sentinels", None)
        hardened._dcoir_required_v4_original_required_risk_sentinels = original_required
    hardened.required_risk_sentinels = lambda sentinels: _required_sentinels(original_required, sentinels)
    hardened.is_required_risk_sentinel = lambda sentinel: _sentinel_kind(sentinel) in HARD_REQUIRED_KIND_TITLES or (bool(getattr(hardened, "_dcoir_required_v4_original_is_required_risk_sentinel", lambda _s: False)(sentinel)))
    if not hasattr(hardened, "_dcoir_required_v4_original_is_required_risk_sentinel"):
        hardened._dcoir_required_v4_original_is_required_risk_sentinel = getattr(hardened, "is_required_risk_sentinel", None)

    hardened.finding_covers_risk_sentinel = lambda finding, sentinel: _finding_covers_sentinel(finding, sentinel) if _sentinel_kind(sentinel) in HARD_REQUIRED_KIND_TITLES else bool(getattr(hardened, "_dcoir_required_v4_original_finding_covers_risk_sentinel", lambda _f, _s: False)(finding, sentinel))
    if not hasattr(hardened, "_dcoir_required_v4_original_finding_covers_risk_sentinel"):
        hardened._dcoir_required_v4_original_finding_covers_risk_sentinel = getattr(hardened, "finding_covers_risk_sentinel", None)

    hardened.risk_sentinel_fallback_finding = lambda sentinel, config: _fallback_finding(sentinel, config) or getattr(hardened, "_dcoir_required_v4_original_risk_sentinel_fallback_finding", lambda _s, _c: {})(sentinel, config)
    if not hasattr(hardened, "_dcoir_required_v4_original_risk_sentinel_fallback_finding"):
        hardened._dcoir_required_v4_original_risk_sentinel_fallback_finding = getattr(hardened, "risk_sentinel_fallback_finding", None)

    original_rank = getattr(module, "_dcoir_required_v4_original_rank_findings_for_required_budget", None)
    if original_rank is None:
        original_rank = getattr(module, "rank_findings_for_required_budget", None)
        module._dcoir_required_v4_original_rank_findings_for_required_budget = original_rank
    module.finding_dedupe_key = _dedupe_key
    module.dedupe_findings_for_ranking = lambda findings: _dedupe_findings(hardened, findings)
    module.rank_findings_for_required_budget = lambda findings, config: _rank_findings(module, hardened, original_rank, findings, config)
    hardened.finding_merge_key = lambda finding: (str(finding.get("path", "") or ""), _finding_line(finding), _semantic_kind(finding) or "unknown")

    hardened.add_risk_sentinel_fallback_findings = lambda findings, risk_sentinels, config, unanchored_findings=None: _add_risk_sentinel_fallback_findings(hardened, original_rank, findings, risk_sentinels, config, unanchored_findings)

    review_quality_error = getattr(hardened, "ReviewQualityError", RuntimeError)

    def required_v4_enforce_risk_sentinel_findings(findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> None:
        findings[:] = hardened.add_risk_sentinel_fallback_findings(findings, risk_sentinels, config, unanchored_findings)
        uncovered = [sentinel for sentinel in hardened.required_risk_sentinels(risk_sentinels) if not any(_finding_covers_sentinel(finding, sentinel) for finding in findings)]
        if uncovered:
            digest = "; ".join(f"{getattr(s, 'path', '')}:{getattr(s, 'line', '')} {_sentinel_kind(s)}" for s in uncovered)
            raise review_quality_error(f"DCOIR Review quality failure: required changed-line signals remain uncovered after v4 refill: {digest}.")

    hardened.enforce_risk_sentinel_findings = required_v4_enforce_risk_sentinel_findings

    original_synthesize = getattr(module, "_dcoir_required_v4_original_synthesize_fix_for_finding", None)
    if original_synthesize is None:
        original_synthesize = getattr(module, "synthesize_fix_for_finding", None)
        module._dcoir_required_v4_original_synthesize_fix_for_finding = original_synthesize
    if callable(original_synthesize):
        module.synthesize_fix_for_finding = lambda index, finding, file_text, schema, config: _normalize_comment_finding(original_synthesize(index, finding, file_text, schema, config))

    if base is not None and callable(getattr(base, "build_inline_comment", None)):
        original_build = getattr(base, "_dcoir_required_v4_original_build_inline_comment", None)
        if original_build is None:
            original_build = base.build_inline_comment
            base._dcoir_required_v4_original_build_inline_comment = original_build

        def required_v4_build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
            normalized = _normalize_comment_finding(finding)
            kind = _semantic_kind(normalized)
            if kind in HARD_REQUIRED_KIND_TITLES or kind == YAML_METADATA_SHELL or _is_env_token_callback(normalized):
                try:
                    if callable(getattr(base, "emit_status", None)):
                        base.emit_status("required-v4-deterministic-comment", f"{normalized.get('path')}:{normalized.get('line')} {kind}")
                except Exception:
                    pass
                return _render_deterministic_comment(normalized, model_used)
            return _final_rendered_scrub(original_build(normalized, model_used, config), normalized)

        base.build_inline_comment = required_v4_build_inline_comment
