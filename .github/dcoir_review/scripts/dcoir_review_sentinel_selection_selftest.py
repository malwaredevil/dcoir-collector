#!/usr/bin/env python3
"""Regression checks for stable ordinary-finding / sentinel selection."""

from __future__ import annotations

import importlib

from dcoir_review.entrypoint import DcoirReviewEntrypoint


PATH = ".github/dcoir_review/evaluation/live_verifier_probe.py"


def patched_review():
    review = importlib.import_module("openrouter_pr_review_pareto_context")
    DcoirReviewEntrypoint().apply_runtime_patches(review)
    return review


def test_no_sentinel_selection_is_identity(review) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    finding = {
        "title": "Upper-bound comparison is inverted",
        "severity": "high",
        "confidence": 1.0,
        "path": PATH,
        "line": 12,
        "body": "The expression requires age_minutes >= 60 where the local contract requires an inclusive upper bound of 60.",
        "suggested_replacement": "",
    }
    selected = review.hardened.add_risk_sentinel_fallback_findings([finding], [], config, [])
    assert len(selected) == 1, selected
    assert selected[0] == finding, selected
    assert selected[0]["line"] == 12
    assert selected[0]["title"] == "Upper-bound comparison is inverted"


def test_no_sentinel_selection_preserves_multiple_model_sites(review) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    findings = [
        {
            "title": "First ordinary finding",
            "severity": "medium",
            "confidence": 0.95,
            "path": "probe.py",
            "line": 4,
            "body": "First exact changed-line issue.",
        },
        {
            "title": "Second ordinary finding",
            "severity": "medium",
            "confidence": 0.94,
            "path": "probe.py",
            "line": 9,
            "body": "Second exact changed-line issue.",
        },
    ]
    selected = review.hardened.add_risk_sentinel_fallback_findings(findings, [], config, [])
    assert [(item["path"], item["line"]) for item in selected] == [("probe.py", 4), ("probe.py", 9)]
    assert [item["title"] for item in selected] == ["First ordinary finding", "Second ordinary finding"]


def test_real_sentinel_priority_preserves_unrelated_model_finding(review) -> None:
    config = review.load_pareto_context_config(".github/dcoir_review/openrouter-pr-review-pareto.yml")
    sentinel_type = review.hardened.RiskSentinel
    sentinel = sentinel_type(
        path=".github/workflows/probe.yml",
        line=7,
        label="Workflow executes pull request metadata in a shell",
        detail="probe",
        text='run: echo "${{ github.event.pull_request.title }}" | bash',
    )
    findings = [
        {
            "title": "Ordinary unrelated model issue",
            "severity": "medium",
            "confidence": 0.90,
            "path": "probe.py",
            "line": 4,
            "body": "ordinary exact changed-line issue",
        },
        {
            "title": "Ordinary prose at sentinel site",
            "severity": "medium",
            "confidence": 0.91,
            "path": ".github/workflows/probe.yml",
            "line": 7,
            "body": "mentions shell but is not deterministic provenance",
        },
    ]
    selected = review.hardened.add_risk_sentinel_fallback_findings(findings, [sentinel], config, [])
    assert len(selected) == 2, selected
    deterministic, ordinary = selected
    assert deterministic["path"] == ".github/workflows/probe.yml", deterministic
    assert deterministic["line"] == 7, deterministic
    assert deterministic.get("_risk_sentinel_key") == [
        ".github/workflows/probe.yml",
        7,
        "yaml_metadata_shell",
    ], deterministic
    assert ordinary == findings[0], selected
    assert all(item.get("title") != "Ordinary prose at sentinel site" for item in selected), selected


def test_stable_owner_composition() -> None:
    entrypoint = DcoirReviewEntrypoint()
    names = (
        *entrypoint.patch_module_names,
        *entrypoint.terminal_patch_module_names,
        *entrypoint.post_terminal_patch_module_names,
        *entrypoint.candidate_integrity_patch_module_names,
        *entrypoint.stage_local_patch_module_names,
        *entrypoint.execution_policy_patch_module_names,
        *entrypoint.telemetry_patch_module_names,
        *entrypoint.post_telemetry_patch_module_names,
    )
    assert 'dcoir_review.sentinel_selection' in names, names
    assert 'dcoir_review_required_runtime_patch_v26' not in names, names


def main() -> None:
    test_stable_owner_composition()
    review = patched_review()
    test_no_sentinel_selection_is_identity(review)
    test_no_sentinel_selection_preserves_multiple_model_sites(review)
    test_real_sentinel_priority_preserves_unrelated_model_finding(review)
    print("dcoir_review_sentinel_selection_selftest passed")


if __name__ == "__main__":
    main()
