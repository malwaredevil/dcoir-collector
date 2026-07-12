#!/usr/bin/env python3
"""Compatibility wrapper for connector-safe DCOIR Review layer openrouter_pr_review_pareto_context_regression_selftest."""

from __future__ import annotations

from pathlib import Path
import sys

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from dcoir_review.module_loader import load_segments_into

load_segments_into(globals(), 'openrouter_pr_review_pareto_context_regression_selftest')
