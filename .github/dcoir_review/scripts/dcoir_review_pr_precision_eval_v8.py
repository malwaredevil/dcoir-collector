#!/usr/bin/env python3
"""Current v8 production-shaped clean-PR precision evaluator.

V8 preserves the complete historical v7 composition and replaces only three
controls exposed by the operator-approved v7 Sonnet clean-nine adjudication:
PowerShell native-exit behavioral coverage, JSON fallback-policy semantics,
and the fork-workflow permissions guard. The v7 evaluator remains unchanged so
all earlier paid evidence stays reproducible.
"""
from __future__ import annotations

import dcoir_review_pr_precision_eval as v7

V8_REPLACEMENTS_PATH = v7.target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_replacements_v8.json"
V8_REPLACEMENTS_SCHEMA = "dcoir_review_pr_precision_clean_replacements_v8"


def load_v8_cases() -> list[dict[str, object]]:
    return v7._apply_replacements(
        v7.load_v7_cases(),
        V8_REPLACEMENTS_PATH,
        V8_REPLACEMENTS_SCHEMA,
        "v8",
        expected_replacement_count=3,
    )


def main() -> int:
    v7.target.load_cases = load_v8_cases
    v7.target.build_pr_prompt = v7.build_pr_prompt
    v7.target.REPORT_SCHEMA = "dcoir_review_pr_precision_eval_report_v8"
    v7.resilient.install(v7.target.base)
    return v7.target.main()


if __name__ == "__main__":
    raise SystemExit(main())
