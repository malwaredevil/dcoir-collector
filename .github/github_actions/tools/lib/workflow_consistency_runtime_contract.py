"""Agent-runtime workflow contract values and expected step bodies."""
from __future__ import annotations
from pathlib import Path

AGENT_RUNTIME_TARGETED_WORKFLOWS = [
    Path(".github/workflows/validate-on-push.yml"),
    Path(".github/workflows/validate-on-pr.yml"),
]

AGENT_RUNTIME_PATH_MARKERS = [
    "project_sources/agent_runtime/**",
    "project_sources/gemini/docs/**",
    "project_sources/gemini/README.md",
    "knowledge/**",
    ".gitattributes",
]

AGENT_RUNTIME_VALIDATION_STEPS = [
    (
        "Validate shared agent source contract",
        "python project_sources/agent_runtime/tools/validate_shared_agent_source_contract.py",
        "Shared agent source contract validation failed.",
    ),
    (
        "Run shared agent source contract self-tests",
        "python project_sources/agent_runtime/tests/validate_shared_agent_source_contract_selftest.py",
        "Shared agent source contract self-tests failed.",
    ),
    (
        "Verify agent behavior adapter materialization",
        "python project_sources/agent_runtime/tools/materialize_agent_behavior_adapters.py --check",
        "Agent behavior adapter materialization check failed.",
    ),
    (
        "Run agent behavior adapter self-tests",
        "python project_sources/agent_runtime/tests/materialize_agent_behavior_adapters_selftest.py",
        "Agent behavior adapter self-tests failed.",
    ),
    (
        "Verify agent knowledge projection",
        "python project_sources/agent_runtime/tools/project_agent_knowledge.py --check",
        "Agent knowledge projection check failed.",
    ),
    (
        "Run agent knowledge projection self-tests",
        "python project_sources/agent_runtime/tests/project_agent_knowledge_selftest.py",
        "Agent knowledge projection self-tests failed.",
    ),
    (
        "Run Gemini Knowledge consolidation evaluation self-tests",
        "python project_sources/agent_runtime/tests/evaluate_gemini_knowledge_consolidation_selftest.py",
        "Gemini Knowledge consolidation evaluation self-tests failed.",
    ),
    (
        "Verify OpenAI DCOIR package materialization",
        "python project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py --check",
        "OpenAI DCOIR package materialization check failed.",
    ),
    (
        "Run OpenAI DCOIR package self-tests",
        "python project_sources/agent_runtime/tests/build_openai_dcoir_analyst_selftest.py",
        "OpenAI DCOIR package self-tests failed.",
    ),
    (
        "Verify OpenAI USB package materialization",
        "python project_sources/agent_runtime/tools/build_openai_usb_reporting.py --check",
        "OpenAI USB package materialization check failed.",
    ),
    (
        "Run OpenAI USB package self-tests",
        "python project_sources/agent_runtime/tests/build_openai_usb_reporting_selftest.py",
        "OpenAI USB package self-tests failed.",
    ),
    (
        "Run USB reporting behavior scorer self-tests",
        "python project_sources/agent_runtime/tests/score_usb_reporting_behavior_selftest.py",
        "USB reporting behavior scorer self-tests failed.",
    ),
    (
        "Run agent release parity self-tests",
        "python project_sources/agent_runtime/tests/report_agent_release_parity_selftest.py",
        "Agent release parity self-tests failed.",
    ),
]

AGENT_RUNTIME_PARITY_REPORT_STEP = "Build unified agent release parity report"
AGENT_RUNTIME_PARITY_REPORT_COMMAND = "python project_sources/agent_runtime/tools/report_agent_release_parity.py"
AGENT_RUNTIME_PARITY_REPORT_FAILURE = "Agent release parity report failed."
AGENT_RUNTIME_RECEIPT_STEP = "Write agent-runtime validation receipt"
AGENT_RUNTIME_UPLOAD_STEP = "Upload validation artifacts"
AGENT_RUNTIME_REPORT_STEP = "Write ChatGPT workflow report section"

def extract_event_paths(text: str, event_name: str) -> list[str]:
    """Return active path-list values for one top-level GitHub event."""
    lines = text.splitlines()
    event_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line == f"  {event_name}:"
        ),
        None,
    )
    if event_index is None:
        return []
    paths_index = next(
        (
            index
            for index in range(event_index + 1, len(lines))
            if lines[index] == "    paths:"
        ),
        None,
    )
    if paths_index is None:
        return []
    values: list[str] = []
    for line in lines[paths_index + 1:]:
        if line and len(line) - len(line.lstrip()) <= 4:
            break
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        value = stripped[2:].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values.append(value)
    return values


def find_named_step(text: str, step_name: str) -> list[tuple[int, str]]:
    """Return line/body pairs for exact named YAML steps at their own indentation."""
    lines = text.splitlines()
    target = f"- name: {step_name}"
    matches: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if line.strip() != target:
            continue
        indent = len(line) - len(line.lstrip())
        end = len(lines)
        for candidate_index in range(index + 1, len(lines)):
            candidate = lines[candidate_index]
            if (
                candidate.strip().startswith("- name: ")
                and len(candidate) - len(candidate.lstrip()) == indent
            ):
                end = candidate_index
                break
        matches.append((index + 1, "\n".join(lines[index + 1:end])))
    return matches


def active_step_lines(body: str) -> list[str]:
    return [
        line.strip()
        for line in body.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def expected_agent_runtime_step_lines(
    command: str, failure_message: str
) -> list[str]:
    return [
        "shell: pwsh",
        "run: |",
        command,
        "if ($LASTEXITCODE -ne 0) {",
        f"throw '{failure_message}'",
        "}",
    ]


def agent_runtime_identity_env(event_name: str) -> tuple[str, str]:
    reviewed = (
        "${{ github.event.pull_request.head.sha || github.sha }}"
        if event_name == "pull_request"
        else "${{ github.sha }}"
    )
    return reviewed, "${{ github.sha }}"


def expected_agent_runtime_receipt_lines(event_name: str) -> list[str]:
    reviewed, tested = agent_runtime_identity_env(event_name)
    lane = "pr" if event_name == "pull_request" else "push"
    workflow = f"validate-on-{lane}"
    output_dir = f"project_sources/validation/out_validate_on_{lane}_agent_runtime"
    lines = [
        "shell: pwsh",
        "env:",
        f"AGENT_RUNTIME_REVIEWED_HEAD_SHA: {reviewed}",
        f"AGENT_RUNTIME_TESTED_COMMIT_SHA: {tested}",
        "run: |",
        "$commands = @(",
    ]
    lines.extend(f"'{command}'" for _, command, _ in AGENT_RUNTIME_VALIDATION_STEPS)
    lines.extend(
        [
            ")",
            "$receipt = [ordered]@{",
            "schema_version = 'dcoir_agent_runtime_validation_workflow_receipt_v1'",
            f"workflow = '{workflow}'",
            "workflow_run_id = $env:GITHUB_RUN_ID",
            "workflow_run_attempt = $env:GITHUB_RUN_ATTEMPT",
            "head_sha = $env:AGENT_RUNTIME_REVIEWED_HEAD_SHA",
            "tested_commit_sha = $env:AGENT_RUNTIME_TESTED_COMMIT_SHA",
            "event_name = $env:GITHUB_EVENT_NAME",
            "documented_contract = 'project_sources/agent_runtime/README.md'",
            "command_count = $commands.Count",
            "commands = @($commands | ForEach-Object { [ordered]@{ command = $_; result = 'pass' } })",
            "}",
            f"New-Item -ItemType Directory -Force -Path {output_dir} | Out-Null",
            "$receipt | ConvertTo-Json -Depth 5 | Set-Content -Path "
            f"{output_dir}/agent_runtime_validation.json -Encoding utf8",
        ]
    )
    return lines


def expected_agent_runtime_upload_lines(event_name: str) -> list[str]:
    lane = "pr" if event_name == "pull_request" else "push"
    return [
        "id: upload_validation_artifacts",
        "if: always()",
        "uses: ./.github/actions/upload-chatgpt-artifact",
        "with:",
        f"name: validate-on-{lane}-results",
        "path: |",
        "project_sources/TestResults/**",
        f"project_sources/validation/out_validate_on_{lane}_gemini/**",
        f"project_sources/validation/out_validate_on_{lane}_agent_runtime/**",
        f"project_sources/validation/out_validate_on_{lane}_collector/**",
        f"project_sources/validation/out_validate_on_{lane}_validate_dcoir_run_fixtures/**",
        "project_sources/validation/out_preflight_documentation_quality/**",
        f"project_sources/validation/out_validate_on_{lane}_documentation_quality/**",
        "project_sources/collector/powershell_analyzer_report.json",
        "project_sources/collector/powershell_duplicate_function_report.json",
        "project_sources/collector/powershell_duplicate_function_report.md",
        "project_sources/collector/powershell_review_assist_workflow_report.json",
        "project_sources/collector/powershell_review_assist_workflow_report.md",
        "if-no-files-found: warn",
        "retention-days: 14",
    ]


def expected_agent_runtime_report_lines(event_name: str) -> list[str]:
    reviewed, tested = agent_runtime_identity_env(event_name)
    lane = "pr" if event_name == "pull_request" else "push"
    additional_output = (
        "collector runtime output"
        if event_name == "pull_request"
        else "collector package smoke-build output"
    )
    artifact_claims = (
        "package, harness, or report-specific claims"
        if event_name == "pull_request"
        else "harness, package, documentation, or report-specific claims"
    )
    return [
        "if: always()",
        "shell: pwsh",
        "env:",
        f"AGENT_RUNTIME_REVIEWED_HEAD_SHA: {reviewed}",
        f"AGENT_RUNTIME_TESTED_COMMIT_SHA: {tested}",
        "AGENT_RUNTIME_ARTIFACT_UPLOAD_OUTCOME: ${{ steps.upload_validation_artifacts.outcome }}",
        "run: |",
        f"$agentRuntimeReceiptPath = 'project_sources/validation/out_validate_on_{lane}_agent_runtime/agent_runtime_validation.json'",
        "if (Test-Path -LiteralPath $agentRuntimeReceiptPath -PathType Leaf) {",
        "if ($env:AGENT_RUNTIME_ARTIFACT_UPLOAD_OUTCOME -eq 'success') {",
        "$agentRuntimeValidation = 'passed_receipt_uploaded'",
        f"$agentRuntimeArtifact = 'agent_runtime_validation.json is included in validate-on-{lane}-results.'",
        "}",
        "else {",
        '$agentRuntimeValidation = "passed_receipt_produced_artifact_upload_$($env:AGENT_RUNTIME_ARTIFACT_UPLOAD_OUTCOME)"',
        "$agentRuntimeArtifact = 'agent_runtime_validation.json was produced locally, but primary artifact upload did not succeed.'",
        "}",
        "}",
        "else {",
        "$agentRuntimeValidation = 'incomplete_or_failed_receipt_not_produced'",
        "$agentRuntimeArtifact = 'agent_runtime_validation.json is absent because the thirteen-command contract did not complete successfully.'",
        "}",
        "New-Item -ItemType Directory -Force -Path chatgpt_workflow_report_section | Out-Null",
        '@"',
        f"- workflow: validate-on-{lane}",
        "- workflow_run_id: $env:GITHUB_RUN_ID",
        "- workflow_run_attempt: $env:GITHUB_RUN_ATTEMPT",
        "- head_sha: $env:AGENT_RUNTIME_REVIEWED_HEAD_SHA",
        "- tested_commit_sha: $env:AGENT_RUNTIME_TESTED_COMMIT_SHA",
        "- ref: $env:GITHUB_REF",
        "- event_name: $env:GITHUB_EVENT_NAME",
        f"- primary_artifact: validate-on-{lane}-results",
        "- artifact_note: includes the agent-runtime validation receipt only when all thirteen commands pass; "
        f"also includes Gemini smoke-build output, {additional_output}, validate_DCOIR_Run fixture output, "
        "documentation-quality output, PSScriptAnalyzer JSON, duplicate-function JSON/Markdown, "
        "PowerShell review-assist JSON/Markdown, and TestResults when produced.",
        "- agent_runtime_validation: $agentRuntimeValidation",
        "- agent_runtime_artifact: $agentRuntimeArtifact",
        "- job_summary: review-assist report written to GITHUB_STEP_SUMMARY.",
        "- duplicate_function_check: emits JSON/Markdown artifacts before the static analysis validation gate blocks merge on any cross-file function name collision in collector source.",
        "- psscriptanalyzer_gate: emits canonical analyzer JSON; the static gate blocks Error findings and unbaselined Warnings from six governed policy rules; incomplete or malformed evidence fails closed.",
        "- static_analysis_gate: runs after static reports are generated so review tooling can consume the evidence artifact even when the gate fails.",
        f"The workflow conclusion is the authoritative pass/fail signal for the {lane.upper() if lane == 'pr' else lane} validation lane. Use artifact readback for {artifact_claims}.",
        '"@ | Set-Content -Path chatgpt_workflow_report_section/chatgpt_workflow_report_section.md -Encoding utf8',
    ]
