#!/usr/bin/env python3
"""Offline checks for review-quality recovery retries."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "openrouter_pr_review_hardened.py"

spec = importlib.util.spec_from_file_location("openrouter_pr_review_hardened", SCRIPT)
if spec is None or spec.loader is None:
    raise SystemExit("unable to load openrouter_pr_review_hardened.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

os.environ["GITHUB_REPOSITORY"] = "DCOIR-Collector/dcoir-collector"
os.environ["PR_NUMBER"] = "296"

config = mod.load_hardened_config(str(ROOT / ".github" / "openrouter-pr-review-governed.yml"))
assert config.review_quality_retry_on_rejected_output is True

schema = json.loads((ROOT / "schemas" / "openrouter-pr-review.schema.json").read_text(encoding="utf-8"))
sample_diff = """diff --git a/docs/review.md b/docs/review.md
index 1111111..2222222 100644
--- a/docs/review.md
+++ b/docs/review.md
@@ -1,2 +1,3 @@
 Review gates remain required.
+External review may be skipped after local checks.
 Keep issue receipts current.
"""
line_index = mod.build_added_line_index(sample_diff)
assert ("docs/review.md", 2) in line_index
assert ("docs/review.md", 1) not in line_index
assert ("docs/review.md", 3) not in line_index

optional_only_sentinel = mod.RiskSentinel(
    path="tools/example.ts",
    line=7,
    label="Node.js command execution",
    detail="child-process execution can turn request-controlled strings into command execution unless command and arguments are bounded",
    text="exec(request.command)",
)
assert not mod.is_required_risk_sentinel(optional_only_sentinel)
assert (
    mod.review_quality_retry_reason(
        {"summary": "No high-confidence findings were found.", "findings": []},
        config,
        [optional_only_sentinel],
        {("tools/example.ts", 7): 1},
    )
    == ""
)


def accepted_result(confidence: float = 0.94) -> dict:
    return {
        "summary": "One actionable review-gate regression.",
        "findings": [
            {
                "title": "Review gate bypass",
                "severity": "high",
                "confidence": confidence,
                "path": "docs/review.md",
                "line": 2,
                "body": "The changed line weakens governed review ordering.",
                "suggested_replacement": "",
                "validation": "Read back issue and PR review gates.",
            }
        ],
    }


def run_recovery_case(first_result: dict, expected_reason: str) -> None:
    calls: list[str] = []
    original_openrouter_review = mod.openrouter_review

    def fake_openrouter_review(prompt: str, _schema: dict, _config: object, _reporter: object | None = None):
        calls.append(prompt)
        if len(calls) == 1:
            return first_result, "first-model", ""
        return accepted_result(), "recovery-model", ""

    mod.openrouter_review = fake_openrouter_review
    try:
        retry_result, retry_model, _retry_tier = mod.openrouter_review_with_quality_retry(
            "initial prompt",
            schema,
            config,
            None,
            [],
            line_index,
        )
    finally:
        mod.openrouter_review = original_openrouter_review

    assert len(calls) == 2
    assert retry_model == "recovery-model"
    assert len(mod.normalize_findings(retry_result, config, line_index)) == 1
    assert "Review quality retry" in calls[1]
    assert expected_reason in calls[1]


run_recovery_case(
    {"summary": "A governance regression remains in the review gate.", "findings": []},
    "summary indicated a possible issue",
)

run_recovery_case(
    {
        "summary": "Possible review gate bypass.",
        "findings": [
            {
                "title": "Review gate bypass",
                "severity": "high",
                "confidence": 0.20,
                "path": "docs/review.md",
                "line": 2,
                "body": "The changed line may weaken governed review ordering.",
                "suggested_replacement": "",
                "validation": "Read back issue and PR review gates.",
            }
        ],
    },
    "none met the configured minimum confidence",
)


run_recovery_case(
    {
        "summary": "One actionable review-gate regression, but the anchor is wrong.",
        "findings": [
            {
                "title": "Review gate bypass",
                "severity": "high",
                "confidence": 0.95,
                "path": "docs/review.md",
                "line": 99,
                "body": "The changed line weakens governed review ordering.",
                "suggested_replacement": "",
                "validation": "Read back issue and PR review gates.",
            }
        ],
    },
    "none were anchored to changed diff lines",
)

run_recovery_case(
    {
        "summary": "One actionable review-gate regression, but the anchor is on context.",
        "findings": [
            {
                "title": "Review gate bypass",
                "severity": "high",
                "confidence": 0.95,
                "path": "docs/review.md",
                "line": 1,
                "body": "The changed line weakens governed review ordering, but this anchor is unchanged context.",
                "suggested_replacement": "",
                "validation": "Read back issue and PR review gates.",
            }
        ],
    },
    "none were anchored to changed diff lines",
)

merge_diff = """diff --git a/tools/first.py b/tools/first.py
index 0000000..1111111 100644
--- /dev/null
+++ b/tools/first.py
@@ -0,0 +1,2 @@
+subprocess.run(request["command"], shell=True)
+print("done")
diff --git a/tools/second.py b/tools/second.py
index 0000000..2222222 100644
--- /dev/null
+++ b/tools/second.py
@@ -0,0 +1,2 @@
+cursor.execute(f"select * from alerts where {request['filter']}")
+print("done")
"""
merge_line_index = mod.build_added_line_index(merge_diff)
merge_sentinels = [
    mod.RiskSentinel(
        path="tools/second.py",
        line=1,
        label="raw SQL/query string interpolation",
        detail="raw variables are interpolated into a query-like string",
        text='cursor.execute(f"select * from alerts where {request[\'filter\']}")',
    )
]
merge_calls: list[str] = []
original_openrouter_review = mod.openrouter_review


def fake_merge_review(prompt: str, _schema: dict, _config: object, _reporter: object | None = None):
    merge_calls.append(prompt)
    if len(merge_calls) == 1:
        return {
            "summary": "Found one command execution issue.",
            "findings": [
                {
                    "title": "Shell command execution",
                    "severity": "critical",
                    "confidence": 0.98,
                    "path": "tools/first.py",
                    "line": 1,
                    "body": "shell=True executes request-controlled command text.",
                    "suggested_replacement": "",
                    "validation": "python3 -m py_compile tools/first.py",
                }
            ],
        }, "first-model", ""
    return {
        "summary": "Found one SQL issue.",
        "findings": [
            {
                "title": "SQL interpolation",
                "severity": "critical",
                "confidence": 0.98,
                "path": "tools/second.py",
                "line": 1,
                "body": "SQL interpolation accepts request-controlled filter text; use parameters or a bounded query builder.",
                "suggested_replacement": "",
                "validation": "python3 -m py_compile tools/second.py",
            }
        ],
    }, "recovery-model", ""


mod.openrouter_review = fake_merge_review
try:
    merged_result, merged_model, _merged_tier = mod.openrouter_review_with_quality_retry(
        "initial prompt",
        schema,
        config,
        None,
        merge_sentinels,
        merge_line_index,
    )
finally:
    mod.openrouter_review = original_openrouter_review

assert len(merge_calls) == 2
assert merged_model == "recovery-model"
merged_findings = mod.normalize_findings(merged_result, config, merge_line_index)
assert len(merged_findings) == 2
assert {item["path"] for item in merged_findings} == {"tools/first.py", "tools/second.py"}

debug_artifact_config = copy.copy(config)
debug_artifact_config.debug = True
with tempfile.TemporaryDirectory() as tmp:
    previous_debug_artifact_dir = os.environ.get("DCOIR_REVIEW_DEBUG_ARTIFACT_DIR")
    os.environ["DCOIR_REVIEW_DEBUG_ARTIFACT_DIR"] = tmp
    calls: list[str] = []
    original_openrouter_review = mod.openrouter_review

    def fake_debug_artifact_review(prompt: str, _schema: dict, _config: object, _reporter: object | None = None):
        calls.append(prompt)
        if len(calls) == 1:
            return {"summary": "A governance regression remains in the review gate.", "findings": []}, "first-model", ""
        return accepted_result(), "recovery-model", ""

    mod.openrouter_review = fake_debug_artifact_review
    try:
        mod.openrouter_review_with_quality_retry("initial prompt", schema, debug_artifact_config, None, [], line_index)
    finally:
        mod.openrouter_review = original_openrouter_review
        if previous_debug_artifact_dir is None:
            os.environ.pop("DCOIR_REVIEW_DEBUG_ARTIFACT_DIR", None)
        else:
            os.environ["DCOIR_REVIEW_DEBUG_ARTIFACT_DIR"] = previous_debug_artifact_dir

    assert (Path(tmp) / "prompts/01-initial-prompt.txt").read_text(encoding="utf-8") == "initial prompt"
    retry_prompt = (Path(tmp) / "prompts/02-quality-retry-prompt.txt").read_text(encoding="utf-8")
    assert "Review quality retry" in retry_prompt
    assert "summary indicated a possible issue" in retry_prompt
    retry_metadata = json.loads((Path(tmp) / "metadata/02-quality-retry-request.json").read_text(encoding="utf-8"))
    assert "summary indicated a possible issue" in retry_metadata["retry_reason"]
    assert json.loads((Path(tmp) / "responses/02-quality-retry-result.json").read_text(encoding="utf-8"))["model_used"] == "recovery-model"
    merged_response = json.loads((Path(tmp) / "responses/03-quality-retry-merged-result.json").read_text(encoding="utf-8"))
    assert merged_response["merged_finding_count"] == 1

retry_disabled = copy.copy(config)
retry_disabled.review_quality_retry_on_rejected_output = False
calls: list[str] = []
original_openrouter_review = mod.openrouter_review


def fake_disabled_review(prompt: str, _schema: dict, _config: object, _reporter: object | None = None):
    calls.append(prompt)
    return {"summary": "A governance regression remains in the review gate.", "findings": []}, "first-model", ""


mod.openrouter_review = fake_disabled_review
try:
    disabled_result, _disabled_model, _disabled_tier = mod.openrouter_review_with_quality_retry(
        "initial prompt",
        schema,
        retry_disabled,
        None,
        [],
        line_index,
    )
finally:
    mod.openrouter_review = original_openrouter_review

assert len(calls) == 1
try:
    mod.normalize_findings(disabled_result, retry_disabled, line_index)
except mod.ReviewQualityError as exc:
    assert "summary indicated a possible issue" in str(exc)
else:
    raise AssertionError("summary-only quality failure should still fail closed when recovery is disabled")

print("review quality recovery selftest passed")
