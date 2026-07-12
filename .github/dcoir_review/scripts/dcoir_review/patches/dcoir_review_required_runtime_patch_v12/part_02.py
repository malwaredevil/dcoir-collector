def _select_once(
    hardened: Any,
    findings: list[dict[str, Any]],
    risk_sentinels: list[Any],
    config: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    limit = max(0, int(getattr(config, "max_inline_comments", 12)))
    required_all = _required_sentinels(hardened, risk_sentinels)
    required_targets, duplicate_covered = _coalesce_required(required_all)
    expected = _expected_by_line(hardened, risk_sentinels)
    required_coverage = {_coverage_key(_sentinel_key(item)) for item in required_targets}

    candidates, dropped = _dedupe([item for item in findings if isinstance(item, dict)], expected)
    by_key = {_postable_key(item): item for item in candidates}
    fallback_by_key: dict[SentinelKey, dict[str, Any]] = {}
    for sentinel in required_targets:
        key = _sentinel_key(sentinel)
        fallback_by_key[key] = _fallback_candidate(hardened, sentinel, config, expected)
        if key not in by_key:
            by_key[key] = fallback_by_key[key]
            candidates.append(fallback_by_key[key])

    selected: list[dict[str, Any]] = []
    selected_coverage: set[SentinelKey] = set()
    suppressed: set[str] = set()

    def add_item(item: dict[str, Any], source_key: SentinelKey | None = None) -> None:
        key = _postable_key(item)
        if source_key is not None:
            key = source_key
        coverage = _coverage_key(key)
        if len(selected) >= limit or coverage in selected_coverage:
            return
        if _semantic_mismatch(item, expected):
            suppressed.add(_key_text(key))
            fallback = fallback_by_key.get(key)
            if fallback and not _semantic_mismatch(fallback, expected):
                selected.append(fallback)
                selected_coverage.add(coverage)
            return
        selected.append(item)
        selected_coverage.add(coverage)

    for sentinel in _balanced_required_order(required_targets):
        key = _sentinel_key(sentinel)
        add_item(by_key.get(key, fallback_by_key[key]), key)

    for item in sorted(candidates, key=_spare_priority):
        key = _postable_key(item)
        if not key[2] or _coverage_key(key) in selected_coverage:
            continue
        add_item(item, key)

    for item in selected:
        path, line, kind = _postable_key(item)
        validation = _validation_for_key(kind, path, line)
        if validation:
            item["validation"] = validation
            guidance = item.get("fix_guidance")
            if isinstance(guidance, dict):
                guidance["validation"] = validation
        v10._scrub_shell_pipe_wording(item)

    final_invalid = [_key_text(_postable_key(item)) for item in selected if _semantic_mismatch(item, expected)]
    selected_keys = [_postable_key(item) for item in selected]
    selected_coverage = {_coverage_key(key) for key in selected_keys}
    omitted_required = [
        _sentinel_record(item, "auto", required_coverage, selected_coverage, limit)
        for item in required_targets
        if _coverage_key(_sentinel_key(item)) not in selected_coverage
    ]
    optional_high_risk = [
        _sentinel_record(item, "auto", required_coverage, selected_coverage, limit)
        for item in risk_sentinels
        if _coverage_key(_sentinel_key(item)) not in selected_coverage
        and _coverage_key(_sentinel_key(item)) not in required_coverage
        and _sentinel_key(item)[2]
    ]
    required_ledger_keys = sorted(
        {
            _key_text(_coverage_key(key))
            for key in selected_keys
            if _coverage_key(key) in required_coverage
        }
        | {
            _key_text(_coverage_key(_sentinel_key(item)))
            for item in required_targets
            if _coverage_key(_sentinel_key(item)) not in selected_coverage
        }
    )
    duplicate_required_keys = {
        _key_text(_coverage_key((str(item.get("path", "") or ""), int(item.get("line", 0) or 0), str(item.get("kind", "") or ""))))
        for item in duplicate_covered
    }
    required_ledger_keys = sorted(set(required_ledger_keys) | duplicate_required_keys)
    metadata = {
        "version": VERSION,
        "hard_required_count": len(required_all),
        "coalesced_required_count": len(required_targets),
        "final_postable_count": len(selected),
        "inline_limit": limit,
        "partial_overflow": bool(omitted_required or optional_high_risk),
        "overflow_required_count": len(omitted_required),
        "overflow_optional_high_risk_count": len(optional_high_risk),
        "selected_keys": [_key_text(key) for key in selected_keys],
        "duplicate_covered_sentinels": duplicate_covered[:80],
        "dropped_invalid_or_duplicate_candidates": dropped[:120],
        "suppressed_invalid_selected_keys": sorted(suppressed),
        "final_invalid_selected_keys": final_invalid,
        "omitted_required_sentinels": omitted_required[:80],
        "omitted_optional_high_risk_sentinels": optional_high_risk[:80],
        "omitted_sentinels": (omitted_required + optional_high_risk)[:80],
        "final_uncovered": [f"{item.get('path')}:{item.get('line')} {item.get('kind')}" for item in omitted_required],
        "required_ledger_keys": required_ledger_keys[:120],
        "required_ledger_accounted_count": len(required_ledger_keys),
    }
    return selected, metadata


def _key_text(key: SentinelKey) -> str:
    return f"{key[0]}:{key[1]} {key[2]}"


def _sentinel_record(
    sentinel: Any,
    reason: str,
    required: set[SentinelKey],
    selected: set[SentinelKey],
    limit: int,
) -> dict[str, Any]:
    key = _sentinel_key(sentinel)
    coverage = _coverage_key(key)
    bucket = "hard-required" if coverage in required else "optional-pressure" if key[2].startswith("k8s_") else "high-risk"
    actual_reason = reason
    if reason == "auto":
        actual_reason = "duplicate_covered" if coverage in selected else "omitted_due_to_inline_budget" if len(selected) >= limit else "not_selected"
    return {
        "path": key[0],
        "line": key[1],
        "kind": key[2],
        "priority_bucket": bucket,
        "reason": actual_reason,
        "label": str(getattr(sentinel, "label", "") or ""),
        "detail": str(getattr(sentinel, "detail", "") or "")[:240],
        "text": str(getattr(sentinel, "text", "") or "")[:240],
    }


def _select_required_postable(
    hardened: Any,
    findings: list[dict[str, Any]],
    risk_sentinels: list[Any],
    config: Any,
    unanchored_findings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    del unanchored_findings
    selected, metadata = _select_once(hardened, findings, risk_sentinels, config)
    core.SELECTION_SUMMARY.clear()
    core.SELECTION_SUMMARY.update(metadata)
    writer = getattr(hardened, "write_debug_json_artifact_safely", None)
    if callable(writer):
        writer(config, "metadata/required-v12-final-selection.json", metadata)
        writer(config, "metadata/required-v11-final-selection.json", metadata)
        writer(config, "metadata/required-v10-final-selection.json", metadata)
        writer(config, "metadata/required-v9-final-selection.json", metadata)
    if metadata["final_invalid_selected_keys"]:
        raise getattr(hardened, "ReviewQualityError", RuntimeError)(
            "DCOIR Review quality failure: final selected findings have semantic mismatches: "
            + "; ".join(metadata["final_invalid_selected_keys"])
        )
    v9._ensure_prompt_review(config)
    return selected


def _patch_required_selection(module: Any, hardened: Any) -> None:
    def add_risk_sentinel_fallback_findings(
        findings: list[dict[str, Any]],
        risk_sentinels: list[Any],
        config: Any,
        unanchored_findings: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        return _select_required_postable(hardened, findings, risk_sentinels, config, unanchored_findings)

    def enforce_risk_sentinel_findings(
        findings: list[dict[str, Any]],
        risk_sentinels: list[Any],
        config: Any,
        unanchored_findings: list[dict[str, Any]] | None = None,
    ) -> None:
        findings[:] = _select_required_postable(hardened, findings, risk_sentinels, config, unanchored_findings)

    hardened.add_risk_sentinel_fallback_findings = add_risk_sentinel_fallback_findings
    hardened.enforce_risk_sentinel_findings = enforce_risk_sentinel_findings
    module.rank_findings_for_required_budget = lambda findings, config: sorted(
        [v5._normalize_comment_finding(item) for item in findings if isinstance(item, dict)],
        key=_spare_priority,
    )[: max(0, int(getattr(config, "max_inline_comments", 12)))]


def _patch_python_extra_sentinels(owner: Any, sentinel_owner: Any | None = None) -> None:
    original = getattr(owner, "_dcoir_required_v12_original_detect_risk_sentinels", None)
    if original is None:
        original = getattr(owner, "detect_risk_sentinels", None)
        owner._dcoir_required_v12_original_detect_risk_sentinels = original
    if not callable(original):
        return

    def detect_risk_sentinels(diff: str, *args: Any, **kwargs: Any) -> list[Any]:
        widened_args = list(args)
        if widened_args and isinstance(widened_args[0], int):
            widened_args[0] = None
        widened_kwargs = dict(kwargs)
        for name in ("max_anchors", "max_sentinels", "limit"):
            if name in widened_kwargs:
                widened_kwargs[name] = None
        try:
            sentinels = list(original(diff, *widened_args, **widened_kwargs))
        except TypeError:
            sentinels = list(original(diff, *args, **kwargs))
        existing = {_sentinel_key(item) for item in sentinels}
        risk_sentinel_type = getattr(owner, "RiskSentinel", None) or getattr(sentinel_owner, "RiskSentinel", None)
        if risk_sentinel_type is None:
            return sentinels
        for path, line, text in selection._iter_added_diff_lines(diff):
            if Path(path.lower()).suffix != ".py":
                continue
            comment_checker = getattr(owner, "is_comment_only_added_line", None) or getattr(sentinel_owner, "is_comment_only_added_line", None)
            if callable(comment_checker) and comment_checker(path, text):
                continue
            kind = v11._line_kind(path, text)
            if kind not in {v11.PYTHON_ARCHIVE_EXTRACT, v11.PYTHON_PATH_WRITE}:
                continue
            key = (path, line, kind)
            if key in existing:
                continue
            if kind == v11.PYTHON_ARCHIVE_EXTRACT:
                label = "Python unsafe archive extraction"
                detail = "archive extraction needs destination containment and member traversal checks before unpacking untrusted archives"
            else:
                label = "Python request-controlled file write"
                detail = "request-controlled paths must be resolved under an allowlisted base directory before writing"
            sentinels.append(risk_sentinel_type(path=path, line=line, label=label, detail=detail, text=text))
            existing.add(key)
        return sentinels

    owner.detect_risk_sentinels = detect_risk_sentinels


def _patch_core_semantics() -> None:
    core._sentinel_key = _sentinel_key
    core._postable_key = _postable_key
    core._coverage_key = _coverage_key
    core._required_sentinels = _required_sentinels
    core._expected_by_line = _expected_by_line
    core._semantic_mismatch = _semantic_mismatch
    core._dedupe = _dedupe
    core._spare_priority = _spare_priority
    core._validation_for_key = _validation_for_key
    v9._sentinel_key = _sentinel_key
    v9._postable_key = _postable_key
    v9._semantic_mismatch = _semantic_mismatch
    v11._sentinel_key = _sentinel_key
    v11._postable_key = _postable_key
    v11._coverage_key = _coverage_key
    v11._required_sentinels = _required_sentinels
    v11._expected_by_line = _expected_by_line
    v11._semantic_mismatch = _semantic_mismatch
    v11._dedupe = _dedupe
    v11._spare_priority = _spare_priority
    v11._validation_for_key = _validation_for_key


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    _patch_core_semantics()
    _patch_python_extra_sentinels(module, hardened)
    if hardened is not None:
        _patch_python_extra_sentinels(hardened)
        _patch_required_selection(module, hardened)
    if base is not None:
        v11._patch_progress_comment(base, hardened)
