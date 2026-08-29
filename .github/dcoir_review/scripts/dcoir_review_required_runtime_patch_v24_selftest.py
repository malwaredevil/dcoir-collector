#!/usr/bin/env python3
"""Production-stack regression for DCOIR Review v24 rendering semantics."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


PROBE_PATH = ".github/dcoir_review/evaluation/live_verifier_probe.py"


def patched_review():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    return review


def test_model_judge_finding_preserves_verified_semantics(review) -> None:
    v20 = importlib.import_module("dcoir_review_required_runtime_patch_v20")
    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    finding = {
        "title": "Inverted upper-bound check excludes valid recent ages",
        "severity": "medium",
        "confidence": 0.99,
        "path": PROBE_PATH,
        "line": 11,
        "body": "The documented inclusive range is 0 through 60 minutes, but the second comparison uses >= 60 instead of <= 60.",
        "suggested_replacement": '    return age_minutes >= 0 and age_minutes <= 60',
        "validation": "python3 -m py_compile .github/dcoir_review/evaluation/live_verifier_probe.py",
        "fix_guidance": {
            "language": "python",
            "notes": "Reverse the upper-bound comparison so the implementation matches the documented inclusive range.",
        },
        v20.SYNTHESIS_VERIFIED_MARKER: True,
        v21.VERIFIER_MARKER: {
            "mode": "model-judge",
            "supported": True,
            "confidence": 0.99,
            "evidence": "The docstring says 0 through 60 inclusive while the return expression requires age_minutes >= 60.",
            "head_sha": "probe-head",
            "line": 11,
        },
    }
    rendered = review.base.build_inline_comment(finding, "test-model", config)
    assert "Inverted upper-bound check excludes valid recent ages" in rendered
    assert "second comparison uses >= 60 instead of <= 60" in rendered
    assert "Python executes caller-controlled code" not in rendered
    assert "evaluates text as Python code" not in rendered
    assert '```suggestion\n    return age_minutes >= 0 and age_minutes <= 60\n```' in rendered


def test_deterministic_sentinel_still_uses_canonical_renderer(review) -> None:
    v20 = importlib.import_module("dcoir_review_required_runtime_patch_v20")
    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    finding = {
        "title": "model wording should not replace deterministic sentinel template",
        "severity": "high",
        "confidence": 0.99,
        "path": ".github/dcoir_review/evaluation/live_suggestion_probe.py",
        "line": 10,
        "body": "model body",
        "suggested_replacement": "",
        "validation": "python3 -m py_compile .github/dcoir_review/evaluation/live_suggestion_probe.py",
        "_anchored_line_text": '    if severity == "critical" or "high":',
        "_risk_sentinel_key": [
            ".github/dcoir_review/evaluation/live_suggestion_probe.py",
            10,
            v20.PYTHON_TRUTHY_LITERAL_BRANCH,
        ],
        "_risk_sentinel_kind": v20.PYTHON_TRUTHY_LITERAL_BRANCH,
        v21.VERIFIER_MARKER: {
            "mode": "deterministic-core-sentinel",
            "supported": True,
            "kind": v20.PYTHON_TRUTHY_LITERAL_BRANCH,
            "head_sha": "probe-head",
            "line": 10,
        },
    }
    rendered = review.base.build_inline_comment(finding, "test-model", config)
    assert "Python branch condition contains an always-truthy literal" in rendered
    assert "model wording should not replace deterministic sentinel template" not in rendered


def main() -> None:
    review = patched_review()
    test_model_judge_finding_preserves_verified_semantics(review)
    test_deterministic_sentinel_still_uses_canonical_renderer(review)
    print("dcoir_review_required_runtime_patch_v24_selftest passed")


if __name__ == "__main__":
    main()
