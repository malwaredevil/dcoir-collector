#!/usr/bin/env python3
"""Deterministic semantic guards for the current clean-precision v11 corpus."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

import dcoir_review_pr_precision_eval as base
import dcoir_review_pr_precision_eval_v10 as v10
import dcoir_review_pr_precision_eval_v11 as current
import dcoir_review_pr_precision_fixture_v9_selftest as fixture_util


def _materialized_file(case: dict, filename: str) -> str:
    return fixture_util.right_side_file(case, filename)


def _run_embedded_fixture_tests(case: dict) -> int:
    workflow = _materialized_file(case, ".github/workflows/pr-diagnostics.yml")
    script = _materialized_file(case, ".github/scripts/pr-diagnostic.sh")
    test_source = _materialized_file(case, "tests/test_pr_diagnostics_workflow.py")
    compile(test_source, "tests/test_pr_diagnostics_workflow.py", "exec")
    namespace: dict[str, object] = {"__name__": "v11_embedded_fixture"}
    exec(compile(test_source, "tests/test_pr_diagnostics_workflow.py", "exec"), namespace)
    with tempfile.TemporaryDirectory(prefix="dcoir-v11-") as tmp:
        root = Path(tmp)
        (root / ".github/workflows").mkdir(parents=True)
        (root / ".github/scripts").mkdir(parents=True)
        (root / "tests").mkdir(parents=True)
        (root / ".github/workflows/pr-diagnostics.yml").write_text(workflow, encoding="utf-8")
        (root / ".github/scripts/pr-diagnostic.sh").write_text(script, encoding="utf-8")
        previous = Path.cwd()
        try:
            os.chdir(root)
            tests = sorted(
                value for name, value in namespace.items()
                if name.startswith("test_") and callable(value)
            )
            assert len(tests) == 23, f"expected 23 embedded v11 tests, found {len(tests)}"
            for test in tests:
                test()
        finally:
            os.chdir(previous)
    return len(tests)


def main() -> None:
    v10_cases = {str(case["id"]): case for case in v10.load_v10_cases()}
    v11_cases = {str(case["id"]): case for case in current.load_v11_cases()}
    assert len(v10_cases) == len(v11_cases) == 10
    assert all(case["expected_findings"] == [] for case in v11_cases.values())

    old_id = "precision-gha-fork-step-aware-checkout-approved-tested"
    new_id = "precision-gha-fork-grammar-aligned-checkout-approved-tested"
    assert old_id in v10_cases and old_id not in v11_cases
    assert new_id not in v10_cases and new_id in v11_cases
    assert {key: value for key, value in v10_cases.items() if key != old_id} == {
        key: value for key, value in v11_cases.items() if key != new_id
    }

    fork_case = v11_cases[new_id]
    fork_test = _materialized_file(fork_case, "tests/test_pr_diagnostics_workflow.py")
    for needle in (
        "text.startswith(\"''\", index)",
        "double-quoted GitHub expression strings are invalid",
        "_direct_step_entries",
        "_logical_mapping_indent",
        "test_guard_rejects_secret_context_after_backslash_quote_boundary",
        "test_guard_rejects_persist_credentials_inside_block_scalar",
        "test_guard_rejects_persist_credentials_under_sibling_env",
        "test_guard_accepts_flush_sequence_checkout_with_disabled_credentials",
        "test_guard_accepts_doubled_single_quote_string_without_secret_context",
    ):
        assert needle in fork_test, f"missing v11 fork invariant: {needle!r}"
    embedded_tests = _run_embedded_fixture_tests(fork_case)

    workflow_cases = [
        case for case in v11_cases.values()
        if any(str(item["filename"]).startswith(".github/workflows/") for item in case["files"])
    ]
    assert len(workflow_cases) == 2
    assert all(str(case.get("trusted_context", "")).strip() for case in workflow_cases)

    old = os.environ.get("DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT")
    try:
        os.environ["DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT"] = "1"
        for case in v11_cases.values():
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
        "dcoir_review_pr_precision_fixture_v11_selftest passed: v10 history is preserved; "
        f"{embedded_tests} embedded tests align GitHub expression quoting, checkout with-scope, "
        "and indentless steps semantics; ground truth stays hidden"
    )


if __name__ == "__main__":
    main()
