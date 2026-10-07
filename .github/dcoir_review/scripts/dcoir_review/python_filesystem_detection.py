"""Stable Python archive/path-write sentinel detection for DCOIR Review.

This owner preserves the deterministic archive-extraction and explicit path-write
sentinels historically installed by the v12 runtime root. Later v16 filtering
remains authoritative for alias/shadowing precision and dedupes these sentinels
by path, line, and semantic kind.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import dcoir_review.python_k8s_risk_semantics as v11
import dcoir_review.risk_sentinel_selection_support as selection


APPLIED_MARKER = "_dcoir_review_python_filesystem_detection_applied"


def _is_python_test_file(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").lower()
    name = normalized.rsplit("/", 1)[-1]
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "/test/" in normalized
        or "/tests/" in normalized
    )


def _sentinel_key(sentinel: Any) -> tuple[str, int, str]:
    path = str(getattr(sentinel, "path", "") or "")
    try:
        line = int(getattr(sentinel, "line", 0) or 0)
    except (TypeError, ValueError):
        line = 0
    text = str(getattr(sentinel, "text", "") or "")
    kind = v11._line_kind(path, text) or v11._base_sentinel_key(sentinel)[2]
    return path, line, str(kind or "")


def build_detector(owner: Any, sentinel_owner: Any | None, next_detect: Any):
    """Compose deterministic Python filesystem sentinels around ``next_detect``."""
    if not callable(next_detect):
        raise RuntimeError("DCOIR Python filesystem detection requires a callable detector")
    original = next_detect

    def detect_risk_sentinels(diff: str, *args: Any, **kwargs: Any) -> list[Any]:
        widened_args = list(args)
        if widened_args and isinstance(widened_args[0], int):
            widened_args[0] = None
        widened_kwargs = dict(kwargs)
        for name in ("max_anchors", "max_sentinels", "limit"):
            if name in widened_kwargs:
                widened_kwargs[name] = None
        try:
            sentinels = list(original(diff, *widened_args, **widened_kwargs))
        except TypeError:
            sentinels = list(original(diff, *args, **kwargs))

        existing = {_sentinel_key(item) for item in sentinels}
        risk_sentinel_type = getattr(owner, "RiskSentinel", None) or getattr(sentinel_owner, "RiskSentinel", None)
        if risk_sentinel_type is None:
            return sentinels
        comment_checker = getattr(owner, "is_comment_only_added_line", None) or getattr(sentinel_owner, "is_comment_only_added_line", None)

        for path, line, text in selection._iter_added_diff_lines(diff):
            if Path(path.lower()).suffix != ".py":
                continue
            if callable(comment_checker) and comment_checker(path, text):
                continue
            kind = v11._line_kind(path, text)
            if kind not in {v11.PYTHON_ARCHIVE_EXTRACT, v11.PYTHON_PATH_WRITE}:
                continue
            if kind == v11.PYTHON_PATH_WRITE and _is_python_test_file(path):
                continue
            key = (path, line, kind)
            if key in existing:
                continue
            if kind == v11.PYTHON_ARCHIVE_EXTRACT:
                label = "Python unsafe archive extraction"
                detail = "archive extraction needs destination containment and member traversal checks before unpacking untrusted archives"
            else:
                label = "Python request-controlled file write"
                detail = "request-controlled paths must be resolved under an allowlisted base directory before writing"
            sentinels.append(risk_sentinel_type(path=path, line=line, label=label, detail=detail, text=text))
            existing.add(key)
        return sentinels

    return detect_risk_sentinels


def _patch_python_filesystem_sentinels(owner: Any, sentinel_owner: Any | None = None) -> None:
    current = getattr(owner, "detect_risk_sentinels", None)
    if callable(current):
        owner.detect_risk_sentinels = build_detector(owner, sentinel_owner, current)


def apply_pareto_context_module(module: Any) -> None:
    if getattr(module, APPLIED_MARKER, False):
        return
    hardened = getattr(module, "hardened", None)
    _patch_python_filesystem_sentinels(module, hardened)
    if hardened is not None:
        _patch_python_filesystem_sentinels(hardened)
    setattr(module, APPLIED_MARKER, True)
