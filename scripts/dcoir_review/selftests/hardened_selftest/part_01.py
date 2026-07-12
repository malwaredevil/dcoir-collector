#!/usr/bin/env python3
"""Offline checks for the hardened DCOIR Review runner."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "openrouter_pr_review_hardened.py"

spec = importlib.util.spec_from_file_location("openrouter_pr_review_hardened", SCRIPT)
if spec is None or spec.loader is None:
    raise SystemExit("unable to load openrouter_pr_review_hardened.py")
mod = importlib.util.module_from_spec(spec)
import sys

sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

os.environ["GITHUB_REPOSITORY"] = "DCOIR-Collector/dcoir-collector"
os.environ["PR_NUMBER"] = "277"

config = mod.load_hardened_config(str(ROOT / ".github" / "openrouter-pr-review-governed.yml"))
assert "/or-review" in config.commands
assert "/dcoir-review" in config.commands
assert config.model == "openrouter/auto"
assert config.model_stack == ["openrouter/auto"]
assert config.smoke_test_free_model is False
assert config.auto_cost_quality_tradeoff == 2
assert "openai/gpt-5*" in config.auto_allowed_models
assert "google/gemini-2.5-pro*" in config.auto_allowed_models
assert "google/gemini-3.1-pro*" in config.auto_allowed_models
assert "google/gemini-*" not in config.auto_allowed_models
assert config.fallback_models == []
assert config.fail_on_unanchored_findings is True
assert config.fail_on_summary_only_problem is True
assert config.risk_sentinel_quality_gate is True
assert config.risk_sentinel_retry_on_empty is True
assert config.risk_sentinel_max_anchors == 12
assert config.debug is False
assert config.post_progress_comment is False

budgeted_findings = mod.select_findings_for_inline(
    [
        {
            "title": "Optional TypeScript issue",
            "severity": "critical",
            "confidence": 0.99,
            "path": "project_sources/validation/example.ts",
            "line": 10,
            "body": "Optional TypeScript issue.",
            "suggested_replacement": "",
            "validation": "",
        },
        {
            "title": "PowerShell issue",
            "severity": "high",
            "confidence": 0.90,
            "path": "collector/run.ps1",
            "line": 20,
            "body": "PowerShell issue.",
            "suggested_replacement": "",
            "validation": "",
        },
        {
            "title": "GitHub Actions issue",
            "severity": "medium",
            "confidence": 0.90,
            "path": ".github/workflows/validate.yml",
            "line": 5,
            "body": "GitHub Actions issue.",
            "suggested_replacement": "",
            "validation": "",
        },
    ],
    2,
)
assert [item["path"] for item in budgeted_findings] == ["collector/run.ps1", ".github/workflows/validate.yml"]

validation_hints = mod.validation_hint_block(
    [
        {"filename": "collector/example.py"},
        {"filename": "collector/example.ps1"},
        {"filename": ".github/workflows/openrouter-pr-review.yml"},
    ]
)
assert "python3 -m py_compile collector/example.py" in validation_hints
assert "PSParser" in validation_hints
assert "build_workflow_inventory.py --check" in validation_hints

short_prompt_config = copy.copy(config)
short_prompt_config.max_prompt_chars = 900
large_diff = """diff --git a/docs/review.md b/docs/review.md
index 1111111..2222222 100644
--- a/docs/review.md
+++ b/docs/review.md
@@ -1,2 +1,3 @@
 Review gates remain required.
+External review may be skipped after local checks.
 Keep issue receipts current.
""" + ("+filler line to force prompt truncation\n" * 200)
bounded_prompt = mod.build_prompt(
    {"number": 277, "title": "Prompt budget test", "body": "Ensure hardening survives truncation."},
    [{"filename": "docs/review.md", "status": "modified", "additions": 201, "deletions": 0, "changes": 201}],
    large_diff,
    short_prompt_config,
)
assert len(bounded_prompt) <= short_prompt_config.max_prompt_chars
assert bounded_prompt.startswith("Governed review hardening requirements:")
assert "Every semantic, Markdown, governance, validation, or review-gate concern" in bounded_prompt

schema = json.loads((ROOT / "schemas" / "openrouter-pr-review.schema.json").read_text(encoding="utf-8"))
payload = mod.build_openrouter_payload("review prompt", schema, config, ["venice"], "openrouter/auto")
assert payload["model"] == "openrouter/auto"
assert "models" not in payload
assert payload["provider"]["ignore"] == ["venice"]
assert payload["provider"]["allow_fallbacks"] is True
assert payload["provider"]["require_parameters"] is True
assert payload["response_format"]["type"] == "json_schema"
assert payload["response_format"]["json_schema"]["strict"] is True
assert payload["plugins"] == [
    {
        "id": "auto-router",
        "allowed_models": config.auto_allowed_models,
        "cost_quality_tradeoff": 2,
    }
]
assert payload["session_id"].startswith("dcoir-review:DCOIR-Collector-dcoir-collector:pr-277")
assert len(payload["session_id"]) <= 256

with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
    handle.write(
        "\n".join(
            [
                "commands:",
                "  - /or-review",
                "model: openrouter/free",
                "model_stack:",
                "  - openrouter/free",
                "smoke_test_free_model: false",
            ]
        )
    )
    free_config_path = handle.name
try:
    try:
        mod.load_hardened_config(free_config_path)
    except RuntimeError as exc:
        assert "smoke-test only" in str(exc)
    else:
        raise AssertionError("free-router config without smoke opt-in should fail")
finally:
    Path(free_config_path).unlink(missing_ok=True)

sample_diff = """diff --git a/docs/review.md b/docs/review.md
index 1111111..2222222 100644
--- a/docs/review.md
+++ b/docs/review.md
@@ -1,2 +1,3 @@
 Review gates remain required.
+External review may be skipped after local checks.
 Keep issue receipts current.
"""
line_index = mod.base.build_diff_line_index(sample_diff)
accepted = mod.normalize_findings(
    {
        "summary": "One actionable review-gate regression.",
        "findings": [
            {
                "title": "Review gate bypass",
                "severity": "high",
                "confidence": 0.95,
                "path": "docs/review.md",
                "line": 2,
                "body": "The changed line weakens governed review ordering.",
                "suggested_replacement": "",
                "validation": "Read back issue and PR review gates.",
            }
        ],
    },
    config,
    line_index,
)
assert len(accepted) == 1

inline_findings, review_body_findings = mod.split_findings(
    {
        "summary": "The only high-signal finding is a review-gate regression.",
        "findings": [
            {
                "title": "Review gate bypass",
                "severity": "high",
                "confidence": 0.95,
                "path": "docs/review.md",
                "line": 99,
                "body": "The changed wording weakens governed review ordering.",
                "suggested_replacement": "",
                "validation": "Read back issue and PR review gates.",
            }
        ],
    },
    config,
    line_index,
)
assert inline_findings == []
assert len(review_body_findings) == 1
assert "not an added changed line" in review_body_findings[0]["_unanchored_reason"]


def assert_clean(summary: str) -> None:
    assert mod.normalize_findings({"summary": summary, "findings": []}, config, line_index) == []
