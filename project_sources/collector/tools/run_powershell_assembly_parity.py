#!/usr/bin/env python3
"""Compatibility facade for PowerShell assembly parity validation."""
from __future__ import annotations

import powershell_assembly_parity_builders as _builders
import powershell_assembly_parity_cli as _cli
import powershell_assembly_parity_parsing as _parsing

from powershell_assembly_parity_builders import *
from powershell_assembly_parity_cli import parse_args
from powershell_assembly_parity_common import *
from powershell_assembly_parity_controls import *
from powershell_assembly_parity_parsing import static_powershell_parse
from powershell_assembly_parity_reporting import *


def parse_powershell_text(text: str) -> dict[str, object]:
    return _parsing.parse_powershell_text(text)


def build_collector_output(repo_root: Path, manifest: dict[str, object], errors: list[str]):
    return _builders.build_collector_output(
        repo_root,
        manifest,
        errors,
        part_entry_fn=part_entry,
        read_part_text_fn=read_part_text,
        parse_powershell_text_fn=parse_powershell_text,
    )


def build_harness_output(repo_root: Path, errors: list[str]):
    return _builders.build_harness_output(
        repo_root,
        errors,
        part_entry_fn=part_entry,
        read_part_text_fn=read_part_text,
        parse_powershell_text_fn=parse_powershell_text,
    )


def build_report(args: argparse.Namespace):
    return _cli.build_report(
        args,
        build_collector_output_fn=build_collector_output,
        build_harness_output_fn=build_harness_output,
    )


def main() -> int:
    return _cli.main(build_report_fn=build_report)


if __name__ == "__main__":
    raise SystemExit(main())
