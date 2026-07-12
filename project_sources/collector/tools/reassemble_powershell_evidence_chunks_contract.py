#!/usr/bin/env python3
"""Constants and errors for PowerShell evidence chunk reassembly."""
from pathlib import Path

DEFAULT_CHUNK_ROOT = Path("project_sources/collector/report_chunks/issue349_pr350_powershell_evidence")
ROOT_SCHEMA_VERSION = "dcoir_powershell_evidence_chunk_set_v1"
REPORT_MANIFEST_SCHEMA_VERSION = "dcoir_report_chunk_manifest_v1"
CHUNK_SCHEMA_VERSION = "dcoir_report_chunk_v1"


class ChunkValidationError(RuntimeError):
    """Raised when a chunk set cannot be safely reassembled."""
