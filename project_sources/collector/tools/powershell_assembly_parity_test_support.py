#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_powershell_assembly_parity as parity


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class PowerShellAssemblyParityTestCase(unittest.TestCase):
    def make_repo(
        self,
        *,
        collector_part_text: str = 'function Invoke-CollectorPart { Write-Output "ok" }\n',
        harness_part_text: str = 'function Invoke-HarnessPart { Write-Output "ok" }\n',
        checked_in_harness_text: str | None = None,
        manifest_wrapper: str | None = None,
        manifest_parts: list[str] | None = None,
    ) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        wrapper = "project_sources/collector/source/DCOIR_Collector.ps1"
        collector_part = "project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1"
        harness_part = "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-000.ps1.txt"
        write(
            root / wrapper,
            textwrap.dedent(
                """\
                [CmdletBinding()]
                param()
                $collectorPartsRoot = Join-Path $PSScriptRoot 'parts'
                $collectorPartFiles = @()
                foreach ($partFile in $collectorPartFiles) {
                  . $partFile
                }
                function Invoke-DCOIRWrapper { Write-Output "wrapper" }
                """
            ),
        )
        write(root / collector_part, collector_part_text)
        write(root / harness_part, harness_part_text)
        if checked_in_harness_text is not None:
            write(root / parity.HARNESS_GENERATED_OUTPUT, checked_in_harness_text)
        part_list = [collector_part] if manifest_parts is None else manifest_parts
        manifest = {
            "source_strategy": "compile_single_runtime_then_package",
            "collector_wrapper_source": wrapper if manifest_wrapper is None else manifest_wrapper,
            "collector_part_files": part_list,
            "compiled_runtime_name": "DCOIR_Collector.ps1",
        }
        inventory = {
            "schema_version": "dcoir_powershell_surface_inventory_v1",
            "controls": {
                "collector_manifest": {
                    "expected_path_count": 1 + len(part_list),
                    "present_path_count": 1 + len(part_list),
                    "paths": [],
                },
                "harness_source_parts": {
                    "part_count": 1,
                    "parts": [],
                },
                "generated_outputs": [
                    {
                        "path": parity.HARNESS_GENERATED_OUTPUT.as_posix(),
                        "expected_presence": "optional_when_generated",
                        "exists": checked_in_harness_text is not None,
                    }
                ],
            },
            "summary": {"total_surfaces": 3},
            "validation": {"success": True, "errors": [], "warnings": []},
            "surfaces": [],
        }
        write(root / parity.DEFAULT_MANIFEST, json.dumps(manifest, indent=2) + "\n")
        write(root / parity.DEFAULT_INVENTORY, json.dumps(inventory, indent=2) + "\n")
        return temp

    def args(self, root: Path, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "repo_root": str(root),
            "manifest": parity.DEFAULT_MANIFEST.as_posix(),
            "inventory": parity.DEFAULT_INVENTORY.as_posix(),
            "json_output": parity.DEFAULT_JSON_OUTPUT.as_posix(),
            "markdown_output": parity.DEFAULT_MARKDOWN_OUTPUT.as_posix(),
            "baseline_report": "",
            "shrink_exception": [],
            "no_write": True,
        }
        values.update(overrides)
        return argparse.Namespace(**values)
