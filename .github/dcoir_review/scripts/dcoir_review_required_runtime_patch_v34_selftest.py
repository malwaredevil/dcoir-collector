#!/usr/bin/env python3
"""Regression checks for DCOIR Review v34 predicate audit and blank-anchor verification."""

from __future__ import annotations

import importlib
from typing import Any

from dcoir_review.entrypoint import DcoirReviewEntrypoint


class _Reporter:
    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    def update(self, stage: str, message: str) -> None:
        self.events.append((stage, message))


def main() -> None:
    entrypoint = DcoirReviewEntrypoint()
    assert "dcoir_review_required_runtime_patch_v34" in entrypoint.patch_module_names
    assert entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v33") < entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v34")
    assert entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v34") < entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v31")

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    v32 = importlib.import_module("dcoir_review_required_runtime_patch_v32")
    v34 = importlib.import_module("dcoir_review_required_runtime_patch_v34")

    assert getattr(review, v34.APPLIED_MARKER, False) is True
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    assert config.debug is False

    # v34 strengthens both primary and independent prompts without teaching a
    # PR-specific answer. The audit is structural: call-site defaults, every OR
    # branch, and rejected/mentioned propositions must be examined.
    assert v34.PREDICATE_AUDIT_BLOCK in v32.ADVERSARIAL_SEMANTIC_BLOCK
    assert v34.PREDICATE_AUDIT_BLOCK in v32.INDEPENDENT_CONFIRMATION_BLOCK
    assert "omitted defaults" in v34.PREDICATE_AUDIT_BLOCK
    assert "Audit each OR branch independently" in v34.PREDICATE_AUDIT_BLOCK
    assert "rejected proposition" in v34.PREDICATE_AUDIT_BLOCK

    # An in-range blank changed line is valid GitHub anchoring evidence and must
    # remain distinguishable from missing/out-of-range file evidence.
    assert v21._file_line_text("alpha\n\nomega\n", 2) == v34.BLANK_LINE_NOTATION
    assert v21._file_line_text("alpha\n\nomega\n", 4) == ""

    original_fetch = review.fetch_pr_file_text
    original_openrouter = review.hardened.openrouter_review
    original_debug = review.hardened.write_debug_json_artifact_safely
    debug_paths: list[str] = []
    debug_payloads: dict[str, dict[str, Any]] = {}

    def fake_openrouter(prompt: str, schema: dict[str, Any], cfg: Any, reporter: Any = None):
        assert v34.BLANK_LINE_NOTATION in prompt
        return (
            {
                "supported": True,
                "confidence": 0.96,
                "evidence": "The full head-file context directly supports the candidate adjacent to the intentionally blank changed anchor.",
                "reason": "supported",
            },
            "test-verifier-model",
            "default",
        )

    def capture_debug(cfg: Any, relative_path: str, payload: dict[str, Any]) -> None:
        debug_paths.append(relative_path)
        debug_payloads[relative_path] = payload

    review.fetch_pr_file_text = lambda *args, **kwargs: "alpha\n\nomega\n"
    review.hardened.openrouter_review = fake_openrouter
    review.hardened.write_debug_json_artifact_safely = capture_debug
    candidate = {
        "title": "Blank-anchor candidate",
        "severity": "high",
        "confidence": 0.95,
        "path": "probe.py",
        "line": 2,
        "body": "The changed behavior adjacent to this blank anchor is incorrect.",
        "validation": "focused regression",
    }
    try:
        verified = v21.verify_findings_for_publication(
            review,
            [candidate],
            object(),
            {"head": {"sha": "deadbeef"}},
            config,
            _Reporter(),
        )
    finally:
        review.fetch_pr_file_text = original_fetch
        review.hardened.openrouter_review = original_openrouter
        review.hardened.write_debug_json_artifact_safely = original_debug

    assert len(verified) == 1
    assert "metadata/v34-verifier-input.json" in debug_paths
    assert "responses/finding-verifier/01.json" in debug_paths
    assert "responses/v34-verifier-output.json" in debug_paths
    assert debug_payloads["metadata/v34-verifier-input.json"]["candidate_count"] == 1
    assert debug_payloads["metadata/v34-verifier-input.json"]["candidates"][0]["line"] == 2
    assert debug_payloads["responses/v34-verifier-output.json"]["verified_count"] == 1

    # Re-applying v34 is a no-op; wrappers and prompt blocks must not stack.
    verifier_before = v21.verify_findings_for_publication
    semantic_before = v32.ADVERSARIAL_SEMANTIC_BLOCK
    confirmation_before = v32.INDEPENDENT_CONFIRMATION_BLOCK
    v34.apply_pareto_context_module(review)
    v34.apply_pareto_context_module(review)
    assert v21.verify_findings_for_publication is verifier_before
    assert v32.ADVERSARIAL_SEMANTIC_BLOCK == semantic_before
    assert v32.INDEPENDENT_CONFIRMATION_BLOCK == confirmation_before

    print("dcoir_review_required_runtime_patch_v34_selftest passed")


if __name__ == "__main__":
    main()
