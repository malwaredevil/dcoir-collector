#!/usr/bin/env python3
"""Decode and apply a single-file ChatGPT apply-in payload bundle."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import zipfile
from typing import Any

SCHEMA = "dcoir.chatgpt_staging.apply_manifest.v1"
TRUNCATION_MARKER = "[... ELLIPSIZATION ...]"
FORBIDDEN_PAYLOAD_MARKERS = ("# dcoir-payload-b64-parts-v1", "payload.zip.b64.parts")
BLOCKED_PREFIXES = (
    ".git/",
    "chatgpt_staging/out/",
    "chatgpt_staging/work/",
    "chatgpt_staging/apply_reports/",
    "chatgpt_staging/failure_reports/",
    "chatgpt_staging/cleanup_requests/",
    "chatgpt_staging/status_reports/",
)


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_payload(payload_path: pathlib.Path, output_path: pathlib.Path) -> None:
    raw = payload_path.read_text(encoding="utf-8", errors="replace")
    if any(marker in raw for marker in FORBIDDEN_PAYLOAD_MARKERS):
        raise SystemExit(
            "Unsupported staging shape. This workflow accepts exactly one "
            "base64 ZIP file: payload.zip.b64. Do not use parts/chunks."
        )
    if TRUNCATION_MARKER in raw:
        raise SystemExit("payload.zip.b64 contains a truncation marker; rebuild and stage the full base64 file")
    cleaned = "".join(raw.split())
    bad_chars = sorted(set(re.sub(r"[A-Za-z0-9+/=]", "", cleaned)))
    if bad_chars:
        shown = " ".join(repr(ch) for ch in bad_chars[:20])
        raise SystemExit(f"Invalid base64 characters in payload.zip.b64: {shown}")
    if len(cleaned) % 4:
        raise SystemExit(
            f"Invalid base64 length: {len(cleaned)} characters leaves remainder "
            f"{len(cleaned) % 4}; payload may be truncated"
        )
    try:
        blob = base64.b64decode(cleaned, validate=True)
    except binascii.Error as exc:
        raise SystemExit(f"Invalid base64 payload: {exc}") from exc
    if not blob.startswith(b"PK"):
        raise SystemExit(f"Decoded payload is not a ZIP file; first bytes={blob[:8]!r}")
    output_path.write_bytes(blob)
    print(f"Decoded single payload.zip.b64: {len(cleaned)} chars -> {len(blob)} bytes")


def safe_extract_zip(zip_path: pathlib.Path, destination: pathlib.Path) -> None:
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            member_path = pathlib.PurePosixPath(member.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise SystemExit(f"Unsafe ZIP member path: {member.filename}")
            target = (destination / member.filename).resolve()
            if target != destination_resolved and destination_resolved not in target.parents:
                raise SystemExit(f"ZIP member escapes extraction root: {member.filename}")
        zf.extractall(destination)


def load_manifest(extract_root: pathlib.Path) -> dict[str, Any]:
    manifest_path = extract_root / "apply_manifest.json"
    if not manifest_path.is_file():
        raise SystemExit("Decoded ZIP did not contain apply_manifest.json at archive root")
    if not (extract_root / "files").is_dir():
        raise SystemExit("Decoded ZIP did not contain files/ at archive root")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schema = manifest.get("schema")
    if schema != SCHEMA:
        raise SystemExit(f"apply_manifest schema must be {SCHEMA}, got {schema!r}")
    return manifest


def safe_rel(path: str, *, allowed_roots: list[str], allow_workflows: bool) -> bool:
    p = pathlib.PurePosixPath(path)
    if path.startswith("/") or ".." in p.parts:
        return False
    if path in {"", "."} or len(p.parts) < 2:
        return False
    if any(path.startswith(prefix) for prefix in BLOCKED_PREFIXES):
        return False
    if path.startswith(".github/workflows/") and not allow_workflows:
        return False
    return any(path == root.rstrip("/") or path.startswith(root.rstrip("/") + "/") for root in allowed_roots)


def tracked_blob_sha(target: str) -> str:
    out = subprocess.check_output(["git", "ls-files", "-s", "--", target], text=True).split()
    return out[1] if len(out) > 1 else ""


def tracked_paths_under(target: str) -> list[str]:
    out = subprocess.check_output(["git", "ls-files", "--", target], text=True)
    return [line for line in out.splitlines() if line.strip()]


def validate_allowed_roots(allowed_roots: Any) -> list[str]:
    roots = allowed_roots or []
    if not isinstance(roots, list) or not roots:
        raise SystemExit("allowed_roots is required")
    normalized = [str(root) for root in roots]
    if any(not root.strip().strip("/") for root in normalized):
        raise SystemExit("allowed_roots must not include repo root or blank roots")
    return normalized


def apply_manifest(manifest: dict[str, Any], extract_root: pathlib.Path) -> tuple[list[str], list[str], list[str]]:
    allowed_roots = validate_allowed_roots(manifest.get("allowed_roots"))
    allow_missing_current_hash = bool(manifest.get("allow_missing_current_hash", False))
    allow_workflows = bool(manifest.get("allow_workflow_changes", False))
    workflow_change_reason = str(manifest.get("workflow_change_reason", "")).strip()
    if allow_workflows and not workflow_change_reason:
        raise SystemExit("allow_workflow_changes=true requires workflow_change_reason")

    applied: list[str] = []
    deleted: list[str] = []
    warnings: list[str] = []

    for item in manifest.get("files", []):
        target = item.get("path", "")
        source = item.get("source", "")
        expected_blob_sha = item.get("expected_blob_sha")
        expected_current_sha256 = item.get("expected_current_sha256")
        expected_new_sha256 = item.get("expected_new_sha256")
        create_only = bool(item.get("create_only", False))

        if not safe_rel(target, allowed_roots=allowed_roots, allow_workflows=allow_workflows):
            raise SystemExit(f"Unsafe or disallowed target path: {target}")
        if not source or source.startswith("/") or ".." in pathlib.PurePosixPath(source).parts:
            raise SystemExit(f"Unsafe source path: {source}")
        if not source.startswith("files/"):
            raise SystemExit(f"Source path must live under files/: {source}")
        src_path = extract_root / source
        if not src_path.is_file():
            raise SystemExit(f"Source file missing in ZIP: {src_path}")

        dst_path = pathlib.Path(target)
        exists = dst_path.exists()
        blob_sha = tracked_blob_sha(target)
        is_tracked = bool(blob_sha)

        if create_only:
            if exists:
                raise SystemExit(f"create_only target already exists: {target}")
            if not expected_new_sha256:
                raise SystemExit(f"create_only requires expected_new_sha256 for {target}")
        elif exists:
            if is_tracked and not (expected_blob_sha or expected_current_sha256):
                if not allow_missing_current_hash:
                    raise SystemExit(f"Existing tracked file requires expected_blob_sha or expected_current_sha256: {target}")
                warnings.append(f"allow_missing_current_hash override used for {target}")
            if not is_tracked:
                raise SystemExit(f"Existing untracked file cannot be overwritten by apply-in: {target}")
        else:
            if not expected_new_sha256:
                raise SystemExit(f"New file requires expected_new_sha256 and create_only=true for {target}")
            if not create_only:
                raise SystemExit(f"New file requires create_only=true for {target}")

        if expected_blob_sha and is_tracked and blob_sha != expected_blob_sha:
            raise SystemExit(f"Blob SHA mismatch for {target}: expected {expected_blob_sha}, got {blob_sha}")
        if expected_current_sha256 and exists:
            actual = sha256_file(dst_path)
            if actual != expected_current_sha256:
                raise SystemExit(f"Current sha256 mismatch for {target}: expected {expected_current_sha256}, got {actual}")
        if expected_new_sha256:
            actual_new = sha256_file(src_path)
            if actual_new != expected_new_sha256:
                raise SystemExit(f"New sha256 mismatch for {target}: expected {expected_new_sha256}, got {actual_new}")

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)
        applied.append(target)

    for item in manifest.get("deletes", []):
        target = str(item.get("path", "")).rstrip("/")
        expected_blob_sha = item.get("expected_blob_sha")
        expected_current_sha256 = item.get("expected_current_sha256")
        recursive = bool(item.get("recursive", False))
        require_exists = bool(item.get("require_exists", True))
        if not safe_rel(target, allowed_roots=allowed_roots, allow_workflows=allow_workflows):
            raise SystemExit(f"Unsafe or disallowed delete path: {target}")
        if target.startswith(".github/workflows/"):
            raise SystemExit("Workflow deletion is not allowed through apply-in")
        dst_path = pathlib.Path(target)
        tracked = tracked_paths_under(target)
        if not tracked:
            if require_exists:
                raise SystemExit(f"Delete target has no tracked files: {target}")
            warnings.append(f"delete target already absent: {target}")
            continue
        if dst_path.is_dir() and not recursive:
            raise SystemExit(f"Directory delete requires recursive=true: {target}")
        if len(pathlib.PurePosixPath(target).parts) < 3 and recursive:
            raise SystemExit(f"Recursive delete target is too broad: {target}")
        if expected_blob_sha:
            blob_sha = tracked_blob_sha(target)
            if blob_sha != expected_blob_sha:
                raise SystemExit(f"Blob SHA mismatch for delete target {target}: expected {expected_blob_sha}, got {blob_sha}")
        if expected_current_sha256:
            if not dst_path.is_file():
                raise SystemExit(f"expected_current_sha256 is only supported for file delete targets: {target}")
            actual = sha256_file(dst_path)
            if actual != expected_current_sha256:
                raise SystemExit(f"Current sha256 mismatch for delete target {target}: expected {expected_current_sha256}, got {actual}")
        subprocess.check_call(["git", "rm", "-r", "--", target])
        deleted.append(target)

    if not applied and not deleted:
        raise SystemExit("No files applied or deleted")
    return applied, deleted, warnings


def write_apply_outputs(
    *,
    manifest: dict[str, Any],
    applied: list[str],
    deleted: list[str],
    warnings: list[str],
    applied_paths: pathlib.Path,
    deleted_paths: pathlib.Path,
    hash_warnings: pathlib.Path,
) -> None:
    request_id = manifest.get("request_id", "unknown")
    report_dir = pathlib.Path("chatgpt_staging/apply_reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report = report_dir / f"{request_id}_apply_report.md"
    lines = ["# ChatGPT apply-in report", ""]
    lines.extend(f"- applied: `{path}`" for path in applied)
    lines.extend(f"- deleted: `{path}`" for path in deleted)
    if warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    applied_paths.parent.mkdir(parents=True, exist_ok=True)
    applied_paths.write_text("\n".join(applied) + ("\n" if applied else ""), encoding="utf-8")
    deleted_paths.write_text("\n".join(deleted) + ("\n" if deleted else ""), encoding="utf-8")
    if warnings:
        hash_warnings.write_text("\n".join(warnings) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", required=True, help="Repo-relative payload.zip.b64 path.")
    parser.add_argument("--work-dir", required=True, help="Repo-relative workflow scratch directory.")
    parser.add_argument("--applied-paths", default="chatgpt_staging/work/applied_paths.txt")
    parser.add_argument("--deleted-paths", default="chatgpt_staging/work/deleted_paths.txt")
    parser.add_argument("--hash-warnings", default="chatgpt_staging/work/hash_warnings.txt")
    args = parser.parse_args(argv)

    payload_path = pathlib.Path(args.payload)
    work_dir = pathlib.Path(args.work_dir)
    extract_root = work_dir / "extract"
    payload_zip = work_dir / "payload.zip"

    shutil.rmtree(work_dir, ignore_errors=True)
    extract_root.mkdir(parents=True, exist_ok=True)
    decode_payload(payload_path, payload_zip)
    safe_extract_zip(payload_zip, extract_root)
    manifest = load_manifest(extract_root)
    applied, deleted, warnings = apply_manifest(manifest, extract_root)
    write_apply_outputs(
        manifest=manifest,
        applied=applied,
        deleted=deleted,
        warnings=warnings,
        applied_paths=pathlib.Path(args.applied_paths),
        deleted_paths=pathlib.Path(args.deleted_paths),
        hash_warnings=pathlib.Path(args.hash_warnings),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
