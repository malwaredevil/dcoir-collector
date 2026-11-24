#!/usr/bin/env python3
"""Compatibility bridge for historical dcoir_review_required_runtime_patch_v9_prompting imports.

Canonical implementation lives in ``dcoir_review.prompt_review_diagnostics_helpers``.
"""

from __future__ import annotations

from dcoir_review.historical_compat import install_historical_alias
from dcoir_review import prompt_review_diagnostics_helpers as _stable

install_historical_alias(__name__, _stable)
