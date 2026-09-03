"""Contracts and configuration helpers for DCOIR Review v46."""

from __future__ import annotations

from typing import Any


VERSION = "v46"
CONTEXT_PACKAGE_CONTRACT = "architecture-b-semantic-context-package-v1"
BUDGET_CONTRACT = "architecture-b-adaptive-semantic-budget-v1"
PACKAGE_ATTR = "_dcoir_v46_context_package"
RUNTIME_ATTR = "_dcoir_v46_context_runtime"
APPLIED_ATTR = "_dcoir_v46_applied"


def positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def valid_head(value: Any) -> bool:
    candidate = str(value or "").strip().lower()
    return len(candidate) == 40 and all(char in "0123456789abcdef" for char in candidate)


__all__ = [
    "APPLIED_ATTR",
    "BUDGET_CONTRACT",
    "CONTEXT_PACKAGE_CONTRACT",
    "PACKAGE_ATTR",
    "RUNTIME_ATTR",
    "VERSION",
    "positive_int",
    "valid_head",
]
