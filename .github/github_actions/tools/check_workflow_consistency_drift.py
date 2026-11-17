#!/usr/bin/env python3
"""Audit DCOIR workflow surfaces for known consistency drift patterns."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from functools import partial
import json

from lib.workflow_files import iter_workflow_files as _shared_iter_workflow_files
from lib.workflow_files import resolve_action_metadata
from lib.workflow_consistency_runtime_contract import AGENT_RUNTIME_TARGETED_WORKFLOWS
from lib.workflow_consistency_runtime_audit import (
    agent_runtime_contract_findings,
    run_agent_runtime_contract_selftests,
)

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

SHARED_CONTRACT_FILES = [
    Path(REQUIRED_SURFACES_HELPER),
    Path(GEMINI_MANIFEST_HELPER),
    Path(".github/github_actions/tools/test_check_gemini_manifest_surfaces.py"),
    Path(".github/github_actions/workflow_required_surface_profiles.json"),
    Path(".github/github_actions/workflow_required_surface_profile_supplements.json"),
    Path(".github/github_actions/workflow_required_surface_profile_supplements/event_text_query_bound_policy.json"),
    Path(".github/github_actions/workflow_required_surface_profile_supplements/powershell_surface_inventory.json"),
    Path(".github/github_actions/workflow_required_surface_profile_supplements/path_safety.json"),
    Path(".github/github_actions/tools/build_workflow_inventory.py"),
    Path(".github/github_actions/tools/check_workflow_modularization_contracts.py"),
    Path(".github/github_actions/tools/audit_reusable_contracts.py"),
    Path(".github/github_actions/workflow_modularization_contracts.json"),
    Path(".github/github_actions/workflow_inventory.json"),
    Path(".github/github_actions/workflow_inventory.md"),
]

LOCAL_USES_RE = re.compile(r"^\./\.github/(workflows/[^@\s#]+|actions/[^@\s#]+)")


class WorkflowYamlError(Exception):
    def __init__(self, path: Path, cause: str) -> None:
        self.path = path
        self.cause = cause
        super().__init__(f"{path}: invalid YAML: {cause}")


iter_workflow_files = partial(_shared_iter_workflow_files, WORKFLOW_DIR)


def find_lines_with_substring(path: Path, needle: str) -> list[int]:
    return [
        line_no
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if needle in line
    ]


def _strip_yaml_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if quote == '"' and char == "\\" and not escaped:
            escaped = True
            continue
        if char in {"'", '"'} and not escaped:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
        elif char == "#" and quote is None and (index == 0 or line[index - 1].isspace()):
            return line[:index]
        escaped = False
    return line


def _yaml_scalar(value: str) -> str:
    value = _strip_yaml_comment(value).strip()
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    return value


def local_uses_references(text: str, path: Path) -> list[str]:
    """Return local references from workflow jobs and composite-action steps."""
    references: list[str] = []
    entry_re = re.compile(r"^(?P<indent> *)(?P<sequence>-\s+)?(?P<key>[A-Za-z_][\w.-]*):(?:\s*(?P<value>.*))?$")
    block_scalar_re = re.compile(r"^[|>](?:[+-]?[1-9]?|[1-9]?[+-]?)?$")
    section: str | None = None
    job_indent: int | None = None
    job_field_indent: int | None = None
    job_steps_indent: int | None = None
    job_step_indent: int | None = None
    runs_field_indent: int | None = None
    runs_steps_indent: int | None = None
    runs_step_indent: int | None = None
    composite_action = False
    block_scalar_indent: int | None = None
    flow_stack: list[tuple[str, int]] = []
    flow_openers = {"[": "]", "{": "}"}

    def check_flow(value: str, line_number: int) -> None:
        quote: str | None = None
        escaped = False
        for char in value:
            if quote == '"' and char == "\\" and not escaped:
                escaped = True
                continue
            if char in {"'", '"'} and not escaped:
                if quote is None:
                    quote = char
                elif quote == char:
                    quote = None
            elif quote is None:
                if char in flow_openers:
                    flow_stack.append((flow_openers[char], line_number))
                elif char in {"]", "}"}:
                    if not flow_stack or flow_stack[-1][0] != char:
                        raise WorkflowYamlError(path, f"unexpected {char!r} on line {line_number}")
                    flow_stack.pop()
            escaped = False

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if "\t" in raw_line[:indent + 1]:
            raise WorkflowYamlError(path, f"tab indentation on line {line_number}")
        line = _strip_yaml_comment(raw_line).rstrip()
        if block_scalar_indent is not None:
            if not line.strip() or indent > block_scalar_indent:
                continue
            block_scalar_indent = None
        if not line.strip():
            continue
        match = entry_re.match(line)
        if not match:
            if flow_stack:
                check_flow(line.strip(), line_number)
            continue

        indent = len(match.group("indent"))
        sequence = match.group("sequence") is not None
        key_indent = indent + (2 if sequence else 0)
        key = match.group("key")
        raw_value = match.group("value") or ""
        value = _yaml_scalar(raw_value)
        if block_scalar_re.fullmatch(value):
            block_scalar_indent = key_indent

        if flow_stack:
            check_flow(line.strip(), line_number)
        elif value.startswith(("[", "{")):
            check_flow(value, line_number)

        if indent == 0 and not sequence:
            section = key if key in {"jobs", "runs"} else None
            job_indent = None
            job_field_indent = None
            job_steps_indent = None
            job_step_indent = None
            runs_field_indent = None
            runs_steps_indent = None
            runs_step_indent = None
            composite_action = False
            continue

        if section == "jobs":
            if not sequence and value == "" and indent > 0 and (
                job_indent is None or indent <= job_indent
            ):
                job_indent = indent
                job_field_indent = None
                job_steps_indent = None
                job_step_indent = None
                continue
            if job_indent is None:
                continue
            if not sequence and indent > job_indent:
                if job_field_indent is None:
                    job_field_indent = indent
                if indent == job_field_indent:
                    job_step_indent = None
                    if key == "uses":
                        if value:
                            references.append(value)
                    job_steps_indent = indent if key == "steps" else None
                    continue
            if job_steps_indent is not None and indent >= job_steps_indent:
                if sequence:
                    job_step_indent = indent
                    if key == "uses":
                        if value:
                            references.append(value)
                elif job_step_indent is not None and key_indent == job_step_indent + 2 and key == "uses":
                    if value:
                        references.append(value)
            continue

        if section == "runs":
            if not sequence and indent > 0:
                if runs_field_indent is None:
                    runs_field_indent = indent
                if indent == runs_field_indent:
                    runs_step_indent = None
                    if key == "using":
                        composite_action = value == "composite"
                    if key == "steps":
                        runs_steps_indent = indent
                    continue
            if runs_steps_indent is not None and indent >= runs_steps_indent:
                if sequence:
                    runs_step_indent = indent
                    if key == "uses":
                        if value:
                            references.append(value)
                elif (
                    runs_step_indent is not None
                    and key_indent == runs_step_indent + 2
                    and key == "uses"
                ):
                    if value:
                        references.append(value)

    if flow_stack:
        _, line_number = flow_stack[-1]
        raise WorkflowYamlError(path, f"unclosed flow collection starting on line {line_number}")
    return references


def expanded_local_text(path: Path, seen: set[Path] | None = None) -> str:
    """Return workflow text plus local reusable workflow/action bodies it calls."""
    seen = seen or set()
    if path in seen or not path.exists():
        return ""
    seen.add(path)
    text = path.read_text(encoding="utf-8")
    chunks = [text]
    for candidate in local_uses_references(text, path):
        match = LOCAL_USES_RE.match(candidate)
        if not match:
            continue
        ref = f"./.github/{match.group(1)}"
        target = Path(ref.removeprefix("./"))
        if "/actions/" in ref:
            metadata = resolve_action_metadata(target)
            if metadata is None:
                continue
            target = metadata
        chunks.append(expanded_local_text(target, seen))
    return "\n".join(chunks)


def expanded_local_text_or_findings(path: Path, findings: list[str]) -> str:
    try:
        return expanded_local_text(path)
    except WorkflowYamlError as exc:
        findings.append(f"{exc.path}:1: invalid YAML: {exc.cause}")
        return ""


def add_string_findings(findings: list[str], path: Path, needle: str) -> None:
    for line_no in find_lines_with_substring(path, needle):
        findings.append(f"{path}:{line_no}: forbidden workflow consistency drift marker present: {needle}")


def ensure_exists(findings: list[str], path: Path) -> bool:
    if path.exists():
        return True
    findings.append(f"{path}:1: required workflow maintenance contract file is missing")
    return False


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
        text = expanded_local_text_or_findings(path, findings)
        if REQUIRED_SURFACES_HELPER not in text:
            findings.append(f"{path}:1: missing required shared required-surface helper call: {REQUIRED_SURFACES_HELPER}")
        add_string_findings(findings, path, INLINE_REQUIRED_MARKER)

    for path in GEMINI_TARGETED_WORKFLOWS:
        if not ensure_exists(findings, path):
            continue
        text = expanded_local_text_or_findings(path, findings)
        if GEMINI_MANIFEST_HELPER not in text:
            findings.append(f"{path}:1: missing required shared Gemini manifest helper call: {GEMINI_MANIFEST_HELPER}")
        for needle in INLINE_GEMINI_MARKERS:
            add_string_findings(findings, path, needle)

    for path in AGENT_RUNTIME_TARGETED_WORKFLOWS:
        if not ensure_exists(findings, path):
            continue
        entry_text = path.read_text(encoding="utf-8")
        expanded_text = expanded_local_text_or_findings(path, findings)
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
