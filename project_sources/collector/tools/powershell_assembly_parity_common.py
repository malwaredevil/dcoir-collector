#!/usr/bin/env python3
"""Shared constants and path helpers for PowerShell assembly parity validation."""
from __future__ import annotations


import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

__all__ = (
    "Any",
    "AssemblyParityError",
    "COLLECTOR_IMPORT_BLOCK",
    "DEFAULT_INVENTORY",
    "DEFAULT_JSON_OUTPUT",
    "DEFAULT_MANIFEST",
    "DEFAULT_MARKDOWN_OUTPUT",
    "HARNESS_GENERATED_OUTPUT",
    "HARNESS_PARTS_ROOT",
    "ISSUE_NUMBER",
    "PARENT_ISSUE_NUMBER",
    "POWERSHELL_PARSE_SCRIPT",
    "Path",
    "SCHEMA_VERSION",
    "argparse",
    "file_facts",
    "hashlib",
    "is_absolute_repo_input",
    "json",
    "normalize_repo_path",
    "normalize_text",
    "part_entry",
    "path_is_dir_inside_repo",
    "path_is_file_inside_repo",
    "path_resolves_inside_repo",
    "re",
    "read_json",
    "read_part_text",
    "relpath",
    "repo_relative_input_path",
    "require_non_empty_string",
    "require_non_empty_string_list",
    "safe_relpath",
    "sha256_file",
    "sha256_text",
    "shutil",
    "source_line_count",
    "subprocess",
    "sys",
    "tempfile",
    "validate_manifest_repo_path",
)

SCHEMA_VERSION = "dcoir_powershell_assembly_parity_report_v1"
ISSUE_NUMBER = 265
PARENT_ISSUE_NUMBER = 260
DEFAULT_MANIFEST = Path("project_sources/collector/manifests/Collector_Runtime_Package_Manifest.json")
DEFAULT_INVENTORY = Path("project_sources/collector/powershell_surface_inventory.json")
DEFAULT_JSON_OUTPUT = Path("project_sources/collector/powershell_assembly_parity_report.json")
DEFAULT_MARKDOWN_OUTPUT = Path("project_sources/collector/powershell_assembly_parity_report.md")
HARNESS_PARTS_ROOT = Path("project_sources/collector/harness/source/parts")
HARNESS_GENERATED_OUTPUT = Path("project_sources/collector/harness/run_DCOIR_Tests.generated.ps1")
COLLECTOR_IMPORT_BLOCK = re.compile(
    r"(?ms)^\$collectorPartsRoot = .*?^foreach \(\$partFile in \$collectorPartFiles\) \{.*?^\}\s*"
)
POWERSHELL_PARSE_SCRIPT = """\
param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$tokens = $null
$parseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$parseErrors) | Out-Null
if ($parseErrors -and $parseErrors.Count -gt 0) {
    $parseErrors | ForEach-Object {
        '{0}:{1}: {2}' -f $_.Extent.StartLineNumber, $_.Extent.StartColumnNumber, $_.Message
    }
    exit 1
}
"""


class AssemblyParityError(RuntimeError):
    """Raised for fail-closed #265 assembly parity validation errors."""


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AssemblyParityError(f"{label} missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AssemblyParityError(f"{label} invalid JSON: {path}: {exc}") from exc
    except OSError as exc:
        raise AssemblyParityError(f"{label} could not be read: {path}: {exc}") from exc


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def relpath(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def path_resolves_inside_repo(path: Path, repo_root: Path) -> bool:
    try:
        path.resolve().relative_to(repo_root.resolve())
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def path_is_file_inside_repo(path: Path, repo_root: Path) -> bool:
    return path_resolves_inside_repo(path, repo_root) and path.is_file()


def path_is_dir_inside_repo(path: Path, repo_root: Path) -> bool:
    return path_resolves_inside_repo(path, repo_root) and path.is_dir()


def safe_relpath(path: Path, repo_root: Path) -> str:
    try:
        return relpath(path, repo_root)
    except (OSError, RuntimeError, ValueError):
        return path.as_posix()


def file_facts(path: Path, repo_root: Path) -> dict[str, Any]:
    if not path_resolves_inside_repo(path, repo_root) or not path.is_file():
        return {
            "path": safe_relpath(path, repo_root),
            "exists": False,
            "size_bytes": None,
            "line_count": None,
            "sha256": None,
        }
    data = path.read_bytes()
    return {
        "path": safe_relpath(path, repo_root),
        "exists": True,
        "size_bytes": len(data),
        "line_count": data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def normalize_repo_path(value: str) -> str:
    slash_path = value.replace("\\", "/")
    while slash_path.startswith("./"):
        slash_path = slash_path[2:]
    return Path(slash_path).as_posix()


def is_absolute_repo_input(value: str) -> bool:
    raw = value.strip()
    slash_path = raw.replace("\\", "/")
    return slash_path.startswith("/") or re.match(r"^[A-Za-z]:", slash_path) is not None or Path(raw).is_absolute()


def validate_manifest_repo_path(value: str, key: str, label: str, repo_root: Path, errors: list[str]) -> str | None:
    raw = value.strip()
    slash_path = raw.replace("\\", "/")
    rel = normalize_repo_path(raw)
    raw_parts = tuple(part for part in slash_path.split("/") if part)
    parts = Path(rel).parts
    if not raw or is_absolute_repo_input(raw) or ".." in raw_parts or rel.startswith("../") or ".." in parts or Path(rel).is_absolute():
        errors.append(f"{label}: {key} must be a repo-relative path without traversal")
        return None
    try:
        (repo_root / rel).resolve().relative_to(repo_root.resolve())
    except (OSError, RuntimeError, ValueError):
        errors.append(f"{label}: {key} must resolve inside the repository root")
        return None
    return rel


def repo_relative_input_path(value: str, key: str, label: str, repo_root: Path, errors: list[str]) -> Path | None:
    rel = validate_manifest_repo_path(value, key, label, repo_root, errors)
    return repo_root / rel if rel is not None else None


def require_non_empty_string(mapping: dict[str, Any], key: str, label: str, repo_root: Path, errors: list[str]) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: {key} must be a non-empty string")
        return ""
    rel = validate_manifest_repo_path(value, key, label, repo_root, errors)
    return rel or ""


def require_non_empty_string_list(mapping: dict[str, Any], key: str, label: str, repo_root: Path, errors: list[str]) -> list[str]:
    value = mapping.get(key)
    if not isinstance(value, list) or not value:
        errors.append(f"{label}: {key} must be a non-empty list")
        return []
    normalized: list[str] = []
    for index, raw_item in enumerate(value, start=1):
        item_key = f"{key}[{index}]"
        if not isinstance(raw_item, str) or not raw_item.strip():
            errors.append(f"{label}: {item_key} must be a non-empty string")
            continue
        rel = validate_manifest_repo_path(raw_item, item_key, label, repo_root, errors)
        if rel is not None:
            normalized.append(rel)
    return normalized


def part_entry(path: Path, repo_root: Path) -> dict[str, Any]:
    facts = file_facts(path, repo_root)
    facts["empty"] = bool(facts["exists"] and facts["size_bytes"] == 0)
    return facts


def source_line_count(text: str) -> int:
    normalized = normalize_text(text)
    return normalized.count("\n") + (1 if normalized and not normalized.endswith("\n") else 0)


def read_part_text(path: Path) -> str:
    text = normalize_text(path.read_text(encoding="utf-8"))
    if not text.endswith("\n"):
        text += "\n"
    return text
