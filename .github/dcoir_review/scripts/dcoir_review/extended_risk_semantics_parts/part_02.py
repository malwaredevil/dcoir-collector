def _sentinel_sort_key(sentinel: Any) -> tuple[int, str, int, str]:
    path, line, kind = _sentinel_key(sentinel)
    return _kind_rank(kind), path, line, str(getattr(sentinel, "text", "") or "")


def _balanced_required_order(targets: list[Any]) -> list[Any]:
    return sorted(targets, key=_sentinel_sort_key)


def _spare_priority(finding: dict[str, Any]) -> tuple[int, int, int, float, str, int]:
    path, line, kind = _postable_key(finding)
    family_rank = 0 if kind.startswith("yaml_") else 1 if kind.startswith("ps_") else 2 if kind.startswith("python_") else 5 if kind.startswith("k8s_") else 6 if kind.startswith("ts_") else 7
    if "/optional_" in path.lower() or path.rsplit("/", 1)[-1].startswith("optional_"):
        family_rank += 5
    return family_rank, _kind_rank(kind), core._severity_rank(finding), -core._confidence(finding), path, line


def _dedupe(findings: list[dict[str, Any]], expected: dict[tuple[str, int], set[str]]) -> tuple[list[dict[str, Any]], list[str]]:
    kept: dict[SentinelKey, dict[str, Any]] = {}
    order: list[SentinelKey] = []
    dropped: list[str] = []
    for raw in findings:
        item = v5._normalize_comment_finding(raw)
        key = _postable_key(item)
        if _semantic_mismatch(item, expected):
            rendered_as = ",".join(sorted(_text_kinds(key[0], "\n".join(str(item.get(name, "") or "") for name in ("title", "body")))))
            dropped.append(f"{key[0]}:{key[1]} reason=contradictory_render_kind expected={','.join(sorted(expected.get((key[0], key[1]), set())))} actual={key[2]} rendered_as={rendered_as}")
            continue
        if not key[2]:
            dropped.append(f"{key[0]}:{key[1]} reason=empty_kind")
            continue
        normalized = _integrity_finding(item, key)
        if key not in kept:
            kept[key] = normalized
            order.append(key)
        elif (core._severity_rank(normalized), -core._confidence(normalized)) < (core._severity_rank(kept[key]), -core._confidence(kept[key])):
            kept[key] = normalized
    return [kept[key] for key in order], dropped


def _deterministic_inline_comment(finding: dict[str, Any]) -> str:
    item = _integrity_finding(finding, _postable_key(finding), force_template=True)
    guidance = item.get("fix_guidance") if isinstance(item.get("fix_guidance"), dict) else {}
    lines = [f"### {item.get('title', 'Security-sensitive changed line')}", "", str(item.get("body", "") or "").strip()]
    notes = str(guidance.get("notes", "") or "").strip()
    validation = str(item.get("validation", "") or guidance.get("validation", "") or "").strip()
    if notes:
        lines.extend(["", "**Suggested fix:**", notes])
    if validation:
        lines.extend(["", "**Validation:**", f"`{validation}`"])
    return "\n".join(lines).strip()


def _rendered_comment_has_problem(rendered: str, finding: dict[str, Any]) -> bool:
    path, _line, kind = _postable_key(finding)
    if "Reviewed with " in rendered or "_Reviewed with " in rendered:
        return True
    if "<<" in rendered or "assert text.strip()" in rendered or rendered.count("```") % 2:
        return True
    return bool({candidate for candidate in _text_kinds(path, rendered) if candidate != kind and candidate in TRACKED_HIGH_RISK_KINDS})


def _sanitize_rendered_inline_comment(rendered: Any, finding: dict[str, Any]) -> str:
    text = str(_scrub_model_footer(rendered or "")).strip()
    if not text or _rendered_comment_has_problem(text, finding):
        return _deterministic_inline_comment(finding)
    return text


def _overflow_section(metadata: dict[str, Any]) -> str:
    omitted_required = list(metadata.get("omitted_required_sentinels", []) or [])
    optional = list(metadata.get("omitted_optional_high_risk_sentinels", []) or [])
    detector = list(metadata.get("detector_only_high_risk_overflow", []) or [])
    if not omitted_required and not optional and not detector:
        return ""
    def line(prefix: str, item: dict[str, Any]) -> str:
        return f"- {prefix}: `{item.get('path')}:{item.get('line')}` `{item.get('kind')}` ({item.get('reason', 'overflow')})"
    lines = ["", "---", "", "### DCOIR Review Overflow", "The inline review comment budget was reached. The findings below were not posted inline and should still be reviewed."]
    if omitted_required:
        lines.extend(["", "**Omitted hard-required findings:**"])
        lines.extend(line("Required", item) for item in omitted_required[:12])
    if optional:
        lines.extend(["", "**Omitted optional/high-risk findings:**"])
        lines.extend(line("High risk", item) for item in optional[:8])
    if detector:
        lines.extend(["", "**Detected high-risk findings outside selected sentinel budget:**"])
        lines.extend(line("Detected", item) for item in detector[:8])
    return "\n".join(lines).strip()


def _append_overflow_to_review_body(body: Any) -> str:
    text = str(_scrub_model_footer(body or "")).strip()
    section = _overflow_section(dict(core.SELECTION_SUMMARY))
    if not section or "### DCOIR Review Overflow" in text:
        return text
    return f"{text}\n\n{section}".strip()


def _sentinel_record(sentinel: Any, reason: str, required: set[SentinelKey], selected: set[SentinelKey], limit: int) -> dict[str, Any]:
    key = _sentinel_key(sentinel)
    coverage = _coverage_key(key)
    if reason == "auto":
        reason = "duplicate_covered" if coverage in selected else "omitted_due_to_inline_budget" if len(selected) >= limit else "not_selected"
    return {"path": key[0], "line": key[1], "kind": key[2], "reason": reason, "label": str(getattr(sentinel, "label", "") or ""), "detail": str(getattr(sentinel, "detail", "") or "")[:240], "text": str(getattr(sentinel, "text", "") or "")[:240]}


def _augment_metadata(selected: list[dict[str, Any]], findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    limit = max(0, int(getattr(config, "max_inline_comments", 12)))
    required_targets = list(v12._coalesce_required(v12._required_sentinels(None, risk_sentinels))[0])
    required_cov = {_coverage_key(_sentinel_key(item)) for item in required_targets}
    selected_keys = [_postable_key(item) for item in selected]
    selected_cov = {_coverage_key(key) for key in selected_keys}
    omitted_required = [_sentinel_record(item, "auto", required_cov, selected_cov, limit) for item in required_targets if _coverage_key(_sentinel_key(item)) not in selected_cov]
    optional = [_sentinel_record(item, "auto", required_cov, selected_cov, limit) for item in risk_sentinels if _coverage_key(_sentinel_key(item)) not in selected_cov and _coverage_key(_sentinel_key(item)) not in required_cov and _sentinel_key(item)[2] in TRACKED_HIGH_RISK_KINDS]
    detector: list[dict[str, Any]] = []
    seen: set[SentinelKey] = set()
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        key = _postable_key(finding)
        coverage = _coverage_key(key)
        if key[2] in TRACKED_HIGH_RISK_KINDS and coverage not in selected_cov and coverage not in required_cov and key not in seen:
            detector.append({"path": key[0], "line": key[1], "kind": key[2], "reason": "detected_not_selected", "title": str(finding.get("title", "") or "")[:160]})
            seen.add(key)
    metadata = dict(metadata)
    metadata.pop("required_ledger_keys", None)
    metadata.pop("required_ledger_accounted_count", None)
    metadata.update({
        "version": VERSION,
        "selected_keys": [f"{path}:{line} {kind}" for path, line, kind in selected_keys],
        "final_postable_count": len(selected),
        "inline_limit": limit,
        "posted_required_sentinels": [f"{path}:{line} {kind}" for path, line, kind in selected_keys if _coverage_key((path, line, kind)) in required_cov],
        "omitted_required_sentinels": omitted_required[:80],
        "omitted_optional_high_risk_sentinels": optional[:80],
        "detector_only_high_risk_overflow": detector[:80],
        "overflow_required_count": len(omitted_required),
        "overflow_optional_high_risk_count": len(optional),
        "overflow_detector_high_risk_count": len(detector),
        "partial_overflow": bool(omitted_required or optional or detector),
        "required_ledger_schema": "v13_split_posted_omitted_duplicate_suppressed",
        "final_invalid_selected_keys": [],
        "final_uncovered": [f"{item['path']}:{item['line']} {item['kind']}" for item in omitted_required],
    })
    return metadata
