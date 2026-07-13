#!/usr/bin/env python3
"""Validate and apply one governed ops patch request."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from lib.apply_patch_request_contract import RequestError
from lib.apply_patch_request_execution import apply_request, validate_request

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "apply"))
    parser.add_argument("--repo", default=".")
    parser.add_argument("--request", required=True)
    parser.add_argument("--default-branch", default="main")
    parser.add_argument("--report-dir")
    parser.add_argument("--local-only", action="store_true", help="Use the local target branch and do not fetch or push.")
    parser.add_argument("--no-push", action="store_true", help="Commit locally but do not push.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return validate_request(args)
        return apply_request(args)
    except (RequestError, subprocess.CalledProcessError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            if exc.stdout:
                print(exc.stdout, file=sys.stderr)
            if exc.stderr:
                print(exc.stderr, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
