"""Core workflow inventory parsing and model construction."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

WORKFLOW_DIR = Path(".github/workflows")
CONTRACT_PATH = Path("project_sources/github_actions/workflow_modularization_contracts.json")
DEFAULT_JSON_OUTPUT = Path("project_sources/github_actions/workflow_inventory.json")
DEFAULT_MARKDOWN_OUTPUT = Path("project_sources/github_actions/workflow_inventory.md")

SECRET_RE = re.compile(r"(?:secrets|vars)\.([A-Za-z_][A-Za-z0-9_]*)")
LOCAL_REUSABLE_RE = re.compile(r"^\s*uses:\s*(\./\.github/workflows/[^@\s#]+)", re.IGNORECASE | re.MULTILINE)
SCHEDULE_RE = re.compile(r"cron:\s*['\"]?([^'\"]+)")


def read_contracts() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def iter_workflow_files() -> list[Path]:
    if not WORKFLOW_DIR.exists():
        return []
    return sorted(
        path for path in WORKFLOW_DIR.iterdir()
        if path.is_file()
        and path.suffix.lower() in {".yml", ".yaml"}
        and not path.name.startswith("reusable-")
    )


def top_level_key(line: str) -> str | None:
    if not line or line.startswith((" ", "\t", "#")):
        return None
    if ":" not in line:
        return None
    return line.split(":", 1)[0].strip()


def scalar_after_colon(line: str) -> str | None:
    if ":" not in line:
        return None
    value = line.split(":", 1)[1].strip()
    if not value:
        return None
    return value.strip("'\"")


def collect_top_level_block(lines: list[str], key: str) -> list[str]:
    block: list[str] = []
    in_block = False
    for line in lines:
        current_key = top_level_key(line)
        if current_key == key:
            in_block = True
            block.append(line)
            continue
        if in_block and current_key is not None:
            break
        if in_block:
            block.append(line)
    return block


def collect_header(lines: list[str]) -> list[str]:
    header: list[str] = []
    for line in lines:
        if line.startswith("#") or not line.strip():
            header.append(line)
            continue
        break
    return header


def extract_header_field(header: list[str], field: str) -> str | None:
    marker = f"# {field}:"
    for index, line in enumerate(header):
        if line.strip() == marker:
            values: list[str] = []
            for follow in header[index + 1:]:
                stripped = follow.strip()
                if stripped.startswith("# - "):
                    values.append(stripped[4:].strip())
                    continue
                if stripped.startswith("#") and stripped.endswith(":"):
                    break
                if stripped and not stripped.startswith("#"):
                    break
            return "; ".join(values) if values else None
    return None


def extract_triggers(lines: list[str]) -> dict[str, Any]:
    block = collect_top_level_block(lines, "on")
    triggers: set[str] = set()
    schedules: list[str] = []
    if not block:
        return {"events": [], "schedules": []}
    first_value = scalar_after_colon(block[0])
    if first_value:
        if first_value.startswith("[") and first_value.endswith("]"):
            for item in first_value.strip("[]").split(","):
                candidate = item.strip().strip("'\"")
                if candidate:
                    triggers.add(candidate)
        else:
            triggers.add(first_value)
    for line in block[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("  ") and not line.startswith("    ") and stripped.startswith("- "):
            candidate = stripped[2:].split(":", 1)[0].strip()
            if candidate and candidate != "cron":
                triggers.add(candidate)
        elif line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            candidate = stripped[:-1].strip()
            if candidate and candidate != "cron":
                triggers.add(candidate)
        elif line.startswith("  ") and not line.startswith("    ") and ":" in stripped:
            candidate = stripped.split(":", 1)[0].strip()
            if candidate and candidate != "cron":
                triggers.add(candidate)
        cron_match = SCHEDULE_RE.search(stripped)
        if cron_match:
            schedules.append(cron_match.group(1))
    return {"events": sorted(triggers), "schedules": sorted(set(schedules))}


def extract_permissions(lines: list[str]) -> dict[str, str] | str | None:
    block = collect_top_level_block(lines, "permissions")
    if not block:
        return None
    first_value = scalar_after_colon(block[0])
    if first_value:
        return first_value
    permissions: dict[str, str] = {}
    for line in block[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        name, value = stripped.split(":", 1)
        permissions[name.strip()] = value.strip().strip("'\"")
    return permissions or None


def extract_artifact_names(lines: list[str]) -> list[str]:
    artifacts: set[str] = set()
    for index, line in enumerate(lines):
        if (
            "actions/upload-artifact" not in line
            and "actions/download-artifact" not in line
            and "./.github/actions/upload-chatgpt-artifact" not in line
        ):
            continue
        for follow in lines[index + 1:index + 12]:
            stripped = follow.strip()
            if stripped.startswith("name:"):
                value = stripped.split(":", 1)[1].strip().strip("'\"")
                if value:
                    artifacts.add(value)
                break
    return sorted(artifacts)


def classify_report_family(path: Path, text: str) -> str:
    if "chatgpt_staging/status_reports/repo-workflows/" in text:
        return "repo-workflows completed summary"
    if "latest_progress_marker.json" in text or "progress_history.jsonl" in text:
        return "live heartbeat"
    if "chatgpt-workflow-report-section" in text:
        return "chatgpt workflow report section"
    if "workflow_report.md" in text:
        return "standalone workflow report"
    if path.name.startswith("ops-"):
        return "central reporter only when applicable"
    return "none declared"


def expanded_workflow_text(path: Path, seen: set[Path] | None = None) -> str:
    seen = seen or set()
    if path in seen or not path.exists():
        return ""
    seen.add(path)
    text = path.read_text(encoding="utf-8")
    chunks = [text]
    for match in LOCAL_REUSABLE_RE.finditer(text):
        target = Path(match.group(1).removeprefix("./"))
        chunks.append(expanded_workflow_text(target, seen))
    return "\n".join(chunks)


def workflow_entry(path: Path, contract_by_file: dict[str, dict[str, Any]]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    expanded_text = expanded_workflow_text(path)
    lines = text.splitlines()
    expanded_lines = expanded_text.splitlines()
    header = collect_header(lines)
    contract = contract_by_file.get(path.as_posix(), {})
    secrets = sorted({match.group(1) for match in SECRET_RE.finditer(text)})
    trigger_info = extract_triggers(lines)
    return {
        "file": path.as_posix(),
        "workflow_name": next(
            (scalar_after_colon(line) for line in lines if top_level_key(line) == "name"),
            None,
        ),
        "operator_purpose": extract_header_field(header, "Purpose"),
        "trigger_events": trigger_info["events"],
        "schedules": trigger_info["schedules"],
        "permissions": extract_permissions(lines),
        "concurrency_declared": bool(collect_top_level_block(lines, "concurrency")),
        "secret_or_var_count": len(secrets),
        "artifacts": extract_artifact_names(expanded_lines),
        "report_family": classify_report_family(path, expanded_text),
        "contract_family": contract.get("contract_family"),
        "migration_status": contract.get("migration_status"),
        "risk": contract.get("risk"),
    }


def build_inventory() -> dict[str, Any]:
    contracts = read_contracts()
    contract_by_file = {
        entry["file"]: entry
        for entry in contracts.get("workflow_contracts", [])
    }
    workflows = [workflow_entry(path, contract_by_file) for path in iter_workflow_files()]
    reusable_workflows = sorted(WORKFLOW_DIR.glob("reusable-*.yml")) if WORKFLOW_DIR.exists() else []
    composite_actions = sorted(Path(".github/actions").glob("*/action.yml"))
    action_call_sources = iter_workflow_files() + reusable_workflows + composite_actions
    local_reusable_calls = sum(
        1
        for path in iter_workflow_files() + reusable_workflows
        for line in path.read_text(encoding="utf-8").splitlines()
        if "uses: ./.github/workflows/reusable-" in line
    )
    local_action_calls = sum(
        1
        for path in action_call_sources
        for line in path.read_text(encoding="utf-8").splitlines()
        if "uses: ./.github/actions/" in line
    )
    return {
        "schema_version": "dcoir_workflow_inventory_v1",
        "governing_issue": contracts.get("governing_issue"),
        "existing_workflow_count_expected": contracts.get("existing_workflow_count"),
        "workflow_count": len(workflows),
        "reusable_workflow_count": len(reusable_workflows),
        "composite_action_count": len(composite_actions),
        "local_reusable_workflow_calls": local_reusable_calls,
        "local_composite_action_calls": local_action_calls,
        "contract_registry": CONTRACT_PATH.as_posix(),
        "workflows": workflows,
    }
