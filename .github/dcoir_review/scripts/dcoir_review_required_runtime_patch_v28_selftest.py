#!/usr/bin/env python3
"""Regression checks for DCOIR Review v28 staged repair reliability."""

from __future__ import annotations

import importlib
from typing import Any, Callable

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
    entrypoint = DcoirReviewEntrypoint()
    assert "dcoir_review_required_runtime_patch_v28" in entrypoint.patch_module_names
    assert "dcoir_review_required_runtime_patch_v30" in entrypoint.patch_module_names
    assert "dcoir_review_required_runtime_patch_v31" in entrypoint.patch_module_names
    assert entrypoint.patch_module_names[-1] == "dcoir_review_required_runtime_patch_v31"
    assert entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v28") < entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v30")
    assert entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v30") < entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v31")
    entrypoint.apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    v25 = importlib.import_module("dcoir_review_required_runtime_patch_v25")
    v28 = importlib.import_module("dcoir_review_required_runtime_patch_v28")
    return review, v21, v25, v28


def verified_finding(v21, v25):
    finding = {
        "title": "Upper-bound comparison is inverted",
        "severity": "medium",
        "confidence": 1.0,
        "path": PATH,
        "line": LINE,
        "body": "The upper-bound comparison uses >= 60 instead of <= 60, contradicting the documented inclusive 0..60 contract.",
        "suggested_replacement": "detector output is never trusted as a repair",
        "validation": "python3 -m py_compile .github/dcoir_review/evaluation/live_verifier_probe.py",
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
    return v25._strip_legacy_model_finding_provenance(finding)


def config_for(review):
    return review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")


def run_with_openrouter(review, fake: Callable[..., tuple[dict[str, Any], str, str]], action: Callable[[], Any]):
    original = review.hardened.openrouter_review
    review.hardened.openrouter_review = fake
    try:
        return action()
    finally:
        review.hardened.openrouter_review = original


def schema_title(schema: dict[str, Any]) -> str:
    return str(schema.get("title", "") or "")


def test_native_suggestion_survives_missing_author_display_text(review, v21, v25, v28) -> None:
    calls: list[str] = []

    def fake(_prompt, schema, _config, reporter=None):
        del reporter
        title = schema_title(schema)
        calls.append(title)
        if title == "DCOIR Verified Finding Repair Author":
            return (
                {
                    "defect_present": True,
                    "action": "replace_line",
                    "replacement": REPLACEMENT,
                    "confidence": 0.99,
                    "rationale": "The documented range needs an upper-bound comparison.",
                    "validation": "python3 -m py_compile .github/dcoir_review/evaluation/live_verifier_probe.py",
                },
                "test-author-model",
                "",
            )
        if title == "DCOIR Verified Finding Repair Critic":
            return (
                {"accepted": True, "confidence": 0.99, "reason": "Exact one-line repair matches the verified contract."},
                "test-critic-model",
                "",
            )
        raise AssertionError(title)

    finding = verified_finding(v21, v25)
    item = run_with_openrouter(
        review,
        fake,
        lambda: v28.build_repair_for_finding(review, 1, finding, FILE_TEXT, config_for(review)),
    )
    marker = item[v25.REPAIR_MARKER]
    assert calls == ["DCOIR Verified Finding Repair Author", "DCOIR Verified Finding Repair Critic"], calls
    assert marker["version"] == "v28", marker
    assert marker["outcome"] == "native-suggestion", marker
    assert marker["critic_accepted"] is True, marker
    assert item["suggested_replacement"] == REPLACEMENT
    assert item["title"] == finding["title"]
    assert item["body"] == finding["body"]
    rendered = review.base.build_inline_comment(item, "test-model", config_for(review))
    assert f"```suggestion\n{REPLACEMENT}\n```" in rendered, rendered
    assert "verified repair pipeline v28" in rendered, rendered


def test_author_decline_skips_critic(review, v21, v25, v28) -> None:
    calls: list[str] = []

    def fake(_prompt, schema, _config, reporter=None):
        del reporter
        title = schema_title(schema)
        calls.append(title)
        assert title == "DCOIR Verified Finding Repair Author"
        return (
            {
                "defect_present": True,
                "action": "no_safe_single_line_fix",
                "replacement": "",
                "confidence": 0.98,
                "display_title": "",
                "display_body": "",
                "rationale": "A one-line repair is not sufficiently proven.",
                "validation": "",
            },
            "test-author-model",
            "",
        )

    item = run_with_openrouter(
        review,
        fake,
        lambda: v28.build_repair_for_finding(review, 2, verified_finding(v21, v25), FILE_TEXT, config_for(review)),
    )
    assert len(calls) == 1, calls
    assert item[v25.REPAIR_MARKER]["outcome"] == "author-declined"
    assert item["suggested_replacement"] == ""


def test_deterministic_precheck_skips_critic(review, v21, v25, v28) -> None:
    calls: list[str] = []

    def fake(_prompt, schema, _config, reporter=None):
        del reporter
        title = schema_title(schema)
        calls.append(title)
        assert title == "DCOIR Verified Finding Repair Author"
        return (
            {
                "defect_present": True,
                "action": "replace_line",
                "replacement": "return age_minutes >= 0 and age_minutes <= 60",
                "confidence": 0.99,
                "display_title": "Upper-bound comparison is inverted",
                "display_body": "The exact changed line uses the wrong upper-bound operator.",
                "rationale": "Change the upper-bound operator.",
                "validation": "",
            },
            "test-author-model",
            "",
        )

    item = run_with_openrouter(
        review,
        fake,
        lambda: v28.build_repair_for_finding(review, 3, verified_finding(v21, v25), FILE_TEXT, config_for(review)),
    )
    assert len(calls) == 1, calls
    assert item[v25.REPAIR_MARKER]["outcome"] == "deterministic-precheck-declined"
    assert "indentation" in item[v25.REPAIR_MARKER]["reason"], item[v25.REPAIR_MARKER]


def test_author_call_failure_is_bounded(review, v21, v25, v28) -> None:
    def fake(_prompt, _schema, _config, reporter=None):
        del reporter
        raise RuntimeError("synthetic author transport failure")

    item = run_with_openrouter(
        review,
        fake,
        lambda: v28.build_repair_for_finding(review, 4, verified_finding(v21, v25), FILE_TEXT, config_for(review)),
    )
    marker = item[v25.REPAIR_MARKER]
    assert marker["outcome"] == "author-call-stage-failed-closed", marker
    assert "synthetic author transport failure" in marker["reason"], marker
    assert item["suggested_replacement"] == ""


def test_critic_call_failure_is_bounded(review, v21, v25, v28) -> None:
    calls = 0

    def fake(_prompt, schema, _config, reporter=None):
        nonlocal calls
        del reporter
        calls += 1
        if schema_title(schema) == "DCOIR Verified Finding Repair Author":
            return (
                {
                    "defect_present": True,
                    "action": "replace_line",
                    "replacement": REPLACEMENT,
                    "confidence": 0.99,
                    "display_title": "Upper-bound comparison is inverted",
                    "display_body": "The exact changed line uses the wrong upper-bound operator.",
                    "rationale": "Change the upper-bound operator.",
                    "validation": "",
                },
                "test-author-model",
                "",
            )
        raise RuntimeError("synthetic critic transport failure")

    item = run_with_openrouter(
        review,
        fake,
        lambda: v28.build_repair_for_finding(review, 5, verified_finding(v21, v25), FILE_TEXT, config_for(review)),
    )
    marker = item[v25.REPAIR_MARKER]
    assert calls == 2, calls
    assert marker["outcome"] == "critic-call-stage-failed-closed", marker
    assert "synthetic critic transport failure" in marker["reason"], marker
    assert item["suggested_replacement"] == ""


def main() -> None:
    review, v21, v25, v28 = patched_modules()
    test_native_suggestion_survives_missing_author_display_text(review, v21, v25, v28)
    test_author_decline_skips_critic(review, v21, v25, v28)
    test_deterministic_precheck_skips_critic(review, v21, v25, v28)
    test_author_call_failure_is_bounded(review, v21, v25, v28)
    test_critic_call_failure_is_bounded(review, v21, v25, v28)
    print("dcoir_review_required_runtime_patch_v28_selftest passed")


if __name__ == "__main__":
    main()
