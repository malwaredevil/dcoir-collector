#!/usr/bin/env python3
"""Production-shaped clean-PR precision evaluator for DCOIR candidates.

This evaluation-only lane supplies ten PRs whose hidden ground truth is clean
under the full reviewer policy. V3 through V9 are retained as historical
compositions for reproducibility. V7 composes from v6 and replaces the final
PR-title control exposed by the Sonnet 5/high v6 confirmation: v6 recognized
normalized dot-notation title expressions but could miss equivalent bracket/
index access inside shell source. V7 enforces the stronger structural boundary
that this workflow's run shell source contains no direct GitHub expressions;
dynamic GitHub values must cross through env bindings. V8 hardens three
ambiguous clean controls exposed by v7 adjudication. V9 is implemented in the
separate v9 wrapper and replaces only the v8 fork-workflow guard after live
Sonnet evidence showed its literal `secrets.` check could miss semantic
whole-context or function-wrapped secret-context expressions.

Workflow cases may include an explicit trusted approval receipt injected into
trusted context; PR body text remains untrusted. Set
DCOIR_PRECISION_INCLUDE_TRUSTED_CONTEXT=0 to run the same cases without that
receipt and measure the current prompt-context gap. No benchmark label or
ground truth is shown to the model. The resilient request adapter prevents one
malformed response from aborting a paid batch.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import dcoir_review_eval_resilient_openrouter as resilient
import dcoir_review_pr_mutation_eval as target

BASE_CORPUS_PATH = target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_cases_v2.json"
BASE_CORPUS_SCHEMA = "dcoir_review_pr_precision_clean_cases_v2"
V3_REPLACEMENTS_PATH = target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_replacements_v3.json"
V3_REPLACEMENTS_SCHEMA = "dcoir_review_pr_precision_clean_replacements_v3"
V4_REPLACEMENTS_PATH = target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_replacements_v4.json"
V4_REPLACEMENTS_SCHEMA = "dcoir_review_pr_precision_clean_replacements_v4"
V5_REPLACEMENTS_PATH = target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_replacements_v5.json"
V5_REPLACEMENTS_SCHEMA = "dcoir_review_pr_precision_clean_replacements_v5"
V6_REPLACEMENTS_PATH = target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_replacements_v6.json"
V6_REPLACEMENTS_SCHEMA = "dcoir_review_pr_precision_clean_replacements_v6"
V7_REPLACEMENTS_PATH = target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_replacements_v7.json"
V7_REPLACEMENTS_SCHEMA = "dcoir_review_pr_precision_clean_replacements_v7"


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


def _apply_replacements(
    cases: list[dict[str, Any]],
    replacement_path: Path,
    replacement_schema: str,
    version: str,
    expected_replacement_count: int,
) -> list[dict[str, Any]]:
    replacement_data = target.base.load_json(replacement_path)
    if replacement_data.get("schema_version") != replacement_schema:
        raise ValueError(f"Unexpected clean PR precision {version} replacement schema")
    replace_ids = replacement_data.get("replaces_case_ids")
    replacement_raw = replacement_data.get("cases")
    if (
        not isinstance(replace_ids, list)
        or len(replace_ids) != expected_replacement_count
        or len(set(map(str, replace_ids))) != expected_replacement_count
    ):
        raise ValueError(
            f"Clean PR precision {version} must replace exactly "
            f"{expected_replacement_count} unique prior-version cases"
        )
    if not isinstance(replacement_raw, list) or len(replacement_raw) != expected_replacement_count:
        raise ValueError(
            f"Clean PR precision {version} must supply exactly "
            f"{expected_replacement_count} replacement cases"
        )

    replace_set = {str(item) for item in replace_ids}
    case_ids = {str(case["id"]) for case in cases}
    if not replace_set.issubset(case_ids):
        raise ValueError(f"Clean PR precision {version} replacement ids must exist in the prior version")
    replacements = [_validate_case(raw) for raw in replacement_raw]

    resolved = [case for case in cases if str(case["id"]) not in replace_set] + replacements
    resolved_ids = [str(case["id"]) for case in resolved]
    if len(resolved) != 10 or len(set(resolved_ids)) != 10:
        raise ValueError(f"Clean PR precision {version} must resolve to exactly 10 unique cases")
    if replace_set.intersection(resolved_ids):
        raise ValueError(f"Superseded clean cases leaked into {version}")
    return resolved


def load_v3_cases() -> list[dict[str, Any]]:
    base_data = target.base.load_json(BASE_CORPUS_PATH)
    if base_data.get("schema_version") != BASE_CORPUS_SCHEMA:
        raise ValueError("Unexpected clean PR precision base corpus schema")
    base_raw = base_data.get("cases")
    if not isinstance(base_raw, list) or len(base_raw) != 10:
        raise ValueError("Clean PR precision v2 base corpus must contain exactly 10 cases")
    base_cases = [_validate_case(raw) for raw in base_raw]
    return _apply_replacements(
        base_cases,
        V3_REPLACEMENTS_PATH,
        V3_REPLACEMENTS_SCHEMA,
        "v3",
        expected_replacement_count=2,
    )


def load_v4_cases() -> list[dict[str, Any]]:
    return _apply_replacements(
        load_v3_cases(),
        V4_REPLACEMENTS_PATH,
        V4_REPLACEMENTS_SCHEMA,
        "v4",
        expected_replacement_count=2,
    )


def load_v5_cases() -> list[dict[str, Any]]:
    return _apply_replacements(
        load_v4_cases(),
        V5_REPLACEMENTS_PATH,
        V5_REPLACEMENTS_SCHEMA,
        "v5",
        expected_replacement_count=3,
    )


def load_cases() -> list[dict[str, Any]]:
    """Historical v5 compatibility loader for the retained v5 fixture selftest."""
    return load_v5_cases()


def load_v6_cases() -> list[dict[str, Any]]:
    return _apply_replacements(
        load_v5_cases(),
        V6_REPLACEMENTS_PATH,
        V6_REPLACEMENTS_SCHEMA,
        "v6",
        expected_replacement_count=1,
    )


def load_v7_cases() -> list[dict[str, Any]]:
    return _apply_replacements(
        load_v6_cases(),
        V7_REPLACEMENTS_PATH,
        V7_REPLACEMENTS_SCHEMA,
        "v7",
        expected_replacement_count=1,
    )


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
    target.load_cases = load_v7_cases
    target.build_pr_prompt = build_pr_prompt
    target.REPORT_SCHEMA = "dcoir_review_pr_precision_eval_report_v7"
    resilient.install(target.base)
    return target.main()


if __name__ == "__main__":
    raise SystemExit(main())
