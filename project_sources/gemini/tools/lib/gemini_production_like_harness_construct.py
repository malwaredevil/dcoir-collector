"""Construct-loading validation for the Gemini production-like harness."""
from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from lib.gemini_production_like_harness_common import (
    EXPECTED_CONSTRUCT_COUNTS,
    add_message,
    load_json,
    repo_relative,
)


def validate_construct(root: Path, output_dir: Path, messages: list[dict[str, str]], mode: str) -> dict[str, Any]:
    source_root = root / "project_sources/gemini/bundle_source"
    manifest_path = source_root / "Gemini_Bundle_Source_Manifest.json"
    manifest = load_json(manifest_path)
    topology = manifest["topology"]
    chunks = load_json(source_root / manifest["prime_agent_chunk_manifest"])
    counts = {
        "prime_chunks": len(chunks["chunks"]),
        "sub_agents": len(topology["sub_agent_files"]),
        "knowledge_sources": len(manifest["knowledge_attachment_sources"]),
    }

    for key, expected_count in EXPECTED_CONSTRUCT_COUNTS.items():
        if counts[key] != expected_count:
            add_message(messages, "error", f"{key} {counts[key]} != {expected_count}", repo_relative(source_root, root))

    build: dict[str, Any] = {"attempted": False}
    if mode in ("medium", "full"):
        build_output_dir = output_dir / "construct_load"
        command = [
            sys.executable,
            str(root / "project_sources/gemini/tools/build_dcoir_gemini_release.py"),
            "--source-root",
            str(source_root),
            "--output-dir",
            str(build_output_dir),
        ]
        process = subprocess.run(command, text=True, capture_output=True)
        build = {"attempted": True, "returncode": process.returncode}
        if process.returncode:
            add_message(messages, "error", "construct build failed", repo_relative(source_root, root))
            build["stderr"] = process.stderr[-2000:]

        zip_paths = sorted(build_output_dir.glob("*.zip"))
        if zip_paths:
            with zipfile.ZipFile(zip_paths[-1]) as archive:
                names = archive.namelist()
            relative_entries = [name.split("/", 1)[1] if "/" in name else name for name in names]
            source_only_files = set(manifest.get("source_only_files", []))
            source_only_dirs = manifest.get("source_only_dirs", [])
            leaks = [
                entry
                for entry in relative_entries
                if entry in source_only_files
                or any(entry.startswith(directory.rstrip("/") + "/") for directory in source_only_dirs)
            ]
            build.update(
                {
                    "zip_path": repo_relative(zip_paths[-1], root),
                    "zip_entry_count": len(names),
                    "prime_present": topology["prime_agent_file"] in relative_entries,
                    "source_only_leaks": leaks,
                }
            )
            if not build["prime_present"] or leaks:
                add_message(messages, "error", "construct zip contract failed", repo_relative(zip_paths[-1], root))

    return {"manifest_path": repo_relative(manifest_path, root), "counts": counts, "build": build}
