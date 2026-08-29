#!/usr/bin/env python3
"""Full-stack regression checks for DCOIR Review v25 verified repairs."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


PATH = ".github/dcoir_review/evaluation/live_verifier_probe.py"
LINE = 12
ORIGINAL = "    return age_minutes >= 0 and age_minutes >= 60"
REPLACEMENT = "    return age_minutes >= 0 and age_minutes <= 60"
FILE_TEXT = '''"""TEST ONLY - NEVER MERGE: controlled DCOIR Review verifier probe.

This file intentionally contains one deterministic semantic bug that should be
found by ordinary model review, not by a high-risk sentinel. The function's
contract is explicit so a verifier can judge the finding against full-file
context and the exact changed line.
"""


def is_recent(age_minutes: int) -> bool:
    """Return True when age_minutes is between 0 and 60 inclusive."""
    return age_minutes >= 0 and age_minutes >= 60
'''


def patched_modules():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    v25 = importlib.import_module("dcoir_review_required_runtime_patch_v25")
    return review, v21, v25


def model_judged_finding(v21):
    return {
        "title": "Upper-bound comparison is inverted",
        "severity": "high",
        "confidence": 1.0,
        "path": PATH,
        "line": LINE,
        "body": "The upper-bound comparison uses >= 60 instead of <= 60, contradicting the documented inclusive 0..60 contract.",
        "suggested_replacement": "detector output must never be trusted",
        "_risk_sentinel_kind": "python_dynamic_exec",
        "_risk_sentinel_key": [PATH, LINE, "python_dynamic_exec"],
        "covered_risk_sentinel_keys": [[PATH, LINE, "python_dynamic_exec"]],
        v21.VERIFIER_MARKER: {
            "mode": "model-judge",
            "supported": True,
            "confidence": 0.99,
            "evidence": "The docstring says 0 through 60 inclusive, but the second comparison is age_minutes >= 60.",
            "reason": "The changed line contradicts the local function contract.",
            "model_used": "test-verifier",
            "head_sha": "deadbeef",
            "line": LINE,
        },
    }


def test_diff_position_first_hunk(review) -> None:
    added_lines = "\n".join(f"+line-{index}" for index in range(1, 13))
    diff = (
        "diff --git a/probe.py b/probe.py\n"
        "new file mode 100644\n"
        "index 0000000..1111111\n"
        "--- /dev/null\n"
        "+++ b/probe.py\n"
        "@@ -0,0 +1,12 @@\n"
        f"{added_lines}\n"
    )
    mapping = review.base.build_diff_line_index(diff)
    assert mapping[("probe.py", 1)] == 1, mapping
    assert mapping[("probe.py", 12)] == 12, mapping


def test_model_judge_provenance_is_cleaned(v21, v25) -> None:
    cleaned = v25._strip_legacy_model_finding_provenance(model_judged_finding(v21))
    assert "_risk_sentinel_kind" not in cleaned
    assert "_risk_sentinel_key" not in cleaned
    assert "covered_risk_sentinel_keys" not in cleaned
    assert cleaned["suggested_replacement"] == ""
    assert cleaned["_detector_suggested_replacement"] == "detector output must never be trusted"


def test_exact_python_replacement_passes(review, v25) -> None:
    reason = v25._replacement_validation_reason(review, PATH, LINE, ORIGINAL, REPLACEMENT, FILE_TEXT)
    assert reason == "", reason


def test_multiline_replacement_is_rejected(review, v25) -> None:
    reason = v25._replacement_validation_reason(
        review,
        PATH,
        LINE,
        ORIGINAL,
        REPLACEMENT + "\n    pass",
        FILE_TEXT,
    )
    assert "one plain source line" in reason, reason


def test_wrong_indentation_is_rejected(review, v25) -> None:
    reason = v25._replacement_validation_reason(
        review,
        PATH,
        LINE,
        ORIGINAL,
        "return age_minutes >= 0 and age_minutes <= 60",
        FILE_TEXT,
    )
    assert "indentation" in reason, reason


def test_python_syntax_break_is_rejected(review, v25) -> None:
    reason = v25._replacement_validation_reason(
        review,
        PATH,
        LINE,
        ORIGINAL,
        "    return (age_minutes >= 0 and age_minutes <= 60",
        FILE_TEXT,
    )
    assert "Python syntax invalid" in reason, reason


def test_author_no_safe_fix(v25, review) -> None:
    parsed = v25._parse_author(
        {
            "action": "no_safe_single_line_fix",
            "replacement": REPLACEMENT,
            "confidence": 0.95,
            "display_title": "Upper bound is inverted",
            "display_body": "The verified range check is inverted.",
            "rationale": "Needs a broader change.",
            "validation": "",
        },
        review.hardened,
    )
    assert parsed["action"] == "no_safe_single_line_fix"
    assert parsed["replacement"] == ""


def test_low_confidence_critic_rejects(v25, review) -> None:
    accepted, confidence, _reason = v25._parse_critic(
        {"accepted": True, "confidence": 0.70, "reason": "Probably correct."},
        review.hardened,
    )
    assert accepted is False
    assert confidence == 0.70


def test_native_renderer_preserves_verified_semantics(review, v21, v25) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    finding = v25._strip_legacy_model_finding_provenance(model_judged_finding(v21))
    finding["title"] = "Upper-bound comparison is inverted"
    finding["body"] = "The function documents an inclusive 0..60 range, but this line requires age_minutes to be at least 60 for the upper-bound term."
    finding["suggested_replacement"] = REPLACEMENT
    finding[v25.REPAIR_MARKER] = {
        "version": v25.VERSION,
        "outcome": "native-suggestion",
        "path": PATH,
        "line": LINE,
        "critic_accepted": True,
        "critic_confidence": 0.99,
    }
    rendered = review.base.build_inline_comment(finding, "test-model", config)
    assert "Upper-bound comparison is inverted" in rendered
    assert "inclusive 0..60 range" in rendered
    assert "executes caller-controlled code" not in rendered.lower()
    assert f"```suggestion\n{REPLACEMENT}\n```" in rendered, rendered


def test_fallback_renderer_has_no_native_fence(review, v21, v25) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    finding = v25._strip_legacy_model_finding_provenance(model_judged_finding(v21))
    finding["title"] = "Upper-bound comparison is inverted"
    finding["body"] = "Verified boundary-condition issue."
    finding["suggested_replacement"] = ""
    finding["fix_guidance"] = {"language": "py", "notes": "No safe exact one-line fix was proven."}
    finding[v25.REPAIR_MARKER] = {
        "version": v25.VERSION,
        "outcome": "no-safe-single-line-fix",
        "path": PATH,
        "line": LINE,
    }
    rendered = review.base.build_inline_comment(finding, "test-model", config)
    assert "```suggestion" not in rendered
    assert "No safe exact one-line fix was proven" in rendered


def main() -> None:
    review, v21, v25 = patched_modules()
    test_diff_position_first_hunk(review)
    test_model_judge_provenance_is_cleaned(v21, v25)
    test_exact_python_replacement_passes(review, v25)
    test_multiline_replacement_is_rejected(review, v25)
    test_wrong_indentation_is_rejected(review, v25)
    test_python_syntax_break_is_rejected(review, v25)
    test_author_no_safe_fix(v25, review)
    test_low_confidence_critic_rejects(v25, review)
    test_native_renderer_preserves_verified_semantics(review, v21, v25)
    test_fallback_renderer_has_no_native_fence(review, v21, v25)
    print("dcoir_review_required_runtime_patch_v25_selftest passed")


if __name__ == "__main__":
    main()
