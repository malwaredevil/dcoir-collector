"""Sixteenth required-coverage layer for DCOIR Review.

v16 addresses the #342 live-test selector failure. The previous layers could
run successfully, but they still treated a full 12-comment review as success
while hard/core YAML, Python, and PowerShell risks were omitted. This overlay
keeps Kubernetes optional/bonus, makes workflow and PowerShell aggregate
coverage explicit, detects token-to-PR-metadata URLs, and reports every core
sentinel as posted, aggregate-covered, omitted, duplicate-covered, or
suppressed.
"""

from __future__ import annotations

import ast
import os
import re
import shlex
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v5 as v5
import dcoir_review_required_runtime_patch_v9 as v9
import dcoir_review_required_runtime_patch_v9_core as core
import dcoir_review_required_runtime_patch_v9_selection as selection
import dcoir_review_required_runtime_patch_v10 as v10
import dcoir_review_required_runtime_patch_v11 as v11
import dcoir_review_required_runtime_patch_v12 as v12
import dcoir_review_required_runtime_patch_v13 as v13
import dcoir_review_required_runtime_patch_v14 as v14

SentinelKey = tuple[str, int, str]

VERSION = "v16"
PYTHON_DYNAMIC_EXEC = "python_dynamic_exec"

CORE_REQUIRED_KINDS = set(getattr(v12, "REQUIRED_KINDS", set())) | {
    PYTHON_DYNAMIC_EXEC,
    getattr(v13, "PS_PLAINTEXT_SECURE_STRING", "ps_plaintext_secure_string"),
    getattr(v13, "PS_RUN_KEY_PERSISTENCE", "ps_run_key_persistence"),
}

TRACKED_KINDS = set(getattr(v13, "TRACKED_HIGH_RISK_KINDS", set())) | CORE_REQUIRED_KINDS
OPTIONAL_PRESSURE_KINDS = {
    getattr(v13, "TS_INNER_HTML", "ts_inner_html"),
    getattr(v13, "TS_DYNAMIC_EXECUTION", "ts_dynamic_execution"),
}

_ORIGINAL_V13_LINE_KIND = getattr(v13, "_line_kind")
_ORIGINAL_V13_SENTINEL_KEY = getattr(v13, "_sentinel_key")
_ORIGINAL_V13_POSTABLE_KEY = getattr(v13, "_postable_key")
_ORIGINAL_V13_TEMPLATE_FOR_KIND = getattr(v13, "_template_for_kind")
_ORIGINAL_V13_VALIDATION_FOR_KEY = getattr(v13, "_validation_for_key")

PR_METADATA_TOKEN_RE = re.compile(
    r"(?:secrets\.github_token|github_token|authorization\s*:?|bearer)"
    r".*(?:github\.event\.pull_request\.(?:body|title|labels|head\.ref|head\.sha)|pull_request\.(?:body|title|labels|head))"
    r"|(?:github\.event\.pull_request\.(?:body|title|labels|head\.ref|head\.sha)|pull_request\.(?:body|title|labels|head))"
    r".*(?:secrets\.github_token|github_token|authorization\s*:?|bearer)",
    re.I,
)
PYTHON_BUILTIN_DYNAMIC_EXEC_RE = re.compile(
    r"(?<![A-Za-z0-9_.])(?:eval|exec)\s*\(|(?:builtins|__builtins__)\.(?:eval|exec)\s*\(",
    re.IGNORECASE,
)
PYTHON_KNOWN_URLOPEN_RE = re.compile(r"\burllib(?:\.request)?\.urlopen\s*\(", re.IGNORECASE)
PYTHON_KNOWN_READ_MODE_OPEN_CALLS = frozenset({"bz2.open", "gzip.open", "lzma.open", "tarfile.open"})
PYTHON_OS_OPEN_ACCESS_MODE_MASK = getattr(os, "O_ACCMODE", 3)
PYTHON_OS_OPEN_RDONLY_MODE = getattr(os, "O_RDONLY", 0)
PYTHON_INT_EXPR_SHIFT_MAX = 128
PYTHON_INT_EXPR_MAX_BITS = 4096
PYTHON_OS_OPEN_MUTATING_FLAG_MASK = (
    getattr(os, "O_APPEND", 0)
    | getattr(os, "O_CREAT", 0)
    | getattr(os, "O_TMPFILE", 0)
    | getattr(os, "O_TRUNC", 0)
)
PYTHON_PATH_ALIAS_CONTEXT: dict[str, set[str]] = {}
PYTHON_OS_ALIAS_CONTEXT: dict[str, set[str]] = {}
PYTHON_URLLIB_URLOPEN_CALL_CONTEXT: dict[str, set[str]] = {}
PYTHON_SHADOWED_NAME_CONTEXT: dict[str, set[str]] = {}


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _line_number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_workflow_path(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").lower()
    return normalized.startswith(".github/workflows/") and normalized.endswith((".yml", ".yaml"))


def _is_optional_path(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").lower()
    basename = normalized.rsplit("/", 1)[-1]
    return "/optional_" in normalized or basename.startswith("optional_")


def _is_python_test_file(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").lower()
    basename = normalized.rsplit("/", 1)[-1]
    return (
        basename.startswith("test_")
        or basename.endswith("_test.py")
        or "/test/" in normalized
        or "/tests/" in normalized
    )


def _python_parse_diff_line(text: str) -> ast.Module | None:
    source = text.lstrip()
    try:
        return ast.parse(source)
    except SyntaxError:
        if source.rstrip().endswith(":"):
            try:
                return ast.parse(source.rstrip() + "\n    pass")
            except SyntaxError:
                return None
        return None


def _python_call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _python_call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _python_call_arg(call: ast.Call, position: int, *keyword_names: str) -> ast.AST | None:
    if len(call.args) > position:
        return call.args[position]
    for keyword in call.keywords:
        if keyword.arg in keyword_names:
            return keyword.value
    return None


def _python_bounded_int_expr(value: int) -> int | None:
    return value if abs(value).bit_length() <= PYTHON_INT_EXPR_MAX_BITS else None


def _python_fold_os_flag_expr(node: ast.AST | None, os_module_names: set[str] | None = None) -> int | None:
    if node is None:
        return None
    modules = os_module_names or {"os"}
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return _python_bounded_int_expr(int(node.value))
    if isinstance(node, ast.Attribute) and _python_call_name(node.value) in modules:
        value = getattr(os, node.attr, None)
        return _python_bounded_int_expr(value) if isinstance(value, int) else None
    if isinstance(node, ast.UnaryOp):
        operand = _python_fold_os_flag_expr(node.operand, modules)
        if operand is None:
            return None
        if isinstance(node.op, ast.Invert):
            return _python_bounded_int_expr(~operand)
        if isinstance(node.op, ast.UAdd):
            return _python_bounded_int_expr(+operand)
        if isinstance(node.op, ast.USub):
            return _python_bounded_int_expr(-operand)
        return None
    if isinstance(node, ast.BinOp):
        left = _python_fold_os_flag_expr(node.left, modules)
        right = _python_fold_os_flag_expr(node.right, modules)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.BitOr):
            return _python_bounded_int_expr(left | right)
        if isinstance(node.op, ast.BitAnd):
            return _python_bounded_int_expr(left & right)
        if isinstance(node.op, ast.BitXor):
            return _python_bounded_int_expr(left ^ right)
        if isinstance(node.op, ast.LShift):
            if right < 0 or right > PYTHON_INT_EXPR_SHIFT_MAX:
                return None
            return _python_bounded_int_expr(left << right)
        if isinstance(node.op, ast.RShift):
            if right < 0 or right > PYTHON_INT_EXPR_SHIFT_MAX:
                return None
            return _python_bounded_int_expr(left >> right)
        if isinstance(node.op, ast.Add):
            return _python_bounded_int_expr(left + right)
        if isinstance(node.op, ast.Sub):
            return _python_bounded_int_expr(left - right)
    return None


def _python_os_open_uses_write_mode(call: ast.Call, os_module_names: set[str] | None = None) -> bool:
    flags_node = _python_call_arg(call, 1, "flags")
    if flags_node is None:
        return any(keyword.arg is None for keyword in call.keywords)
    folded_flags = _python_fold_os_flag_expr(flags_node, os_module_names)
    if folded_flags is None:
        return True
    access_mode = folded_flags & PYTHON_OS_OPEN_ACCESS_MODE_MASK
    if access_mode == PYTHON_OS_OPEN_RDONLY_MODE:
        return bool(folded_flags & PYTHON_OS_OPEN_MUTATING_FLAG_MASK)
    return True


def _python_is_proven_path_receiver(node: ast.AST, path_constructor_names: set[str] | None = None) -> bool:
    constructors = path_constructor_names or {"Path", "pathlib.Path"}
    if isinstance(node, ast.Call) and _python_call_name(node.func) in constructors:
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _python_is_proven_path_receiver(node.left, constructors)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "joinpath":
        return _python_is_proven_path_receiver(node.func.value, constructors)
    return False


def _python_call_uses_write_mode(
    call: ast.Call,
    path_constructor_names: set[str] | None = None,
    os_module_names: set[str] | None = None,
    shadowed_names: set[str] | None = None,
) -> bool:
    call_name = _python_call_name(call.func)
    os_open_names = {f"{name}.open" for name in (os_module_names or {"os"})}
    if call_name in os_open_names:
        return _python_os_open_uses_write_mode(call, os_module_names)
    if isinstance(call.func, ast.Name) and call.func.id == "open":
        if shadowed_names and "open" in shadowed_names:
            return True
        mode_node = _python_call_arg(call, 1, "mode")
    elif call_name in PYTHON_KNOWN_READ_MODE_OPEN_CALLS:
        mode_node = _python_call_arg(call, 1, "mode")
    elif (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "open"
        and _python_is_proven_path_receiver(call.func.value, path_constructor_names)
    ):
        mode_node = _python_call_arg(call, 0, "mode")
    else:
        return False
    if mode_node is None:
        return False
    if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
        return any(token in mode_node.value.lower() for token in ("w", "a", "x", "+"))
    return True
