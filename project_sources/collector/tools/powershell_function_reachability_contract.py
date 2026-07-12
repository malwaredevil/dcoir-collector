#!/usr/bin/env python3
"""Shared contract helpers for the PowerShell function reachability report."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from powershell_analyzer_contract import AnalyzerContractError, repo_relative_input_path, sha256_file

SCHEMA_VERSION = "dcoir_powershell_function_reachability_report_v1"
ISSUE_NUMBER = 306
PARENT_ISSUE_NUMBER = 260
DEFAULT_MANIFEST = Path("project_sources/collector/manifests/Collector_Runtime_Package_Manifest.json")
DEFAULT_JSON_OUTPUT = Path("project_sources/collector/powershell_function_reachability_report.json")
DEFAULT_MARKDOWN_OUTPUT = Path("project_sources/collector/powershell_function_reachability_report.md")

CLASSIFICATIONS = (
    "entrypoint",
    "literal_referenced",
    "dynamic_invocation_uncertain",
    "static_unreferenced",
)

NON_CLAIMS = [
    "This report is not whole-program dead-code proof.",
    "This report does not claim any function is safe to delete.",
    "This report only covers manifest-declared collector runtime source.",
    "Runtime-lane coverage is not collected unless explicit suite evidence is supplied by a later lane.",
    "Static absence is reported as bounded evidence, not as proof of operator or dynamic invocation absence.",
]


class ReachabilityError(RuntimeError):
    """Raised for fail-closed reachability report errors."""


@dataclass(frozen=True)
class SourceFile:
    repo_path: str
    path: Path
    load_order: int


@dataclass(frozen=True)
class Definition:
    name: str
    source_path: str
    line: int
    column: int | None
    end_line: int | None
    definition_kind: str
    load_order: int

    @property
    def key(self) -> str:
        return self.name.casefold()


@dataclass(frozen=True)
class Reference:
    name: str
    source_path: str
    line: int
    column: int | None
    invocation_kind: str
    parser: str

    @property
    def key(self) -> str:
        return self.name.casefold()


def scalar(value: Any) -> str:
    return "" if value is None else str(value)


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReachabilityError(f"{label} is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReachabilityError(f"{label} is invalid JSON: {path}: {exc}") from exc
    except OSError as exc:
        raise ReachabilityError(f"{label} could not be read: {path}: {exc}") from exc


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def line_column(text: str, index: int) -> tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    line_start = text.rfind("\n", 0, index)
    return line, index + 1 if line_start < 0 else index - line_start


def context_line(text: str, line: int) -> str:
    lines = normalize_newlines(text).splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()
    return ""


def ast_definition_kind(value: Any) -> str:
    normalized = scalar(value).strip()
    return normalized or "top_level"


def ast_invocation_kind(value: Any) -> str:
    normalized = scalar(value).strip()
    return normalized or "not_extracted"


def safe_manifest_source_path(repo_root: Path, value: str | Path, label: str = "collector runtime source") -> Path:
    try:
        path = repo_relative_input_path(repo_root, value, label)
    except AnalyzerContractError as exc:
        raise ReachabilityError(str(exc)) from exc
    if not path.is_file():
        raise ReachabilityError(f"{label} is missing: {value}")
    return path


def safe_output_path(repo_root: Path, value: str | Path, label: str, suffix: str) -> tuple[Path, str]:
    try:
        path = repo_relative_input_path(repo_root, value, label)
    except AnalyzerContractError as exc:
        raise ReachabilityError(str(exc)) from exc
    try:
        repo_path = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ReachabilityError(f"{label} must resolve inside the repository root") from exc
    if not repo_path.startswith("project_sources/collector/"):
        raise ReachabilityError(f"{label} must stay under project_sources/collector/: {repo_path}")
    if path.suffix != suffix:
        raise ReachabilityError(f"{label} must use {suffix} suffix: {repo_path}")
    return path, repo_path


def resolve_sources(repo_root: Path, manifest_path: Path) -> tuple[dict[str, Any], list[SourceFile], list[str]]:
    manifest = read_json(manifest_path, "collector runtime manifest")
    if not isinstance(manifest, dict):
        raise ReachabilityError("collector runtime manifest must be a JSON object")

    errors: list[str] = []
    source_values: list[str] = []
    wrapper = manifest.get("collector_wrapper_source")
    if not isinstance(wrapper, str) or not wrapper.strip():
        errors.append("collector manifest: collector_wrapper_source must be a non-empty string")
    else:
        source_values.append(wrapper)

    part_files = manifest.get("collector_part_files")
    if not isinstance(part_files, list) or not part_files:
        errors.append("collector manifest: collector_part_files must be a non-empty list")
    else:
        for index, item in enumerate(part_files, start=1):
            if not isinstance(item, str) or not item.strip():
                errors.append(f"collector manifest: collector_part_files[{index}] must be a non-empty string")
            else:
                source_values.append(item)

    sources: list[SourceFile] = []
    for load_order, raw in enumerate(source_values):
        try:
            path = repo_relative_input_path(repo_root, raw, "collector runtime source")
        except AnalyzerContractError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"collector runtime source is missing: {raw}")
            continue
        sources.append(
            SourceFile(
                repo_path=path.resolve().relative_to(repo_root.resolve()).as_posix(),
                path=path,
                load_order=load_order,
            )
        )
    return manifest, sources, errors
