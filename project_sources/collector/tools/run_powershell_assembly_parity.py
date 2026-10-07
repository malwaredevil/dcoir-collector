#!/usr/bin/env python3
"""CLI entry point and stable import surface for PowerShell assembly parity validation.

Behavior is owned by the ``powershell_assembly_parity_*`` modules; this module only
re-exports their public names. Tests that need to intercept a dependency patch the
owning module (for example ``powershell_assembly_parity_builders.part_entry``).
"""
from __future__ import annotations

from powershell_assembly_parity_builders import *
from powershell_assembly_parity_cli import build_report, main, parse_args
from powershell_assembly_parity_common import *
from powershell_assembly_parity_controls import *
from powershell_assembly_parity_parsing import parse_powershell_text, static_powershell_parse
from powershell_assembly_parity_reporting import *

# Explicit re-exports; names from the star imports stay reachable as attributes.
__all__ = [
    "build_report",
    "main",
    "parse_args",
    "parse_powershell_text",
    "static_powershell_parse",
]


if __name__ == "__main__":
    raise SystemExit(main())
