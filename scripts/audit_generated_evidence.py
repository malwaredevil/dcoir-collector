#!/usr/bin/env python3
"""Inventory tracked generated evidence and enforce durable sidecar policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess
from typing import Iterable


SCHEMA_VERSION = "dcoir_generated_evidence_inventory_v1"
TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".ps1", ".py", ".txt", ".yaml", ".yml"}
CANONICAL_REPORT_SUFFIXES = {".json", ".md"}


def tracked_paths(repo_root: Path) -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=repo_root)
    return [repo_root / raw.decode("utf-8") for raw in output.split(b"\0") if raw]


def relative(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def is_canonical_collector_report(path: PurePosixPath) -> bool:
    if path.parts[:2] != ("project_sources", "collector") or len(path.parts) != 3:
        return False
    name = path.name.lower()
    return path.suffix.lower() in CANONICAL_REPORT_SUFFIXES and (
        "report" in name or "inventory" in name
    )


def classify(path: PurePosixPath) -> set[str]:
    classes: set[str] = set()
    if "report_chunks" in path.parts:
        classes.add("durable_report_chunks")
    if path.parts and path.parts[0] == "chatgpt_staging":
        classes.add("chatgpt_staging")
    if path.parts[:2] == ("chatgpt_staging", "status_reports"):
        classes.add("chatgpt_status_reports")
    if "fixtures" in path.parts or "testdata" in path.parts:
        classes.add("fixtures")
    if is_canonical_collector_report(path):
        classes.add("canonical_collector_reports")
    return classes


def contains_airtable(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    try:
        return "airtable" in path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return False


def summarize(paths: Iterable[Path], repo_root: Path) -> dict[str, object]:
    buckets: dict[str, dict[str, int]] = {}
    airtable_files: list[str] = []
    tracked_count = 0
    tracked_bytes = 0
    for path in paths:
        if not path.is_file():
            continue
        tracked_count += 1
        size = path.stat().st_size
        tracked_bytes += size
        rel = relative(path, repo_root)
        pure = PurePosixPath(rel)
        for name in classify(pure):
            bucket = buckets.setdefault(name, {"files": 0, "bytes": 0})
            bucket["files"] += 1
            bucket["bytes"] += size
        if contains_airtable(path):
            airtable_files.append(rel)

    chunks = buckets.get("durable_report_chunks", {"files": 0, "bytes": 0})
    violations = []
    if chunks["files"]:
        violations.append(
            "tracked project_sources report_chunks are prohibited without a scoped policy exception"
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "tracked_files": tracked_count,
        "tracked_bytes": tracked_bytes,
        "classes": dict(sorted(buckets.items())),
        "airtable_reference_files_requiring_context_classification": sorted(airtable_files),
        "airtable_reference_file_count": len(airtable_files),
        "violations": violations,
        "success": not violations,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true", help="Exit nonzero for policy violations.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    result = summarize(tracked_paths(repo_root), repo_root)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if args.check and not result["success"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
