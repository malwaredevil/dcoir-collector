#!/usr/bin/env python3
"""Implementation helpers for PowerShell evidence chunk reassembly."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from reassemble_powershell_evidence_chunks_contract import ROOT_SCHEMA_VERSION, ChunkValidationError

from reassemble_powershell_evidence_chunks_part_01 import (
    sha256_bytes,
    normalize_repo_path,
    safe_repo_path,
    relpath,
    read_json_file,
    read_chunk_bytes,
    require_mapping,
    validate_report_manifest,
)
from reassemble_powershell_evidence_chunks_part_02 import (
    safe_sidecar_path,
    reassemble_markdown,
    compare_canonical,
)
from reassemble_powershell_evidence_chunks_part_03 import (
    reassemble_json,
)

def validate_chunk_set(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, bytes]]:
    repo_root = Path(args.repo_root).resolve()
    chunk_root = safe_repo_path(args.chunk_root, repo_root=repo_root, label="chunk root")
    manifest_path = chunk_root / "manifest.json"
    try:
        manifest_path.resolve().relative_to(repo_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ChunkValidationError("root manifest path must resolve inside the repository root") from exc
    root_manifest = require_mapping(read_json_file(manifest_path, label="root manifest"), label="root manifest")
    if root_manifest.get("schema_version") != ROOT_SCHEMA_VERSION:
        raise ChunkValidationError("root manifest: unsupported schema_version")
    if root_manifest.get("issue") != 349:
        raise ChunkValidationError("root manifest: issue must be 349")
    if root_manifest.get("pull_request") != 350:
        raise ChunkValidationError("root manifest: pull_request must be 350")
    reports = root_manifest.get("reports")
    if not isinstance(reports, list) or len(reports) != root_manifest.get("report_count"):
        raise ChunkValidationError("root manifest: report_count does not match reports length")

    results: list[dict[str, Any]] = []
    reconstructed_outputs: dict[str, bytes] = {}
    errors: list[str] = []
    warnings: list[str] = []
    seen_manifests: set[str] = set()
    seen_source_reports: set[str] = set()
    strict_source_hash = bool(args.strict_source_hash)
    compare_canonical_reports = bool(args.compare_canonical)
    require_canonical_parity = bool(args.require_canonical_parity)
    allow_lossy_json_order = bool(args.allow_lossy_json_order_reconstruction)
    actual_files = {relpath(path, repo_root) for path in chunk_root.rglob("*") if path.is_file()}
    expected_files = {relpath(manifest_path, repo_root)}
    if root_manifest.get("file_count") != len(actual_files):
        errors.append(
            "root manifest: "
            f"file_count {root_manifest.get('file_count')!r} does not match actual file count {len(actual_files)}"
        )
    top_level_files = root_manifest.get("top_level_files", [])
    if top_level_files is None:
        top_level_files = []
    if not isinstance(top_level_files, list):
        raise ChunkValidationError("root manifest: top_level_files must be a list when present")
    for index, entry_value in enumerate(top_level_files):
        entry = require_mapping(entry_value, label=f"top_level_files[{index}]")
        top_path = safe_sidecar_path(
            entry.get("path"),
            repo_root=repo_root,
            chunk_root=chunk_root,
            label=f"top_level_files[{index}]",
        )
        top_rel = relpath(top_path, repo_root)
        expected_files.add(top_rel)
        raw = read_chunk_bytes(top_path, label=f"top_level_files[{index}]")
        if entry.get("bytes") != len(raw):
            errors.append(f"{top_rel}: byte count does not match top_level_files entry")
        if entry.get("sha256") != sha256_bytes(raw):
            errors.append(f"{top_rel}: sha256 does not match top_level_files entry")

    for report_index, root_report_value in enumerate(reports):
        root_report = require_mapping(root_report_value, label=f"root report {report_index}")
        report_id = str(root_report.get("report_id"))
        source_report = root_report.get("source_report")
        if not isinstance(source_report, str) or not source_report.strip():
            raise ChunkValidationError(f"{report_id}: source_report must be a non-empty string")
        normalized_source_report = normalize_repo_path(source_report)
        if normalized_source_report in seen_source_reports:
            raise ChunkValidationError(f"{report_id}: duplicate source_report {normalized_source_report!r}")
        seen_source_reports.add(normalized_source_report)
        manifest_file = safe_sidecar_path(
            root_report.get("manifest_path"),
            repo_root=repo_root,
            chunk_root=chunk_root,
            label=f"{report_id} manifest",
        )
        manifest_rel = relpath(manifest_file, repo_root)
        if manifest_rel in seen_manifests:
            raise ChunkValidationError(f"{report_id}: duplicate report manifest path {manifest_rel}")
        seen_manifests.add(manifest_rel)
        report_manifest = validate_report_manifest(
            read_json_file(manifest_file, label=f"{report_id} manifest"),
            root_report,
            label=f"{report_id} manifest",
        )
        reconstructed_document: Any | None = None
        if report_manifest["source_format"] == "markdown":
            reconstructed_bytes, chunk_results = reassemble_markdown(
                report_manifest,
                repo_root=repo_root,
                chunk_root=chunk_root,
            )
        elif report_manifest["source_format"] == "json":
            reconstructed_bytes, reconstructed_document, chunk_results = reassemble_json(
                report_manifest,
                repo_root=repo_root,
                chunk_root=chunk_root,
            )
        else:
            raise ChunkValidationError(f"{report_id}: unsupported source_format {report_manifest['source_format']!r}")

        reconstructed_sha = sha256_bytes(reconstructed_bytes)
        source_sha_match = reconstructed_sha == report_manifest["source_sha256"]
        source_bytes_match = len(reconstructed_bytes) == report_manifest["source_bytes"]
        report_result: dict[str, Any] = {
            "report_id": report_id,
            "source_format": report_manifest["source_format"],
            "source_report": report_manifest["source_report"],
            "manifest_path": manifest_rel,
            "chunk_count": len(chunk_results),
            "chunk_integrity": "pass",
            "byte_exact": source_sha_match,
            "reconstructed_bytes": len(reconstructed_bytes),
            "reconstructed_sha256": reconstructed_sha,
            "source_bytes": report_manifest["source_bytes"],
            "source_sha256": report_manifest["source_sha256"],
            "source_bytes_match": source_bytes_match,
            "source_sha256_match": source_sha_match,
            "strict_source_hash_required_for_byte_readiness": not source_sha_match,
            "chunks": chunk_results,
        }
        if not source_bytes_match:
            errors.append(f"{report_manifest['source_report']}: reconstructed byte count does not match source_bytes")
        if not source_sha_match:
            message = (
                f"{report_manifest['source_report']}: reconstructed SHA-256 does not match source_sha256; "
                "for JSON this can indicate missing byte-order metadata in the sidecar schema"
            )
            if (
                allow_lossy_json_order
                and report_manifest["source_format"] == "json"
                and not strict_source_hash
            ):
                warnings.append(message)
            else:
                errors.append(message)
        if compare_canonical_reports:
            canonical_parity = compare_canonical(
                repo_root=repo_root,
                report_manifest=report_manifest,
                reconstructed_bytes=reconstructed_bytes,
                reconstructed_document=reconstructed_document,
            )
            report_result["canonical_parity"] = canonical_parity
            if canonical_parity.get("status") != "pass":
                message = (
                    f"{report_manifest['source_report']}: "
                    f"canonical parity status is {canonical_parity.get('status')}"
                )
                if require_canonical_parity:
                    errors.append(message)
                else:
                    warnings.append(message)
        if source_sha_match:
            reconstructed_outputs[normalize_repo_path(report_manifest["source_report"])] = reconstructed_bytes
        expected_files.add(manifest_rel)
        expected_files.update(chunk_result["path"] for chunk_result in chunk_results)
        results.append(report_result)

    missing_files = sorted(expected_files - actual_files)
    unexpected_files = sorted(actual_files - expected_files)
    if missing_files:
        errors.append(f"chunk sidecar is missing expected files: {missing_files}")
    if unexpected_files:
        errors.append(f"chunk sidecar has unexpected files: {unexpected_files}")

    chunk_integrity_success = not any(
        "canonical parity status" not in error and "reconstructed SHA-256 does not match source_sha256" not in error
        for error in errors
    )
    reconstruction_exact_success = all(report["byte_exact"] for report in results)
    canonical_parity_success = (
        all(report.get("canonical_parity", {}).get("status") == "pass" for report in results)
        if compare_canonical_reports
        else None
    )
    readiness_gaps: list[str] = []
    if not reconstruction_exact_success:
        readiness_gaps.append(
            "byte-exact source-hash validation is not clean; "
            "only --allow-lossy-json-order-reconstruction can downgrade this to a warning"
        )
    if compare_canonical_reports and not canonical_parity_success:
        readiness_gaps.append(
            "canonical reports do not match the reassembled chunk sidecar; "
            "sidecar validation is not canonical replacement"
        )
    if not compare_canonical_reports:
        readiness_gaps.append(
            "canonical reports were not compared; "
            "sidecar validation is not canonical replacement"
        )

    output = {
        "schema_version": "dcoir_powershell_evidence_chunk_validation_v1",
        "chunk_root": relpath(chunk_root, repo_root),
        "issue": root_manifest.get("issue"),
        "pull_request": root_manifest.get("pull_request"),
        "report_count": len(results),
        "strict_source_hash": strict_source_hash,
        "compare_canonical": compare_canonical_reports,
        "require_canonical_parity": require_canonical_parity,
        "allow_lossy_json_order_reconstruction": allow_lossy_json_order,
        "chunk_integrity_success": chunk_integrity_success,
        "reconstruction_exact_success": reconstruction_exact_success,
        "canonical_parity_success": canonical_parity_success,
        "readiness_gaps": readiness_gaps,
        "validation": {
            "success": not errors,
            "errors": errors,
            "warnings": warnings,
        },
        "reports": results,
    }
    return output, reconstructed_outputs
