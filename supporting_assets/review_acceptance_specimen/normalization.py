from __future__ import annotations


def canonical_identifier(value: str) -> str:
    """Normalize identifiers for equality comparisons without changing meaning."""
    return "-".join(part for part in value.strip().lower().replace("_", "-").split("-") if part)


def same_identifier(left: str, right: str) -> bool:
    return canonical_identifier(left) == canonical_identifier(right)
