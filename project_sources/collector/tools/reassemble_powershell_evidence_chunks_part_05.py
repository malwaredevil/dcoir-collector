#!/usr/bin/env python3
"""Implementation helpers for PowerShell evidence chunk reassembly."""
from __future__ import annotations

import sys
from pathlib import Path

from reassemble_powershell_evidence_chunks_contract import ChunkValidationError

from reassemble_powershell_evidence_chunks_part_01 import (
    json_dumps,
    write_outputs,
    build_parser,
)
from reassemble_powershell_evidence_chunks_part_04 import (
    validate_chunk_set,
)

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report, outputs = validate_chunk_set(args)
        if args.write_output_dir:
            if not report["validation"]["success"]:
                raise ChunkValidationError("refusing to write reconstructed outputs because validation did not succeed")
            write_outputs(outputs, output_dir=Path(args.write_output_dir).resolve())
        rendered = json_dumps(report)
        if args.json_output:
            output_path = Path(args.json_output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        return 0 if report["validation"]["success"] else 1
    except ChunkValidationError as exc:
        error_report = {
            "schema_version": "dcoir_powershell_evidence_chunk_validation_v1",
            "validation": {"success": False, "errors": [str(exc)], "warnings": []},
        }
        sys.stdout.write(json_dumps(error_report))
        return 1
