#!/usr/bin/env python3
"""Pareto routing and first-pass context wrapper for the hardened PR reviewer."""

from __future__ import annotations

import ast
import base64
import concurrent.futures
import copy
import json
import os
import re
import signal
import sys
import urllib.parse
from pathlib import Path
from typing import Any, NamedTuple

import openrouter_pr_review_hardened as hardened
from dcoir_review import review_config


base = hardened.base
CONTEXT_REVIEW_MARKER = "Context mode:"
DEEP_CONTEXT_MIN_PARTIAL_CHARS = 400
DEEP_CONTEXT_BUDGET_EXHAUSTED_SUFFIX = "\n~~~\n\n[deep context budget exhausted]"
DEEP_CONTEXT_PROMPT_TRUNCATED_MARKER = "\n\n[deep context truncated by reviewer]"
REVIEW_ASSIST_CONTEXT_ROOT = Path("/tmp/review-assist-context")
REVIEW_ASSIST_CONTEXT_REPORT = Path("project_sources/collector/powershell_review_assist_workflow_report.md")
REQUIRED_FINDING_FAMILIES = ("powershell", "python", "github-actions-yaml")
OPTIONAL_FINDING_FAMILIES = ("typescript", "kubernetes-yaml")


def optional_float(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Config key {key!r} must be a number or empty, got {value!r}") from exc


def load_pareto_context_config(path: str) -> Any:
    config = hardened.load_hardened_config(path)
    data = hardened.parse_yaml_like_data(path)
    config.pareto_min_coding_score = optional_float(data, "pareto_min_coding_score")
    config.first_pass_deep_review = hardened.bool_value(data, "first_pass_deep_review", True)
    config.per_file_first_pass_review = hardened.bool_value(data, "per_file_first_pass_review", True)
    config.per_file_review_concurrency = int(data.get("per_file_review_concurrency", 4))
    config.per_file_review_max_files = int(data.get("per_file_review_max_files", data.get("deep_review_max_files", 8)))
    config.per_file_review_max_file_chars = int(data.get("per_file_review_max_file_chars", data.get("deep_review_max_file_chars", 12000)))
    config.fix_synthesis_enabled = hardened.bool_value(data, "fix_synthesis_enabled", True)
    config.fix_synthesis_max_findings = int(data.get("fix_synthesis_max_findings", 12))
    config.fix_synthesis_min_confidence = float(data.get("fix_synthesis_min_confidence", 0.80))
    config.required_finding_reserved_budget = int(
        data.get("required_finding_reserved_budget", min(getattr(config, "max_inline_comments", 12), 9))
    )
    config.required_finding_min_per_family = int(data.get("required_finding_min_per_family", 2))
    config.deep_review_max_files = int(data.get("deep_review_max_files", min(getattr(config, "max_files", 30), 8)))
    config.deep_review_max_file_chars = int(data.get("deep_review_max_file_chars", 12000))
    config.deep_review_max_total_chars = int(data.get("deep_review_max_total_chars", 24000))
    review_config.apply_review_config(config, data, hardened)
    hardened.ensure_free_models_are_opt_in(config)
    return config


_original_build_openrouter_payload = hardened.build_openrouter_payload
_original_detect_risk_sentinels = hardened.detect_risk_sentinels

FILE_WRITE_PATH_LABEL = "unsafe file-write path construction"
FILE_WRITE_PATH_DETAIL = (
    "dynamic path segments reached a file write; verify or add segment validation, "
    "normalization, and root containment checks before writing or staging files"
)
PYTHON_DYNAMIC_EXEC_LABEL = "Python eval/exec dynamic code execution"
PYTHON_DYNAMIC_EXEC_DETAIL = (
    "eval/exec can execute caller-controlled Python expressions; remove dynamic evaluation "
    "or replace it with ast.literal_eval, a constrained parser, or an explicit allowlist"
)
GITHUB_ACTIONS_BROAD_WRITE_PERMISSION_LABEL = "GitHub Actions broad write permission"
GITHUB_ACTIONS_BROAD_WRITE_PERMISSION_DETAIL = (
    "workflow permissions grant repository write privileges; narrow permissions to the minimum read/write scopes needed"
)
GITHUB_ACTIONS_UNTRUSTED_CHECKOUT_REF_LABEL = "GitHub Actions untrusted checkout ref"
GITHUB_ACTIONS_UNTRUSTED_CHECKOUT_REF_DETAIL = (
    "checkout uses untrusted pull request head refs or SHAs; privileged workflows must not execute PR-controlled code with write tokens"
)
PYTHON_DYNAMIC_EXEC_CALL_NAMES = frozenset(
    {"eval", "exec", "builtins.eval", "builtins.exec", "__builtins__.eval", "__builtins__.exec"}
)
PYTHON_PATH_TARGET_PART = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
PYTHON_PATH_ASSIGNMENT_MAX_CHARS = 10000
PYTHON_PATH_ASSIGNMENT_RE = re.compile(
    rf"^\s*(?P<target>{PYTHON_PATH_TARGET_PART})\s*=\s*(?P<expr>[^\n#]*(?:Path|os\.path\.join)\s*\([^\n#]*)"
)
PYTHON_PATH_ASSIGNMENT_START_RE = re.compile(
    rf"^\s*{PYTHON_PATH_TARGET_PART}\s*(?::\s*[^=]+)?=\s*(?:Path|pathlib\.Path|os\.path\.join)\s*\("
)
PYTHON_ASSIGNMENT_CONTINUATION_START_RE = re.compile(
    rf"^\s*{PYTHON_PATH_TARGET_PART}\s*(?::\s*[^=]+)?=\s*(?:\(|\\)\s*$"
)
PYTHON_FILE_WRITE_RE = re.compile(
    rf"(?:\b(?P<target>{PYTHON_PATH_TARGET_PART})|\b(?:Path|pathlib\.Path)\s*\(\s*(?P<wrapped_target>{PYTHON_PATH_TARGET_PART})\s*\))"
    r"\.write_(?:text|bytes)\s*\("
)
PYTHON_SCOPE_BOUNDARY_RE = re.compile(r"^\s*(?:async\s+def|def|class)\s+[A-Za-z_][A-Za-z0-9_]*\b")
PYTHON_HUNK_CONTEXT_RE = re.compile(r"^@@.*?@@\s*(?P<context>.*)$")
PYTHON_TRIPLE_QUOTE_RE = re.compile(r"(?<!\\)(?:'''|\"\"\")")
DEFAULT_PYTHON_PATH_CONSTRUCTORS = frozenset({"Path", "pathlib.Path"})
DEFAULT_PYTHON_OS_MODULES = frozenset({"os"})
PYTHON_OS_OPEN_ACCESS_MODE_MASK = getattr(os, "O_ACCMODE", 3)
PYTHON_OS_OPEN_RDONLY_MODE = getattr(os, "O_RDONLY", 0)
PYTHON_INT_EXPR_SHIFT_MAX = 128
PYTHON_INT_EXPR_MAX_BITS = 4096
PYTHON_OS_OPEN_WRITE_ACCESS_NAMES = frozenset({"O_WRONLY", "O_RDWR"})
PYTHON_OS_OPEN_READ_ACCESS_NAMES = frozenset({"O_RDONLY"})
PYTHON_OS_OPEN_NON_MUTATING_FLAG_NAMES = frozenset({"O_CLOEXEC"})
PYTHON_OS_OPEN_MUTATING_FLAG_NAMES = frozenset({"O_CREAT", "O_TRUNC", "O_APPEND", "O_EXCL", "O_TMPFILE"})
PYTHON_OS_OPEN_KNOWN_FLAG_NAMES = (
    PYTHON_OS_OPEN_WRITE_ACCESS_NAMES
    | PYTHON_OS_OPEN_READ_ACCESS_NAMES
    | PYTHON_OS_OPEN_NON_MUTATING_FLAG_NAMES
    | PYTHON_OS_OPEN_MUTATING_FLAG_NAMES
)
PYTHON_OS_OPEN_MUTATING_FLAG_MASK = 0
for _flag_name in PYTHON_OS_OPEN_MUTATING_FLAG_NAMES:
    _flag_value = getattr(os, _flag_name, 0)
    if isinstance(_flag_value, int):
        PYTHON_OS_OPEN_MUTATING_FLAG_MASK |= _flag_value
PYTHON_PATH_ALIAS_CONTEXT: dict[str, set[str]] = {}
PYTHON_OS_ALIAS_CONTEXT: dict[str, set[str]] = {}
PYTHON_URLLIB_URLOPEN_CALL_CONTEXT: dict[str, set[str]] = {}
GITHUB_ACTIONS_WRITE_PERMISSION_RE = re.compile(
    r"^\s*(?:permissions\s*:\s*write-all|(?:actions|checks|contents|deployments|id-token|issues|packages|pull-requests|statuses)\s*:\s*write)\b",
    re.IGNORECASE,
)
GITHUB_ACTIONS_UNTRUSTED_CHECKOUT_REF_RE = re.compile(
    r"github\.event\.pull_request\.head\.(?:ref|sha)|github\.head_ref",
    re.IGNORECASE,
)


class PythonDiffLine(NamedTuple):
    path: str
    hunk: int
    line: int
    text: str
    is_added: bool
    inside_multiline_string: bool
    inside_diff_fixture_string: bool
    hunk_context: str = ""


class PythonTrackedPath(NamedTuple):
    assignment: PythonDiffLine | None
    indent: int
    scope_id: int = 0


class PythonScope(NamedTuple):
    indent: int
    key: str
    scope_id: int


def build_openrouter_payload(
    prompt: str,
    schema: dict[str, Any],
    config: Any,
    ignored_providers: list[str],
    model: str,
) -> dict[str, Any]:
    payload = _original_build_openrouter_payload(prompt, schema, config, ignored_providers, model)
    if model.startswith("openrouter/pareto-code"):
        plugin: dict[str, Any] = {"id": "pareto-router"}
        min_coding_score = getattr(config, "pareto_min_coding_score", None)
        if min_coding_score is not None:
            plugin["min_coding_score"] = min_coding_score
        payload["plugins"] = [plugin]
    return payload


hardened.build_openrouter_payload = build_openrouter_payload
