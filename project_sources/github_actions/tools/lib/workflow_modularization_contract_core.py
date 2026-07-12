"""Core data checks for workflow modularization contracts."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

WORKFLOW_DIR = Path(".github/workflows")
ACTION_DIR = Path(".github/actions")
CONTRACT_PATH = Path("project_sources/github_actions/workflow_modularization_contracts.json")
INVENTORY_PATH = Path("project_sources/github_actions/workflow_inventory.json")
REPORTER_PATH = Path(".github/workflows/chatgpt-workflow-run-reporter.yml")

REQUIRED_CONTRACT_FIELDS = [
    "file",
    "family",
    "contract_family",
    "target_architecture",
    "migration_status",
    "risk",
    "rollback",
    "acceptance_evidence",
]

ALLOWED_MIGRATION_STATUS = {"planned", "foundation", "active", "intentionally-inline"}
ALLOWED_RISK = {"low", "medium", "high"}
WORKFLOW_NAME_PATTERN = re.compile(
    r"^\d{2} (?:Operator|Validation|Security|Maintenance|Automation|Ops|Reporting|Module|Review) - .+$"
)


def iter_workflow_files() -> list[Path]:
    if not WORKFLOW_DIR.exists():
        return []
    return sorted(
        path for path in WORKFLOW_DIR.iterdir()
        if path.is_file()
        and path.suffix.lower() in {".yml", ".yaml"}
        and not path.name.startswith("reusable-")
    )


def iter_all_workflow_files() -> list[Path]:
    if not WORKFLOW_DIR.exists():
        return []
    return sorted(
        path for path in WORKFLOW_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_exists(findings: list[str], path: Path) -> bool:
    if path.exists():
        return True
    findings.append(f"{path}:1: required workflow modularization surface is missing")
    return False


def extract_workflow_name(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            return stripped.split(":", 1)[1].strip().strip("'\"")
    return None


def check_workflow_names(findings: list[str], workflow_files: list[Path]) -> None:
    for path in workflow_files:
        workflow_name = extract_workflow_name(path)
        if not workflow_name:
            findings.append(f"{path}:1: workflow is missing top-level name")
            continue
        if not WORKFLOW_NAME_PATTERN.fullmatch(workflow_name):
            findings.append(
                f"{path}:1: workflow name must use 'NN Category - Name' format; found {workflow_name!r}"
            )


def check_contract_registry(findings: list[str], contracts: dict[str, Any], workflow_files: list[Path]) -> None:
    expected_count = contracts.get("existing_workflow_count")
    if expected_count != len(workflow_files):
        findings.append(
            f"{CONTRACT_PATH}:1: existing_workflow_count is {expected_count}, but {len(workflow_files)} workflow files were found"
        )

    required_families = set(contracts.get("required_contract_families", []))
    workflow_contracts = contracts.get("workflow_contracts", [])
    if not isinstance(workflow_contracts, list):
        findings.append(f"{CONTRACT_PATH}:1: workflow_contracts must be a list")
        return

    actual_files = {path.as_posix() for path in workflow_files}
    contracted_files: set[str] = set()
    contracted_families: set[str] = set()

    for index, entry in enumerate(workflow_contracts, start=1):
        if not isinstance(entry, dict):
            findings.append(f"{CONTRACT_PATH}:workflow_contracts[{index}]: entry must be an object")
            continue
        for field in REQUIRED_CONTRACT_FIELDS:
            if not entry.get(field):
                findings.append(f"{CONTRACT_PATH}:workflow_contracts[{index}]: missing required field {field}")
        file_name = entry.get("file")
        if file_name:
            contracted_files.add(file_name)
            if file_name not in actual_files:
                findings.append(f"{CONTRACT_PATH}:workflow_contracts[{index}]: contract references missing workflow {file_name}")
        family = entry.get("contract_family")
        if family:
            contracted_families.add(family)
        status = entry.get("migration_status")
        if status and status not in ALLOWED_MIGRATION_STATUS:
            findings.append(f"{CONTRACT_PATH}:workflow_contracts[{index}]: unsupported migration_status {status}")
        risk = entry.get("risk")
        if risk and risk not in ALLOWED_RISK:
            findings.append(f"{CONTRACT_PATH}:workflow_contracts[{index}]: unsupported risk {risk}")

    for missing_file in sorted(actual_files - contracted_files):
        findings.append(f"{CONTRACT_PATH}:1: workflow missing modularization contract: {missing_file}")
    for missing_family in sorted(required_families - contracted_families):
        findings.append(f"{CONTRACT_PATH}:1: required contract family is not mapped by any workflow: {missing_family}")


def check_inventory(findings: list[str], contracts: dict[str, Any], workflow_files: list[Path]) -> None:
    if not ensure_exists(findings, INVENTORY_PATH):
        return
    inventory = load_json(INVENTORY_PATH)
    workflows = inventory.get("workflows", [])
    if len(workflows) != len(workflow_files):
        findings.append(f"{INVENTORY_PATH}:1: inventory has {len(workflows)} workflows, expected {len(workflow_files)}")
    expected_files = {path.as_posix() for path in workflow_files}
    inventoried_files = {entry.get("file") for entry in workflows if isinstance(entry, dict)}
    for missing_file in sorted(expected_files - inventoried_files):
        findings.append(f"{INVENTORY_PATH}:1: workflow missing from generated inventory: {missing_file}")
    contract_by_file = {
        entry["file"]: entry
        for entry in contracts.get("workflow_contracts", [])
        if isinstance(entry, dict) and entry.get("file")
    }
    for entry in workflows:
        if not isinstance(entry, dict):
            continue
        file_name = entry.get("file")
        contract = contract_by_file.get(file_name, {})
        for field in ("contract_family", "migration_status", "risk"):
            if entry.get(field) != contract.get(field):
                findings.append(f"{INVENTORY_PATH}:1: inventory field {field} is stale for {file_name}")
