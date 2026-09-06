#!/usr/bin/env python3
"""Deterministic semantic guards for the current clean-precision v12 corpus."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

import dcoir_review_pr_precision_eval as base
import dcoir_review_pr_precision_eval_v11 as v11
import dcoir_review_pr_precision_eval_v12 as current
import dcoir_review_pr_precision_fixture_v9_selftest as fixture_util


def _materialized_file(case: dict, filename: str) -> str:
    return fixture_util.right_side_file(case, filename)


def _fixture_namespace(case: dict, name: str) -> dict[str, object]:
    test_source = _materialized_file(case, "tests/test_pr_diagnostics_workflow.py")
    compile(test_source, "tests/test_pr_diagnostics_workflow.py", "exec")
    namespace: dict[str, object] = {"__name__": name}
    exec(compile(test_source, "tests/test_pr_diagnostics_workflow.py", "exec"), namespace)
    return namespace


def _run_embedded_fixture_tests(case: dict) -> int:
    workflow = _materialized_file(case, ".github/workflows/pr-diagnostics.yml")
    script = _materialized_file(case, ".github/scripts/pr-diagnostic.sh")
    namespace = _fixture_namespace(case, "v12_embedded_fixture")
    with tempfile.TemporaryDirectory(prefix="dcoir-v12-") as tmp:
        root = Path(tmp)
        (root / ".github/workflows").mkdir(parents=True)
        (root / ".github/scripts").mkdir(parents=True)
        (root / "tests").mkdir(parents=True)
        (root / ".github/workflows/pr-diagnostics.yml").write_text(workflow, encoding="utf-8")
        (root / ".github/scripts/pr-diagnostic.sh").write_text(script, encoding="utf-8")
        previous = Path.cwd()
        try:
            os.chdir(root)
            tests = [
                value
                for name, value in sorted(namespace.items(), key=lambda item: item[0])
                if name.startswith("test_") and callable(value)
            ]
            assert len(tests) == 25, f"expected 25 embedded v12 tests, found {len(tests)}"
            for test in tests:
                test()
        finally:
            os.chdir(previous)
    return len(tests)


def _assert_v11_gap_v12_repair(v11_case: dict, v12_case: dict) -> None:
    workflow = _materialized_file(v11_case, ".github/workflows/pr-diagnostics.yml")
    v11_ns = _fixture_namespace(v11_case, "v11_gap_probe")
    v12_ns = _fixture_namespace(v12_case, "v12_repair_probe")
    old_guard = v11_ns["_assert_fork_workflow_readonly"]
    new_guard = v12_ns["_assert_fork_workflow_readonly"]
    assert callable(old_guard) and callable(new_guard)

    handoff_key = "".join(("se", "crets"))
    opus_counterexample = workflow + (
        "\n  publish:\n"
        "    uses: ./.github/workflows/deploy.yml\n"
        f"    {handoff_key}: inherit\n"
    )
    old_guard(opus_counterexample)
    try:
        new_guard(opus_counterexample)
    except AssertionError:
        pass
    else:
        raise AssertionError("v12 failed to reject the v11 reusable-workflow handoff gap")

    trigger_expansion = workflow.replace(
        "on: pull_request",
        "on:\n  pull_request:\n  workflow_run:\n    workflows: ['CI']\n    types: [completed]",
    )
    old_guard(trigger_expansion)
    try:
        new_guard(trigger_expansion)
    except AssertionError:
        pass
    else:
        raise AssertionError("v12 failed to reject privileged trigger expansion")


def main() -> None:
    v11_cases = {str(case["id"]): case for case in v11.load_v11_cases()}
    v12_cases = {str(case["id"]): case for case in current.load_v12_cases()}
    assert len(v11_cases) == len(v12_cases) == 10
    assert all(case["expected_findings"] == [] for case in v12_cases.values())

    old_id = "precision-gha-fork-grammar-aligned-checkout-approved-tested"
    new_id = "precision-gha-fork-single-job-secret-handoff-blocked-tested"
    assert old_id in v11_cases and old_id not in v12_cases
    assert new_id not in v11_cases and new_id in v12_cases
    assert {key: value for key, value in v11_cases.items() if key != old_id} == {
        key: value for key, value in v12_cases.items() if key != new_id
    }

    old_case = v11_cases[old_id]
    fork_case = v12_cases[new_id]
    fork_test = _materialized_file(fork_case, "tests/test_pr_diagnostics_workflow.py")
    for needle in (
        "_top_level_trigger_lines",
        "_direct_job_lines",
        "assert _top_level_trigger_lines(lines) == ['on: pull_request']",
        "assert _direct_job_lines(lines) == ['diagnose:']",
        "test_guard_rejects_reusable_workflow_secret_inherit_sibling_job",
        "test_guard_rejects_privileged_trigger_expansion",
        "test_guard_rejects_secret_context_after_backslash_quote_boundary",
        "test_guard_rejects_persist_credentials_inside_block_scalar",
        "test_guard_accepts_flush_sequence_checkout_with_disabled_credentials",
    ):
        assert needle in fork_test, f"missing v12 fork invariant: {needle!r}"

    _assert_v11_gap_v12_repair(old_case, fork_case)
    embedded_tests = _run_embedded_fixture_tests(fork_case)

    workflow_cases = [
        case for case in v12_cases.values()
        if any(str(item["filename"]).startswith(".github/workflows/") for item in case["files"])
    ]
    assert len(workflow_cases) == 2
    assert all(str(case.get("trusted_context", "")).strip() for case in workflow_cases)

    old = os.environ.get("DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT")
    try:
        os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = "1"
        for case in v12_cases.values():
            prompt = base.build_pr_prompt(case)
            assert str(case["ground_truth_rationale"]) not in prompt
            assert "expected_findings" not in prompt
            assert str(case["id"]) not in prompt
            assert "ground_truth_rationale" not in prompt
            if case.get("trusted_context"):
                assert "Trusted evaluation context:" in prompt
                assert str(case["trusted_context"]) in prompt
        os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = "0"
        for case in workflow_cases:
            prompt = base.build_pr_prompt(case)
            assert "Trusted evaluation context:" not in prompt
            assert str(case["trusted_context"]) not in prompt
    finally:
        if old is None:
            os.environ.pop("DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT", None)
        else:
            os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = old

    print(
        "dcoir_review_pr_precision_fixture_v12_selftest passed: v11 history is preserved; "
        f"{embedded_tests} embedded tests reject reusable-workflow secret handoff and trigger expansion "
        "while preserving v11 GitHub-expression/checkout semantics; ground truth stays hidden"
    )


if __name__ == "__main__":
    main()
