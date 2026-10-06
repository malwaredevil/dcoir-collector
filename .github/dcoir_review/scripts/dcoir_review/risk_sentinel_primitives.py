"""Canonical deterministic risk-sentinel primitives.

This module owns the classifier, selector, coverage, aggregation, and detector
helpers historically implemented under runtime-patch v16. Historical v16 imports
remain supported through a thin compatibility wrapper, but stable production
owners depend on this responsibility-named module instead of source chronology.
"""

from __future__ import annotations

from dcoir_review.module_loader import load_segments_into

load_segments_into(globals(), "dcoir_review.risk_sentinel_primitives")
