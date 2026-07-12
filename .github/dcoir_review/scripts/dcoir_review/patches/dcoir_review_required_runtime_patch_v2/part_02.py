def _rank_findings(module: Any, hardened: Any, original_rank: Any, findings: list[dict[str, Any]], config: Any) -> list[dict[str, Any]]:
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

    for kind in REQUIRED_KIND_ORDER:
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
    kind = _sentinel_kind(sentinel)
    if kind in required.YAML_REQUIRED_KIND_TITLES:
        return required._finding_covers_sentinel(finding, sentinel)
    if kind == PS_ACL_KIND:
        if str(finding.get("path", "") or "") != str(getattr(sentinel, "path", "") or ""):
            return False
        if _semantic_kind(finding) != PS_ACL_KIND:
            return False
        finding_line = _finding_line(finding)
        sentinel_line = _sentinel_line(sentinel)
        if finding_line <= 0 or sentinel_line <= 0:
            return False
        return abs(finding_line - sentinel_line) <= 4
    return False


def _required_sentinels(original_required: Any, sentinels: list[Any]) -> list[Any]:
    original_items = original_required(sentinels) if callable(original_required) else []
    combined = [*original_items, *(sentinel for sentinel in sentinels if _sentinel_kind(sentinel) in HARD_REQUIRED_KIND_TITLES)]
    return _dedupe_sentinels(combined)


def _ps_acl_fallback_body(sentinel: Any) -> str:
    changed = str(getattr(sentinel, "text", "") or "").strip()
    detail = f" The changed line is `{changed}`." if changed else ""
    return "This PowerShell change grants broad filesystem ACL rights. Narrow the identity and rights to the minimum collector path access required, and avoid Everyone or FullControl grants." + detail


def _risk_sentinel_fallback_finding(hardened: Any, original_fallback: Any, sentinel: Any, config: Any) -> dict[str, Any]:
    kind = _sentinel_kind(sentinel)
    if kind == PS_ACL_KIND:
        path = str(getattr(sentinel, "path", "") or "")
        return {
            "title": HARD_REQUIRED_KIND_TITLES[kind],
            "severity": "high",
            "confidence": 0.99,
            "path": path,
            "line": _sentinel_line(sentinel),
            "body": _ps_acl_fallback_body(sentinel),
            "suggested_replacement": "",
            "validation": _validation_for_path(path, kind),
            "_anchored_line_text": str(getattr(sentinel, "text", "") or ""),
        }
    if kind in required.YAML_REQUIRED_KIND_TITLES:
        return required._risk_sentinel_fallback_finding(hardened, original_fallback, sentinel, config)
    return original_fallback(sentinel, config) if callable(original_fallback) else {}


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return

    if not hasattr(hardened, "_dcoir_required_v2_original_select_risk_sentinels") and callable(getattr(hardened, "select_risk_sentinels", None)):
        hardened._dcoir_required_v2_original_select_risk_sentinels = hardened.select_risk_sentinels

    original_detect = getattr(module, "_dcoir_required_v2_original_detect_risk_sentinels", None)
    if original_detect is None:
        original_detect = getattr(module, "detect_risk_sentinels", getattr(hardened, "detect_risk_sentinels", None))
        module._dcoir_required_v2_original_detect_risk_sentinels = original_detect
    if callable(original_detect):
        def required_v2_detect_risk_sentinels(diff: str, max_anchors: int | None = None) -> list[Any]:
            existing = original_detect(diff, None)
            ps_acl = _make_ps_acl_sentinels(hardened, diff)
            return _select_sentinels(hardened, [*existing, *ps_acl], max_anchors)

        module.detect_risk_sentinels = required_v2_detect_risk_sentinels
        hardened.detect_risk_sentinels = required_v2_detect_risk_sentinels
        hardened.select_risk_sentinels = lambda sentinels, max_anchors=None: _select_sentinels(hardened, sentinels, max_anchors)

    original_required = getattr(hardened, "_dcoir_required_v2_original_required_risk_sentinels", None)
    if original_required is None:
        original_required = getattr(hardened, "required_risk_sentinels", None)
        hardened._dcoir_required_v2_original_required_risk_sentinels = original_required
    hardened.required_risk_sentinels = lambda sentinels: _required_sentinels(original_required, sentinels)

    original_is_required = getattr(hardened, "_dcoir_required_v2_original_is_required_risk_sentinel", None)
    if original_is_required is None:
        original_is_required = getattr(hardened, "is_required_risk_sentinel", None)
        hardened._dcoir_required_v2_original_is_required_risk_sentinel = original_is_required

    def required_v2_is_required_risk_sentinel(sentinel: Any) -> bool:
        if _sentinel_kind(sentinel) in HARD_REQUIRED_KIND_TITLES:
            return True
        return bool(original_is_required(sentinel)) if callable(original_is_required) else False

    hardened.is_required_risk_sentinel = required_v2_is_required_risk_sentinel

    original_covers = getattr(hardened, "_dcoir_required_v2_original_finding_covers_risk_sentinel", None)
    if original_covers is None:
        original_covers = getattr(hardened, "finding_covers_risk_sentinel", None)
        hardened._dcoir_required_v2_original_finding_covers_risk_sentinel = original_covers

    def required_v2_finding_covers_risk_sentinel(finding: dict[str, Any], sentinel: Any) -> bool:
        if _sentinel_kind(sentinel) in HARD_REQUIRED_KIND_TITLES:
            return _finding_covers_sentinel(finding, sentinel)
        return bool(original_covers(finding, sentinel)) if callable(original_covers) else False

    hardened.finding_covers_risk_sentinel = required_v2_finding_covers_risk_sentinel

    original_fallback = getattr(hardened, "_dcoir_required_v2_original_risk_sentinel_fallback_finding", None)
    if original_fallback is None:
        original_fallback = getattr(hardened, "risk_sentinel_fallback_finding", None)
        hardened._dcoir_required_v2_original_risk_sentinel_fallback_finding = original_fallback
    hardened.risk_sentinel_fallback_finding = lambda sentinel, config: _risk_sentinel_fallback_finding(hardened, original_fallback, sentinel, config)

    original_add = getattr(hardened, "_dcoir_required_v2_original_add_risk_sentinel_fallback_findings", None)
    if original_add is None:
        original_add = getattr(hardened, "add_risk_sentinel_fallback_findings", None)
        hardened._dcoir_required_v2_original_add_risk_sentinel_fallback_findings = original_add

    def required_v2_add_risk_sentinel_fallback_findings(
        findings: list[dict[str, Any]],
        risk_sentinels: list[Any],
        config: Any,
        unanchored_findings: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        required_sentinels = hardened.required_risk_sentinels(risk_sentinels)
        coverage_pool = [*findings, *(unanchored_findings or [])]
        uncovered = [
            sentinel
            for sentinel in required_sentinels
            if not any(hardened.finding_covers_risk_sentinel(finding, sentinel) for finding in coverage_pool)
        ]
        inline_limit = max(0, int(getattr(config, "max_inline_comments", 12)))
        fallback_findings = [hardened.risk_sentinel_fallback_finding(sentinel, config) for sentinel in uncovered[:inline_limit]]
        fallback_findings = [finding for finding in fallback_findings if finding]
        existing_budget = max(0, inline_limit - len(fallback_findings))
        existing = _rank_findings(module, hardened, getattr(module, "_dcoir_required_v2_original_rank_findings_for_required_budget", None), findings, config)[:existing_budget]
        return _rank_findings(module, hardened, None, [*existing, *fallback_findings], config)

    hardened.add_risk_sentinel_fallback_findings = required_v2_add_risk_sentinel_fallback_findings

    review_quality_error = getattr(hardened, "ReviewQualityError", RuntimeError)

    def required_v2_enforce_risk_sentinel_findings(
        findings: list[dict[str, Any]],
        risk_sentinels: list[Any],
        config: Any,
        unanchored_findings: list[dict[str, Any]] | None = None,
    ) -> None:
        findings[:] = required_v2_add_risk_sentinel_fallback_findings(findings, risk_sentinels, config, unanchored_findings)
        uncovered = [
            sentinel
            for sentinel in hardened.required_risk_sentinels(risk_sentinels)
            if not any(hardened.finding_covers_risk_sentinel(finding, sentinel) for finding in findings)
        ]
        if uncovered:
            digest = getattr(hardened, "risk_sentinel_coverage_digest", lambda items: "; ".join(str(item) for item in items))(uncovered)
            raise review_quality_error(f"DCOIR Review quality failure: required changed-line signals remain uncovered: {digest}.")

    hardened.enforce_risk_sentinel_findings = required_v2_enforce_risk_sentinel_findings

    original_merge_key = getattr(hardened, "_dcoir_required_v2_original_finding_merge_key", None)
    if original_merge_key is None:
        original_merge_key = getattr(hardened, "finding_merge_key", None)
        hardened._dcoir_required_v2_original_finding_merge_key = original_merge_key

    def required_v2_finding_merge_key(finding: dict[str, Any]) -> tuple[str, int, str]:
        kind = _semantic_kind(finding)
        if kind:
            line = 0 if kind in {"python_ssrf", PS_ACL_KIND} else _finding_line(finding)
            return str(finding.get("path", "") or ""), line, kind
        return original_merge_key(finding) if callable(original_merge_key) else (str(finding.get("path", "") or ""), _finding_line(finding), "unknown")

    hardened.finding_merge_key = required_v2_finding_merge_key
    module.finding_dedupe_key = _dedupe_key
    module.dedupe_findings_for_ranking = lambda findings: _dedupe_findings(hardened, findings)

    original_rank = getattr(module, "_dcoir_required_v2_original_rank_findings_for_required_budget", None)
    if original_rank is None:
        original_rank = getattr(module, "rank_findings_for_required_budget", None)
        module._dcoir_required_v2_original_rank_findings_for_required_budget = original_rank
    module.rank_findings_for_required_budget = lambda findings, config: _rank_findings(module, hardened, original_rank, findings, config)

    original_score = getattr(module, "_dcoir_required_v2_original_anchor_candidate_score", None)
    if original_score is None:
        original_score = getattr(module, "anchor_candidate_score", None)
        module._dcoir_required_v2_original_anchor_candidate_score = original_score
    if callable(original_score):
        def required_v2_anchor_candidate_score(finding: dict[str, Any], candidate: Any, original_line: int, terms: list[str], risk_sentinels: list[Any]) -> int:
            score = int(original_score(finding, candidate, original_line, terms, risk_sentinels))
            finding_kind = _semantic_kind(finding)
            candidate_kind = _line_kind(str(getattr(candidate, "path", "") or ""), str(getattr(candidate, "text", "") or ""))
            candidate_text = _normalize(getattr(candidate, "text", ""))
            if finding_kind == PS_ACL_KIND:
                if candidate_kind == PS_ACL_KIND:
                    score += 320
                elif candidate_kind == "ps_outbound_token":
                    score -= 240
            if finding_kind in {"python_ssrf", "ps_outbound_token"} and ENV_TOKEN_RE.search(candidate_text):
                score += 220
            return score

        module.anchor_candidate_score = required_v2_anchor_candidate_score

    original_synthesize = getattr(module, "_dcoir_required_v2_original_synthesize_fix_for_finding", None)
    if original_synthesize is None:
        original_synthesize = getattr(module, "synthesize_fix_for_finding", None)
        module._dcoir_required_v2_original_synthesize_fix_for_finding = original_synthesize
    if callable(original_synthesize):
        def required_v2_synthesize_fix_for_finding(index: int, finding: dict[str, Any], file_text: str, schema: dict[str, Any], config: Any) -> dict[str, Any]:
            enriched = original_synthesize(index, finding, file_text, schema, config)
            return _normalize_comment_finding(enriched)

        module.synthesize_fix_for_finding = required_v2_synthesize_fix_for_finding

    if base is not None and callable(getattr(base, "build_inline_comment", None)):
        original_build = getattr(base, "_dcoir_required_v2_original_build_inline_comment", None)
        if original_build is None:
            original_build = getattr(base, "_dcoir_strict_original_build_inline_comment", None)
            if original_build is None:
                original_build = getattr(base, "_dcoir_original_build_inline_comment", None)
            if original_build is None:
                original_build = base.build_inline_comment
            base._dcoir_required_v2_original_build_inline_comment = original_build

        def required_v2_build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
            return original_build(_normalize_comment_finding(finding), model_used, config)

        base.build_inline_comment = required_v2_build_inline_comment
