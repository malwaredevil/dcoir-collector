#!/usr/bin/env python3
"""Production-shaped clean-PR precision evaluator for DCOIR candidates.

This evaluation-only lane supplies ten PRs whose hidden ground truth is clean
under the full reviewer policy. V3 is composed from the audited-good v2 cases
plus two replacement fixtures that remove optimistic assumptions discovered
before acceptance testing. Workflow cases may include an explicit trusted
approval receipt injected into trusted context; PR body text remains untrusted.
Set DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT=0 to run the same cases without
that receipt and measure the current prompt-context gap. No benchmark label or
ground truth is shown to the model. The resilient request adapter prevents one
malformed response from aborting the paid batch.
"""
from __future__ import annotations

import json
import os
from typing import Any

import dcoir_review_eval_resilient_openrouter as resilient
import dcoir_review_pr_mutation_eval as target

BASE_CORPUS_PATH = target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_cases_v2.json"
BASE_CORPUS_SCHEMA = "dcoir_review_pr_precision_clean_cases_v2"
REPLACEMENTS_PATH = target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_replacements_v3.json"
REPLACEMENTS_SCHEMA = "dcoir_review_pr_precision_clean_replacements_v3"


def _validate_case(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Clean PR precision case must be an object")
    case = dict(raw)
    case_id = str(case.get("id", "")).strip()
    if not case_id:
        raise ValueError("Clean PR precision case id is required")
    files = case.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError(f"{case_id}: files must be a non-empty list")
    names = [str(item.get("filename", "")) for item in files if isinstance(item, dict)]
    if len(names) != len(files) or any(not name for name in names) or len(set(names)) != len(names):
        raise ValueError(f"{case_id}: changed file names must be present and unique")
    if case.get("expected_findings") != []:
        raise ValueError(f"{case_id}: clean precision cases must have zero expected findings")
    return case


def load_cases() -> list[dict[str, Any]]:
    base_data = target.base.load_json(BASE_CORPUS_PATH)
    if base_data.get("schema_version") != BASE_CORPUS_SCHEMA:
        raise ValueError("Unexpected clean PR precision base corpus schema")
    base_raw = base_data.get("cases")
    if not isinstance(base_raw, list) or len(base_raw) != 10:
        raise ValueError("Clean PR precision v2 base corpus must contain exactly 10 cases")

    replacement_data = target.base.load_json(REPLACEMENTS_PATH)
    if replacement_data.get("schema_version") != REPLACEMENTS_SCHEMA:
        raise ValueError("Unexpected clean PR precision replacement schema")
    replace_ids = replacement_data.get("replaces_case_ids")
    replacement_raw = replacement_data.get("cases")
    if not isinstance(replace_ids, list) or len(replace_ids) != 2 or len(set(map(str, replace_ids))) != 2:
        raise ValueError("Clean PR precision v3 must replace exactly two unique v2 cases")
    if not isinstance(replacement_raw, list) or len(replacement_raw) != 2:
        raise ValueError("Clean PR precision v3 must supply exactly two replacement cases")

    replace_set = {str(item) for item in replace_ids}
    base_cases = [_validate_case(raw) for raw in base_raw]
    base_ids = {str(case["id"]) for case in base_cases}
    if not replace_set.issubset(base_ids):
        raise ValueError("Clean PR precision v3 replacement ids must exist in v2")
    replacements = [_validate_case(raw) for raw in replacement_raw]

    cases = [case for case in base_cases if str(case["id"]) not in replace_set] + replacements
    ids = [str(case["id"]) for case in cases]
    if len(cases) != 10 or len(set(ids)) != 10:
        raise ValueError("Clean PR precision v3 must resolve to exactly 10 unique cases")
    if replace_set.intersection(ids):
        raise ValueError("Superseded v2 clean cases leaked into v3")
    return cases


def include_trusted_context() -> bool:
    return os.environ.get("DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT", "1").strip().lower() not in {"0", "false", "no", "off"}


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
    trusted_context = str(case.get("trusted_context", "")).strip() if include_trusted_context() else ""
    trusted_extra = f"\n\nTrusted evaluation context:\n{trusted_context}" if trusted_context else ""
    unified_diff = "\n".join(patches)
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
{unified_diff}

Review task:
Find only high-signal issues in the PR diff. For each finding, give the exact changed file path and right-side line number. Provide a suggested_replacement only when a small GitHub suggestion block would be safe and likely to apply cleanly. Include validation commands that should pass after the fix.""".strip()


def main() -> int:
    target.load_cases = load_cases
    target.build_pr_prompt = build_pr_prompt
    target.REPORT_SCHEMA = "dcoir_review_pr_precision_eval_report_v3"
    resilient.install(target.base)
    return target.main()


if __name__ == "__main__":
    raise SystemExit(main())
