

def test_overflow_sentinel_is_reported_when_budget_is_full() -> None:
    required = pr332_sentinels()
    extra = sentinel(POWERSHELL, 30, "Invoke-Expression $Arguments")
    extra.label = "PowerShell dynamic execution"
    extra.detail = "Invoke-Expression executes caller-controlled text"
    hardened = FakeHardenedRequiredSubset(required)
    result = v9._select_required_postable(hardened, pr332_findings(), [*required, extra], Config())
    metadata = hardened.debug["metadata/required-v9-final-selection.json"]
    assert len(result) == 12
    assert metadata["omitted_sentinel_count"] == 1
    omitted = metadata["omitted_sentinels"][0]
    assert omitted["path"] == POWERSHELL
    assert omitted["line"] == 30
    assert omitted["kind"] == v9.PS_DYNAMIC_EXEC
    assert omitted["reason"] == "omitted_due_to_inline_budget"
    assert omitted["priority_bucket"] == "required-adjacent"
    assert v9.SELECTION_SUMMARY["omitted_sentinel_count"] == 1


def test_python_env_assignment_sentinel_keeps_env_token_kind() -> None:
    env_sentinel = sentinel(PYTHON, 22, '    api_token = os.environ["DCOIR_TOKEN"]')
    env_sentinel.label = "Environment token forwarded to request-controlled callback"
    env_sentinel.detail = "The env token is later sent as a Bearer authorization header to a callback URL."
    finding = {
        "path": PYTHON,
        "line": 22,
        "title": "Environment token forwarded to request-controlled callback",
        "body": "Environment token read from os.environ and forwarded to request-controlled callback using a Bearer Authorization header.",
        "severity": "critical",
        "confidence": 0.99,
        "_anchored_line_text": '    api_token = os.environ["DCOIR_TOKEN"]',
    }
    hardened = FakeHardened()
    result = v9._select_required_postable(hardened, [finding], [env_sentinel], Config())
    assert [v9._postable_key(item) for item in result] == [(PYTHON, 22, v9.v5.PYTHON_ENV_TOKEN)]
    metadata = hardened.debug["metadata/required-v9-final-selection.json"]
    assert metadata["final_invalid_selected_keys"] == []
    assert metadata["final_uncovered"] == []


def test_inline_model_footer_is_removed() -> None:
    body = "**Finding**\n\nBody.\n\n_Reviewed with deepseek/deepseek-v4-pro-20260423._"
    assert "Reviewed with" not in v9._strip_footer(body)
    dotted = "**Finding**\n\nReviewed with google/gemini-2.5-flash-lite."
    assert "Reviewed with" not in v9._strip_footer(dotted)
    stamped = "**Finding**\n\nBody.\n\n<sub>DCOIR Review</sub>"
    assert "DCOIR Review" not in v9._strip_footer(stamped)
    stacked = "**Finding**\n\nBody.\n\n_Reviewed with openrouter/pareto._\n\n<sub>DCOIR Review</sub>"
    stripped = v9._strip_footer(stacked)
    assert "Reviewed with" not in stripped
    assert "DCOIR Review" not in stripped


def test_inline_comment_normalization_removes_prefix_and_validation_alias() -> None:
    body = (
        "**HIGH: Environment token forwarded to request-controlled callback**\n\n"
        "Finding body.\n\n"
        "**Validation expected after fix:**\n"
        "```bash\n"
        "pwsh -NoProfile -Command 'Get-Content file.ps1'\n"
        "```\n\n"
        "<sub>DCOIR Review</sub>"
    )
    normalized = v9._normalize_inline_comment(body, {})
    assert normalized.startswith("**Environment token forwarded to request-controlled callback**")
    assert "HIGH:" not in normalized
    assert "**Validation:**" in normalized
    assert "Validation expected after fix" not in normalized
    assert "DCOIR Review" not in normalized
    plain = "CRITICAL: Unsafe pickle deserialization\n\nValidation expected after fix:\npython3 -m py_compile probe.py"
    normalized_plain = v9._normalize_inline_comment(plain, {})
    assert normalized_plain.startswith("Unsafe pickle deserialization")
    assert "CRITICAL:" not in normalized_plain
    assert "**Validation:**" in normalized_plain
    assert "Validation expected after fix" not in normalized_plain


def test_invoke_expression_line_is_dynamic_exec_kind() -> None:
    assert v9._line_kind(POWERSHELL, "Invoke-Expression $Arguments") == v9.PS_DYNAMIC_EXEC


def test_module_level_pickle_detector_is_patched() -> None:
    owner = FakeDetectorOwner()
    diff = (
        "diff --git a/probe.py b/probe.py\n"
        "--- a/probe.py\n"
        "+++ b/probe.py\n"
        "@@ -0,0 +1 @@\n"
        "+state = pickle.loads(raw_state)\n"
    )
    v9._patch_pickle_sentinels(owner)
    sentinels = owner.detect_risk_sentinels(diff)
    assert owner.calls == 1
    assert len(sentinels) == 1
    assert v9._sentinel_key(sentinels[0]) == ("probe.py", 1, v9.PYTHON_PICKLE_LOAD)


def test_yaml_safe_load_identifier_normalization_uses_anchored_arg() -> None:
    finding = {
        "path": PYTHON,
        "line": 10,
        "title": "Unsafe YAML deserialization",
        "body": "yaml.load with yaml.Loader",
        "_anchored_line_text": "    return yaml.load(text, Loader=yaml.Loader)",
    }
    body = "Use yaml.safe_load(profile_text) or yaml.load(profile_text, Loader=yaml.SafeLoader)."
    normalized = v9._normalize_yaml_identifier(body, finding)
    assert "yaml.safe_load(text)" in normalized
    assert "yaml.load(text, Loader=yaml.SafeLoader)" in normalized
    assert "profile_text" not in normalized


def test_powershell_validation_is_quote_safe() -> None:
    validation = v9._validation_for_key(v9.v5.PS_ENV_TOKEN, POWERSHELL, 15)
    assert "$p = '" in validation
    assert '$p = "' not in validation
    assert "'(?i)\\$env:DCOIR_TOKEN'" in validation
    dollar_path_validation = v9._validation_for_key(v9.v5.PS_ENV_TOKEN, "chatgpt_staging/$bad/path.ps1", 15)
    assert "$bad" in dollar_path_validation
    assert '$p = "chatgpt_staging/$bad/path.ps1"' not in dollar_path_validation
    assert "chatgpt_staging/$bad/path.ps1" in dollar_path_validation


def test_prompt_review_accounting_requires_fresh_preflight() -> None:
    v9.PROMPT_REVIEW_CALLS[:] = []
    v9.PROMPT_REVIEW_EVENTS[:] = []
    v9.PARETO_CALL_EVENTS[:] = []
    prompt = "Per-file detector pass"
    v9._record_target_call(prompt, "openrouter/pareto-code", 0, 0)
    assert "missing OpenRouter Auto" in v9._prompt_review_problem()
    v9.PROMPT_REVIEW_FAILURES[:] = []
    v9.PARETO_CALL_EVENTS[:] = []
    v9._record_prompt_review_call(prompt, prompt)
    v9._record_prompt_review_event("per-file-detector", {"accepted": True, "addendum_chars": 5}, prompt)
    before_calls = len(v9.PROMPT_REVIEW_CALLS)
    before_events = len(v9.PROMPT_REVIEW_EVENTS)
    v9._record_target_call(prompt, "openrouter/pareto-code", before_calls, before_events)
    assert v9._prompt_review_problem() == ""
    assert v9.PARETO_CALL_EVENTS[-1]["prompt_review_call_recorded"]
    assert v9.PARETO_CALL_EVENTS[-1]["prompt_review_debug_event_recorded"]


def test_prompt_review_artifact_refreshes_after_pareto_call() -> None:
    v9.PROMPT_REVIEW_CALLS[:] = []
    v9.PROMPT_REVIEW_EVENTS[:] = []
    v9.PROMPT_REVIEW_FAILURES[:] = []
    v9.PARETO_CALL_EVENTS[:] = []
    prompt = "Per-file detector pass"
    hardened = FakeHardened()

    def original(prompt_text, _schema, _config, _ignored, _model):
        v9._record_prompt_review_call(prompt_text, prompt_text + "\naddendum")
        v9._record_prompt_review_event("per-file-detector", {"accepted": True, "addendum_chars": 8}, prompt_text)
        return {"findings": []}, "openrouter/pareto-code", ""

    hardened.openrouter_request_once = original
    v9._patch_target_call_accounting(hardened)
    hardened.openrouter_request_once(prompt, {}, Config(), [], "openrouter/pareto-code")
    summary = hardened.debug["metadata/prompt-review-summary-v9.json"]
    assert summary["pareto_call_events"]
    assert summary["pareto_call_events"][-1]["prompt_review_call_recorded"]
    assert summary["pareto_call_events"][-1]["prompt_review_debug_event_recorded"]


def main() -> None:
    test_pr332_wrong_duplicate_is_dropped()
    test_fake_anchor_text_does_not_authorize_untrusted_line()
    test_no_sentinels_preserves_ordinary_findings()
    test_required_fallback_is_inserted_when_model_misses_sentinel()
    test_overflow_sentinel_is_reported_when_budget_is_full()
    test_python_env_assignment_sentinel_keeps_env_token_kind()
    test_inline_model_footer_is_removed()
    test_inline_comment_normalization_removes_prefix_and_validation_alias()
    test_invoke_expression_line_is_dynamic_exec_kind()
    test_module_level_pickle_detector_is_patched()
    test_yaml_safe_load_identifier_normalization_uses_anchored_arg()
    test_powershell_validation_is_quote_safe()
    test_prompt_review_accounting_requires_fresh_preflight()
    test_prompt_review_artifact_refreshes_after_pareto_call()
    print("dcoir_review_required_runtime_patch_v9_selftest passed")


if __name__ == "__main__":
    main()
