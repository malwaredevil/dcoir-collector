from __future__ import annotations

from collections.abc import Iterable

from .models import IncidentJob, ProjectRecord


class RecordRepository:
    def __init__(self, records: Iterable[ProjectRecord] = ()) -> None:
        self._records = {record.record_id: record for record in records}

    def get(self, record_id: str) -> ProjectRecord | None:
        return self._records.get(record_id)

    def put(self, record: ProjectRecord) -> None:
        self._records[record.record_id] = record


class JobRepository:
    def __init__(self, jobs: Iterable[IncidentJob] = ()) -> None:
        self._jobs = {job.job_id: job for job in jobs}

    def get(self, job_id: str) -> IncidentJob | None:
        return self._jobs.get(job_id)

    def put(self, job: IncidentJob) -> None:
        self._jobs[job.job_id] = job
