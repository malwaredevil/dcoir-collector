#!/usr/bin/env python3
"""Implementation helpers for PowerShell evidence chunk reassembly."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reassemble_powershell_evidence_chunks_contract import ChunkValidationError

from reassemble_powershell_evidence_chunks_part_01 import (
    sha256_bytes,
    safe_repo_path,
    relpath,
    read_chunk_bytes,
    require_mapping,
    require_list,
    require_int_field,
    ensure_object_parent,
)

def safe_sidecar_path(value: Any, *, repo_root: Path, chunk_root: Path, label: str) -> Path:
    path = safe_repo_path(value, repo_root=repo_root, label=label)
    try:
        path.resolve().relative_to(chunk_root.resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise ChunkValidationError(f"{label}: path must resolve inside the chunk root") from exc
    return path


def set_json_value(document: dict[str, Any], pointer: str, value: Any, *, label: str, assigned: set[str]) -> Any:
    if pointer in assigned:
        raise ChunkValidationError(f"{label}: duplicate json_value pointer {pointer}")
    assigned.add(pointer)
    parent_info = ensure_object_parent(document, pointer, label=label)
    if parent_info is None:
        return value
    parent, key = parent_info
    if key in parent:
        raise ChunkValidationError(f"{label}: pointer {pointer} would overwrite an existing value")
    parent[key] = value
    return document


def apply_json_list_items(
    document: dict[str, Any],
    pointer: str,
    items: Any,
    *,
    label: str,
    item_start: Any,
    item_count: Any,
) -> dict[str, Any]:
    values = require_list(items, label=f"{label}: data")
    if not isinstance(item_start, int) or item_start < 0:
        raise ChunkValidationError(f"{label}: item_start must be a non-negative integer")
    if item_count != len(values):
        raise ChunkValidationError(f"{label}: item_count does not match data length")
    parent_info = ensure_object_parent(document, pointer, label=label)
    if parent_info is None:
        if item_start != 0:
            raise ChunkValidationError(f"{label}: root list item_start must be 0")
        return values  # type: ignore[return-value]
    parent, key = parent_info
    if key not in parent:
        parent[key] = []
    target = require_list(parent[key], label=f"{label}: target")
    if item_start != len(target):
        raise ChunkValidationError(
            f"{label}: list range for {pointer} has a gap or overlap; expected start {len(target)}, got {item_start}"
        )
    target.extend(values)
    return document


def compare_canonical(
    *,
    repo_root: Path,
    report_manifest: dict[str, Any],
    reconstructed_bytes: bytes,
    reconstructed_document: Any | None,
) -> dict[str, Any]:
    source_path = safe_repo_path(
        report_manifest.get("source_report"),
        repo_root=repo_root,
        label="canonical source report",
    )
    if not source_path.exists():
        return {"checked": False, "status": "missing", "path": relpath(source_path, repo_root)}
    raw = source_path.read_bytes()
    exact_match = raw == reconstructed_bytes
    result: dict[str, Any] = {
        "checked": True,
        "path": relpath(source_path, repo_root),
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "source_sha256_match": sha256_bytes(raw) == report_manifest.get("source_sha256"),
        "exact_reconstruction_match": exact_match,
    }
    if report_manifest.get("source_format") == "json" and reconstructed_document is not None:
        try:
            result["semantic_reconstruction_match"] = json.loads(raw.decode("utf-8")) == reconstructed_document
        except (UnicodeDecodeError, json.JSONDecodeError):
            result["semantic_reconstruction_match"] = False
    result["status"] = "pass" if exact_match else "mismatch"
    return result


def reassemble_markdown(
    report_manifest: dict[str, Any],
    *,
    repo_root: Path,
    chunk_root: Path,
) -> tuple[bytes, list[dict[str, Any]]]:
    output = bytearray()
    chunk_results: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for index, chunk_info in enumerate(report_manifest["chunks"]):
        chunk_label = f"{report_manifest['source_report']} chunk {index}"
        chunk_info = require_mapping(chunk_info, label=chunk_label)
        if chunk_info.get("chunk_kind") != "markdown_section":
            raise ChunkValidationError(
                f"{chunk_label}: unsupported Markdown chunk kind {chunk_info.get('chunk_kind')!r}"
            )
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
        output.extend(raw)
        chunk_results.append({"path": chunk_rel, "sha256": digest, "bytes": len(raw), "status": "pass"})
    return bytes(output), chunk_results


def reassemble_json_text_slices(
    report_manifest: dict[str, Any],
    *,
    repo_root: Path,
    chunk_root: Path,
) -> tuple[bytes, Any, list[dict[str, Any]]]:
    if report_manifest.get("reassembly_mode") != "byte_exact_text_slices":
        raise ChunkValidationError(
            f"{report_manifest['source_report']}: json_text_slice reports require "
            "reassembly_mode 'byte_exact_text_slices'"
        )
    output = bytearray()
    chunk_results: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    expected_offset = 0
    for index, chunk_info in enumerate(report_manifest["chunks"]):
        chunk_label = f"{report_manifest['source_report']} chunk {index}"
        chunk_info = require_mapping(chunk_info, label=chunk_label)
        if chunk_info.get("chunk_kind") != "json_text_slice":
            raise ChunkValidationError(
                f"{chunk_label}: json_text_slice reports cannot mix chunk kind {chunk_info.get('chunk_kind')!r}"
            )
        if chunk_info.get("format") != report_manifest.get("source_format"):
            raise ChunkValidationError(f"{chunk_label}: chunk format does not match report format")
        chunk_index = require_int_field(chunk_info, "chunk_index", label=chunk_label, minimum=0)
        if chunk_index != index:
            raise ChunkValidationError(f"{chunk_label}: chunk_index must match manifest order")
        byte_start = require_int_field(chunk_info, "byte_start", label=chunk_label, minimum=0)
        byte_end = require_int_field(chunk_info, "byte_end", label=chunk_label, minimum=0)
        if byte_start != expected_offset:
            raise ChunkValidationError(
                f"{chunk_label}: byte range has a gap or overlap; expected start {expected_offset}, got {byte_start}"
            )
        if byte_end <= byte_start:
            raise ChunkValidationError(f"{chunk_label}: byte_end must be greater than byte_start")
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
        if byte_end - byte_start != len(raw):
            raise ChunkValidationError(f"{chunk_label}: byte range length does not match chunk bytes")
        digest = sha256_bytes(raw)
        if chunk_info.get("sha256") != digest:
            raise ChunkValidationError(f"{chunk_label}: sha256 mismatch")
        output.extend(raw)
        expected_offset = byte_end
        chunk_results.append(
            {
                "path": chunk_rel,
                "sha256": digest,
                "bytes": len(raw),
                "byte_start": byte_start,
                "byte_end": byte_end,
                "status": "pass",
            }
        )

    if expected_offset != report_manifest.get("source_bytes"):
        raise ChunkValidationError(
            f"{report_manifest['source_report']}: text-slice bytes do not cover source_bytes"
        )
    reconstructed_bytes = bytes(output)
    try:
        document = json.loads(reconstructed_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ChunkValidationError(f"{report_manifest['source_report']}: reassembled JSON is invalid: {exc}") from exc
    return reconstructed_bytes, document, chunk_results
