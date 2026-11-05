"""Agent-runtime workflow consistency checks and hostile mutation self-tests."""
from __future__ import annotations

from pathlib import Path

from .workflow_consistency_runtime_contract import (
    AGENT_RUNTIME_PATH_MARKERS,
    AGENT_RUNTIME_VALIDATION_STEPS,
    AGENT_RUNTIME_PARITY_REPORT_STEP,
    AGENT_RUNTIME_PARITY_REPORT_COMMAND,
    AGENT_RUNTIME_PARITY_REPORT_FAILURE,
    AGENT_RUNTIME_RECEIPT_STEP,
    AGENT_RUNTIME_UPLOAD_STEP,
    AGENT_RUNTIME_REPORT_STEP,
    extract_event_paths,
    find_named_step,
    active_step_lines,
    expected_agent_runtime_step_lines,
    agent_runtime_identity_env,
    expected_agent_runtime_receipt_lines,
    expected_agent_runtime_upload_lines,
    expected_agent_runtime_report_lines,
)

def agent_runtime_contract_findings(
    path: Path,
    event_name: str,
    entry_text: str,
    expanded_text: str,
) -> list[str]:
    findings: list[str] = []
    active_paths = extract_event_paths(entry_text, event_name)
    for marker in AGENT_RUNTIME_PATH_MARKERS:
        if marker not in active_paths:
            findings.append(
                f"{path}:1: missing active agent-runtime {event_name} path: {marker}"
            )

    execution_lines: list[int] = []
    for step_name, command, failure_message in AGENT_RUNTIME_VALIDATION_STEPS:
        matches = find_named_step(expanded_text, step_name)
        if len(matches) != 1:
            findings.append(
                f"{path}:1: expected exactly one enabled agent-runtime step named "
                f"{step_name!r}; found {len(matches)}"
            )
            continue
        line_no, body = matches[0]
        execution_lines.append(line_no)
        lines = active_step_lines(body)
        expected_lines = expected_agent_runtime_step_lines(command, failure_message)
        if lines != expected_lines:
            findings.append(
                f"{path}:{line_no}: agent-runtime step {step_name!r} executable body drifted"
            )

    parity_matches = find_named_step(expanded_text, AGENT_RUNTIME_PARITY_REPORT_STEP)
    if len(parity_matches) != 1:
        findings.append(
            f"{path}:1: expected exactly one enabled {AGENT_RUNTIME_PARITY_REPORT_STEP!r} step; "
            f"found {len(parity_matches)}"
        )
    else:
        parity_line, parity_body = parity_matches[0]
        if execution_lines and parity_line <= max(execution_lines):
            findings.append(f"{path}:{parity_line}: parity report must run after self-tests")
        if active_step_lines(parity_body) != expected_agent_runtime_step_lines(
            AGENT_RUNTIME_PARITY_REPORT_COMMAND, AGENT_RUNTIME_PARITY_REPORT_FAILURE
        ):
            findings.append(f"{path}:{parity_line}: parity report step contract drifted")

    receipt_matches = find_named_step(expanded_text, AGENT_RUNTIME_RECEIPT_STEP)
    if len(receipt_matches) != 1:
        findings.append(
            f"{path}:1: expected exactly one enabled {AGENT_RUNTIME_RECEIPT_STEP!r} step; "
            f"found {len(receipt_matches)}"
        )
    else:
        receipt_line, receipt_body = receipt_matches[0]
        receipt_lines = active_step_lines(receipt_body)
        if execution_lines and receipt_line <= max(execution_lines):
            findings.append(
                f"{path}:{receipt_line}: agent-runtime receipt must run after all thirteen validation steps"
            )
        if parity_matches and parity_matches[0][0] <= receipt_line:
            findings.append(
                f"{path}:{receipt_line}: agent-runtime receipt must run before the separate parity report"
            )
        if receipt_lines != expected_agent_runtime_receipt_lines(event_name):
            findings.append(
                f"{path}:{receipt_line}: agent-runtime receipt contract drifted"
            )

    upload_matches = find_named_step(expanded_text, AGENT_RUNTIME_UPLOAD_STEP)
    if len(upload_matches) != 1:
        findings.append(
            f"{path}:1: expected exactly one {AGENT_RUNTIME_UPLOAD_STEP!r} step; "
            f"found {len(upload_matches)}"
        )
    else:
        upload_line, upload_body = upload_matches[0]
        upload_lines = active_step_lines(upload_body)
        if receipt_matches and upload_line <= receipt_matches[0][0]:
            findings.append(
                f"{path}:{upload_line}: validation artifact upload must run after the agent-runtime receipt"
            )
        if upload_lines != expected_agent_runtime_upload_lines(event_name):
            findings.append(
                f"{path}:{upload_line}: validation artifact upload contract drifted"
            )

    report_matches = find_named_step(expanded_text, AGENT_RUNTIME_REPORT_STEP)
    if len(report_matches) != 1:
        findings.append(
            f"{path}:1: expected exactly one {AGENT_RUNTIME_REPORT_STEP!r} step; "
            f"found {len(report_matches)}"
        )
    else:
        report_line, report_body = report_matches[0]
        report_lines = active_step_lines(report_body)
        if upload_matches and report_line <= upload_matches[0][0]:
            findings.append(
                f"{path}:{report_line}: agent-runtime report must run after validation artifact upload"
            )
        if report_lines != expected_agent_runtime_report_lines(event_name):
            findings.append(
                f"{path}:{report_line}: agent-runtime report contract drifted"
            )
    return findings


def run_agent_runtime_contract_selftests() -> list[str]:
    """Exercise the mutation bypasses this audit is intended to block."""
    event_name = "pull_request"
    entry_lines = ["on:", f"  {event_name}:", "    paths:"]
    entry_lines.extend(f"      - '{marker}'" for marker in AGENT_RUNTIME_PATH_MARKERS)
    step_chunks = []
    for step_name, command, failure_message in AGENT_RUNTIME_VALIDATION_STEPS:
        step_chunks.append(
            "\n".join(
                [f"      - name: {step_name}"]
                + [f"        {line}" for line in expected_agent_runtime_step_lines(
                    command, failure_message
                )]
            )
        )
    receipt = "\n".join(
        [f"      - name: {AGENT_RUNTIME_RECEIPT_STEP}"]
        + [f"        {line}" for line in expected_agent_runtime_receipt_lines(event_name)]
    )
    upload = "\n".join(
        [f"      - name: {AGENT_RUNTIME_UPLOAD_STEP}"]
        + [f"        {line}" for line in expected_agent_runtime_upload_lines(event_name)]
    )
    reviewed, _ = agent_runtime_identity_env(event_name)
    report = "\n".join(
        [f"      - name: {AGENT_RUNTIME_REPORT_STEP}"]
        + [f"        {line}" for line in expected_agent_runtime_report_lines(event_name)]
    )
    parity = "\n".join(
        [f"      - name: {AGENT_RUNTIME_PARITY_REPORT_STEP}"]
        + [f"        {line}" for line in expected_agent_runtime_step_lines(
            AGENT_RUNTIME_PARITY_REPORT_COMMAND, AGENT_RUNTIME_PARITY_REPORT_FAILURE
        )]
    )
    entry_text = "\n".join(entry_lines)
    good_expanded = "\n".join(step_chunks + [receipt, parity, upload, report])
    test_path = Path("<agent-runtime-contract-selftest>")
    selftest_findings: list[str] = []
    if agent_runtime_contract_findings(
        test_path, event_name, entry_text, good_expanded
    ):
        selftest_findings.append(
            "agent-runtime workflow contract selftest rejected the valid fixture"
        )

    first_step, first_command, first_failure = AGENT_RUNTIME_VALIDATION_STEPS[0]
    first_throw = f"throw '{first_failure}'"
    receipt_command_lines = "\n".join(
        f"        '{command}'" for _, command, _ in AGENT_RUNTIME_VALIDATION_STEPS
    )
    reversed_receipt_command_lines = "\n".join(
        f"        '{command}'"
        for _, command, _ in reversed(AGENT_RUNTIME_VALIDATION_STEPS)
    )
    mutations = {
        "missing parity report": good_expanded.replace(parity, "", 1),
        "parity report early exit": good_expanded.replace(
            f"        {AGENT_RUNTIME_PARITY_REPORT_COMMAND}",
            f"        exit 0\n        {AGENT_RUNTIME_PARITY_REPORT_COMMAND}",
            1,
        ),
        "parity report before receipt": good_expanded.replace(
            f"{receipt}\n{parity}",
            f"{parity}\n{receipt}",
            1,
        ),
        "receipt-only command": good_expanded.replace(
            f"        {first_command}\n        if ($LASTEXITCODE",
            "        Write-Host 'execution removed'\n        if ($LASTEXITCODE",
            1,
        ),
        "early exit": good_expanded.replace(
            f"        run: |\n        {first_command}",
            f"        run: |\n        exit 0\n        {first_command}",
            1,
        ),
        "false PowerShell branch": good_expanded.replace(
            f"        {first_command}",
            f"        if ($false) {{\n        {first_command}\n        }}",
            1,
        ),
        "detached throw": good_expanded.replace(
            f"        {first_throw}\n        }}",
            "        Write-Warning 'ignored failure'\n        }\n        throw 'unrelated later failure'",
            1,
        ),
        "conditional step": good_expanded.replace(
            f"      - name: {first_step}\n",
            f"      - name: {first_step}\n        if: false\n",
            1,
        ),
        "continue-on-error step": good_expanded.replace(
            f"      - name: {first_step}\n",
            f"      - name: {first_step}\n        continue-on-error: true\n",
            1,
        ),
        "documentary-only receipt": good_expanded.replace(
            "$receipt | ConvertTo-Json -Depth 5 | Set-Content -Path project_sources/validation/out_validate_on_pr_agent_runtime/agent_runtime_validation.json -Encoding utf8",
            "# agent_runtime_validation.json is documented but not written",
            1,
        ),
        "wrong reviewed-head mapping": good_expanded.replace(
            f"AGENT_RUNTIME_REVIEWED_HEAD_SHA: {reviewed}",
            "AGENT_RUNTIME_REVIEWED_HEAD_SHA: deadbeef",
            1,
        ),
        "empty receipt command list": good_expanded.replace(
            receipt_command_lines,
            "        # receipt command list removed",
            1,
        ),
        "reordered receipt command list": good_expanded.replace(
            receipt_command_lines,
            reversed_receipt_command_lines,
            1,
        ),
        "wrong report reviewed-head mapping": good_expanded.replace(
            f"AGENT_RUNTIME_REVIEWED_HEAD_SHA: {reviewed}",
            "AGENT_RUNTIME_REVIEWED_HEAD_SHA: deadbeef",
            2,
        ),
        "omitted receipt artifact glob": good_expanded.replace(
            "        project_sources/validation/out_validate_on_pr_agent_runtime/**\n",
            "",
            1,
        ),
        "wrong primary artifact name": good_expanded.replace(
            "        name: validate-on-pr-results",
            "        name: validate-on-pr-result",
            1,
        ),
        "upload continue-on-error": good_expanded.replace(
            f"      - name: {AGENT_RUNTIME_UPLOAD_STEP}\n",
            f"      - name: {AGENT_RUNTIME_UPLOAD_STEP}\n        continue-on-error: true\n",
            1,
        ),
        "report early exit": good_expanded.replace(
            "        run: |\n        $agentRuntimeReceiptPath",
            "        run: |\n        exit 0\n        $agentRuntimeReceiptPath",
            1,
        ),
    }
    for label, mutated in mutations.items():
        if not agent_runtime_contract_findings(
            test_path, event_name, entry_text, mutated
        ):
            selftest_findings.append(
                f"agent-runtime workflow contract selftest missed {label} mutation"
            )
    commented_entry = entry_text.replace(
        f"      - '{AGENT_RUNTIME_PATH_MARKERS[0]}'",
        f"      # {AGENT_RUNTIME_PATH_MARKERS[0]}",
        1,
    )
    if not agent_runtime_contract_findings(
        test_path, event_name, commented_entry, good_expanded
    ):
        selftest_findings.append(
            "agent-runtime workflow contract selftest missed commented path mutation"
        )
    return selftest_findings
