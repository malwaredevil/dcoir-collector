#!/usr/bin/env python3
"""Compatibility facade for PowerShell assembly parity validation."""
from __future__ import annotations

import sys

import powershell_assembly_parity_builders as _builders
import powershell_assembly_parity_cli as _cli
import powershell_assembly_parity_parsing as _parsing

from powershell_assembly_parity_builders import *
from powershell_assembly_parity_cli import parse_args
from powershell_assembly_parity_common import *
from powershell_assembly_parity_controls import *
from powershell_assembly_parity_parsing import static_powershell_parse
from powershell_assembly_parity_reporting import *


def _sync_compat_globals() -> None:
    for name in ("file_facts", "part_entry", "read_part_text"):
        if name in globals():
            setattr(_builders, name, globals()[name])
    if "parse_powershell_text" in globals():
        _builders.parse_powershell_text = globals()["parse_powershell_text"]


def parse_powershell_text(text: str) -> dict[str, object]:
    _sync_compat_globals()
    return _parsing.parse_powershell_text(text)


def build_collector_output(repo_root: Path, manifest: dict[str, object], errors: list[str]):
    _sync_compat_globals()
    return _builders.build_collector_output(repo_root, manifest, errors)


def build_harness_output(repo_root: Path, errors: list[str]):
    _sync_compat_globals()
    return _builders.build_harness_output(repo_root, errors)


def build_report(args: argparse.Namespace):
    _sync_compat_globals()
    return _cli.build_report(args)


def main() -> int:
    _sync_compat_globals()
    return _cli.main()


if __name__ == "__main__":
    raise SystemExit(main())
