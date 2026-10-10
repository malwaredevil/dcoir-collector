"""Config attributes for the diff-mode bounded low-confidence disposition.

Kept dependency-free so any review stage can read or isolate this state
without importing the disposition pipeline and its escalation imports.
"""

from __future__ import annotations

from typing import Any

ALLOW_ATTR = "_dcoir_v52_allow_low_confidence_disposition"
PENDING_ATTR = "_dcoir_v52_pending_low_confidence_disposition"
# Inner stages run on shallow config copies (for example the semantic-context
# budget). A mutable holder created by the outermost disposition stage is
# shared by every copy, so a pending plan recorded deep in the pipeline still
# reaches the stage that acts on it.
PENDING_BOX_ATTR = "_dcoir_v52_pending_low_confidence_box"


def begin_pending(config: Any) -> None:
    setattr(config, PENDING_BOX_ATTR, {})
    setattr(config, PENDING_ATTR, None)


def set_pending(config: Any, value: Any) -> None:
    setattr(config, PENDING_ATTR, value)
    box = getattr(config, PENDING_BOX_ATTR, None)
    if isinstance(box, dict):
        box["pending"] = value


def get_pending(config: Any) -> Any:
    box = getattr(config, PENDING_BOX_ATTR, None)
    if isinstance(box, dict) and "pending" in box:
        return box["pending"]
    return getattr(config, PENDING_ATTR, None)
