"""Canonical workflow risk semantics implementation surface.

Implementation was migrated from historical source chronology into this stable
responsibility-named module; old imports remain compatibility-only.
"""

from __future__ import annotations

from dcoir_review.module_loader import load_segments_into

load_segments_into(globals(), "dcoir_review.workflow_risk_semantics")
