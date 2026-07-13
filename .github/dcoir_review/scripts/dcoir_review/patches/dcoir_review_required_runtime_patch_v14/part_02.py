def _coalesce_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept: dict[SentinelKey, dict[str, Any]] = {}
    for record in records:
        key = (
            str(record.get("path", "") or ""),
            int(record.get("line", 0) or 0),
            str(record.get("kind", "") or ""),
        )
        coverage = _coverage_key(key)
        current = kept.get(coverage)
        if current is None:
            kept[coverage] = record
            continue
        current_key = (
            str(current.get("path", "") or ""),
            int(current.get("line", 0) or 0),
            str(current.get("kind", "") or ""),
        )
        current_score = (SELECTION_KIND_RANK.get(current_key[2], v13._kind_rank(current_key[2])), _sink_preference(current_key[2], str(current.get("text", "") or "")), current_key[1])
        next_score = (SELECTION_KIND_RANK.get(key[2], v13._kind_rank(key[2])), _sink_preference(key[2], str(record.get("text", "") or "")), key[1])
        if next_score < current_score:
            kept[coverage] = record
    return list(kept.values())


def _augment_metadata(
    selected: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    risk_sentinels: list[Any],
    *args: Any,
) -> dict[str, Any]:
    if len(args) == 2:
        hardened = None
        config, metadata = args
    elif len(args) == 3:
        hardened, config, metadata = args
    else:
        raise TypeError("_augment_metadata expected selected, findings, risk_sentinels, [hardened], config, metadata")
    try:
        updated = _ORIGINAL_V13_AUGMENT_METADATA(selected, findings, risk_sentinels, hardened, config, metadata)
    except TypeError:
        try:
            updated = _ORIGINAL_V13_AUGMENT_METADATA(selected, findings, risk_sentinels, config, metadata)
        except NameError:
            updated = dict(metadata)
    except NameError:
        updated = dict(metadata)
    updated["version"] = VERSION
    for key in ("omitted_required_sentinels", "omitted_optional_high_risk_sentinels", "detector_only_high_risk_overflow"):
        updated[key] = _coalesce_records(list(updated.get(key, []) or []))
    updated["overflow_required_count"] = len(updated.get("omitted_required_sentinels", []) or [])
    updated["overflow_optional_high_risk_count"] = len(updated.get("omitted_optional_high_risk_sentinels", []) or [])
    updated["overflow_detector_high_risk_count"] = len(updated.get("detector_only_high_risk_overflow", []) or [])
    updated["final_uncovered"] = [
        f"{item['path']}:{item['line']} {item['kind']}"
        for item in (updated.get("omitted_required_sentinels", []) or [])
        if item.get("path") and item.get("kind")
    ]
    updated["required_ledger_omitted_keys"] = list(updated["final_uncovered"])
    posted = list(updated.get("posted_required_sentinels", []) or [])
    omitted = list(updated.get("required_ledger_omitted_keys", []) or updated.get("final_uncovered", []) or [])
    updated["posted_required_family_counts"] = _family_counts(posted)
    updated["omitted_required_family_counts"] = _family_counts(omitted)
    updated["required_family_balancing"] = "round_robin_after_coverage_coalescing"
    return updated


def _select_required_postable(
    hardened: Any,
    findings: list[dict[str, Any]],
    risk_sentinels: list[Any],
    config: Any,
    unanchored_findings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    _patch_core_semantics()
    selected = _ORIGINAL_V13_SELECT_REQUIRED(hardened, findings, risk_sentinels, config, unanchored_findings)
    metadata = dict(core.SELECTION_SUMMARY)
    metadata["version"] = VERSION
    core.SELECTION_SUMMARY.clear()
    core.SELECTION_SUMMARY.update(metadata)
    writer = getattr(hardened, "write_debug_json_artifact_safely", None)
    if callable(writer):
        writer(config, "metadata/required-v14-final-selection.json", metadata)
    return selected


def _patch_v12_globals() -> None:
    _ORIGINAL_V13_PATCH_V12_GLOBALS()
    v12._coverage_key = _coverage_key
    v12._sentinel_sort_key = _sentinel_sort_key
    v12._balanced_required_order = _balanced_required_order
    v12._spare_priority = _spare_priority
    v12._validation_for_key = _validation_for_key


def _patch_core_semantics() -> None:
    _ORIGINAL_V13_PATCH_CORE_SEMANTICS()
    _patch_v12_globals()
    v13._coverage_key = _coverage_key
    v13._sentinel_sort_key = _sentinel_sort_key
    v13._balanced_required_order = _balanced_required_order
    v13._spare_priority = _spare_priority
    v13._template_for_kind = _template_for_kind
    v13._safe_validation = _safe_validation
    v13._integrity_finding = _integrity_finding
    v13._render_integrity_errors = _render_integrity_errors
    v13._rendered_comment_has_integrity_problem = _rendered_comment_has_integrity_problem
    v13._rendered_comment_has_problem = _rendered_comment_has_integrity_problem
    v13._augment_metadata = _augment_metadata
    v13._select_required_postable = _select_required_postable
    core._coverage_key = _coverage_key
    core._spare_priority = _spare_priority
    core._validation_for_key = _validation_for_key
    v11._coverage_key = _coverage_key
    v11._spare_priority = _spare_priority
    v11._validation_for_key = _validation_for_key


def apply_pareto_context_module(module: Any) -> None:
    _patch_core_semantics()
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    if hardened is not None:
        v13._patch_required_selection(module, hardened)
        v13._patch_review_body_overflow(hardened)
    if base is not None:
        v13._patch_final_rendering(base)
        v11._patch_progress_comment(base, hardened)
