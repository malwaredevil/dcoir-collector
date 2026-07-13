

def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    if hardened is None:
        return

    if not hasattr(hardened, "_dcoir_required_original_select_risk_sentinels") and callable(getattr(hardened, "select_risk_sentinels", None)):
        hardened._dcoir_required_original_select_risk_sentinels = hardened.select_risk_sentinels

    original_detect = getattr(module, "_dcoir_required_original_detect_risk_sentinels", None)
    if original_detect is None:
        original_detect = getattr(module, "detect_risk_sentinels", getattr(hardened, "detect_risk_sentinels", None))
        module._dcoir_required_original_detect_risk_sentinels = original_detect

    if callable(original_detect):
        def required_detect_risk_sentinels(diff: str, max_anchors: int | None = None) -> list[Any]:
            existing = original_detect(diff, None)
            strict_yaml = _make_yaml_sentinels(hardened, diff)
            return _select_sentinels(hardened, [*existing, *strict_yaml], max_anchors)

        module.detect_risk_sentinels = required_detect_risk_sentinels
        hardened.detect_risk_sentinels = required_detect_risk_sentinels

    original_is_required = getattr(hardened, "_dcoir_required_original_is_required_risk_sentinel", None)
    if original_is_required is None:
        original_is_required = getattr(hardened, "is_required_risk_sentinel", None)
        hardened._dcoir_required_original_is_required_risk_sentinel = original_is_required

    def required_is_required_risk_sentinel(sentinel: Any) -> bool:
        if _sentinel_kind(sentinel) in YAML_REQUIRED_KIND_TITLES:
            return True
        return bool(original_is_required(sentinel)) if callable(original_is_required) else False

    hardened.is_required_risk_sentinel = required_is_required_risk_sentinel

    original_required = getattr(hardened, "_dcoir_required_original_required_risk_sentinels", None)
    if original_required is None:
        original_required = getattr(hardened, "required_risk_sentinels", None)
        hardened._dcoir_required_original_required_risk_sentinels = original_required

    hardened.required_risk_sentinels = lambda sentinels: _required_sentinels(original_required, sentinels)

    original_covers = getattr(hardened, "_dcoir_required_original_finding_covers_risk_sentinel", None)
    if original_covers is None:
        original_covers = getattr(hardened, "finding_covers_risk_sentinel", None)
        hardened._dcoir_required_original_finding_covers_risk_sentinel = original_covers

    def required_finding_covers_risk_sentinel(finding: dict[str, Any], sentinel: Any) -> bool:
        if _sentinel_kind(sentinel) in YAML_REQUIRED_KIND_TITLES:
            return _finding_covers_sentinel(finding, sentinel)
        return bool(original_covers(finding, sentinel)) if callable(original_covers) else False

    hardened.finding_covers_risk_sentinel = required_finding_covers_risk_sentinel

    original_fallback = getattr(hardened, "_dcoir_required_original_risk_sentinel_fallback_finding", None)
    if original_fallback is None:
        original_fallback = getattr(hardened, "risk_sentinel_fallback_finding", None)
        hardened._dcoir_required_original_risk_sentinel_fallback_finding = original_fallback

    hardened.risk_sentinel_fallback_finding = lambda sentinel, config: _risk_sentinel_fallback_finding(hardened, original_fallback, sentinel, config)

    def required_add_risk_sentinel_fallback_findings(
        findings: list[dict[str, Any]],
        risk_sentinels: list[Any],
        config: Any,
        unanchored_findings: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        required = hardened.required_risk_sentinels(risk_sentinels)
        uncovered = [
            sentinel
            for sentinel in required
            if not any(
                hardened.finding_covers_risk_sentinel(finding, sentinel)
                for finding in (findings if _sentinel_kind(sentinel) in YAML_REQUIRED_KIND_TITLES else [*findings, *(unanchored_findings or [])])
            )
        ]
        if not uncovered:
            return _dedupe_findings(hardened, findings)
        inline_limit = max(0, int(getattr(config, "max_inline_comments", 12)))
        fallback_findings = [hardened.risk_sentinel_fallback_finding(sentinel, config) for sentinel in uncovered[:inline_limit]]
        fallback_findings = [finding for finding in fallback_findings if finding]
        existing_budget = max(0, inline_limit - len(fallback_findings))
        existing = _strict_rank_findings(module, hardened, getattr(module, "_dcoir_required_original_rank_findings_for_required_budget", None), findings, config)[:existing_budget]
        return _strict_rank_findings(module, hardened, None, [*existing, *fallback_findings], config)

    hardened.add_risk_sentinel_fallback_findings = required_add_risk_sentinel_fallback_findings

    review_quality_error = getattr(hardened, "ReviewQualityError", RuntimeError)

    def required_enforce_risk_sentinel_findings(
        findings: list[dict[str, Any]],
        risk_sentinels: list[Any],
        config: Any,
        unanchored_findings: list[dict[str, Any]] | None = None,
    ) -> None:
        augmented = required_add_risk_sentinel_fallback_findings(findings, risk_sentinels, config, unanchored_findings)
        findings[:] = augmented
        uncovered = [
            sentinel
            for sentinel in hardened.required_risk_sentinels(risk_sentinels)
            if not any(hardened.finding_covers_risk_sentinel(finding, sentinel) for finding in findings)
        ]
        if uncovered:
            digest = getattr(hardened, "risk_sentinel_coverage_digest", lambda items: "; ".join(str(item) for item in items))(uncovered)
            raise review_quality_error(f"DCOIR Review quality failure: required changed-line signals remain uncovered: {digest}.")

    hardened.enforce_risk_sentinel_findings = required_enforce_risk_sentinel_findings

    original_merge_key = getattr(hardened, "_dcoir_required_original_finding_merge_key", None)
    if original_merge_key is None:
        original_merge_key = getattr(hardened, "finding_merge_key", None)
        hardened._dcoir_required_original_finding_merge_key = original_merge_key

    def required_finding_merge_key(finding: dict[str, Any]) -> tuple[str, int, str]:
        kind = _semantic_kind(finding)
        if kind:
            path = str(finding.get("path", "") or "").strip()
            line_text = _dedupe_line_key(kind, finding)
            try:
                line = int(line_text or 0)
            except (TypeError, ValueError):
                line = 0
            return (path, line, kind)
        return original_merge_key(finding) if callable(original_merge_key) else (str(finding.get("path", "") or ""), int(finding.get("line", 0) or 0), "unknown")

    hardened.finding_merge_key = required_finding_merge_key

    original_dedupe_key = getattr(module, "_dcoir_required_original_finding_dedupe_key", None)
    if original_dedupe_key is None:
        original_dedupe_key = getattr(module, "finding_dedupe_key", None)
        module._dcoir_required_original_finding_dedupe_key = original_dedupe_key

    module.finding_dedupe_key = _dedupe_key
    module.dedupe_findings_for_ranking = lambda findings: _dedupe_findings(hardened, findings)

    original_rank = getattr(module, "_dcoir_required_original_rank_findings_for_required_budget", None)
    if original_rank is None:
        original_rank = getattr(module, "rank_findings_for_required_budget", None)
        module._dcoir_required_original_rank_findings_for_required_budget = original_rank

    module.rank_findings_for_required_budget = lambda findings, config: _strict_rank_findings(module, hardened, original_rank, findings, config)

    original_score = getattr(module, "_dcoir_required_original_anchor_candidate_score", None)
    if original_score is None:
        original_score = getattr(module, "anchor_candidate_score", None)
        module._dcoir_required_original_anchor_candidate_score = original_score

    if callable(original_score):
        def required_anchor_candidate_score(finding: dict[str, Any], candidate: Any, original_line: int, terms: list[str], risk_sentinels: list[Any]) -> int:
            score = int(original_score(finding, candidate, original_line, terms, risk_sentinels))
            finding_kind = _semantic_kind(finding)
            candidate_kind = _candidate_kind(candidate)
            candidate_text = _normalize(getattr(candidate, "text", ""))
            if finding_kind and candidate_kind:
                if finding_kind == candidate_kind:
                    score += 240
                elif finding_kind.startswith("yaml_") and candidate_kind.startswith("yaml_"):
                    score -= 180
            if finding_kind == "python_ssrf":
                if candidate_text.startswith("def "):
                    score -= 220
                if any(term in candidate_text for term in ("urlopen", "urllib.request.request", "authorization", "bearer", "callback_url", "os.environ")):
                    score += 260
            if finding_kind == "ps_acl" and any(term in candidate_text for term in ("filesystemaccessrule", "set-acl", "everyone", "fullcontrol")):
                score += 240
            return score

        module.anchor_candidate_score = required_anchor_candidate_score

    original_synthesize = getattr(module, "_dcoir_required_original_synthesize_fix_for_finding", None)
    if original_synthesize is None:
        original_synthesize = getattr(module, "synthesize_fix_for_finding", None)
        module._dcoir_required_original_synthesize_fix_for_finding = original_synthesize

    if callable(original_synthesize):
        def required_synthesize_fix_for_finding(index: int, finding: dict[str, Any], file_text: str, schema: dict[str, Any], config: Any) -> dict[str, Any]:
            enriched = original_synthesize(index, finding, file_text, schema, config)
            path = str(enriched.get("path", finding.get("path", "")) or "")
            try:
                line = int(enriched.get("line", finding.get("line", 0)) or 0)
            except (TypeError, ValueError):
                line = 0
            suggestion = str(enriched.get("suggested_replacement", "") or "")
            if suggestion and not _strict_suggestion_is_safe(suggestion, file_text, line, path, enriched):
                guidance = dict(enriched.get("fix_guidance") if isinstance(enriched.get("fix_guidance"), dict) else {})
                note = "Native GitHub suggestion suppressed because the candidate replacement did not pass strict changed-file safety checks. Use the prose guidance and add a focused exact patch instead."
                existing_notes = str(guidance.get("notes", "") or "").strip()
                guidance["notes"] = "\n\n".join(part for part in (existing_notes, note) if part)
                enriched["fix_guidance"] = guidance
                enriched["suggested_replacement"] = ""
            return _normalize_comment_finding(enriched)

        module.synthesize_fix_for_finding = required_synthesize_fix_for_finding

    if base is not None and callable(getattr(base, "build_inline_comment", None)):
        original_build = getattr(base, "_dcoir_required_original_build_inline_comment", None)
        if original_build is None:
            original_build = base.build_inline_comment
            base._dcoir_required_original_build_inline_comment = original_build

        def required_build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
            return original_build(_normalize_comment_finding(finding), model_used, config)

        base.build_inline_comment = required_build_inline_comment
