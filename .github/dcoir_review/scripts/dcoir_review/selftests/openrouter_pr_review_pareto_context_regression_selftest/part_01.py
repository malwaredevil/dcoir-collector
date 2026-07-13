#!/usr/bin/env python3
"""Focused regression checks for path-write review findings."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "openrouter_pr_review_pareto_context.py"

spec = importlib.util.spec_from_file_location("openrouter_pr_review_pareto_context", SCRIPT)
if spec is None or spec.loader is None:
    raise SystemExit("unable to load openrouter_pr_review_pareto_context.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
