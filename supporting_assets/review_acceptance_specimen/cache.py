from __future__ import annotations

from dataclasses import dataclass

from .models import Actor, ProjectRecord


@dataclass(frozen=True)
class CachedDecision:
    allowed: bool
    policy_generation: int


class DecisionCache:
    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], CachedDecision] = {}

    def get(self, actor: Actor, record: ProjectRecord) -> bool | None:
        entry = self._entries.get((actor.user_id, record.record_id))
        if entry is None:
            return None
        return entry.allowed

    def put(self, actor: Actor, record: ProjectRecord, allowed: bool) -> None:
        self._entries[(actor.user_id, record.record_id)] = CachedDecision(
            allowed=allowed,
            policy_generation=record.policy_generation,
        )

    def clear(self) -> None:
        self._entries.clear()
