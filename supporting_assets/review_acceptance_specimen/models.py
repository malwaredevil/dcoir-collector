from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone


@dataclass(frozen=True)
class Actor:
    user_id: str
    tenant_id: str
    project_ids: frozenset[str]
    is_admin: bool = False


@dataclass(frozen=True)
class ProjectRecord:
    record_id: str
    tenant_id: str
    project_id: str
    payload: str
    policy_generation: int


@dataclass(frozen=True)
class IncidentJob:
    job_id: str
    tenant_id: str
    state: str = "queued"
    upload_complete: bool = False
    cleanup_complete: bool = False
    generation: int = 0
    completed_at: datetime | None = None

    def with_generation(self, generation: int) -> "IncidentJob":
        if generation < 0:
            raise ValueError("generation must be non-negative")
        return replace(self, generation=generation)

    def completed(self) -> "IncidentJob":
        return replace(self, state="complete", completed_at=datetime.now(timezone.utc))
