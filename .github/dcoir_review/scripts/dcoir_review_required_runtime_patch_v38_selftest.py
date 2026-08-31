#!/usr/bin/env python3
"""Regression checks for DCOIR Review v38 repair-author contract hardening."""

from __future__ import annotations

import importlib
from pathlib import Path

from dcoir_review.entrypoint import DcoirReviewEntrypoint


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = entrypoint.patch_module_names
    assert "dcoir_review_required_runtime_patch_v38" in names
    assert names.index("dcoir_review_required_runtime_patch_v37") < names.index("dcoir_review_required_runtime_patch_v38")
    assert names.index("dcoir_review_required_runtime_patch_v38") < names.index("dcoir_review_required_runtime_patch_v31")

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v25 = importlib.import_module("dcoir_review_required_runtime_patch_v25")
    v36 = importlib.import_module("dcoir_review_required_runtime_patch_v36")
    v38 = importlib.import_module("dcoir_review_required_runtime_patch_v38")

    assert getattr(review, v38.APPLIED_MARKER, False) is True
    assert v36.AUTHOR_MIN_CONFIDENCE == 0.0
    assert v36.CRITIC_MIN_CONFIDENCE == 0.95

    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    assert config.debug is False

    finding = {
        "title": "Rejected proposition counts as positive evidence",
        "severity": "medium",
        "confidence": 0.99,
        "path": "probe.py",
        "line": 2,
        "body": "The verified predicate has inconsistent polarity filtering.",
        "validation": "python3 -m py_compile probe.py",
    }

    # Reproduce the live v37 repair-author drift: exact edit, but no purpose and
    # no author confidence. v38 may fill only those metadata fields.
    live_shape = {
        "defect_present": True,
        "action": "repair_set",
        "edits": [
            {
                "path": "probe.py",
                "start_line": 2,
                "end_line": 2,
                "original": "    old_call()",
                "replacement": "    fixed_call()",
            }
        ],
        "display_title": "Fix polarity filter",
        "display_body": "Apply the missing filter.",
        "rationale": "The exact counterexample is removed.",
        "validation": "python3 -m py_compile probe.py",
    }
    parsed = v36._parse_author(live_shape, finding, review.hardened)
    assert parsed["action"] == "repair_set"
    assert parsed["confidence"] == 0.0
    assert parsed["edits"][0]["purpose"].startswith("Repair verified finding:")

    # Low author confidence is transparent but advisory; it must not prevent an
    # exact proposal from reaching the independent critic.
    low_conf_shape = dict(live_shape)
    low_conf_shape["confidence"] = 0.78
    parsed_low = v36._parse_author(low_conf_shape, finding, review.hardened)
    assert parsed_low["action"] == "repair_set"
    assert parsed_low["confidence"] == 0.78

    # Structural defects remain fail-closed; v38 does not fabricate repair
    # semantics beyond purpose/confidence metadata.
    malformed = dict(live_shape)
    malformed["edits"] = [
        {
            "path": "../probe.py",
            "start_line": 2,
            "end_line": 2,
            "original": "    old_call()",
            "replacement": "    fixed_call()",
        }
    ]
    try:
        v36._parse_author(malformed, finding, review.hardened)
    except review.hardened.ReviewQualityError as exc:
        assert "repository-relative" in str(exc)
    else:
        raise AssertionError("v38 forgave a structurally invalid repair path")

    accepted, confidence, _reason = v36._parse_critic(
        {"accepted": True, "confidence": 0.94, "reason": "plausible"}, review.hardened
    )
    assert accepted is False and confidence == 0.94
    accepted, confidence, _reason = v36._parse_critic(
        {"accepted": True, "confidence": 0.95, "reason": "independently proven"}, review.hardened
    )
    assert accepted is True and confidence == 0.95

    prompt = v36._repair_author_prompt(review, finding, "def f():\n    old_call()\n", "", "deadbeef", config)
    for phrase in ("EVERY edit MUST contain all six fields", "purpose", "confidence", "independent cross-family critic"):
        assert phrase in prompt

    # Exercise the active production synthesis chain with the same near-schema
    # author shape seen live: no purpose and no confidence. The independent
    # critic, exact-head validation, and native suggestion rendering must still
    # execute successfully. The synthetic source remains valid Python both before
    # and after the proposed edit so the real syntax safety gate is exercised.
    pipeline_diff = (
        "diff --git a/probe.py b/probe.py\n"
        "--- a/probe.py\n"
        "+++ b/probe.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def f():\n"
        "+    old_call()\n"
    )

    class _FakeGH:
        def get_pr_diff(self, pr_number):
            assert pr_number == 448
            return pipeline_diff

    class _Reporter:
        def __init__(self):
            self.events = []

        def update(self, stage, message):
            self.events.append((stage, message))

    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    original_verify = v21.verify_findings_for_publication
    original_openrouter = review.hardened.openrouter_review
    original_fetch = review.fetch_pr_file_text
    original_debug = review.hardened.write_debug_json_artifact_safely
    model_calls = []

    def _fake_verify(mod, findings, gh, pr, cfg, reporter):
        return [dict(item) for item in findings]

    def _fake_openrouter(prompt_arg, schema_arg, config_arg, reporter=None):
        title = str(schema_arg.get("title", ""))
        model_calls.append((title, list(config_arg.model_stack)))
        if title == "DCOIR Verified Repair Set Author":
            return (dict(live_shape), "anthropic/claude-opus-5", "tier-author")
        if title == "DCOIR Verified Repair Set Critic":
            assert config_arg.model_stack == ["openai/gpt-5.6-sol-pro"]
            return (
                {"accepted": True, "confidence": 0.99, "reason": "Exact, complete, and minimal."},
                "openai/gpt-5.6-sol-pro",
                "tier-critic",
            )
        raise AssertionError(f"unexpected schema title: {title}")

    v21.verify_findings_for_publication = _fake_verify
    review.hardened.openrouter_review = _fake_openrouter
    review.fetch_pr_file_text = lambda gh, target, head: "def f():\n    old_call()\n"
    review.hardened.write_debug_json_artifact_safely = lambda *args, **kwargs: None
    reporter = _Reporter()
    try:
        result = review.synthesize_fixes_for_findings(
            [finding],
            _FakeGH(),
            {"number": 448, "head": {"sha": "deadbeef"}},
            {},
            config,
            reporter,
        )
    finally:
        v21.verify_findings_for_publication = original_verify
        review.hardened.openrouter_review = original_openrouter
        review.fetch_pr_file_text = original_fetch
        review.hardened.write_debug_json_artifact_safely = original_debug

    assert len(result) == 1
    marker = result[0][v25.REPAIR_MARKER]
    assert marker["version"] == v36.VERSION
    assert marker["outcome"] == v36.REPAIR_SET_OUTCOME
    assert marker["author_confidence"] == 0.0
    assert marker["critic_confidence"] == 0.99
    assert marker["native_suggestion_count"] == 1
    assert model_calls[0][0] == "DCOIR Verified Repair Set Author"
    assert model_calls[1] == ("DCOIR Verified Repair Set Critic", ["openai/gpt-5.6-sol-pro"])
    comments = review.build_review_comments_for_finding(result[0], "model", config)
    assert len(comments) == 1
    assert "```suggestion\n    fixed_call()\n```" in comments[0]["body"]

    source = Path(".github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v38.py").read_text(encoding="utf-8")
    for forbidden in ("git push", "create_commit(", "update_file(", "merge_pull_request"):
        assert forbidden not in source

    prompt_before = v36._repair_author_prompt
    parse_before = v36._parse_author
    v38.apply_pareto_context_module(review)
    assert v36._repair_author_prompt is prompt_before
    assert v36._parse_author is parse_before

    print("dcoir_review_required_runtime_patch_v38_selftest passed")


if __name__ == "__main__":
    main()
