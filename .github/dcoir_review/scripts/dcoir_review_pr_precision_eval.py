#!/usr/bin/env python3
"""Production-shaped clean-PR precision evaluator for DCOIR candidates.

This evaluation-only lane reuses the mutation scorer but supplies ten PRs whose
hidden ground truth is clean under the full reviewer policy. Workflow cases may
include an explicit trusted approval receipt injected into trusted context; PR
body text remains untrusted. No benchmark label or ground truth is shown to the
model. The resilient request adapter prevents one malformed response from
aborting the paid batch.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import dcoir_review_eval_resilient_openrouter as resilient
import dcoir_review_pr_mutation_eval as target

CORPUS_PATH = target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_cases_v1.json"
CORPUS_SCHEMA = "dcoir_review_pr_precision_clean_cases_v1"


def load_cases() -> list[dict[str, Any]]:
    data = target.base.load_json(CORPUS_PATH)
    if data.get("schema_version") != CORPUS_SCHEMA:
        raise ValueError("Unexpected clean PR precision corpus schema")
    raw_cases = data.get("cases")
    if not isinstance(raw_cases, list) or len(raw_cases) != 10:
        raise ValueError("Clean PR precision corpus must contain exactly 10 cases")
    cases: list[dict[str, Any]] = []
    ids: set[str] = set()
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise ValueError("Clean PR precision case must be an object")
        case = dict(raw)
        case_id = str(case.get("id", "")).strip()
        if not case_id or case_id in ids:
            raise ValueError(f"Missing or duplicate clean PR precision id: {case_id!r}")
        ids.add(case_id)
        files = case.get("files")
        if not isinstance(files, list) or not files:
            raise ValueError(f"{case_id}: files must be a non-empty list")
        names = [str(item.get("filename", "")) for item in files if isinstance(item, dict)]
        if len(names) != len(files) or any(not name for name in names) or len(set(names)) != len(names):
            raise ValueError(f"{case_id}: changed file names must be present and unique")
        expected = case.get("expected_findings")
        if expected != []:
            raise ValueError(f"{case_id}: clean precision cases must have zero expected findings")
        cases.append(case)
    return cases


def build_pr_prompt(case: dict[str, Any]) -> str:
    changed_files: list[dict[str, Any]] = []
    patches: list[str] = []
    for item in case["files"]:
        patch = str(item.get("patch", ""))
        additions, deletions = target.file_stats(patch)
        changed_files.append({
            "filename": str(item["filename"]),
            "status": str(item.get("status", "modified")),
            "additions": additions,
            "deletions": deletions,
            "changes": additions + deletions,
            "patch": patch,
        })
        patches.append(patch)
    trusted_context = str(case.get("trusted_context", "")).strip()
    trusted_extra = f"\n\nTrusted evaluation context:\n{trusted_context}" if trusted_context else ""
    return f"""Repository: DCOIR-Collector/dcoir-collector
PR number: 9100
PR title: {case['pr_title']}
PR body:
{case['pr_body']}

Trusted repository guidance:
{target.guidance_text()}{trusted_extra}

Preferred validation commands:
{json.dumps(target.VALIDATION_COMMANDS, indent=2)}

Changed file summary:
{json.dumps(changed_files, indent=2)}

Unified diff:
{'\n'.join(patches)}

Review task:
Find only high-signal issues in the PR diff. For each finding, give the exact changed file path and right-side line number. Provide a suggested_replacement only when a small GitHub suggestion block would be safe and likely to apply cleanly. Include validation commands that should pass after the fix.""".strip()


def main() -> int:
    target.load_cases = load_cases
    target.build_pr_prompt = build_pr_prompt
    target.REPORT_SCHEMA = "dcoir_review_pr_precision_eval_report_v1"
    resilient.install(target.base)
    return target.main()


if __name__ == "__main__":
    raise SystemExit(main())
