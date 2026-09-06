#!/usr/bin/env python3
"""Crash-resilient entrypoint for the evaluation-only PR mutation harness."""
from __future__ import annotations

import dcoir_review_eval_resilient_openrouter as resilient
import dcoir_review_pr_mutation_eval as target


def main() -> int:
    resilient.install(target.base)
    return target.main()


if __name__ == "__main__":
    raise SystemExit(main())
