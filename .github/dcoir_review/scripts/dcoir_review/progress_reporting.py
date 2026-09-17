"""Canonical terminal progress-reporter composition for DCOIR Review.

The base reporter owns ordinary status publication. Verified-finding gate semantics
and v54 run telemetry are independent responsibilities that historically replaced
``ProgressReporter`` in sequence. This module composes them once after telemetry
initialization so runtime ownership no longer depends on patch chronology.
"""

from __future__ import annotations

from typing import Any

from dcoir_review import verified_finding_gate as verified_gate
import dcoir_review_required_runtime_patch_v54 as telemetry


APPLIED_MARKER = "_dcoir_review_progress_reporting_applied"
OWNER_MARKER = "_dcoir_review_progress_reporting_owner"


def _reporter_owners(module: Any) -> tuple[Any, ...]:
    return tuple(
        owner
        for owner in (getattr(module, "base", None), getattr(module, "hardened", None), module)
        if owner is not None
    )


def apply_pareto_context_module(module: Any) -> None:
    """Install one reporter owner for gate-aware completion and run telemetry."""

    if getattr(module, APPLIED_MARKER, False):
        return

    owners = _reporter_owners(module)
    original = next(
        (
            getattr(owner, "ProgressReporter", None)
            for owner in owners
            if isinstance(getattr(owner, "ProgressReporter", None), type)
        ),
        None,
    )
    if not isinstance(original, type):
        raise RuntimeError("DCOIR progress reporting could not locate ProgressReporter")

    required = ("complete", "fail", "_record", "_body", "_update_comment")
    if any(not callable(getattr(original, name, None)) for name in required):
        raise RuntimeError("DCOIR progress reporting ProgressReporter contract is incomplete")

    class ProgressReporter(original):
        def complete(self, model_used: str, findings_count: int, review_event: str) -> None:
            if bool(getattr(module, telemetry.APPLIED_MARKER, False)):
                try:
                    telemetry.emit_run_telemetry(module, self)
                except Exception:
                    telemetry._note_telemetry_error(getattr(self, "config", None))
            override = verified_gate.progress_completion_override(
                module,
                getattr(self, "config", None),
                findings_count,
                review_event,
            )
            if override is None:
                return super().complete(model_used, findings_count, review_event)
            message, final_lines = override
            self._record("completed", message)
            self._update_comment(self._body("completed", final_lines=final_lines))
            return None

        def fail(self, message: str) -> None:
            if bool(getattr(module, telemetry.APPLIED_MARKER, False)):
                try:
                    telemetry.emit_run_telemetry(module, self)
                except Exception:
                    telemetry._note_telemetry_error(getattr(self, "config", None))
            return super().fail(message)

    ProgressReporter.__name__ = getattr(original, "__name__", "ProgressReporter")
    ProgressReporter.__qualname__ = getattr(original, "__qualname__", "ProgressReporter")
    setattr(ProgressReporter, OWNER_MARKER, True)

    for owner in owners:
        setattr(owner, "ProgressReporter", ProgressReporter)
    setattr(module, APPLIED_MARKER, True)


__all__ = ["APPLIED_MARKER", "OWNER_MARKER", "apply_pareto_context_module"]
