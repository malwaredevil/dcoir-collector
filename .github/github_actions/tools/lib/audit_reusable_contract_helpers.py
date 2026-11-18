"""Helpers for reusable workflow and composite action contract audits."""
from __future__ import annotations

import re
from pathlib import Path

from .workflow_files import iter_workflow_files
from .workflow_uses import iter_uses_references, workflow_call_contract

WORKFLOW_DIR = Path(".github/workflows")

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
    return workflow_call_contract(path)


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


def iter_all_workflow_files(repo_root: Path) -> list[Path]:
    """Delegate all-workflow discovery to its canonical owner."""
    return iter_workflow_files(repo_root / WORKFLOW_DIR)


def local_uses_refs(source_files: list[Path]) -> tuple[list[tuple[Path, int, str]], list[tuple[Path, int, str]], list[tuple[Path, int, str]]]:
    workflow_refs: list[tuple[Path, int, str]] = []
    action_refs: list[tuple[Path, int, str]] = []
    other_local_refs: list[tuple[Path, int, str]] = []
    for source_file in source_files:
        for line_no, ref in iter_uses_references(source_file):
            if ref.startswith("./.github/workflows/"):
                workflow_refs.append((source_file, line_no, ref))
            elif ref.startswith("./.github/actions/"):
                action_refs.append((source_file, line_no, ref))
            elif ref.startswith("./"):
                other_local_refs.append((source_file, line_no, ref))
    return workflow_refs, action_refs, other_local_refs
