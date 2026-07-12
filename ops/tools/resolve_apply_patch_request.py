#!/usr/bin/env python3
"""Resolve and fingerprint governed ops apply-patch requests for GitHub Actions."""
from __future__ import annotations

import argparse
import pathlib

from lib.apply_patch_request_resolver import directory_tree_sha256, resolve, should_cleanup


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("--caller-event-name", required=True)
    resolve_parser.add_argument("--input-request-path", default="")
    resolve_parser.add_argument("--pending-request-max-age-hours", default="48")
    resolve_parser.add_argument("--event-path", default="")
    resolve_parser.add_argument("--head-sha", default="")
    resolve_parser.add_argument("--output", required=True)
    resolve_parser.set_defaults(func=resolve)

    hash_parser = subparsers.add_parser("tree-hash")
    hash_parser.add_argument("request_dir")
    hash_parser.set_defaults(func=lambda args: print(directory_tree_sha256(pathlib.Path(args.request_dir))) or 0)

    cleanup_parser = subparsers.add_parser("should-cleanup")
    cleanup_parser.add_argument("result_json")
    cleanup_parser.set_defaults(func=should_cleanup)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
