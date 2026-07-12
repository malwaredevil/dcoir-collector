def _select_once(_hardened: Any, findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    limit = max(0, int(getattr(config, "max_inline_comments", 12)))
    core_targets = _core_sentinels(risk_sentinels)
    required_cov = {_coverage_key(_sentinel_key(sentinel)) for sentinel in core_targets}
    aggregate = _aggregate_candidates(core_targets)
    selected: list[dict[str, Any]] = []
    selected_cov: set[SentinelKey] = set()

    def add(item: dict[str, Any]) -> None:
        if len(selected) >= limit:
            return
        item_cov = _coverage_from_finding(item)
        if not item_cov or item_cov <= selected_cov:
            return
        selected.append(item)
        selected_cov.update(item_cov)

    for item in sorted(aggregate, key=_candidate_priority):
        add(item)
    for sentinel in sorted(core_targets, key=lambda item: (_kind_rank(_sentinel_key(item)[2]), _sentinel_key(item)[0], _sentinel_key(item)[1])):
        if _coverage_key(_sentinel_key(sentinel)) not in selected_cov:
            add(_finding_for_sentinel(sentinel))

    model_candidates: list[dict[str, Any]] = []
    for raw in findings:
        if not isinstance(raw, dict):
            continue
        try:
            item = v5._normalize_comment_finding(raw)
        except Exception:
            item = dict(raw)
        key = _postable_key(item)
        if key[2] and key[2] not in CORE_REQUIRED_KINDS:
            item["_risk_sentinel_key"] = [key[0], key[1], key[2]]
            model_candidates.append(item)
    for item in sorted(model_candidates, key=_candidate_priority):
        add(item)

    omitted_required = []
    aggregate_covered = []
    for sentinel in core_targets:
        key = _sentinel_key(sentinel)
        coverage = _coverage_key(key)
        if coverage in selected_cov:
            if not any(_postable_key(item) == key for item in selected):
                aggregate_covered.append(_sentinel_record(sentinel, "aggregate_covered", required_cov, selected_cov, limit))
            continue
        omitted_required.append(_sentinel_record(sentinel, "omitted_due_to_inline_budget", required_cov, selected_cov, limit))

    optional_overflow = []
    for sentinel in risk_sentinels:
        key = _sentinel_key(sentinel)
        coverage = _coverage_key(key)
        if coverage in selected_cov or coverage in required_cov:
            continue
        if key[2] in TRACKED_KINDS or key[2] in OPTIONAL_PRESSURE_KINDS:
            optional_overflow.append(_sentinel_record(sentinel, "omitted_due_to_inline_budget", required_cov, selected_cov, limit))

    selected_keys = [_postable_key(item) for item in selected]
    metadata = {
        "version": VERSION,
        "inline_limit": limit,
        "final_postable_count": len(selected),
        "hard_required_count": len(core_targets),
        "covered_required_count": len(required_cov),
        "selected_keys": [_key_text(key) for key in selected_keys],
        "posted_required_sentinels": [_key_text(key) for key in selected_keys if _coverage_key(key) in required_cov],
        "aggregate_covered_sentinels": aggregate_covered[:100],
        "omitted_required_sentinels": omitted_required[:100],
        "omitted_optional_high_risk_sentinels": optional_overflow[:100],
        "overflow_required_count": len(omitted_required),
        "overflow_optional_high_risk_count": len(optional_overflow),
        "partial_overflow": bool(omitted_required or optional_overflow),
        "final_uncovered": [_key_text((item["path"], int(item["line"]), item["kind"])) for item in omitted_required],
        "required_ledger_schema": "v16_posted_aggregate_covered_omitted_suppressed",
        "core_required_families": _family_counts(required_cov),
        "selected_coverage_families": _family_counts(selected_cov),
        "kubernetes_policy": "optional_bonus_only",
    }
    return selected, metadata


def _family_counts(keys: set[SentinelKey]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for _path, _line, kind in keys:
        family = _family(kind)
        counts[family] = counts.get(family, 0) + 1
    return counts


def _key_text(key: SentinelKey) -> str:
    return f"{key[0]}:{key[1]} {key[2]}"


def _sentinel_record(sentinel: Any, reason: str, required: set[SentinelKey], selected: set[SentinelKey], limit: int) -> dict[str, Any]:
    key = _sentinel_key(sentinel)
    return {
        "path": key[0],
        "line": key[1],
        "kind": key[2],
        "bucket": "hard-required" if _coverage_key(key) in required else "optional-pressure",
        "reason": reason,
        "label": str(getattr(sentinel, "label", "") or ""),
        "detail": str(getattr(sentinel, "detail", "") or "")[:240],
        "text": str(getattr(sentinel, "text", "") or "")[:240],
        "selected_count": len(selected),
        "inline_limit": limit,
    }


def _select_required_postable(hardened: Any, findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    del unanchored_findings
    selected, metadata = _select_once(hardened, findings, risk_sentinels, config)
    core.SELECTION_SUMMARY.clear()
    core.SELECTION_SUMMARY.update(metadata)
    writer = getattr(hardened, "write_debug_json_artifact_safely", None)
    if callable(writer):
        writer(config, "metadata/required-v16-final-selection.json", metadata)
    v9._ensure_prompt_review(config)
    return selected


def _render_comment(finding: dict[str, Any]) -> str:
    path, line, kind = _postable_key(finding)
    title = str(finding.get("title", "") or _template_for_kind(kind)[0]).strip()
    body = str(finding.get("body", "") or _template_for_kind(kind)[1]).strip()
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    notes = str(guidance.get("notes", "") or _template_for_kind(kind)[2]).strip()
    validation = str(finding.get("validation", "") or guidance.get("validation", "") or _validation_for_key(kind, path, line)).strip()
    lines = [f"**{title}**", "", body]
    covered = finding.get("covered_risk_sentinel_keys")
    if isinstance(covered, list) and len(covered) > 1:
        rendered = []
        for raw in covered:
            if isinstance(raw, (list, tuple)) and len(raw) == 3:
                rendered.append(_line_label((str(raw[0] or ""), _line_number(raw[1]), str(raw[2] or ""))))
        if rendered:
            lines.extend(["", "**Covered signals:**", *[f"- {item}" for item in rendered]])
    if notes:
        lines.extend(["", "**Suggested fix:**", "", notes])
    if validation:
        lines.extend(["", "**Validation:**", "", "```bash", validation, "```"])
    return "\n".join(lines).strip()


def _patch_final_rendering(base: Any) -> None:
    def build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
        del model_used, config
        return _render_comment(finding)

    base.build_inline_comment = build_inline_comment


def _patch_review_body_overflow(hardened: Any) -> None:
    original = getattr(hardened, "_dcoir_v16_original_build_review_body_with_unanchored", None)
    if original is None:
        original = getattr(hardened, "build_review_body_with_unanchored", None)
        hardened._dcoir_v16_original_build_review_body_with_unanchored = original
    if not callable(original):
        return

    def build_review_body_with_unanchored(*args: Any, **kwargs: Any) -> str:
        body = str(original(*args, **kwargs) or "").strip()
        metadata = dict(core.SELECTION_SUMMARY)
        covered = list(metadata.get("aggregate_covered_sentinels", []) or [])
        omitted = list(metadata.get("omitted_required_sentinels", []) or [])
        if not covered and not omitted:
            return body
        lines = [body, "", "---", "", "### DCOIR Review Required Coverage Ledger"]
        if covered:
            lines.extend(["", "**Aggregate-covered required findings:**"])
            lines.extend(f"- `{item.get('path')}:{item.get('line')}` `{item.get('kind')}` ({item.get('reason')})" for item in covered[:20])
        if omitted:
            lines.extend(["", "**Omitted required findings:**"])
            lines.extend(f"- `{item.get('path')}:{item.get('line')}` `{item.get('kind')}` ({item.get('reason')})" for item in omitted[:20])
        return "\n".join(line for line in lines if line is not None).strip()

    hardened.build_review_body_with_unanchored = build_review_body_with_unanchored


def _patch_detect(owner: Any, sentinel_owner: Any | None = None) -> None:
    original = getattr(owner, "_dcoir_required_v16_original_detect_risk_sentinels", None)
    if original is None:
        original = getattr(owner, "detect_risk_sentinels", None)
        owner._dcoir_required_v16_original_detect_risk_sentinels = original
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
        checker = getattr(owner, "is_comment_only_added_line", None) or getattr(sentinel_owner, "is_comment_only_added_line", None)
        for path, line, text in selection._iter_added_diff_lines(diff):
            if callable(checker) and checker(path, text):
                continue
            kind = _line_kind(path, text)
            if kind not in TRACKED_KINDS and kind not in OPTIONAL_PRESSURE_KINDS:
                continue
            key = (path, line, kind)
            if key in existing:
                continue
            title, body, _notes = _template_for_kind(kind)
            sentinels.append(risk_sentinel_type(path=path, line=line, label=title, detail=body, text=text))
            existing.add(key)
        return sentinels

    owner.detect_risk_sentinels = detect_risk_sentinels


def _patch_core_semantics() -> None:
    v12.REQUIRED_KINDS = set(getattr(v12, "REQUIRED_KINDS", set())) | CORE_REQUIRED_KINDS
    v13.REQUIRED_KINDS = set(getattr(v13, "REQUIRED_KINDS", set())) | CORE_REQUIRED_KINDS
    v13.TRACKED_HIGH_RISK_KINDS = set(getattr(v13, "TRACKED_HIGH_RISK_KINDS", set())) | TRACKED_KINDS
    v14.SELECTION_KIND_RANK.update({kind: _kind_rank(kind) for kind in CORE_REQUIRED_KINDS | {v10.YAML_TOKEN_TO_PR_URL}})
    v14.FAMILY_ORDER = ("yaml", "python", "powershell", "other", "typescript")
    v15.FAMILY_ORDER = ("yaml", "python", "powershell", "other", "typescript")
    v13._line_kind = _line_kind
    v13._sentinel_key = _sentinel_key
    v13._postable_key = _postable_key
    v13._coverage_key = _coverage_key
    v13._validation_for_key = _validation_for_key
    v13._spare_priority = _candidate_priority
    v14._family = _family
    v14._spare_priority = _candidate_priority
    core._sentinel_key = _sentinel_key
    core._postable_key = _postable_key
    core._coverage_key = _coverage_key
    core._spare_priority = _candidate_priority
    core._validation_for_key = _validation_for_key
    v11._line_kind = _line_kind
    v12._sentinel_key = _sentinel_key
    v12._postable_key = _postable_key
    v12._coverage_key = _coverage_key
    v12._spare_priority = _candidate_priority


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    _patch_core_semantics()
    _patch_detect(module, hardened)
    module.rank_findings_for_required_budget = lambda findings, config: sorted(
        [v5._normalize_comment_finding(item) for item in findings if isinstance(item, dict)],
        key=_candidate_priority,
    )[: max(0, int(getattr(config, "max_inline_comments", 12)))]
    if hardened is not None:
        _patch_detect(hardened)
        hardened.add_risk_sentinel_fallback_findings = lambda findings, risk_sentinels, config, unanchored_findings=None: _select_required_postable(
            hardened, findings, risk_sentinels, config, unanchored_findings
        )
        hardened.enforce_risk_sentinel_findings = lambda findings, risk_sentinels, config, unanchored_findings=None: findings.__setitem__(
            slice(None), _select_required_postable(hardened, findings, risk_sentinels, config, unanchored_findings)
        )
        _patch_review_body_overflow(hardened)
    if base is not None:
        _patch_final_rendering(base)
        v11._patch_progress_comment(base, hardened)
