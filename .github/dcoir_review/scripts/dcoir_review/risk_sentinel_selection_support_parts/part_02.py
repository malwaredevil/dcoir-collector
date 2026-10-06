def _select_required_postable(hardened: Any, findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    limit = max(0, int(getattr(config, "max_inline_comments", 12)))
    required = _required_sentinels(hardened, risk_sentinels)
    expected = _expected_by_line(hardened, risk_sentinels)
    required_key_set = {_sentinel_key(item) for item in required}
    if len(required) > limit:
        metadata = {
            "hard_required_count": len(required),
            "inline_limit": limit,
            "capacity_failure": True,
            "required_keys": [_key_text(_sentinel_key(item)) for item in required],
        }
        SELECTION_SUMMARY.clear()
        SELECTION_SUMMARY.update(metadata)
        hardened.write_debug_json_artifact_safely(config, "metadata/required-v9-final-selection.json", metadata)
        raise getattr(hardened, "ReviewQualityError", RuntimeError)(
            f"DCOIR Review quality failure: required changed-line signals ({len(required)}) exceed inline comment budget ({limit})."
        )
    raw = [item for item in findings if isinstance(item, dict)]
    candidates, dropped = _dedupe(raw, expected)
    by_key = {_postable_key(item): item for item in candidates}
    for sentinel in required:
        key = _sentinel_key(sentinel)
        if key not in by_key:
            fallback = _fallback_for_sentinel(hardened, sentinel, config)
            normalized = dict(fallback) if fallback.get("_dcoir_v9_known_fallback") else v5._normalize_comment_finding(fallback)
            by_key[key] = normalized
            candidates.append(normalized)
    selected: list[dict[str, Any]] = []
    selected_keys: set[SentinelKey] = set()
    for sentinel in required:
        key = _sentinel_key(sentinel)
        if key in by_key and key not in selected_keys and len(selected) < limit:
            selected.append(by_key[key])
            selected_keys.add(key)
    for item in sorted(candidates, key=_spare_priority):
        key = _postable_key(item)
        if len(selected) >= limit:
            break
        if key not in selected_keys and key[2]:
            selected.append(item)
            selected_keys.add(key)
    selected = selected[:limit]
    _rewrite_validation(selected)
    final_invalid = [_key_text(_postable_key(item)) for item in selected if _semantic_mismatch(item, expected)]
    final_uncovered = [key for key in (_sentinel_key(item) for item in required) if key not in selected_keys]
    omitted = [
        _sentinel_summary_record(item, required_key_set, selected_keys, limit)
        for item in risk_sentinels
        if _sentinel_key(item) not in selected_keys
    ]
    metadata = {
        "hard_required_count": len(required),
        "final_postable_count": len(selected),
        "inline_limit": limit,
        "selected_keys": [_key_text(_postable_key(item)) for item in selected],
        "spare_budget_selected": [_key_text(_postable_key(item)) for item in selected if _postable_key(item) not in required_key_set],
        "dropped_invalid_or_duplicate_candidates": dropped[:80],
        "final_invalid_selected_keys": final_invalid,
        "final_uncovered": [_key_text(key) for key in final_uncovered],
        "omitted_sentinel_count": len(omitted),
        "omitted_sentinels": omitted[:80],
    }
    SELECTION_SUMMARY.clear()
    SELECTION_SUMMARY.update(metadata)
    hardened.write_debug_json_artifact_safely(
        config,
        "metadata/required-v9-final-selection.json",
        metadata,
    )
    if final_invalid:
        raise getattr(hardened, "ReviewQualityError", RuntimeError)(
            "DCOIR Review quality failure: final selected findings have semantic mismatches: " + "; ".join(final_invalid)
        )
    if final_uncovered:
        raise getattr(hardened, "ReviewQualityError", RuntimeError)(
            "DCOIR Review quality failure: required changed-line signals remain uncovered after v9 final selection: "
            + "; ".join(_key_text(key) for key in final_uncovered)
        )
    _ensure_prompt_review(config)
    return selected


def _patch_required_selection(module: Any, hardened: Any) -> None:
    def add_risk_sentinel_fallback_findings(findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        return _select_required_postable(hardened, findings, risk_sentinels, config, unanchored_findings)

    def enforce_risk_sentinel_findings(findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> None:
        findings[:] = _select_required_postable(hardened, findings, risk_sentinels, config, unanchored_findings)

    hardened.add_risk_sentinel_fallback_findings = add_risk_sentinel_fallback_findings
    hardened.enforce_risk_sentinel_findings = enforce_risk_sentinel_findings
    module.rank_findings_for_required_budget = lambda findings, config: sorted(
        [v5._normalize_comment_finding(item) for item in findings if isinstance(item, dict)],
        key=_spare_priority,
    )[: max(0, int(getattr(config, "max_inline_comments", 12)))]


def _patch_yaml_safe_load_note() -> None:
    original = getattr(v5, "_dcoir_required_v9_original_template_fields", None)
    if original is None:
        original = getattr(v5, "_template_fields", None)
        v5._dcoir_required_v9_original_template_fields = original
    if not callable(original):
        return

    def template_fields(kind: str, path: str, line_text: str) -> dict[str, Any]:
        fields = original(kind, path, line_text)
        if kind == v5.PYTHON_YAML_LOAD:
            arg = _yaml_load_arg(line_text)
            guidance = dict(fields.get("fix_guidance") or {})
            guidance["notes"] = f"Use `yaml.safe_load({arg})` or `yaml.load({arg}, Loader=yaml.SafeLoader)` when no Python object tags are expected."
            fields["fix_guidance"] = guidance
        return fields

    v5._template_fields = template_fields
