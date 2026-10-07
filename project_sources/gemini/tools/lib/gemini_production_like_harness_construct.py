"""Construct-loading validation for the Gemini production-like harness."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from lib.gemini_bundle_zip_contract import BundleZipContractError, inspect_bundle_zip
from lib.gemini_production_like_harness_common import (
    add_message,
    load_json,
    repo_relative,
)

GEMINI_TARGET_ID = "gemini_dcoir_agent"
BUILD_REPORT_NAME = "build_dcoir_gemini_release_report.json"


def expected_construct_counts(root: Path) -> dict[str, int]:
    """Read the governed construct counts instead of keeping a third copy here."""
    runtime_root = root / "project_sources/agent_runtime"
    adapter = load_json(runtime_root / "Behavior_Module_Manifest.json")["target_adapters"][GEMINI_TARGET_ID]
    projection = load_json(runtime_root / "Knowledge_Projection_Manifest.json")["targets"][GEMINI_TARGET_ID]
    return {
        "prime_chunks": adapter["expected_prime_chunks"],
        "sub_agents": adapter["expected_specialists"],
        "knowledge_sources": projection["expected_attachment_count"],
    }


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

    for key, expected_count in expected_construct_counts(root).items():
        if counts[key] != expected_count:
            add_message(messages, "error", f"{key} {counts[key]} != {expected_count}", repo_relative(source_root, root))

    build: dict[str, Any] = {"attempted": False}
    if mode in ("medium", "full"):
        build_output_dir = output_dir / "construct_load"
        # Start clean so a report or zip from an earlier run can never be inspected.
        shutil.rmtree(build_output_dir, ignore_errors=True)
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

        # Inspect exactly the zip the build reported, through the shared contract owner.
        build_report_path = build_output_dir / BUILD_REPORT_NAME
        zip_value = load_json(build_report_path).get("zip_path") if build_report_path.is_file() else None
        if not process.returncode and not zip_value:
            add_message(messages, "error", "construct build did not report a delivery zip", repo_relative(source_root, root))
        if zip_value:
            try:
                contract = inspect_bundle_zip(Path(zip_value), manifest)
            except BundleZipContractError as exc:
                add_message(messages, "error", f"construct zip contract failed: {exc}", repo_relative(source_root, root))
            else:
                build.update(
                    {
                        "zip_path": repo_relative(Path(zip_value), root),
                        "zip_entry_count": contract["entry_count"],
                        "prime_present": len(contract["prime_agent_entries"]) == 1,
                        "source_only_leaks": contract["source_only_leaks"],
                    }
                )
                if not contract["success"]:
                    add_message(messages, "error", "construct zip contract failed", build["zip_path"])

    return {"manifest_path": repo_relative(manifest_path, root), "counts": counts, "build": build}
