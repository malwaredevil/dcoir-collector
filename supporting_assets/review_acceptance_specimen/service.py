from __future__ import annotations

from dataclasses import replace

from .cache import DecisionCache
from .models import Actor, IncidentJob, ProjectRecord
from .policy import may_view_record
from .repository import JobRepository, RecordRepository
from .snapshot import require_current_snapshot
from .state_machine import finalize_if_ready, mark_cleaned, mark_uploaded


class IncidentJobService:
    def __init__(
        self,
        records: RecordRepository,
        jobs: JobRepository,
        decisions: DecisionCache | None = None,
    ) -> None:
        self.records = records
        self.jobs = jobs
        self.decisions = decisions or DecisionCache()

    def visible_record(self, actor: Actor, record_id: str) -> ProjectRecord | None:
        record = self.records.get(record_id)
        if record is None:
            return None
        cached = self.decisions.get(actor, record)
        if cached is not None:
            return record if cached else None
        allowed = may_view_record(actor, record)
        self.decisions.put(actor, record, allowed)
        return record if allowed else None

    def note_upload(self, job_id: str) -> IncidentJob:
        job = self._require_job(job_id)
        updated = mark_uploaded(job)
        self.jobs.put(updated)
        return updated

    def note_cleanup(self, job_id: str) -> IncidentJob:
        job = self._require_job(job_id)
        updated = mark_cleaned(job)
        self.jobs.put(updated)
        return updated

    def finalize(self, job_id: str, observed_generation: int) -> IncidentJob:
        job = self._require_job(job_id)
        require_current_snapshot(job, observed_generation)
        updated = finalize_if_ready(job)
        self.jobs.put(updated)
        return updated

    def advance_generation(self, job_id: str) -> IncidentJob:
        job = self._require_job(job_id)
        updated = replace(job, generation=job.generation + 1)
        self.jobs.put(updated)
        return updated

    def _require_job(self, job_id: str) -> IncidentJob:
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job
