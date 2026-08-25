#!/usr/bin/env python3
"""Audit DCOIR workflow surfaces for known consistency drift patterns."""
from __future__ import annotations

import re
import sys
from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")
WORKFLOW_GUIDANCE_PATHS = [
    Path(".github/github_actions/README.md"),
    Path(".github/README.md"),
]

STALE_AUTHORITY_STRINGS = [
    "Airtable formula preview",
    "table autonumber suffix",
    "Keep the Airtable GitHub Workflow Inventory row aligned",
    "Airtable routing:",
    "GitHub Workflow Inventory",
]

REQUIRED_SURFACES_HELPER = ".github/github_actions/tools/check_required_surfaces.py"
GEMINI_MANIFEST_HELPER = ".github/github_actions/tools/check_gemini_manifest_surfaces.py"
INLINE_REQUIRED_MARKER = "$required = @(" 
INLINE_GEMINI_MARKERS = [
    "Missing Gemini manifest-required/source-required surfaces",
    "Gemini manifest topology.sub_agent_files is empty.",
    "Discovered Gemini sub-agent files not listed in manifest topology",
    "topology_source_of_truth",
]

TARGETED_WORKFLOWS = [
    Path(".github/workflows/validate-on-push.yml"),
    Path(".github/workflows/validate-on-pr.yml"),
    Path(".github/workflows/manual-full-validation.yml"),
    Path(".github/workflows/scheduled-health-check.yml"),
    Path(".github/workflows/manual-gemini-bundle-build.yml"),
    Path(".github/workflows/manual-collector-runtime-package-build.yml"),
]

GEMINI_TARGETED_WORKFLOWS = [
    Path(".github/workflows/validate-on-push.yml"),
    Path(".github/workflows/validate-on-pr.yml"),
    Path(".github/workflows/manual-full-validation.yml"),
    Path(".github/workflows/scheduled-health-check.yml"),
    Path(".github/workflows/manual-gemini-bundle-build.yml"),
]

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
    ),
    (
        "Run shared agent source contract self-tests",
        "python project_sources/agent_runtime/tests/validate_shared_agent_source_contract_selftest.py",
    ),
    (
        "Verify agent behavior adapter materialization",
        "python project_sources/agent_runtime/tools/materialize_agent_behavior_adapters.py --check",
    ),
    (
        "Run agent behavior adapter self-tests",
        "python project_sources/agent_runtime/tests/materialize_agent_behavior_adapters_selftest.py",
    ),
    (
        "Verify agent knowledge projection",
        "python project_sources/agent_runtime/tools/project_agent_knowledge.py --check",
    ),
    (
        "Run agent knowledge projection self-tests",
        "python project_sources/agent_runtime/tests/project_agent_knowledge_selftest.py",
    ),
    (
        "Verify OpenAI DCOIR package materialization",
        "python project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py --check",
    ),
    (
        "Run OpenAI DCOIR package self-tests",
        "python project_sources/agent_runtime/tests/build_openai_dcoir_analyst_selftest.py",
    ),
]

AGENT_RUNTIME_RECEIPT_STEP = "Write agent-runtime validation receipt"
AGENT_RUNTIME_RECEIPT_WRITER_MARKER = (
    "$receipt | ConvertTo-Json -Depth 5 | Set-Content -Path "
)

SHARED_CONTRACT_FILES = [
    Path(REQUIRED_SURFACES_HELPER),
    Path(GEMINI_MANIFEST_HELPER),
    Path(".github/github_actions/workflow_required_surface_profiles.json"),
    Path(".github/github_actions/workflow_required_surface_profile_supplements.json"),
    Path(".github/github_actions/workflow_required_surface_profile_supplements/event_text_query_bound_policy.json"),
    Path(".github/github_actions/workflow_required_surface_profile_supplements/powershell_surface_inventory.json"),
    Path(".github/github_actions/tools/build_workflow_inventory.py"),
    Path(".github/github_actions/tools/check_workflow_modularization_contracts.py"),
    Path(".github/github_actions/tools/generate_workflow_inventory.py"),
    Path(".github/github_actions/tools/audit_reusable_contracts.py"),
    Path(".github/github_actions/workflow_modularization_contracts.json"),
    Path(".github/github_actions/workflow_inventory.json"),
    Path(".github/github_actions/workflow_inventory.md"),
]

LOCAL_USES_RE = re.compile(r"^\s*uses:\s*(\./\.github/(?:workflows/[^@\s#]+|actions/[^@\s#]+))", re.MULTILINE)


def iter_workflow_files() -> list[Path]:
    if not WORKFLOW_DIR.exists():
        return []
    return sorted(
        path for path in WORKFLOW_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
    )


def find_lines_with_substring(path: Path, needle: str) -> list[int]:
    return [
        line_no
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if needle in line
    ]


def expanded_local_text(path: Path, seen: set[Path] | None = None) -> str:
    """Return workflow text plus local reusable workflow/action bodies it calls."""
    seen = seen or set()
    if path in seen or not path.exists():
        return ""
    seen.add(path)
    text = path.read_text(encoding="utf-8")
    chunks = [text]
    for match in LOCAL_USES_RE.finditer(text):
        ref = match.group(1)
        target = Path(ref.removeprefix("./"))
        if "/actions/" in ref:
            target = target / "action.yml"
        chunks.append(expanded_local_text(target, seen))
    return "\n".join(chunks)


def add_string_findings(findings: list[str], path: Path, needle: str) -> None:
    for line_no in find_lines_with_substring(path, needle):
        findings.append(f"{path}:{line_no}: forbidden workflow consistency drift marker present: {needle}")


def ensure_exists(findings: list[str], path: Path) -> bool:
    if path.exists():
        return True
    findings.append(f"{path}:1: required workflow maintenance contract file is missing")
    return False


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
    for step_name, command in AGENT_RUNTIME_VALIDATION_STEPS:
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
        if "shell: pwsh" not in lines or "run: |" not in lines:
            findings.append(
                f"{path}:{line_no}: agent-runtime step {step_name!r} must execute in pwsh"
            )
        if command not in lines:
            findings.append(
                f"{path}:{line_no}: agent-runtime step {step_name!r} does not execute: {command}"
            )
        if "if ($LASTEXITCODE -ne 0) {" not in lines or not any(
            line.startswith("throw ") for line in lines
        ):
            findings.append(
                f"{path}:{line_no}: agent-runtime step {step_name!r} lacks fail-closed exit handling"
            )
        if any(
            line.startswith("if:") or line.startswith("continue-on-error:")
            for line in lines
        ):
            findings.append(
                f"{path}:{line_no}: agent-runtime step {step_name!r} must not be conditional or continue on error"
            )

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
                f"{path}:{receipt_line}: agent-runtime receipt must run after all eight validation steps"
            )
        if "shell: pwsh" not in receipt_lines or "run: |" not in receipt_lines:
            findings.append(
                f"{path}:{receipt_line}: agent-runtime receipt step must execute in pwsh"
            )
        if any(
            line.startswith("if:") or line.startswith("continue-on-error:")
            for line in receipt_lines
        ):
            findings.append(
                f"{path}:{receipt_line}: agent-runtime receipt step must remain success-gated"
            )
        if not any(
            AGENT_RUNTIME_RECEIPT_WRITER_MARKER in line
            and "agent_runtime_validation.json" in line
            for line in receipt_lines
        ):
            findings.append(
                f"{path}:{receipt_line}: agent-runtime receipt writer is missing"
            )
        for marker in (
            "head_sha = $env:AGENT_RUNTIME_REVIEWED_HEAD_SHA",
            "tested_commit_sha = $env:AGENT_RUNTIME_TESTED_COMMIT_SHA",
        ):
            if marker not in receipt_lines:
                findings.append(
                    f"{path}:{receipt_line}: agent-runtime receipt lacks identity marker: {marker}"
                )
    return findings


def run_agent_runtime_contract_selftests() -> list[str]:
    """Exercise the mutation bypasses this audit is intended to block."""
    event_name = "pull_request"
    entry_lines = ["on:", f"  {event_name}:", "    paths:"]
    entry_lines.extend(f"      - '{marker}'" for marker in AGENT_RUNTIME_PATH_MARKERS)
    step_chunks = []
    for step_name, command in AGENT_RUNTIME_VALIDATION_STEPS:
        step_chunks.append(
            "\n".join(
                [
                    f"      - name: {step_name}",
                    "        shell: pwsh",
                    "        run: |",
                    f"          {command}",
                    "          if ($LASTEXITCODE -ne 0) {",
                    "            throw 'validation failed'",
                    "          }",
                ]
            )
        )
    receipt_commands = "\n".join(
        f"            '{command}'" for _, command in AGENT_RUNTIME_VALIDATION_STEPS
    )
    receipt = "\n".join(
        [
            f"      - name: {AGENT_RUNTIME_RECEIPT_STEP}",
            "        shell: pwsh",
            "        run: |",
            "          $commands = @(",
            receipt_commands,
            "          )",
            "          $receipt = [ordered]@{",
            "            head_sha = $env:AGENT_RUNTIME_REVIEWED_HEAD_SHA",
            "            tested_commit_sha = $env:AGENT_RUNTIME_TESTED_COMMIT_SHA",
            "          }",
            "          $receipt | ConvertTo-Json -Depth 5 | Set-Content -Path out/agent_runtime_validation.json",
        ]
    )
    entry_text = "\n".join(entry_lines)
    good_expanded = "\n".join(step_chunks + [receipt])
    test_path = Path("<agent-runtime-contract-selftest>")
    selftest_findings: list[str] = []
    if agent_runtime_contract_findings(
        test_path, event_name, entry_text, good_expanded
    ):
        selftest_findings.append(
            "agent-runtime workflow contract selftest rejected the valid fixture"
        )

    first_step, first_command = AGENT_RUNTIME_VALIDATION_STEPS[0]
    mutations = {
        "receipt-only command": good_expanded.replace(
            f"          {first_command}\n          if ($LASTEXITCODE",
            "          Write-Host 'execution removed'\n          if ($LASTEXITCODE",
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
            "$receipt | ConvertTo-Json -Depth 5 | Set-Content -Path out/agent_runtime_validation.json",
            "# agent_runtime_validation.json is documented but not written",
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


def main() -> int:
    findings: list[str] = run_agent_runtime_contract_selftests()
    workflow_files = iter_workflow_files()
    if not workflow_files:
        print("No workflow files found.")
        return 0

    for contract_path in SHARED_CONTRACT_FILES:
        ensure_exists(findings, contract_path)

    authority_scan_paths = workflow_files + WORKFLOW_GUIDANCE_PATHS
    for path in authority_scan_paths:
        if not ensure_exists(findings, path):
            continue
        for needle in STALE_AUTHORITY_STRINGS:
            add_string_findings(findings, path, needle)

    for path in TARGETED_WORKFLOWS:
        if not ensure_exists(findings, path):
            continue
        text = expanded_local_text(path)
        if REQUIRED_SURFACES_HELPER not in text:
            findings.append(f"{path}:1: missing required shared required-surface helper call: {REQUIRED_SURFACES_HELPER}")
        add_string_findings(findings, path, INLINE_REQUIRED_MARKER)

    for path in GEMINI_TARGETED_WORKFLOWS:
        if not ensure_exists(findings, path):
            continue
        text = expanded_local_text(path)
        if GEMINI_MANIFEST_HELPER not in text:
            findings.append(f"{path}:1: missing required shared Gemini manifest helper call: {GEMINI_MANIFEST_HELPER}")
        for needle in INLINE_GEMINI_MARKERS:
            add_string_findings(findings, path, needle)

    for path in AGENT_RUNTIME_TARGETED_WORKFLOWS:
        if not ensure_exists(findings, path):
            continue
        entry_text = path.read_text(encoding="utf-8")
        expanded_text = expanded_local_text(path)
        event_name = "push" if path.name == "validate-on-push.yml" else "pull_request"
        findings.extend(
            agent_runtime_contract_findings(
                path, event_name, entry_text, expanded_text
            )
        )

    if findings:
        print("Workflow consistency drift audit failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print(
        "Workflow consistency drift audit passed for "
        f"{len(workflow_files)} workflow files and "
        f"{', '.join(path.as_posix() for path in WORKFLOW_GUIDANCE_PATHS)}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
