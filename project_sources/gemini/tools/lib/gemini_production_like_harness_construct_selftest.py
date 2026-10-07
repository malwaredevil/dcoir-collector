#!/usr/bin/env python3
"""Regression tests for production-like construct archive selection."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

TOOLS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_DIR))

from lib.gemini_bundle_zip_contract import COMPILE_REPORT_NAME
from lib.gemini_production_like_harness_construct import (
    validate_construct,
)

PRIME = "01_GEMINI_AGENT_BUILD/Prime.md.txt"
BUILD_REPORT_NAME = "build_dcoir_gemini_release_report.json"


def write_zip(path: Path, member: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(member, "content")
    return path


class ValidateConstructTests(unittest.TestCase):
    def test_uses_compiler_archive_instead_of_build_report_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_dir = root / "validation-output"
            build_output_dir = output_dir / "construct_load"
            reported_zip = write_zip(
                root / "elsewhere" / "Bundle_1.zip",
                f"Bundle_1/{PRIME}",
            )
            compiler_zip = build_output_dir / "Bundle_1.zip"
            manifest = {
                "topology": {
                    "prime_agent_file": PRIME,
                    "sub_agent_files": [],
                },
                "prime_agent_chunk_manifest": "chunks.json",
                "knowledge_attachment_sources": [],
            }
            messages: list[dict[str, str]] = []

            def run_build(command: list[str], **_: object) -> SimpleNamespace:
                build_dir = Path(command[-1])
                actual_compiler_zip = write_zip(
                    compiler_zip,
                    f"Bundle_1/{PRIME}",
                )
                (build_dir / BUILD_REPORT_NAME).write_text(
                    json.dumps({"zip_path": str(reported_zip)}),
                    encoding="utf-8",
                )
                (build_dir / COMPILE_REPORT_NAME).write_text(
                    json.dumps(
                        {
                            "zip_path": str(actual_compiler_zip),
                            "bundle_name": "Bundle",
                            "bundle_version": "1",
                        }
                    ),
                    encoding="utf-8",
                )
                return SimpleNamespace(returncode=0, stderr="")

            with (
                patch(
                    "lib.gemini_production_like_harness_construct.load_json",
                    side_effect=[manifest, {"chunks": []}],
                ),
                patch(
                    "lib.gemini_production_like_harness_construct.expected_construct_counts",
                    return_value={
                        "prime_chunks": 0,
                        "sub_agents": 0,
                        "knowledge_sources": 0,
                    },
                ),
                patch(
                    "lib.gemini_production_like_harness_construct.subprocess.run",
                    side_effect=run_build,
                ),
                patch(
                    "lib.gemini_production_like_harness_construct.inspect_bundle_zip",
                    return_value={
                        "success": True,
                        "entry_count": 1,
                        "prime_agent_entries": [PRIME],
                        "source_only_leaks": [],
                    },
                ) as inspect,
            ):
                report = validate_construct(root, output_dir, messages, "medium")

            self.assertEqual(inspect.call_args.args[0], compiler_zip)
            self.assertEqual(
                report["build"]["zip_path"],
                compiler_zip.relative_to(root).as_posix(),
            )
            self.assertEqual(messages, [])


if __name__ == "__main__":
    unittest.main()
