#!/usr/bin/env python3
"""Compatibility bridge for historical dcoir_review_required_runtime_patch_v11 imports.

Canonical implementation lives in ``dcoir_review.python_k8s_risk_semantics``.
"""

from __future__ import annotations

from dcoir_review.historical_compat import install_historical_alias
from dcoir_review import python_k8s_risk_semantics as _stable

install_historical_alias(__name__, _stable)
