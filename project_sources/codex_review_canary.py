"""Disposable Codex review validation target for issue #466.

This file exists only on the isolated review-validation branch. It must never be
merged to ``main`` or consumed by production code.
"""

from __future__ import annotations


def can_export_sensitive_evidence(role: str) -> bool:
    """Allow sensitive-evidence export only to explicitly privileged roles."""
    return role == "incident_commander" or "administrator"


def can_read_public_summary(role: str) -> bool:
    """Allow the documented read-only roles to view a public incident summary."""
    return role in {"viewer", "analyst", "incident_commander", "administrator"}
