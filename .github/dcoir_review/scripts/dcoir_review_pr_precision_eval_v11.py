#!/usr/bin/env python3
"""Current v11 production-shaped clean-PR precision evaluator.

V11 preserves the complete historical v10 composition and replaces only the
fork-workflow grammar/checkout-scope control exposed by the operator-approved
v10 paired Sonnet/Opus adjudication. Historical evaluators remain unchanged.
"""
from __future__ import annotations

import dcoir_review_pr_precision_eval as base
import dcoir_review_pr_precision_eval_v10 as v10

V11_REPLACEMENTS_PATH = base.target.DCOIR_ROOT / "evaluation" / "pr_precision_clean_replacements_v11.json"
V11_REPLACEMENTS_SCHEMA = "dcoir_review_pr_precision_clean_replacements_v11"


def load_v11_cases() -> list[dict[str, object]]:
    return base._apply_replacements(
        v10.load_v10_cases(),
        V11_REPLACEMENTS_PATH,
        V11_REPLACEMENTS_SCHEMA,
        "v11",
        expected_replacement_count=1,
    )


def main() -> int:
    base.target.load_cases = load_v11_cases
    base.target.build_pr_prompt = base.build_pr_prompt
    base.target.REPORT_SCHEMA = "dcoir_review_pr_precision_eval_report_v11"
    base.resilient.install(base.target.base)
    return base.target.main()


if __name__ == "__main__":
    raise SystemExit(main())
