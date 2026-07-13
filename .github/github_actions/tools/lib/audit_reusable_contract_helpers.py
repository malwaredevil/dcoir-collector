"""Helpers for reusable workflow and composite action contract audits."""
from __future__ import annotations

import re
from pathlib import Path

WORKFLOW_DIR = Path(".github/workflows")
ACTION_DIR = Path(".github/actions")
EXPECTED_PRIMARY_WORKFLOW_COUNT = 29

USES_RE = re.compile(r"^\s*uses:\s*([^\s#]+)", re.IGNORECASE)
COMPOSITE_USING_RE = re.compile(r"^\s*using:\s*['\"]?composite['\"]?\s*$", re.IGNORECASE | re.MULTILINE)
PERMISSION_ORDER = {"none": 0, "read": 1, "write": 2}
DOUBLE_QUOTED_EXPRESSION_LITERAL_RE = re.compile(r"\$\{\{[^}]*\|\|\s*\"[^\"]*\"[^}]*\}\}")
BARE_INPUT_FORWARD_RE = re.compile(r"\$\{\{\s*inputs\.[A-Za-z0-9_-]+\s*\}\}")


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_workflow_call_contract(path: Path) -> tuple[set[str], set[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    inputs: set[str] = set()
    secrets: set[str] = set()
    in_workflow_call = False
    section: str | None = None
    section_indent = 0
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if stripped == "workflow_call:":
            in_workflow_call = True
            section = None
            continue
        if not in_workflow_call:
            continue
        if stripped in {"inputs:", "secrets:"}:
            section = stripped[:-1]
            section_indent = indent
            continue
        if section and stripped and indent <= section_indent:
            section = None
        if section in {"inputs", "secrets"} and indent == section_indent + 2 and stripped.endswith(":"):
            name = stripped[:-1].strip().strip("'\"")
            if name != "{}":
                (inputs if section == "inputs" else secrets).add(name)
    return inputs, secrets


def collect_mapping_after(lines: list[str], start_index: int, key: str) -> set[str]:
    names: set[str] = set()
    key_indent: int | None = None
    for index in range(start_index, len(lines)):
        line = lines[index]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if key_indent is None:
            if stripped == f"{key}:":
                key_indent = indent
            continue
        if stripped and indent <= key_indent:
            break
        if indent == key_indent + 2 and ":" in stripped:
            names.add(stripped.split(":", 1)[0].strip().strip("'\""))
    return names


def collect_mapping_values_after(lines: list[str], start_index: int, key: str) -> dict[str, str]:
    values: dict[str, str] = {}
    key_indent: int | None = None
    for index in range(start_index, len(lines)):
        line = lines[index]
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if key_indent is None:
            if stripped == f"{key}:":
                key_indent = indent
            continue
        if stripped and indent <= key_indent:
            break
        if indent == key_indent + 2 and ":" in stripped:
            name, value = stripped.split(":", 1)
            values[name.strip().strip("'\"")] = strip_quotes(value.strip())
    return values


def find_mapping_headers(lines: list[str], key: str) -> list[int]:
    return [index for index, line in enumerate(lines) if line.strip() == f"{key}:"]


def permission_satisfies(actual: str | None, required: str) -> bool:
    if actual is None:
        return False
    actual_normalized = strip_quotes(actual).lower()
    required_normalized = required.lower()
    if actual_normalized in {"read-all", "write-all"}:
        return permission_satisfies(actual_normalized.split("-", 1)[0], required_normalized)
    return PERMISSION_ORDER.get(actual_normalized, -1) >= PERMISSION_ORDER[required_normalized]


def required_permissions_for_text(text: str) -> dict[str, str]:
    required: dict[str, str] = {}

    def require(scope: str, level: str) -> None:
        current = required.get(scope)
        if current is None or PERMISSION_ORDER[level] > PERMISSION_ORDER[current]:
            required[scope] = level

    uses_external_wiki_push_token = "DCOIR_WIKI_PUSH_TOKEN" in text and "wiki_url" in text
    if (
        "Invoke-ChatGptReportPush.ps1" in text
        or (re.search(r"\bgit\s+push\b", text) and not uses_external_wiki_push_token)
    ):
        require("contents", "write")
    if re.search(r"\bgh\s+pr\s+merge\b", text):
        require("contents", "write")
        require("pull-requests", "write")
    if "actions/download-artifact@" in text or re.search(r"\bgh\s+run\s+download\b", text):
        require("actions", "read")
    return required


def declares_workflow_call_github_token_secret(text: str) -> bool:
    in_workflow_call = False
    in_secrets = False
    secrets_indent = 0
    for line in text.splitlines():
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if stripped == "workflow_call:":
            in_workflow_call = True
            in_secrets = False
            continue
        if not in_workflow_call:
            continue
        if stripped == "secrets:":
            in_secrets = True
            secrets_indent = indent
            continue
        if in_secrets:
            if stripped and indent <= secrets_indent:
                in_secrets = False
            elif indent == secrets_indent + 2 and stripped.startswith("GITHUB_TOKEN:"):
                return True
    return False


def rel(path: Path, repo_root: Path) -> str:
    if path.is_absolute():
        return path.relative_to(repo_root).as_posix()
    return path.as_posix()


def iter_action_metadata_files(repo_root: Path) -> list[Path]:
    action_dir = repo_root / ACTION_DIR
    if not action_dir.exists():
        return []
    return sorted(
        path for path in action_dir.rglob("*")
        if path.is_file() and path.name.lower() in {"action.yml", "action.yaml"}
    )


def iter_all_workflow_files(repo_root: Path) -> list[Path]:
    workflow_dir = repo_root / WORKFLOW_DIR
    if not workflow_dir.exists():
        return []
    return sorted(
        path for path in workflow_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
    )


def local_uses_refs(source_files: list[Path]) -> tuple[list[tuple[Path, int, str]], list[tuple[Path, int, str]], list[tuple[Path, int, str]]]:
    workflow_refs: list[tuple[Path, int, str]] = []
    action_refs: list[tuple[Path, int, str]] = []
    other_local_refs: list[tuple[Path, int, str]] = []
    for source_file in source_files:
        for line_no, line in enumerate(source_file.read_text(encoding="utf-8").splitlines(), start=1):
            match = USES_RE.match(line)
            if not match:
                continue
            ref = strip_quotes(match.group(1))
            if ref.startswith("./.github/workflows/"):
                workflow_refs.append((source_file, line_no, ref))
            elif ref.startswith("./.github/actions/"):
                action_refs.append((source_file, line_no, ref))
            elif ref.startswith("./"):
                other_local_refs.append((source_file, line_no, ref))
    return workflow_refs, action_refs, other_local_refs
