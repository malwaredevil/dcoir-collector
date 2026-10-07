#!/usr/bin/env python3
"""Compatibility bridge for historical dcoir_review_required_runtime_patch_v5 imports.

Canonical implementation lives in ``dcoir_review.risk_sentinel_policy``.
"""

from __future__ import annotations

from dcoir_review.historical_compat import install_historical_alias
from dcoir_review import risk_sentinel_policy as _stable

install_historical_alias(__name__, _stable)
