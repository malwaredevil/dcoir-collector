#!/usr/bin/env python3
"""Validate duplicate-function JSON and Markdown report artifacts."""
from __future__ import annotations

import argparse
from pathlib import Path

from lib.duplicate_function_report_contract import (
    DEFAULT_JSON,
    DEFAULT_MARKDOWN,
    ValidationError,
    validate_reports,
)
from lib.duplicate_function_report_selftest import run_self_test


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=DEFAULT_JSON.as_posix(), type=Path)
    parser.add_argument("--markdown", default=DEFAULT_MARKDOWN.as_posix(), type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    try:
        if args.self_test:
            run_self_test()
        else:
            validate_reports(args.json, args.markdown)
    except ValidationError as exc:
        print(f"Duplicate-function report validation failed: {exc}")
        return 1

    print("Duplicate-function report validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
