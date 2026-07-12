#!/usr/bin/env python3
"""Create ChatGPT-readable GitHub workflow reports and retention cleanup plans.

Modes:
- workflow-run: read a GitHub workflow_run event payload and write one workflow_report.md.
- cleanup: scan committed workflow_report.md files and cleanup-managed staging paths.
"""
from __future__ import annotations

import argparse

from workflow_report_cleanup import make_cleanup_plan
from workflow_report_run import make_workflow_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    wr = sub.add_parser("workflow-run")
    wr.add_argument("--event-json")
    wr.add_argument("--workflow-name")
    wr.add_argument("--run-id")
    wr.add_argument("--log-file", default="")
    wr.add_argument("--log-error-file", default="")
    wr.add_argument("--max-log-lines", type=int, default=300)
    wr.add_argument("--max-log-chars", type=int, default=40000)
    wr.set_defaults(func=make_workflow_report)

    cl = sub.add_parser("cleanup")
    cl.add_argument("--success-days", type=int, default=1)
    cl.add_argument("--failure-days", type=int, default=7)
    cl.add_argument("--cleanup-days", type=int, default=2)
    cl.add_argument("--request-days", type=int, default=1)
    cl.add_argument("--bundle-days", type=int, default=2)
    cl.add_argument("--workflow-filter", default="")
    cl.add_argument("--report-id", default="")
    cl.add_argument("--removed-paths-file", default=".github/tmp/chatgpt_report_cleanup_removed.txt")
    cl.add_argument("--dry-run", action="store_true")
    cl.add_argument("--keep-latest", action="store_true", default=True)
    cl.set_defaults(func=make_cleanup_plan)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
