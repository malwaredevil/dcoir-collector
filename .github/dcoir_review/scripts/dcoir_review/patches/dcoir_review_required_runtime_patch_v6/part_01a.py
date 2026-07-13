

def _validate_reviewed_prompt(original_prompt: str, candidate: str, addendum: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if candidate == original_prompt:
        return True, reasons
    if not candidate.startswith(original_prompt):
        reasons.append("reviewed prompt did not preserve the original prompt as an immutable prefix")
    if FORBIDDEN_ADDENDUM_RE.search(addendum):
        reasons.append("supplemental instructions attempted to alter protected evidence or constraints")
    for anchor in _extract_sentinel_anchors(original_prompt):
        if anchor not in candidate:
            reasons.append(f"missing required sentinel anchor: {anchor}")
    for provenance in _extract_env_provenance(original_prompt):
        if provenance not in candidate:
            reasons.append(f"missing env-token provenance: {provenance}")
    if "findings" in original_prompt and "findings" not in candidate:
        reasons.append("structured findings contract was not preserved")
    return not reasons, reasons


def _write_prompt_review_debug(
    hardened: Any,
    config: Any,
    prompt_kind: str,
    original_prompt: str,
    candidate_prompt: str,
    metadata: dict[str, Any],
) -> None:
    sequence = _next_prompt_review_id()
    digest = _sha12(original_prompt)
    safe_kind = re.sub(r"[^A-Za-z0-9_.-]+", "-", prompt_kind)[:40] or "prompt"
    stem = f"prompt-review/{sequence:02d}-{safe_kind}-{digest}"
    hardened.write_debug_text_artifact_safely(config, f"prompts/{stem}-original.txt", original_prompt)
    if candidate_prompt != original_prompt:
        hardened.write_debug_text_artifact_safely(config, f"prompts/{stem}-reviewed.txt", candidate_prompt)
    hardened.write_debug_json_artifact_safely(config, f"metadata/{stem}.json", metadata)


def _review_prompt_once(original_prompt: str, config: Any, hardened: Any, base: Any) -> str:
    prompt_kind = _prompt_kind(original_prompt)
    cache_key = f"{prompt_kind}:{_sha12(original_prompt)}"
    if cache_key in _prompt_review_cache:
        return _prompt_review_cache[cache_key][0]
    metadata: dict[str, Any] = {
        "prompt_kind": prompt_kind,
        "original_chars": len(original_prompt),
        "model": PROMPT_REVIEW_MODEL,
        "accepted": False,
        "fallback_to_original": True,
        "validation_reasons": [],
    }
    candidate = original_prompt
    try:
        review, model_used, service_tier = _request_prompt_review(original_prompt, prompt_kind, config, hardened, base)
        metadata["model_used"] = model_used
        metadata["service_tier"] = service_tier
        metadata["use_original"] = bool(review.get("use_original", False))
        metadata["risk_notes"] = review.get("risk_notes", [])
        metadata["preserved_constraints"] = review.get("preserved_constraints", [])
        metadata["rejected_changes"] = review.get("rejected_changes", [])
        addendum = "" if bool(review.get("use_original", False)) else _clean_addendum(review.get("supplemental_instructions", ""))
        candidate = _candidate_with_addendum(original_prompt, addendum, config)
        ok, reasons = _validate_reviewed_prompt(original_prompt, candidate, addendum)
        metadata["validation_reasons"] = reasons
        metadata["addendum_chars"] = len(addendum)
        if ok:
            metadata["accepted"] = candidate != original_prompt
            metadata["fallback_to_original"] = candidate == original_prompt
        else:
            candidate = original_prompt
    except Exception as exc:
        metadata["error"] = str(exc)[:500]
        candidate = original_prompt
    metadata["reviewed_chars"] = len(candidate)
    _write_prompt_review_debug(hardened, config, prompt_kind, original_prompt, candidate, metadata)
    _prompt_review_cache[cache_key] = (candidate, metadata)
    return candidate


def _patch_sanitize_text(base: Any) -> None:
    original = getattr(base, "_dcoir_required_v6_original_sanitize_text", None)
    if original is None:
        original = getattr(base, "sanitize_text", None)
        base._dcoir_required_v6_original_sanitize_text = original
    if not callable(original):
        return

    def required_v6_sanitize_text(text: str, config: Any) -> str:
        protected_text, protected_values = _protect_env_provenance(str(text or ""))
        cleaned = original(protected_text, config)
        return _restore_env_provenance(cleaned, protected_values)

    base.sanitize_text = required_v6_sanitize_text


def _patch_yaml_metadata_priority() -> None:
    original_v4_line_kind = getattr(v4, "_dcoir_required_v6_original_line_kind", None)
    if original_v4_line_kind is None:
        original_v4_line_kind = v4._line_kind
        v4._dcoir_required_v6_original_line_kind = original_v4_line_kind

    def required_v6_v4_line_kind(path: str, text: str) -> str:
        suffix = Path(str(path or "").lower()).suffix
        if suffix in {".yml", ".yaml"} and v4._metadata_shell_line(str(text or "")):
            return v4.YAML_METADATA_SHELL
        return original_v4_line_kind(path, text)

    v4._line_kind = required_v6_v4_line_kind


def _patch_merge_summary(hardened: Any) -> None:
    original = getattr(hardened, "_dcoir_required_v6_original_merge_review_results", None)
    if original is None:
        original = getattr(hardened, "merge_review_results", None)
        hardened._dcoir_required_v6_original_merge_review_results = original
    if not callable(original):
        return

    def required_v6_merge_review_results(initial_result: dict[str, Any], retry_result: dict[str, Any]) -> dict[str, Any]:
        merged = original(initial_result, retry_result)
        retry_findings = hardened.result_findings(retry_result) if hasattr(hardened, "result_findings") else []
        retry_summary = str(retry_result.get("summary", "") if isinstance(retry_result, dict) else "")
        if not retry_findings and callable(getattr(hardened, "summary_suggests_problem", None)) and hardened.summary_suggests_problem(retry_summary):
            initial_summary = str(initial_result.get("summary", "") if isinstance(initial_result, dict) else "").strip()
            merged["summary"] = initial_summary or "Quality retry returned summary-only concerns; deterministic required fallback coverage was applied."
            merged["_dcoir_summary_only_retry_rejected"] = True
        return merged

    hardened.merge_review_results = required_v6_merge_review_results


def _patch_required_coverage_debug(hardened: Any) -> None:
    original = getattr(hardened, "_dcoir_required_v6_original_add_risk_sentinel_fallback_findings", None)
    if original is None:
        original = getattr(hardened, "add_risk_sentinel_fallback_findings", None)
        hardened._dcoir_required_v6_original_add_risk_sentinel_fallback_findings = original
    if not callable(original):
        return

    def required_v6_add_risk_sentinel_fallback_findings(findings: list[dict[str, Any]], risk_sentinels: list[Any], config: Any, unanchored_findings: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        required = list(hardened.required_risk_sentinels(risk_sentinels)) if callable(getattr(hardened, "required_risk_sentinels", None)) else []
        before_covered = [
            sentinel for sentinel in required if any(hardened.finding_covers_risk_sentinel(finding, sentinel) for finding in [*findings, *(unanchored_findings or [])])
        ] if callable(getattr(hardened, "finding_covers_risk_sentinel", None)) else []
        result = original(findings, risk_sentinels, config, unanchored_findings)
        after_covered = [
            sentinel for sentinel in required if any(hardened.finding_covers_risk_sentinel(finding, sentinel) for finding in result)
        ] if callable(getattr(hardened, "finding_covers_risk_sentinel", None)) else []
        metadata = {
            "hard_required_count": len(required),
            "covered_before_count": len(before_covered),
            "covered_after_count": len(after_covered),
            "fallback_inserted_count": max(0, len(result) - len(findings)),
            "input_finding_count": len(findings),
            "postable_finding_count": len(result),
            "required_digest": [f"{getattr(item, 'path', '')}:{getattr(item, 'line', '')} {v5._sentinel_kind(item)}" for item in required],
            "covered_after_digest": [f"{getattr(item, 'path', '')}:{getattr(item, 'line', '')} {v5._sentinel_kind(item)}" for item in after_covered],
        }
        hardened.write_debug_json_artifact_safely(config, "metadata/required-v6-coverage.json", metadata)
        return result

    hardened.add_risk_sentinel_fallback_findings = required_v6_add_risk_sentinel_fallback_findings


def _patch_openrouter_prompt_review(hardened: Any, base: Any) -> None:
    original = getattr(hardened, "_dcoir_required_v6_original_openrouter_request_once", None)
    if original is None:
        original = getattr(hardened, "openrouter_request_once", None)
        hardened._dcoir_required_v6_original_openrouter_request_once = original
    if not callable(original):
        return

    def required_v6_openrouter_request_once(prompt: str, schema: dict[str, Any], config: Any, ignored_providers: list[str], model: str) -> tuple[dict[str, Any], str, str]:
        reviewed_prompt = prompt
        if _should_review_model(model, config):
            reviewed_prompt = _review_prompt_once(prompt, config, hardened, base)
        return original(reviewed_prompt, schema, config, ignored_providers, model)

    hardened.openrouter_request_once = required_v6_openrouter_request_once
