

def _select_required_postable(
    hardened: Any,
    original_rank: Any,
    original_covers: Any,
    original_fallback: Any,
    findings: list[dict[str, Any]],
    risk_sentinels: list[Any],
    config: Any,
    unanchored_findings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    required = list(hardened.required_risk_sentinels(risk_sentinels))
    required_keys = [_sentinel_key(sentinel) for sentinel in required]
    inline_limit = max(0, int(getattr(config, "max_inline_comments", 12)))
    if len(required) > inline_limit:
        metadata = {
            "error": "required_sentinel_count_exceeds_inline_budget",
            "hard_required_count": len(required),
            "inline_limit": inline_limit,
            "required_keys": [_key_text(key) for key in required_keys],
        }
        hardened.write_debug_json_artifact_safely(config, "metadata/required-v7-coverage.json", metadata)
        raise getattr(hardened, "ReviewQualityError", RuntimeError)(
            f"DCOIR Review quality failure: {len(required)} required changed-line signals exceed inline budget {inline_limit}."
        )

    normalized = _dedupe_postable([v5._normalize_comment_finding(finding) for finding in findings if isinstance(finding, dict)])
    unanchored = _dedupe_postable([v5._normalize_comment_finding(finding) for finding in (unanchored_findings or []) if isinstance(finding, dict)])
    coverage_pool = [*normalized, *unanchored]
    selected_required: list[dict[str, Any]] = []
    fallback_keys_added: list[SentinelKey] = []
    covered_before: list[SentinelKey] = []
    uncovered_before: list[SentinelKey] = []

    for sentinel in required:
        matches = [finding for finding in coverage_pool if _covers_required_sentinel(finding, sentinel, original_covers)]
        if matches:
            covered_before.append(_sentinel_key(sentinel))
            selected_required.append(_annotate_required_finding(matches[0], sentinel))
            continue
        uncovered_before.append(_sentinel_key(sentinel))
        fallback = _required_fallback(sentinel, config, original_fallback)
        if fallback:
            fallback_keys_added.append(_sentinel_key(sentinel))
            selected_required.append(fallback)

    selected_required = _dedupe_postable(selected_required)
    required_selected_keys = {_postable_key(finding) for finding in selected_required}
    optional_candidates = [finding for finding in normalized if _postable_key(finding) not in required_selected_keys]
    ranked_optional = v5._rank_findings(None, hardened, original_rank, optional_candidates, config)
    final = [*selected_required]
    for finding in ranked_optional:
        if len(final) >= inline_limit:
            break
        key = _postable_key(finding)
        if key in {_postable_key(item) for item in final}:
            continue
        final.append(v5._normalize_comment_finding(finding))
    final = _dedupe_postable(final)[:inline_limit]
    final_uncovered = [key for key, sentinel in zip(required_keys, required) if not any(_covers_required_sentinel(finding, sentinel, original_covers) for finding in final)]
    covered_after = [key for key in required_keys if key not in final_uncovered]
    metadata = {
        "hard_required_count": len(required),
        "input_finding_count": len(findings),
        "unanchored_finding_count": len(unanchored_findings or []),
        "final_postable_count": len(final),
        "covered_before": [_key_text(key) for key in covered_before],
        "uncovered_before": [_key_text(key) for key in uncovered_before],
        "fallback_keys_added": [_key_text(key) for key in fallback_keys_added],
        "covered_after_inline": [_key_text(key) for key in covered_after],
        "final_uncovered": [_key_text(key) for key in final_uncovered],
    }
    hardened.write_debug_json_artifact_safely(config, "metadata/required-v7-coverage.json", metadata)
    return final


def _patch_required_selection(module: Any, hardened: Any) -> None:
    original_rank = getattr(module, "_dcoir_required_v7_original_rank_findings_for_required_budget", None)
    if original_rank is None:
        original_rank = getattr(module, "rank_findings_for_required_budget", None)
        module._dcoir_required_v7_original_rank_findings_for_required_budget = original_rank
    original_covers = getattr(hardened, "_dcoir_required_v7_original_finding_covers_risk_sentinel", None)
    if original_covers is None:
        original_covers = getattr(hardened, "finding_covers_risk_sentinel", None)
        hardened._dcoir_required_v7_original_finding_covers_risk_sentinel = original_covers
    original_fallback = getattr(hardened, "_dcoir_required_v7_original_risk_sentinel_fallback_finding", None)
    if original_fallback is None:
        original_fallback = getattr(hardened, "risk_sentinel_fallback_finding", None)
        hardened._dcoir_required_v7_original_risk_sentinel_fallback_finding = original_fallback

    def required_v7_add(findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        return _select_required_postable(hardened, original_rank, original_covers, original_fallback, findings, risk_sentinels, config, unanchored_findings)

    def required_v7_enforce(findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> None:
        findings[:] = required_v7_add(findings, risk_sentinels, config, unanchored_findings)
        required = list(hardened.required_risk_sentinels(risk_sentinels))
        final_uncovered = [sentinel for sentinel in required if not any(_covers_required_sentinel(finding, sentinel, original_covers) for finding in findings)]
        if final_uncovered:
            digest = "; ".join(f"{getattr(sentinel, 'path', '')}:{getattr(sentinel, 'line', '')} {v5._sentinel_kind(sentinel)}" for sentinel in final_uncovered)
            raise getattr(hardened, "ReviewQualityError", RuntimeError)(
                f"DCOIR Review quality failure: required changed-line signals remain uncovered after v7 final selection: {digest}."
            )

    hardened.finding_covers_risk_sentinel = lambda finding, sentinel: _covers_required_sentinel(finding, sentinel, original_covers)
    hardened.add_risk_sentinel_fallback_findings = required_v7_add
    hardened.enforce_risk_sentinel_findings = required_v7_enforce
    hardened.finding_merge_key = lambda finding: _postable_key(finding)
    module.finding_dedupe_key = lambda finding: (*_postable_key(finding), v5._normalize(finding.get("_anchored_line_text", "")))
    module.dedupe_findings_for_ranking = lambda findings: _dedupe_postable([v5._normalize_comment_finding(finding) for finding in findings])
    module.rank_findings_for_required_budget = lambda findings, config: _dedupe_postable(v5._rank_findings(module, hardened, original_rank, findings, config))


def _safe_auth_line(line: str) -> bool:
    if not ("bearer" in line.lower() or "authorization" in line.lower()):
        return False
    if STATIC_BEARER_RE.search(line) and not VARIABLE_BEARER_RE.search(line):
        return False
    return VARIABLE_BEARER_RE.search(line) is not None


def _protect_auth_lines(text: str) -> tuple[str, list[str]]:
    protected: list[str] = []

    def stash(match: re.Match[str]) -> str:
        value = match.group(0)
        if not _safe_auth_line(value):
            return value
        protected.append(value)
        return f"__DCOIR_V7_SAFE_AUTH_LINE_{len(protected) - 1}__"

    return SAFE_AUTH_LINE_RE.sub(stash, str(text or "")), protected


def _restore_auth_lines(text: str, protected: list[str]) -> str:
    result = str(text or "")
    for index, value in enumerate(protected):
        result = result.replace(f"__DCOIR_V7_SAFE_AUTH_LINE_{index}__", value)
    return result


def _patch_sanitize_text(base: Any) -> None:
    original = getattr(base, "_dcoir_required_v7_original_sanitize_text", None)
    if original is None:
        original = getattr(base, "sanitize_text", None)
        base._dcoir_required_v7_original_sanitize_text = original
    if not callable(original):
        return

    def required_v7_sanitize_text(text: str, config: Any) -> str:
        protected_text, protected_values = _protect_auth_lines(str(text or ""))
        cleaned = original(protected_text, config)
        return _restore_auth_lines(cleaned, protected_values)

    base.sanitize_text = required_v7_sanitize_text


def _patch_prompt_review_debug() -> None:
    original = getattr(v6, "_dcoir_required_v7_original_write_prompt_review_debug", None)
    if original is None:
        original = getattr(v6, "_write_prompt_review_debug", None)
        v6._dcoir_required_v7_original_write_prompt_review_debug = original
    if not callable(original):
        return

    def required_v7_write_prompt_review_debug(hardened: Any, config: Any, prompt_kind: str, original_prompt: str, candidate_prompt: str, metadata: dict[str, Any]) -> None:
        if candidate_prompt == original_prompt and metadata.get("addendum_chars") and not metadata.get("validation_reasons"):
            metadata.setdefault("fallback_reason", "prompt_budget_exhausted_or_no_room_for_addendum")
        original(hardened, config, prompt_kind, original_prompt, candidate_prompt, metadata)

    v6._write_prompt_review_debug = required_v7_write_prompt_review_debug


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    if base is not None:
        _patch_sanitize_text(base)
    _patch_prompt_review_debug()
    if hardened is not None:
        _patch_required_selection(module, hardened)
