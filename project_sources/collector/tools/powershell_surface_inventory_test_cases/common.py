#!/usr/bin/env python3
"""Shared fixtures for PowerShell surface inventory tests."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


def write(path: Path, text: str = "Write-Output 'ok'\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class InventoryTestCase(unittest.TestCase):
    def make_minimal_repo(self) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        write(
            root / "project_sources/collector/manifests/Collector_Runtime_Package_Manifest.json",
            '{\n'
            '  "collector_wrapper_source": "project_sources/collector/source/DCOIR_Collector.ps1",\n'
            '  "collector_part_files": [\n'
            '    "project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1"\n'
            "  ]\n"
            "}\n",
        )
        write(root / "project_sources/collector/source/DCOIR_Collector.ps1")
        write(root / "project_sources/collector/source/parts/DCOIR_Collector.01_Core.ps1")
        write(root / "project_sources/collector/harness/run_DCOIR_Tests.ps1")
        write(root / "project_sources/collector/harness/source/parts/run_DCOIR_Tests.part-000.ps1.txt")
        write(root / "operator_tools/sample/Invoke-DcoirSample.ps1")
        write(root / ".github/workflows/sample.yml", "jobs:\n  test:\n    steps:\n      - shell: pwsh\n        run: Write-Host ok\n")
        return temp
