#!/usr/bin/env python3
"""Regression checks for actionable-problem language in DCOIR review summaries."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "openrouter_pr_review_hardened.py"

spec = importlib.util.spec_from_file_location("openrouter_pr_review_hardened", SCRIPT)
if spec is None or spec.loader is None:
    raise SystemExit("unable to load openrouter_pr_review_hardened.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

config = mod.load_hardened_config(str(ROOT / "openrouter-pr-review-pareto.yml"))

live_probe_summary = (
    "Completed review of live_suggestion_probe.py. Found a logic error where a truthy string literal "
    "in a boolean condition causes is_high_severity to always evaluate to True."
)
assert mod.summary_suggests_problem(live_probe_summary)
assert mod.review_quality_retry_reason(
    {"summary": live_probe_summary, "findings": []},
    config,
    [],
    {(".github/dcoir_review/evaluation/live_suggestion_probe.py", 10): 1},
) == "model summary indicated a possible issue while the structured findings array was empty"

for clean_summary in (
    "No logic errors were found.",
    "No errors were identified in the changed diff.",
    "Error handling was improved; no actionable findings were found.",
):
    assert not mod.summary_suggests_problem(clean_summary), clean_summary

print("openrouter_pr_review_summary_problem_selftest passed")
