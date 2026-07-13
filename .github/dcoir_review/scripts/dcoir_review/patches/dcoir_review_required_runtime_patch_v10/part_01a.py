

def _fallback_for_sentinel(hardened: Any, sentinel: Any, config: Any) -> dict[str, Any]:
    key = core._sentinel_key(sentinel)
    path, line, kind = key
    line_text = str(getattr(sentinel, "text", "") or "")
    if kind == YAML_TOKEN_TO_PR_URL:
        fallback = {
            "_dcoir_v10_known_fallback": True,
            "title": "Workflow sends GitHub token to PR-controlled URL",
            "severity": "critical",
            "confidence": 0.99,
            "path": path,
            "line": line,
            "body": (
                "This line sends an authorization header or GitHub token to a URL taken from pull request body text. "
                "Pull request body content is attacker-controlled; keep token-bearing requests on trusted, allowlisted destinations."
            ),
            "suggested_replacement": "",
            "validation": _validation_for_token_to_pr_url(path),
            "fix_guidance": {
                "language": "yaml",
                "notes": "Use a trusted allowlisted endpoint or remove the token-bearing request from the pull request workflow.",
                "validation": _validation_for_token_to_pr_url(path),
            },
        }
    else:
        fallback = selection._fallback_for_sentinel(hardened, sentinel, config)
    fallback["_risk_sentinel_key"] = [path, line, kind]
    fallback["_risk_sentinel_kind"] = kind
    fallback["_anchored_line_text"] = line_text
    return fallback


def _scrub_shell_pipe_wording(finding: dict[str, Any]) -> None:
    if core._postable_key(finding)[2] != v4.YAML_SHELL_PIPE:
        return
    anchored = str(finding.get("_anchored_line_text", "") or "")
    if "https://" not in anchored.lower():
        return
    replacement = "network-fetched, unverified"
    for field in ("title", "body", "description", "suggested_replacement", "validation"):
        value = finding.get(field)
        if isinstance(value, str):
            finding[field] = re.sub(r"\bplain\s+http\b", replacement, value, flags=re.I)
    guidance = finding.get("fix_guidance")
    if isinstance(guidance, dict):
        for field, value in list(guidance.items()):
            if isinstance(value, str):
                guidance[field] = re.sub(r"\bplain\s+http\b", replacement, value, flags=re.I)


def _select_required_postable(
    hardened: Any,
    findings: list[dict[str, Any]],
    risk_sentinels: list[Any],
    config: Any,
    unanchored_findings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    del unanchored_findings
    limit = max(0, int(getattr(config, "max_inline_comments", 12)))
    required_all = core._required_sentinels(hardened, risk_sentinels)
    required_targets, duplicate_covered = _coalesce_required(required_all)
    expected = core._expected_by_line(hardened, risk_sentinels)
    required_coverage = {_coverage_key(core._sentinel_key(item)) for item in required_targets}

    raw = [item for item in findings if isinstance(item, dict)]
    candidates, dropped = core._dedupe(raw, expected)
    by_key = {core._postable_key(item): item for item in candidates}

    for sentinel in required_targets:
        key = core._sentinel_key(sentinel)
        if key not in by_key:
            fallback = _fallback_for_sentinel(hardened, sentinel, config)
            normalized = dict(fallback) if fallback.get("_dcoir_v10_known_fallback") else v5._normalize_comment_finding(fallback)
            by_key[key] = normalized
            candidates.append(normalized)

    selected: list[dict[str, Any]] = []
    selected_coverage: set[SentinelKey] = set()

    for sentinel in sorted(required_targets, key=_required_sort_key):
        key = core._sentinel_key(sentinel)
        coverage = _coverage_key(key)
        if coverage in selected_coverage or len(selected) >= limit:
            continue
        item = by_key.get(key)
        if item:
            selected.append(item)
            selected_coverage.add(coverage)

    for item in sorted(candidates, key=core._spare_priority):
        key = core._postable_key(item)
        coverage = _coverage_key(key)
        if len(selected) >= limit:
            break
        if coverage in selected_coverage or not key[2]:
            continue
        selected.append(item)
        selected_coverage.add(coverage)

    selected = selected[:limit]
    core._rewrite_validation(selected)
    for item in selected:
        path, line, kind = core._postable_key(item)
        validation = _validation_for_key(kind, path, line)
        if validation:
            item["validation"] = validation
            guidance = item.get("fix_guidance")
            if isinstance(guidance, dict):
                guidance["validation"] = validation
    for item in selected:
        _scrub_shell_pipe_wording(item)

    final_invalid = [core._key_text(core._postable_key(item)) for item in selected if core._semantic_mismatch(item, expected)]
    selected_keys = [core._postable_key(item) for item in selected]
    selected_coverage = {_coverage_key(key) for key in selected_keys}
    omitted = [
        _sentinel_summary_record(item, required_coverage, selected_coverage, limit)
        for item in risk_sentinels
        if _coverage_key(core._sentinel_key(item)) not in selected_coverage
    ]
    omitted_required = [item for item in omitted if item.get("priority_bucket") == "hard-required"]
    omitted_high_risk = [
        item
        for item in omitted
        if item.get("priority_bucket") in {"hard-required", "required-adjacent", "high-risk"}
    ]
    metadata = {
        "hard_required_count": len(required_all),
        "coalesced_required_count": len(required_targets),
        "final_postable_count": len(selected),
        "inline_limit": limit,
        "partial_overflow": bool(omitted_high_risk),
        "overflow_required_count": len(omitted_required),
        "overflow_high_risk_count": len(omitted_high_risk),
        "selected_keys": [core._key_text(key) for key in selected_keys],
        "spare_budget_selected": [
            core._key_text(key)
            for key in selected_keys
            if _coverage_key(key) not in required_coverage
        ],
        "duplicate_covered_sentinels": duplicate_covered[:80],
        "dropped_invalid_or_duplicate_candidates": dropped[:80],
        "final_invalid_selected_keys": final_invalid,
        "final_uncovered": [f"{item.get('path')}:{item.get('line')} {item.get('kind')}" for item in omitted_required],
        "omitted_sentinel_count": len(omitted),
        "omitted_required_count": len(omitted_required),
        "omitted_sentinels": omitted[:80],
    }
    core.SELECTION_SUMMARY.clear()
    core.SELECTION_SUMMARY.update(metadata)
    writer = getattr(hardened, "write_debug_json_artifact_safely", None)
    if callable(writer):
        writer(config, "metadata/required-v10-final-selection.json", metadata)
        writer(config, "metadata/required-v9-final-selection.json", metadata)

    if final_invalid:
        raise getattr(hardened, "ReviewQualityError", RuntimeError)(
            "DCOIR Review quality failure: final selected findings have semantic mismatches: " + "; ".join(final_invalid)
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
        key=core._spare_priority,
    )[: max(0, int(getattr(config, "max_inline_comments", 12)))]
