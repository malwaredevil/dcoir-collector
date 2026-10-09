"""Config attributes for the diff-mode bounded low-confidence disposition.

Kept dependency-free so any review stage can read or isolate this state
without importing the disposition pipeline and its escalation imports.
"""

from __future__ import annotations

ALLOW_ATTR = "_dcoir_v52_allow_low_confidence_disposition"
PENDING_ATTR = "_dcoir_v52_pending_low_confidence_disposition"
