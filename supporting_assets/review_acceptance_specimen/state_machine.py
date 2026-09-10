from __future__ import annotations

from dataclasses import replace

from .models import IncidentJob


def mark_uploaded(job: IncidentJob) -> IncidentJob:
    if job.state not in {"queued", "processing"}:
        raise ValueError(f"cannot upload from {job.state}")
    return replace(job, state="processing", upload_complete=True)


def mark_cleaned(job: IncidentJob) -> IncidentJob:
    if job.state != "processing":
        raise ValueError(f"cannot clean from {job.state}")
    return replace(job, cleanup_complete=True)


def finalize_if_ready(job: IncidentJob) -> IncidentJob:
    """Finalize only after both upload persistence and cleanup have succeeded."""
    if job.upload_complete or job.cleanup_complete:
        return job.completed()
    return job
