#!/usr/bin/env python3
"""Implementation helpers for PowerShell evidence chunk reassembly."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reassemble_powershell_evidence_chunks_contract import ChunkValidationError

from reassemble_powershell_evidence_chunks_part_01 import (
    sha256_bytes,
    json_dumps,
    relpath,
    read_chunk_bytes,
    require_mapping,
    merge_json_object_members,
    validate_chunk_metadata,
    require_chunk_index,
    require_key_count,
)
from reassemble_powershell_evidence_chunks_part_02 import (
    safe_sidecar_path,
    set_json_value,
    apply_json_list_items,
    reassemble_json_text_slices,
)

def reassemble_json(
    report_manifest: dict[str, Any],
    *,
    repo_root: Path,
    chunk_root: Path,
) -> tuple[bytes, Any, list[dict[str, Any]]]:
    chunk_infos = [
        require_mapping(chunk_info, label=f"{report_manifest['source_report']} chunk {index}")
        for index, chunk_info in enumerate(report_manifest["chunks"])
    ]
    text_slice_count = sum(1 for chunk_info in chunk_infos if chunk_info.get("chunk_kind") == "json_text_slice")
    if text_slice_count:
        if text_slice_count != len(chunk_infos):
            raise ChunkValidationError(
                f"{report_manifest['source_report']}: json_text_slice chunks cannot be mixed with semantic JSON chunks"
            )
        report_manifest = dict(report_manifest)
        report_manifest["chunks"] = chunk_infos
        return reassemble_json_text_slices(report_manifest, repo_root=repo_root, chunk_root=chunk_root)

    document: Any = {}
    assigned_values: set[str] = set()
    chunk_results: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for index, chunk_info in enumerate(chunk_infos):
        chunk_label = f"{report_manifest['source_report']} chunk {index}"
        chunk_path = safe_sidecar_path(
            chunk_info.get("path"),
            repo_root=repo_root,
            chunk_root=chunk_root,
            label=chunk_label,
        )
        chunk_rel = relpath(chunk_path, repo_root)
        if chunk_rel in seen_paths:
            raise ChunkValidationError(f"{chunk_label}: duplicate chunk path {chunk_rel}")
        seen_paths.add(chunk_rel)
        raw = read_chunk_bytes(chunk_path, label=chunk_label)
        if chunk_info.get("bytes") != len(raw):
            raise ChunkValidationError(f"{chunk_label}: byte count mismatch")
        digest = sha256_bytes(raw)
        if chunk_info.get("sha256") != digest:
            raise ChunkValidationError(f"{chunk_label}: sha256 mismatch")
        try:
            chunk = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ChunkValidationError(f"{chunk_label}: invalid JSON chunk: {exc}") from exc
        chunk = require_mapping(chunk, label=chunk_label)
        validate_chunk_metadata(chunk, chunk_info, report_manifest, label=chunk_label)
        kind = chunk.get("chunk_kind")
        pointer = chunk.get("json_pointer")
        if kind == "json_value":
            if not isinstance(document, dict):
                raise ChunkValidationError(f"{chunk_label}: root document is not an object")
            document = set_json_value(document, pointer, chunk.get("data"), label=chunk_label, assigned=assigned_values)
        elif kind == "json_object_members":
            require_chunk_index(chunk, chunk_info, label=chunk_label)
            require_key_count(chunk, chunk_info, label=chunk_label)
            members = require_mapping(chunk.get("data"), label=f"{chunk_label}: data")
            if "key_count" in chunk and chunk["key_count"] != len(members):
                raise ChunkValidationError(f"{chunk_label}: key_count does not match data length")
            if not isinstance(document, dict):
                raise ChunkValidationError(f"{chunk_label}: root document is not an object")
            document = merge_json_object_members(document, pointer, members, label=chunk_label)
        elif kind == "json_list_items":
            require_chunk_index(chunk, chunk_info, label=chunk_label)
            if not isinstance(document, dict):
                raise ChunkValidationError(f"{chunk_label}: root document is not an object")
            document = apply_json_list_items(
                document,
                pointer,
                chunk.get("data"),
                label=chunk_label,
                item_start=chunk.get("item_start"),
                item_count=chunk.get("item_count"),
            )
        else:
            raise ChunkValidationError(f"{chunk_label}: unsupported JSON chunk kind {kind!r}")
        chunk_results.append({"path": chunk_rel, "sha256": digest, "bytes": len(raw), "status": "pass"})
    text = json_dumps(document)
    return text.encode("utf-8"), document, chunk_results
