#!/usr/bin/env python3
"""Validate Gemini manifest-governed bundle surfaces."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MANIFEST_NAME = "Gemini_Bundle_Source_Manifest.json"


def normalize_manifest_path(path: str) -> str:
    return path.replace("\\", "/")


def join_source_path(source_root: Path, relative_path: str) -> Path:
    return source_root.joinpath(*relative_path.split("/"))


def read_manifest(source_root: Path) -> dict:
    manifest_path = source_root / MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Gemini manifest missing: {manifest_path.as_posix()}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {manifest_path.as_posix()}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError("Gemini manifest must decode to a JSON object.")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, help="Gemini bundle source root")
    args = parser.parse_args()

    source_root = Path(args.source_root).resolve()
    try:
        manifest = read_manifest(source_root)
    except (FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1

    topology = manifest.get("topology")
    if not isinstance(topology, dict) or topology.get("topology_source_of_truth") != "manifest":
        print("Gemini topology source of truth must be manifest.", file=sys.stderr)
        return 1

    required_files = manifest.get("required_files")
    if not isinstance(required_files, list) or not required_files:
        print("Gemini manifest required_files is empty.", file=sys.stderr)
        return 1
    source_required_files = manifest.get("source_required_files")
    if not isinstance(source_required_files, list):
        print("Gemini manifest source_required_files must be a list.", file=sys.stderr)
        return 1
    sub_agent_files = topology.get("sub_agent_files")
    if not isinstance(sub_agent_files, list) or not sub_agent_files:
        print("Gemini manifest topology.sub_agent_files is empty.", file=sys.stderr)
        return 1

    required_normalized = [normalize_manifest_path(str(path)) for path in required_files]
    source_required_normalized = [normalize_manifest_path(str(path)) for path in source_required_files]
    sub_agent_normalized = [normalize_manifest_path(str(path)) for path in sub_agent_files]

    manifest_missing = [
        path
        for path in required_normalized + source_required_normalized
        if not join_source_path(source_root, path).exists()
    ]
    if manifest_missing:
        print(
            "Missing Gemini manifest-required/source-required surfaces: " + ", ".join(manifest_missing),
            file=sys.stderr,
        )
        return 1

    missing_sub_agents = [
        path for path in sub_agent_normalized if not join_source_path(source_root, path).exists()
    ]
    if missing_sub_agents:
        print(
            "Missing Gemini manifest-listed sub-agent files: " + ", ".join(missing_sub_agents),
            file=sys.stderr,
        )
        return 1

    agent_build_root = source_root / "01_GEMINI_AGENT_BUILD"
    discovered_sub_agents = sorted(
        path.relative_to(source_root).as_posix()
        for path in agent_build_root.glob("Sub_Agent_*.md.txt")
        if path.is_file()
    )
    unlisted_sub_agents = [path for path in discovered_sub_agents if path not in sub_agent_normalized]
    if unlisted_sub_agents:
        print(
            "Discovered Gemini sub-agent files not listed in manifest topology: " + ", ".join(unlisted_sub_agents),
            file=sys.stderr,
        )
        return 1

    print(
        "Gemini manifest surfaces validated: "
        f"required={len(required_normalized)}; "
        f"source-required={len(source_required_normalized)}; "
        f"sub-agents={len(sub_agent_normalized)}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
