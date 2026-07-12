

def _select_once(hardened: Any, findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _patch_v12_globals()
    selected, metadata = _ORIGINAL_V12_SELECT_ONCE(hardened, findings, risk_sentinels, config)
    selected = [_integrity_finding(item, _postable_key(item), force_template=True) for item in selected]
    return selected, _augment_metadata(selected, findings, risk_sentinels, config, metadata)


def _select_required_postable(hardened: Any, findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    del unanchored_findings
    selected, metadata = _select_once(hardened, findings, risk_sentinels, config)
    core.SELECTION_SUMMARY.clear()
    core.SELECTION_SUMMARY.update(metadata)
    writer = getattr(hardened, "write_debug_json_artifact_safely", None)
    if callable(writer):
        writer(config, "metadata/required-v13-final-selection.json", metadata)
        writer(config, "metadata/required-v12-final-selection.json", metadata)
    v9._ensure_prompt_review(config)
    return selected


def _patch_detect(owner: Any, sentinel_owner: Any | None = None) -> None:
    original = getattr(owner, "_dcoir_required_v13_original_detect_risk_sentinels", None)
    if original is None:
        original = getattr(owner, "detect_risk_sentinels", None)
        owner._dcoir_required_v13_original_detect_risk_sentinels = original
    if not callable(original):
        return
    def detect_risk_sentinels(diff: str, *args: Any, **kwargs: Any) -> list[Any]:
        try:
            sentinels = list(original(diff, *args, **kwargs))
        except TypeError:
            sentinels = list(original(diff))
        risk_sentinel_type = getattr(owner, "RiskSentinel", None) or getattr(sentinel_owner, "RiskSentinel", None)
        if risk_sentinel_type is None:
            return sentinels
        existing = {_sentinel_key(item) for item in sentinels}
        for path, line, text in selection._iter_added_diff_lines(diff):
            checker = getattr(owner, "is_comment_only_added_line", None) or getattr(sentinel_owner, "is_comment_only_added_line", None)
            if callable(checker) and checker(path, text):
                continue
            kind = _line_kind(path, text)
            if kind not in TRACKED_HIGH_RISK_KINDS:
                continue
            key = (path, line, kind)
            if key in existing:
                continue
            title, body, _notes = _template_for_kind(kind)
            sentinels.append(risk_sentinel_type(path=path, line=line, label=title, detail=body, text=text))
            existing.add(key)
        return sentinels
    owner.detect_risk_sentinels = detect_risk_sentinels


def _patch_required_selection(module: Any, hardened: Any) -> None:
    def add_risk_sentinel_fallback_findings(findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        return _select_required_postable(hardened, findings, risk_sentinels, config, unanchored_findings)
    def enforce_risk_sentinel_findings(findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> None:
        findings[:] = _select_required_postable(hardened, findings, risk_sentinels, config, unanchored_findings)
    hardened.add_risk_sentinel_fallback_findings = add_risk_sentinel_fallback_findings
    hardened.enforce_risk_sentinel_findings = enforce_risk_sentinel_findings
    module.rank_findings_for_required_budget = lambda findings, config: sorted([_integrity_finding(v5._normalize_comment_finding(item)) for item in findings if isinstance(item, dict)], key=_spare_priority)[: max(0, int(getattr(config, "max_inline_comments", 12)))]


def _patch_final_rendering(base: Any) -> None:
    original = getattr(base, "_dcoir_v13_original_build_inline_comment", None)
    if original is None:
        original = getattr(base, "build_inline_comment", None)
        base._dcoir_v13_original_build_inline_comment = original
    if not callable(original):
        return
    def v13_build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
        del model_used
        item = _integrity_finding(finding, _postable_key(finding), force_template=True)
        rendered = original(item, "", config)
        return _sanitize_rendered_inline_comment(rendered, item)
    base.build_inline_comment = v13_build_inline_comment


def _patch_review_body_overflow(hardened: Any) -> None:
    original = getattr(hardened, "_dcoir_v13_original_build_review_body_with_unanchored", None)
    if original is None:
        original = getattr(hardened, "build_review_body_with_unanchored", None)
        hardened._dcoir_v13_original_build_review_body_with_unanchored = original
    if not callable(original):
        return
    def v13_build_review_body_with_unanchored(*args: Any, **kwargs: Any) -> str:
        return _append_overflow_to_review_body(original(*args, **kwargs))
    hardened.build_review_body_with_unanchored = v13_build_review_body_with_unanchored


def _patch_v12_globals() -> None:
    v12._canonical_kind = _canonical_kind
    v12._sentinel_key = _sentinel_key
    v12._postable_key = _postable_key
    v12._coverage_key = _coverage_key
    v12._kind_rank = _kind_rank
    v12._sentinel_sort_key = _sentinel_sort_key
    v12._balanced_required_order = _balanced_required_order
    v12._spare_priority = _spare_priority
    v12._semantic_mismatch = _semantic_mismatch
    v12._validation_for_key = _validation_for_key
    v12._fallback_for_sentinel = _fallback_for_sentinel
    v12._dedupe = _dedupe


def _patch_core_semantics() -> None:
    _patch_v12_globals()
    core._sentinel_key = _sentinel_key
    core._postable_key = _postable_key
    core._coverage_key = _coverage_key
    core._semantic_mismatch = _semantic_mismatch
    core._dedupe = _dedupe
    core._spare_priority = _spare_priority
    core._validation_for_key = _validation_for_key
    v9._sentinel_key = _sentinel_key
    v9._postable_key = _postable_key
    v9._semantic_mismatch = _semantic_mismatch
    v11._line_kind = _line_kind
    v11._sentinel_key = _sentinel_key
    v11._postable_key = _postable_key
    v11._coverage_key = _coverage_key
    v11._semantic_mismatch = _semantic_mismatch
    v11._dedupe = _dedupe
    v11._spare_priority = _spare_priority
    v11._validation_for_key = _validation_for_key


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    _patch_core_semantics()
    _patch_detect(module, hardened)
    if base is not None:
        _patch_final_rendering(base)
    if hardened is not None:
        _patch_detect(hardened)
        _patch_required_selection(module, hardened)
        _patch_review_body_overflow(hardened)
    if base is not None:
        v11._patch_progress_comment(base, hardened)
