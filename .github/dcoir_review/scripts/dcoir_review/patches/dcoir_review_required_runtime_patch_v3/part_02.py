def _fallback_finding(hardened: Any, original_fallback: Any, sentinel: Any, config: Any) -> dict[str, Any]:
    kind = _sentinel_kind(sentinel)
    if kind == PS_PROCESS_KIND:
        path = str(getattr(sentinel, "path", "") or "")
        return {
            "title": HARD_REQUIRED_KIND_TITLES[kind],
            "severity": "high",
            "confidence": 0.99,
            "path": path,
            "line": _sentinel_line(sentinel),
            "body": "This line launches a caller-controlled executable or argument string. Replace it with an allowlisted command table or remove the launch from the collector path.",
            "suggested_replacement": "",
            "validation": _validation_for_path(path, kind),
            "_anchored_line_text": str(getattr(sentinel, "text", "") or ""),
        }
    return original_fallback(sentinel, config) if callable(original_fallback) else {}


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return

    if not hasattr(hardened, "_dcoir_required_v3_original_select_risk_sentinels") and callable(getattr(hardened, "select_risk_sentinels", None)):
        hardened._dcoir_required_v3_original_select_risk_sentinels = hardened.select_risk_sentinels

    original_detect = getattr(module, "_dcoir_required_v3_original_detect_risk_sentinels", None)
    if original_detect is None:
        original_detect = getattr(module, "detect_risk_sentinels", getattr(hardened, "detect_risk_sentinels", None))
        module._dcoir_required_v3_original_detect_risk_sentinels = original_detect
    if callable(original_detect):
        def required_v3_detect_risk_sentinels(diff: str, max_anchors: int | None = None) -> list[Any]:
            existing = original_detect(diff, None)
            return _select_sentinels(hardened, [*existing, *_make_v3_sentinels(hardened, diff)], max_anchors)

        module.detect_risk_sentinels = required_v3_detect_risk_sentinels
        hardened.detect_risk_sentinels = required_v3_detect_risk_sentinels
        hardened.select_risk_sentinels = lambda sentinels, max_anchors=None: _select_sentinels(hardened, sentinels, max_anchors)

    original_required = getattr(hardened, "_dcoir_required_v3_original_required_risk_sentinels", None)
    if original_required is None:
        original_required = getattr(hardened, "required_risk_sentinels", None)
        hardened._dcoir_required_v3_original_required_risk_sentinels = original_required
    hardened.required_risk_sentinels = lambda sentinels: _required_sentinels(original_required, sentinels)

    original_is_required = getattr(hardened, "_dcoir_required_v3_original_is_required_risk_sentinel", None)
    if original_is_required is None:
        original_is_required = getattr(hardened, "is_required_risk_sentinel", None)
        hardened._dcoir_required_v3_original_is_required_risk_sentinel = original_is_required
    hardened.is_required_risk_sentinel = lambda sentinel: _sentinel_kind(sentinel) in HARD_REQUIRED_KIND_TITLES or (bool(original_is_required(sentinel)) if callable(original_is_required) else False)

    original_covers = getattr(hardened, "_dcoir_required_v3_original_finding_covers_risk_sentinel", None)
    if original_covers is None:
        original_covers = getattr(hardened, "finding_covers_risk_sentinel", None)
        hardened._dcoir_required_v3_original_finding_covers_risk_sentinel = original_covers
    hardened.finding_covers_risk_sentinel = lambda finding, sentinel: _finding_covers_sentinel(finding, sentinel) if _sentinel_kind(sentinel) in HARD_REQUIRED_KIND_TITLES else (bool(original_covers(finding, sentinel)) if callable(original_covers) else False)

    original_fallback = getattr(hardened, "_dcoir_required_v3_original_risk_sentinel_fallback_finding", None)
    if original_fallback is None:
        original_fallback = getattr(hardened, "risk_sentinel_fallback_finding", None)
        hardened._dcoir_required_v3_original_risk_sentinel_fallback_finding = original_fallback
    hardened.risk_sentinel_fallback_finding = lambda sentinel, config: _fallback_finding(hardened, original_fallback, sentinel, config)

    def required_v3_add_risk_sentinel_fallback_findings(findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        coverage_pool = [*findings, *(unanchored_findings or [])]
        uncovered = [sentinel for sentinel in hardened.required_risk_sentinels(risk_sentinels) if not any(hardened.finding_covers_risk_sentinel(finding, sentinel) for finding in coverage_pool)]
        inline_limit = max(0, int(getattr(config, "max_inline_comments", 12)))
        fallbacks = [hardened.risk_sentinel_fallback_finding(sentinel, config) for sentinel in uncovered[:inline_limit]]
        fallbacks = [finding for finding in fallbacks if finding]
        existing_budget = max(0, inline_limit - len(fallbacks))
        existing = _rank_findings(module, hardened, getattr(module, "_dcoir_required_v3_original_rank_findings_for_required_budget", None), findings, config)[:existing_budget]
        return _rank_findings(module, hardened, None, [*existing, *fallbacks], config)

    hardened.add_risk_sentinel_fallback_findings = required_v3_add_risk_sentinel_fallback_findings

    review_quality_error = getattr(hardened, "ReviewQualityError", RuntimeError)
    def required_v3_enforce_risk_sentinel_findings(findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> None:
        findings[:] = required_v3_add_risk_sentinel_fallback_findings(findings, risk_sentinels, config, unanchored_findings)
        uncovered = [sentinel for sentinel in hardened.required_risk_sentinels(risk_sentinels) if not any(hardened.finding_covers_risk_sentinel(finding, sentinel) for finding in findings)]
        if uncovered:
            digest = getattr(hardened, "risk_sentinel_coverage_digest", lambda items: "; ".join(str(item) for item in items))(uncovered)
            raise review_quality_error(f"DCOIR Review quality failure: required changed-line signals remain uncovered: {digest}.")

    hardened.enforce_risk_sentinel_findings = required_v3_enforce_risk_sentinel_findings
    hardened.finding_merge_key = lambda finding: (str(finding.get("path", "") or ""), 0 if _semantic_kind(finding) in {"python_ssrf", v2.PS_ACL_KIND} else _finding_line(finding), _semantic_kind(finding) or "unknown")
    module.finding_dedupe_key = _dedupe_key
    module.dedupe_findings_for_ranking = lambda findings: _dedupe_findings(hardened, findings)

    original_rank = getattr(module, "_dcoir_required_v3_original_rank_findings_for_required_budget", None)
    if original_rank is None:
        original_rank = getattr(module, "rank_findings_for_required_budget", None)
        module._dcoir_required_v3_original_rank_findings_for_required_budget = original_rank
    module.rank_findings_for_required_budget = lambda findings, config: _rank_findings(module, hardened, original_rank, findings, config)

    original_score = getattr(module, "_dcoir_required_v3_original_anchor_candidate_score", None)
    if original_score is None:
        original_score = getattr(module, "anchor_candidate_score", None)
        module._dcoir_required_v3_original_anchor_candidate_score = original_score
    if callable(original_score):
        def required_v3_anchor_candidate_score(finding: dict[str, Any], candidate: Any, original_line: int, terms: list[str], risk_sentinels: list[Any]) -> int:
            score = int(original_score(finding, candidate, original_line, terms, risk_sentinels))
            finding_kind = _semantic_kind(finding)
            candidate_kind = _line_kind(str(getattr(candidate, "path", "") or ""), str(getattr(candidate, "text", "") or ""))
            if finding_kind and candidate_kind:
                if finding_kind == candidate_kind:
                    score += 360
                elif finding_kind.startswith("yaml_") and candidate_kind.startswith("yaml_"):
                    score -= 220
                elif finding_kind.startswith("ps_") and candidate_kind.startswith("ps_"):
                    score -= 160
            return score

        module.anchor_candidate_score = required_v3_anchor_candidate_score

    original_synthesize = getattr(module, "_dcoir_required_v3_original_synthesize_fix_for_finding", None)
    if original_synthesize is None:
        original_synthesize = getattr(module, "synthesize_fix_for_finding", None)
        module._dcoir_required_v3_original_synthesize_fix_for_finding = original_synthesize
    if callable(original_synthesize):
        def required_v3_synthesize_fix_for_finding(index: int, finding: dict[str, Any], file_text: str, schema: dict[str, Any], config: Any) -> dict[str, Any]:
            return _normalize_comment_finding(original_synthesize(index, finding, file_text, schema, config))

        module.synthesize_fix_for_finding = required_v3_synthesize_fix_for_finding

    if base is not None and callable(getattr(base, "build_inline_comment", None)):
        original_build = getattr(base, "_dcoir_required_v3_original_build_inline_comment", None)
        if original_build is None:
            original_build = getattr(base, "_dcoir_required_v2_original_build_inline_comment", None) or getattr(base, "_dcoir_strict_original_build_inline_comment", None) or getattr(base, "_dcoir_original_build_inline_comment", None) or base.build_inline_comment
            base._dcoir_required_v3_original_build_inline_comment = original_build

        def required_v3_build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
            normalized = _normalize_comment_finding(finding)
            return _rendered_comment_scrub(original_build(normalized, model_used, config), normalized)

        base.build_inline_comment = required_v3_build_inline_comment
