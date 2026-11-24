"""Stable semantic-context contracts and configuration helpers."""

from __future__ import annotations

from typing import Any


RUNTIME_VERSION = "v46"  # Persisted diagnostic compatibility value.
CONTEXT_PACKAGE_CONTRACT = "architecture-b-semantic-context-package-v1"
BUDGET_CONTRACT = "architecture-b-adaptive-semantic-budget-v1"
PACKAGE_ATTR = "_dcoir_semantic_context_package"
RUNTIME_ATTR = "_dcoir_semantic_context_runtime"
CONFIG_PACKAGE_ID_ATTR = "_dcoir_semantic_context_package_id"
BUDGET_MODE_ATTR = "_dcoir_semantic_budget_mode"


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
    "BUDGET_CONTRACT",
    "CONTEXT_PACKAGE_CONTRACT",
    "BUDGET_MODE_ATTR",
    "CONFIG_PACKAGE_ID_ATTR",
    "PACKAGE_ATTR",
    "RUNTIME_ATTR",
    "RUNTIME_VERSION",
    "positive_int",
    "valid_head",
]
