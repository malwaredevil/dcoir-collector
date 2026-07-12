#!/usr/bin/env python3
"""Reassemble and validate connector-sized PowerShell evidence chunks."""
from __future__ import annotations

from reassemble_powershell_evidence_chunks_contract import (
    CHUNK_SCHEMA_VERSION, DEFAULT_CHUNK_ROOT, REPORT_MANIFEST_SCHEMA_VERSION,
    ROOT_SCHEMA_VERSION, ChunkValidationError,
)
from reassemble_powershell_evidence_chunks_part_01 import (
    sha256_bytes,
    json_dumps,
    normalize_repo_path,
    is_absolute_repo_input,
    safe_repo_path,
    relpath,
    read_json_file,
    read_chunk_bytes,
    pointer_parts,
    require_mapping,
    require_list,
    require_int_field,
    ensure_object_parent,
    merge_json_object_members,
    validate_chunk_metadata,
    require_chunk_index,
    require_key_count,
    validate_report_manifest,
    write_outputs,
    build_parser,
)
from reassemble_powershell_evidence_chunks_part_02 import (
    safe_sidecar_path,
    set_json_value,
    apply_json_list_items,
    reassemble_markdown,
    reassemble_json_text_slices,
    compare_canonical,
)
from reassemble_powershell_evidence_chunks_part_03 import (
    reassemble_json,
)
from reassemble_powershell_evidence_chunks_part_04 import (
    validate_chunk_set,
)
from reassemble_powershell_evidence_chunks_part_05 import (
    main,
)

if __name__ == "__main__":
    raise SystemExit(main())
