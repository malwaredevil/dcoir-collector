"""DCOIR Review v31 structural truthy-literal precision overlay for issue #455.

v30 made the repair/publication path fail closed when a deterministic candidate
proved to be a false positive. v31 moves the same precision upstream for Python
branch conditions so valid grouped membership/comparison expressions do not
force an unnecessary quality retry and repair-author pass.

Python truthy-literal classification is structural: a finding exists only when
the parsed boolean ``or`` expression actually contains a bare non-empty string
constant as one of its operands. Strings that are operands of ``in``, ``not in``,
equality, identity, or ordering comparisons are not bare truthy operands. The
structural layer also adds true candidates missed by the legacy line regex, such
as a parenthesized bare literal. Parse failures remain fail-closed and preserve
any existing sentinel rather than suppressing uncertain code.

The runtime has both a raw risk-sentinel label and a later deterministic
canonical title for this same finding family. v31 treats both as the same
semantic sentinel so filtering and true-positive injection stay aligned across
all compatibility layers.

PowerShell detection remains governed by the comparison-aware v30 rule. This
overlay adds no branch-write or autonomous remediation capability.
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path
from typing import Any

import dcoir_review_required_runtime_patch_v16 as v16
import dcoir_review_required_runtime_patch_v20 as v20


VERSION = "v31"
APPLIED_MARKER = "_dcoir_review_v31_applied"
RAW_TRUTHY_LABEL = "truthy literal branch condition"
PYTHON_TRUTHY_KIND = v20.PYTHON_TRUTHY_LITERAL_BRANCH
CANONICAL_TRUTHY_LABEL = v20._template_for_kind(PYTHON_TRUTHY_KIND)[0]
TRUTHY_LABELS = frozenset({RAW_TRUTHY_LABEL, CANONICAL_TRUTHY_LABEL})


def _python_branch_source(text: str) -> str:
    source = textwrap.dedent(str(text or "")).strip()
    if source.startswith("elif "):
        source = "if " + source[5:]
    if source.endswith(":"):
        source += "\n    pass"
    return source


def python_bare_truthy_or_operand(text: str) -> bool | None:
    """Return True/False when Python parses, otherwise None (fail closed)."""

    source = _python_branch_source(text)
    if not source:
        return False
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.BoolOp) or not isinstance(node.op, ast.Or):
            continue
        for operand in node.values:
            if (
                isinstance(operand, ast.Constant)
                and isinstance(operand.value, str)
                and bool(operand.value)
            ):
                return True
    return False


def _truthy_detail(hardened: Any) -> str:
    for label, detail, _pattern in tuple(getattr(hardened, "RISK_SENTINEL_RULES", ())):
        if label == RAW_TRUTHY_LABEL:
            return str(detail)
    return "a bare non-empty string operand of boolean or is always truthy and can bypass the intended comparison"


def _patch_final_risk_sentinel_filter(module: Any) -> None:
    storage = "_dcoir_required_v31_original_detect_risk_sentinels"
    original = getattr(module, storage, None)
    if original is None:
        original = getattr(module, "detect_risk_sentinels", None)
        if callable(original):
            setattr(module, storage, original)
    if not callable(original):
        raise RuntimeError("DCOIR v31 could not locate detect_risk_sentinels")

    hardened = getattr(module, "hardened", None)
    selector = getattr(hardened, "select_risk_sentinels", None) if hardened is not None else None
    iter_added = getattr(hardened, "iter_added_diff_lines", None) if hardened is not None else None
    sentinel_type = getattr(hardened, "RiskSentinel", None) if hardened is not None else None
    is_comment = getattr(hardened, "is_comment_only_added_line", None) if hardened is not None else None
    if not all(callable(item) for item in (selector, iter_added, sentinel_type, is_comment)):
        raise RuntimeError("DCOIR v31 could not locate the hardened risk-sentinel construction surface")

    def detect_risk_sentinels(diff: str, max_anchors: int | None = None):
        # Ask the prior layer for the full candidate set so filtering does not
        # consume an anchor slot that should be available to a later real risk.
        candidates = list(original(diff, None))
        truthy_locations = {
            (str(getattr(item, "path", "")), int(getattr(item, "line", 0) or 0))
            for item in candidates
            if str(getattr(item, "label", "")) in TRUTHY_LABELS
        }

        # Make structural Python detection authoritative in both directions:
        # add real bare-literal cases the old regex missed, then filter old
        # candidates that parse as comparison/membership expressions.
        detail = _truthy_detail(hardened)
        for changed_line in iter_added(diff):
            path = str(getattr(changed_line, "path", ""))
            if Path(path).suffix.lower() != ".py":
                continue
            text = str(getattr(changed_line, "text", ""))
            if is_comment(path, text):
                continue
            if python_bare_truthy_or_operand(text) is not True:
                continue
            line = int(getattr(changed_line, "line", 0) or 0)
            location = (path, line)
            if location in truthy_locations:
                continue
            truthy_locations.add(location)
            candidates.append(
                sentinel_type(
                    path=path,
                    line=line,
                    label=CANONICAL_TRUTHY_LABEL,
                    detail=detail,
                    text=text,
                )
            )

        kept = []
        for sentinel in candidates:
            if (
                str(getattr(sentinel, "label", "")) in TRUTHY_LABELS
                and Path(str(getattr(sentinel, "path", ""))).suffix.lower() == ".py"
            ):
                structural = python_bare_truthy_or_operand(str(getattr(sentinel, "text", "")))
                if structural is False:
                    continue
                # None means the changed line could not be parsed in isolation;
                # preserve the existing risk signal rather than create a false negative.
            kept.append(sentinel)
        return selector(kept, max_anchors)

    module.detect_risk_sentinels = detect_risk_sentinels


def _patch_deterministic_line_kind() -> None:
    storage = "_dcoir_required_v31_original_line_kind"
    original = getattr(v20, storage, None)
    if original is None:
        original = v20._line_kind
        setattr(v20, storage, original)

    def line_kind(path: str, text: str) -> str:
        if Path(str(path or "")).suffix.lower() == ".py":
            structural = python_bare_truthy_or_operand(str(text or ""))
            if structural is True:
                return PYTHON_TRUTHY_KIND
            if structural is False:
                return v20._ORIGINAL_V16_LINE_KIND(path, text)
            # Parse failure is intentionally fail-closed: preserve the existing
            # deterministic classifier rather than silently dropping a risk.
        return original(path, text)

    v20._line_kind = line_kind
    v16._line_kind = line_kind


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    _patch_final_risk_sentinel_filter(module)
    _patch_deterministic_line_kind()
    setattr(module, APPLIED_MARKER, True)
