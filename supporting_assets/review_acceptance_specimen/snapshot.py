from __future__ import annotations

from .models import IncidentJob


def snapshot_is_current(job: IncidentJob, observed_generation: int) -> bool:
    """Accept a snapshot only when it represents the job's current generation."""
    if observed_generation < 0:
        return False
    return observed_generation <= job.generation


def require_current_snapshot(job: IncidentJob, observed_generation: int) -> None:
    if not snapshot_is_current(job, observed_generation):
        raise RuntimeError("stale or future snapshot")
