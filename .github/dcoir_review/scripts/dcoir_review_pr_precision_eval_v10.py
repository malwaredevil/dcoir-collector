#!/usr/bin/env python3
"""Current v10 production-shaped clean-PR precision evaluator.

V10 preserves the complete historical v9 composition and replaces only the
fork-workflow checkout-step control exposed by the operator-approved v9
Opus/xhigh current-control adjudication. Historical evaluators remain unchanged.
"""
from __future__ import annotations

import dcoir_review_pr_precision_eval as base
import dcoir_review_pr_precision_eval_v9 as v9

V10_REPLACEMENTS_PATH = base.target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_replacements_v10.json"
V10_REPLACEMENTS_SCHEMA = "dcoir_review_pr_precision_clean_replacements_v10"

def load_v10_cases() -> list[dict[str, object]]:
    return base._apply_replacements(
        v9.load_v9_cases(),
        V10_REPLACEMENTS_PATH,
        V10_REPLACEMENTS_SCHEMA,
        "v10",
        expected_replacement_count=1,
    )

def main() -> int:
    base.target.load_cases = load_v10_cases
    base.target.build_pr_prompt = base.build_pr_prompt
    base.target.REPORT_SCHEMA = "dcoir_review_pr_precision_eval_report_v10"
    base.resilient.install(base.target.base)
    return base.target.main()

if __name__ == "__main__":
    raise SystemExit(main())
