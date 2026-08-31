#!/usr/bin/env python3
"""Regression checks for DCOIR Review v33 verification/repair budget separation."""

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
    assert "dcoir_review_required_runtime_patch_v33" in entrypoint.patch_module_names
    assert entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v32") < entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v33")
    assert entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v33") < entrypoint.patch_module_names.index("dcoir_review_required_runtime_patch_v31")

    review = importlib.import_module("openrouter_pr_review_pareto_context")
    entrypoint.apply_runtime_patches(review)
    v21 = importlib.import_module("dcoir_review_required_runtime_patch_v21")
    v25 = importlib.import_module("dcoir_review_required_runtime_patch_v25")
    v33 = importlib.import_module("dcoir_review_required_runtime_patch_v33")

    assert getattr(review, v33.APPLIED_MARKER, False) is True
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")

    # v32's compatibility constants remain at the governed repair budget outside
    # an active verifier call. v33 widens only the verifier's temporary ceiling.
    assert v21.VERIFIER_MAX_MODEL_FINDINGS == 8
    assert v25.MAX_REPAIR_CANDIDATES == 8
    assert v33.verifier_candidate_limit(config) == 12
    assert v33.repair_synthesis_budget(config) == 8

    # Prove that a nine-candidate review enters the v21 verifier under the
    # separate 12-candidate verification ceiling and restores the historical
    # constant afterward.
    verifier_storage = getattr(v21, v33.VERIFIER_STORAGE)
    observed: dict[str, int] = {}
    candidates = [
        {
            "title": f"candidate-{index}",
            "severity": "medium",
            "confidence": 0.91,
            "path": "probe.py",
            "line": index,
            "body": "semantic candidate",
            "validation": "focused regression",
        }
        for index in range(1, 10)
    ]

    def fake_verifier(module: Any, findings: list[dict[str, Any]], gh: Any, pr: dict[str, Any], cfg: Any, reporter: Any):
        observed["limit"] = v21.VERIFIER_MAX_MODEL_FINDINGS
        assert len(findings) == 9
        return [dict(item) for item in findings]

    setattr(v21, v33.VERIFIER_STORAGE, fake_verifier)
    try:
        verified = v21.verify_findings_for_publication(
            review,
            candidates,
            object(),
            {"head": {"sha": "deadbeef"}},
            config,
            _Reporter(),
        )
    finally:
        setattr(v21, v33.VERIFIER_STORAGE, verifier_storage)

    assert len(verified) == 9
    assert observed["limit"] == 12
    assert v21.VERIFIER_MAX_MODEL_FINDINGS == 8

    # Prove that all nine verifier-supported findings remain publishable while
    # only the configured eight enter repair-author/critic synthesis.
    original_verify = v21.verify_findings_for_publication
    original_build = v25._build_repair_for_finding
    original_fetch = review.fetch_pr_file_text
    original_debug = review.hardened.write_debug_json_artifact_safely
    repair_calls: list[int] = []

    def return_nine(*args, **kwargs):
        return [dict(item) for item in candidates]

    def fake_build(mod: Any, ordinal: int, finding: dict[str, Any], file_text: str, cfg: Any):
        repair_calls.append(ordinal)
        item = dict(finding)
        item[v25.REPAIR_MARKER] = {
            "version": "test",
            "outcome": "no-safe-single-line-fix",
            "path": finding["path"],
            "line": finding["line"],
        }
        item["suggested_replacement"] = ""
        return item

    v21.verify_findings_for_publication = return_nine
    v25._build_repair_for_finding = fake_build
    review.fetch_pr_file_text = lambda *args, **kwargs: "probe = True\n"
    review.hardened.write_debug_json_artifact_safely = lambda *args, **kwargs: None
    reporter = _Reporter()
    try:
        repaired = v25.synthesize_verified_repairs(
            review,
            candidates,
            object(),
            {"head": {"sha": "deadbeef"}},
            {},
            config,
            reporter,
        )
    finally:
        v21.verify_findings_for_publication = original_verify
        v25._build_repair_for_finding = original_build
        review.fetch_pr_file_text = original_fetch
        review.hardened.write_debug_json_artifact_safely = original_debug

    assert len(repaired) == 9
    assert repair_calls == list(range(1, 9))
    deferred = [item for item in repaired if item.get(v25.REPAIR_MARKER, {}).get("outcome") == v33.DEFERRED_OUTCOME]
    assert len(deferred) == 1
    assert deferred[0]["line"] == 9
    assert deferred[0]["suggested_replacement"] == ""
    assert "repair budget was exhausted" in deferred[0]["fix_guidance"]["notes"]

    # Applying v33 repeatedly must not stack wrappers.
    verifier_before = v21.verify_findings_for_publication
    repair_before = v25.synthesize_verified_repairs
    v33.apply_pareto_context_module(review)
    v33.apply_pareto_context_module(review)
    assert v21.verify_findings_for_publication is verifier_before
    assert v25.synthesize_verified_repairs is repair_before

    print("dcoir_review_required_runtime_patch_v33_selftest passed")


if __name__ == "__main__":
    main()
