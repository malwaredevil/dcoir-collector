#!/usr/bin/env python3
"""Implementation helpers for PowerShell evidence chunk reassembly."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from reassemble_powershell_evidence_chunks_contract import CHUNK_SCHEMA_VERSION, DEFAULT_CHUNK_ROOT, REPORT_MANIFEST_SCHEMA_VERSION, ChunkValidationError


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_dumps(value: Any) -> str:
    return json.dumps(value, indent=2) + "\n"


def normalize_repo_path(value: str) -> str:
    slash_path = value.replace("\\", "/")
    while slash_path.startswith("./"):
        slash_path = slash_path[2:]
    return Path(slash_path).as_posix()


def is_absolute_repo_input(value: str) -> bool:
    raw = value.strip()
    slash_path = raw.replace("\\", "/")
    return (
        slash_path.startswith("/")
        or re.match(r"^[A-Za-z]:", slash_path) is not None
        or Path(raw).is_absolute()
    )


def relpath(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def read_json_file(path: Path, *, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ChunkValidationError(f"{label}: missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ChunkValidationError(f"{label}: invalid JSON: {path}: {exc}") from exc
    except OSError as exc:
        raise ChunkValidationError(f"{label}: could not read file: {path}: {exc}") from exc


def read_chunk_bytes(path: Path, *, label: str) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError as exc:
        raise ChunkValidationError(f"{label}: missing chunk file: {path}") from exc
    except OSError as exc:
        raise ChunkValidationError(f"{label}: could not read chunk file: {path}: {exc}") from exc


def pointer_parts(pointer: Any, *, label: str) -> list[str]:
    if not isinstance(pointer, str):
        raise ChunkValidationError(f"{label}: json_pointer must be a string")
    if pointer == "":
        return []
    if not pointer.startswith("/"):
        raise ChunkValidationError(f"{label}: json_pointer must be empty or start with '/'")
    return [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]


def require_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ChunkValidationError(f"{label}: expected an object")
    return value


def require_list(value: Any, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ChunkValidationError(f"{label}: expected a list")
    return value


def require_int_field(
    value: dict[str, Any],
    key: str,
    *,
    label: str,
    minimum: int | None = None,
) -> int:
    field_value = value.get(key)
    if not isinstance(field_value, int):
        raise ChunkValidationError(f"{label}: {key} must be an integer")
    if minimum is not None and field_value < minimum:
        raise ChunkValidationError(f"{label}: {key} must be at least {minimum}")
    return field_value


def validate_chunk_metadata(
    chunk: dict[str, Any],
    chunk_info: dict[str, Any],
    report_manifest: dict[str, Any],
    *,
    label: str,
) -> None:
    checks = {
        "schema_version": CHUNK_SCHEMA_VERSION,
        "chunk_kind": chunk_info.get("chunk_kind"),
        "report_id": report_manifest.get("report_id"),
        "source_report": report_manifest.get("source_report"),
        "source_sha256": report_manifest.get("source_sha256"),
    }
    for key, expected in checks.items():
        if chunk.get(key) != expected:
            raise ChunkValidationError(f"{label}: {key} mismatch: expected {expected!r}, got {chunk.get(key)!r}")
    if chunk_info.get("format") and chunk_info.get("format") != report_manifest.get("source_format"):
        raise ChunkValidationError(f"{label}: chunk format does not match report format")
    if "json_pointer" in chunk_info and chunk.get("json_pointer") != chunk_info.get("json_pointer"):
        raise ChunkValidationError(f"{label}: json_pointer mismatch")
    if "item_start" in chunk_info and chunk.get("item_start") != chunk_info.get("item_start"):
        raise ChunkValidationError(f"{label}: item_start mismatch")
    if "item_count" in chunk_info and chunk.get("item_count") != chunk_info.get("item_count"):
        raise ChunkValidationError(f"{label}: item_count mismatch")
    if "chunk_index" in chunk_info and chunk.get("chunk_index") != chunk_info.get("chunk_index"):
        raise ChunkValidationError(f"{label}: chunk_index mismatch")
    if "key_count" in chunk_info and chunk.get("key_count") != chunk_info.get("key_count"):
        raise ChunkValidationError(f"{label}: key_count mismatch")


def require_chunk_index(chunk: dict[str, Any], chunk_info: dict[str, Any], *, label: str) -> None:
    if "chunk_index" not in chunk_info or not isinstance(chunk_info["chunk_index"], int):
        raise ChunkValidationError(f"{label}: manifest entry must include integer chunk_index")
    if "chunk_index" not in chunk or not isinstance(chunk["chunk_index"], int):
        raise ChunkValidationError(f"{label}: chunk body must include integer chunk_index")


def require_key_count(chunk: dict[str, Any], chunk_info: dict[str, Any], *, label: str) -> None:
    if "key_count" not in chunk_info or not isinstance(chunk_info["key_count"], int):
        raise ChunkValidationError(f"{label}: manifest entry must include integer key_count")
    if "key_count" not in chunk or not isinstance(chunk["key_count"], int):
        raise ChunkValidationError(f"{label}: chunk body must include integer key_count")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Repository root containing the chunk sidecar.")
    parser.add_argument(
        "--chunk-root",
        default=DEFAULT_CHUNK_ROOT.as_posix(),
        help="Repo-relative chunk sidecar root.",
    )
    parser.add_argument(
        "--strict-source-hash",
        action="store_true",
        help="Fail when reconstructed bytes do not match the manifest source_sha256.",
    )
    parser.add_argument(
        "--allow-lossy-json-order-reconstruction",
        action="store_true",
        help="Permit JSON source-hash mismatches as warnings when chunk values reassemble but byte order differs.",
    )
    parser.add_argument(
        "--compare-canonical",
        action="store_true",
        help="Compare reconstructed outputs with canonical report files when they exist.",
    )
    parser.add_argument(
        "--require-canonical-parity",
        action="store_true",
        help="Fail when --compare-canonical finds missing or mismatched canonical reports.",
    )
    parser.add_argument(
        "--write-output-dir",
        default="",
        help="Optional directory for reconstructed outputs. Does not overwrite canonical report paths.",
    )
    parser.add_argument(
        "--json-output",
        default="",
        help="Optional path for the validation report JSON.",
    )
    return parser


def safe_repo_path(value: Any, *, repo_root: Path, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ChunkValidationError(f"{label}: path must be a non-empty string")
    raw = value.strip()
    slash_path = raw.replace("\\", "/")
    raw_parts = tuple(part for part in slash_path.split("/") if part)
    rel = normalize_repo_path(raw)
    parts = Path(rel).parts
    if (
        not raw
        or is_absolute_repo_input(raw)
        or ".." in raw_parts
        or ".." in parts
        or Path(rel).is_absolute()
    ):
        raise ChunkValidationError(f"{label}: path must be repo-relative without traversal")
    path = repo_root / rel
    try:
        path.resolve().relative_to(repo_root.resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise ChunkValidationError(f"{label}: path must resolve inside the repository root") from exc
    return path


def ensure_object_parent(document: dict[str, Any], pointer: str, *, label: str) -> tuple[dict[str, Any], str] | None:
    parts = pointer_parts(pointer, label=label)
    if not parts:
        return None
    current: Any = document
    for part in parts[:-1]:
        if not isinstance(current, dict):
            raise ChunkValidationError(f"{label}: parent path is not an object before /{part}")
        if part not in current:
            current[part] = {}
        elif not isinstance(current[part], dict):
            raise ChunkValidationError(f"{label}: parent path /{'/'.join(parts[:-1])} is not an object")
        current = current[part]
    if not isinstance(current, dict):
        raise ChunkValidationError(f"{label}: parent path is not an object")
    return current, parts[-1]


def merge_json_object_members(document: dict[str, Any], pointer: str, value: Any, *, label: str) -> dict[str, Any]:
    members = require_mapping(value, label=f"{label}: data")
    parts = pointer_parts(pointer, label=label)
    current: Any = document
    for part in parts:
        if not isinstance(current, dict):
            raise ChunkValidationError(f"{label}: parent path is not an object before /{part}")
        if part not in current:
            current[part] = {}
        elif not isinstance(current[part], dict):
            raise ChunkValidationError(f"{label}: pointer {pointer} targets a non-object")
        current = current[part]
    target = require_mapping(current, label=f"{label}: target")
    for key, member_value in members.items():
        if key in target:
            raise ChunkValidationError(f"{label}: duplicate object member {pointer}/{key}")
        target[key] = member_value
    return document


def validate_report_manifest(
    report_manifest: Any,
    root_report: dict[str, Any],
    *,
    label: str,
) -> dict[str, Any]:
    manifest = require_mapping(report_manifest, label=label)
    expected_pairs = {
        "schema_version": REPORT_MANIFEST_SCHEMA_VERSION,
        "report_id": root_report.get("report_id"),
        "source_format": root_report.get("source_format"),
        "source_report": root_report.get("source_report"),
        "source_sha256": root_report.get("source_sha256"),
        "source_bytes": root_report.get("source_bytes"),
        "chunk_count": root_report.get("chunk_count"),
    }
    for key, expected in expected_pairs.items():
        if manifest.get(key) != expected:
            raise ChunkValidationError(f"{label}: {key} mismatch: expected {expected!r}, got {manifest.get(key)!r}")
    chunks = manifest.get("chunks")
    if not isinstance(chunks, list) or len(chunks) != manifest.get("chunk_count"):
        raise ChunkValidationError(f"{label}: chunks length does not match chunk_count")
    return manifest


def write_outputs(outputs: dict[str, bytes], *, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for source_report, data in outputs.items():
        rel = normalize_repo_path(source_report)
        out_path = output_dir / rel
        try:
            out_path.resolve().relative_to(output_dir.resolve())
        except (OSError, RuntimeError, ValueError) as exc:
            raise ChunkValidationError(f"write output path escapes output directory: {source_report}") from exc
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
