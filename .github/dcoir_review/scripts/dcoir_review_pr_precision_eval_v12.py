#!/usr/bin/env python3
"""Current v12 production-shaped clean-PR precision evaluator.

V12 preserves the complete historical v11 composition and replaces only the
fork-workflow control exposed by the operator-approved v11 paired adjudication.
Historical evaluators and the v11 replacement artifact remain unchanged.
"""
from __future__ import annotations

import copy

import dcoir_review_pr_precision_eval as base
import dcoir_review_pr_precision_eval_v11 as v11

OLD_CASE_ID = "precision-gha-fork-grammar-aligned-checkout-approved-tested"
NEW_CASE_ID = "precision-gha-fork-single-job-secret-handoff-blocked-tested"


def _right_side_file(case: dict[str, object], filename: str) -> str:
    file_item = next(item for item in case["files"] if str(item["filename"]) == filename)
    patch = str(file_item["patch"])
    return "\n".join(
        line[1:]
        for line in patch.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ) + "\n"


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    assert count == 1, f"{label}: expected exactly one match, got {count}"
    return text.replace(old, new, 1)


def _patch_from_source(filename: str, source: str) -> str:
    lines = source.rstrip("\n").split("\n")
    return (
        f"diff --git a/{filename} b/{filename}\n"
        "index aaaa222..cccc222 100644\n"
        f"--- a/{filename}\n"
        f"+++ b/{filename}\n"
        f"@@ -1,2 +1,{len(lines)} @@\n"
        + "\n".join("+" + line for line in lines)
        + "\n"
    )


def _harden_fork_case(source_case: dict[str, object]) -> dict[str, object]:
    case = copy.deepcopy(source_case)
    assert str(case["id"]) == OLD_CASE_ID
    assert case["expected_findings"] == []

    case["id"] = NEW_CASE_ID
    case["pr_title"] = "Bind fork-safe diagnostics to one unprivileged job and block secret handoff"
    case["pr_body"] = (
        "Run diagnostic code only in the unprivileged pull_request context, permit exactly one literal "
        "top-level permissions key with contents: read, require the jobs mapping to contain only the single "
        "diagnose runner job so sibling reusable-workflow calls cannot inherit secrets, reject secrets-context "
        "references using GitHub expression single-quote and doubled-quote string semantics, support block-style "
        "checkout steps in both indented and indentless steps sequences, and require every discovered checkout "
        "step's direct with mapping to contain exactly one persist-credentials: false setting. Fail closed on "
        "unsupported trigger/job expansion and flow-style checkout syntax."
    )
    case["ground_truth_rationale"] = (
        "Trusted approval is supplied. The workflow is bound to exactly the pull_request trigger, exactly one "
        "literal top-level contents: read permissions block, and exactly one diagnose runner job; adding a sibling "
        "reusable-workflow call therefore fails closed before jobs.<job_id>.secrets: inherit can hand repository or "
        "organization secrets into another workflow on same-repository pull_request runs. The existing GitHub-expression "
        "scanner still rejects secrets-context references using documented single-quoted/doubled-quote semantics. "
        "Checkout grouping still supports indented and flush block sequences, and credential validation still binds "
        "persist-credentials to direct children of each checkout step's direct with mapping. Negative controls now "
        "include the Opus-discovered reusable-workflow secrets: inherit sibling job and a valid multi-event workflow_run "
        "trigger expansion in addition to the prior v11 grammar/scope probes."
    )

    test_item = next(
        item for item in case["files"]
        if str(item["filename"]) == "tests/test_pr_diagnostics_workflow.py"
    )
    source = _right_side_file(case, "tests/test_pr_diagnostics_workflow.py")
    assert len(source.splitlines()) == 376

    helper_marker = "\n\ndef _assert_fork_workflow_readonly(text):\n"
    helper_block = r'''

def _top_level_trigger_lines(lines):
    trigger_lines = []
    for line in lines:
        cleaned = _strip_yaml_comment(line)
        stripped = cleaned.strip()
        if not stripped:
            continue
        indent = len(cleaned) - len(cleaned.lstrip())
        if indent == 0 and re.match(r"^(?:on|'on'|\"on\")\s*:", stripped, re.IGNORECASE):
            trigger_lines.append(stripped)
    return trigger_lines


def _direct_job_lines(lines):
    jobs_index = lines.index('jobs:')
    direct = []
    for line in lines[jobs_index + 1:]:
        cleaned = _strip_yaml_comment(line)
        stripped = cleaned.strip()
        if not stripped:
            continue
        indent = len(cleaned) - len(cleaned.lstrip())
        if indent == 0:
            break
        if indent == 2:
            direct.append(stripped)
    return direct
'''
    source = _replace_once(source, helper_marker, helper_block + helper_marker, "insert structural helpers")

    old_guard = """def _assert_fork_workflow_readonly(text):
    lines = text.splitlines()
    assert 'pull_request_target' not in text
    assert not _references_secret_context(text)
    assert 'write-all' not in text

    permission_key_lines = [line for line in lines if 'permissions' in line]
"""
    new_guard = """def _assert_fork_workflow_readonly(text):
    lines = text.splitlines()
    assert _top_level_trigger_lines(lines) == ['on: pull_request']
    assert 'pull_request_target' not in text
    assert not _references_secret_context(text)
    assert 'write-all' not in text
    assert _direct_job_lines(lines) == ['diagnose:']

    permission_key_lines = [line for line in lines if 'permissions' in line]
"""
    source = _replace_once(source, old_guard, new_guard, "strengthen fork guard")

    test_marker = "def test_guard_rejects_named_checkout_without_disabled_credentials():\n"
    regression_tests = r'''def test_guard_rejects_reusable_workflow_secret_inherit_sibling_job():
    text = Path('.github/workflows/pr-diagnostics.yml').read_text()
    unsafe = text + "\n  publish:\n    uses: ./.github/workflows/deploy.yml\n    secrets: inherit\n"
    _expect_rejected(unsafe)


def test_guard_rejects_privileged_trigger_expansion():
    text = Path('.github/workflows/pr-diagnostics.yml').read_text()
    unsafe = text.replace(
        'on: pull_request',
        "on:\n  pull_request:\n  workflow_run:\n    workflows: ['CI']\n    types: [completed]",
    )
    _expect_rejected(unsafe)


'''
    source = _replace_once(source, test_marker, regression_tests + test_marker, "insert Opus regression tests")
    assert len(source.splitlines()) == 422
    test_item["patch"] = _patch_from_source("tests/test_pr_diagnostics_workflow.py", source)
    return case


def load_v12_cases() -> list[dict[str, object]]:
    v11_cases = v11.load_v11_cases()
    matches = [case for case in v11_cases if str(case["id"]) == OLD_CASE_ID]
    assert len(matches) == 1, f"v12 expected one {OLD_CASE_ID!r} case, found {len(matches)}"
    return [
        _harden_fork_case(case) if str(case["id"]) == OLD_CASE_ID else copy.deepcopy(case)
        for case in v11_cases
    ]


def main() -> int:
    base.target.load_cases = load_v12_cases
    base.target.build_pr_prompt = base.build_pr_prompt
    base.target.REPORT_SCHEMA = "dcoir_review_pr_precision_eval_report_v12"
    base.resilient.install(base.target.base)
    return base.target.main()


if __name__ == "__main__":
    raise SystemExit(main())
