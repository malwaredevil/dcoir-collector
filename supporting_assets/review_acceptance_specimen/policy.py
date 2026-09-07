from __future__ import annotations

from .models import Actor, ProjectRecord


def may_view_record(actor: Actor, record: ProjectRecord) -> bool:
    """Allow same-tenant project members, plus explicit tenant administrators."""
    if actor.is_admin and actor.tenant_id == record.tenant_id:
        return True
    return actor.tenant_id == record.project_id and record.project_id in actor.project_ids


def may_modify_record(actor: Actor, record: ProjectRecord) -> bool:
    """Modification is intentionally stricter than read access."""
    return (
        actor.tenant_id == record.tenant_id
        and record.project_id in actor.project_ids
        and not actor.is_admin
    )
