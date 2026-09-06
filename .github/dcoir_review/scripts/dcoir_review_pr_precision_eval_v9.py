#!/usr/bin/env python3
"""Current v9 production-shaped clean-PR precision evaluator.

V9 preserves the complete historical v8 composition and replaces only the
fork-workflow control exposed by the operator-approved v8 Sonnet repaired-three
adjudication. The v8 evaluator remains unchanged so earlier paid evidence stays
reproducible.
"""
from __future__ import annotations

import dcoir_review_pr_precision_eval as base
import dcoir_review_pr_precision_eval_v8 as v8

V9_REPLACEMENTS_PATH = base.target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_replacements_v9.json"
V9_REPLACEMENTS_SCHEMA = "dcoir_review_pr_precision_clean_replacements_v9"


def load_v9_cases() -> list[dict[str, object]]:
    return base._apply_replacements(
        v8.load_v8_cases(),
        V9_REPLACEMENTS_PATH,
        V9_REPLACEMENTS_SCHEMA,
        "v9",
        expected_replacement_count=1,
    )


def main() -> int:
    base.target.load_cases = load_v9_cases
    base.target.build_pr_prompt = base.build_pr_prompt
    base.target.REPORT_SCHEMA = "dcoir_review_pr_precision_eval_report_v9"
    base.resilient.install(base.target.base)
    return base.target.main()


if __name__ == "__main__":
    raise SystemExit(main())
