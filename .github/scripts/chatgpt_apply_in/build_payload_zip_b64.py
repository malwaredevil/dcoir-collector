#!/usr/bin/env python3
"""Build and validate a single-file ChatGPT apply-in payload.zip.b64.

This helper intentionally does not support chunking or parts mode. If the output is too
large for a staging lane, reduce the batch and rebuild a smaller single payload.zip.b64.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "dcoir.chatgpt_staging.apply_manifest.v1"
REQUEST_RE = re.compile(r"^[A-Za-z0-9._-]+$")
TRUNCATION_MARKER = "[... ELLIPSIZATION ...]"
FORBIDDEN_NAMES = {
    "chunk_manifest.json",
}
FORBIDDEN_SUBSTRINGS = (
    "payload.zip.b64.parts",
    "# dcoir-payload-b64-parts-v1",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def repo_rel(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    p = PurePosixPath(normalized)
    if not normalized or normalized == "." or normalized.startswith("/") or ".." in p.parts:
        raise SystemExit(f"unsafe repo-relative path: {path!r}")
    return p.as_posix()


def safe_request_id(request_id: str) -> str:
    if not REQUEST_RE.fullmatch(request_id):
        raise SystemExit(f"unsafe request id: {request_id!r}; use letters, numbers, dots, underscores, and hyphens only")
    return request_id


def parse_map(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        target = repo_rel(raw)
        source = target
    else:
        target_raw, source_raw = raw.split("=", 1)
        target = repo_rel(target_raw)
        source = repo_rel(source_raw)
    return target, source


def ensure_allowed(target: str, allowed_roots: list[str]) -> None:
    if any(not root.strip().strip("/") for root in allowed_roots):
        raise SystemExit("allowed roots must not include blank/repo root")
    if not any(target == root.rstrip("/") or target.startswith(root.rstrip("/") + "/") for root in allowed_roots):
        raise SystemExit(f"target path outside allowed roots: {target}")


def build_manifest(repo_root: Path, request_id: str, allowed_roots: list[str], maps: list[tuple[str, str]], *, allow_workflow_changes: bool, workflow_change_reason: str) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for target, source in maps:
        ensure_allowed(target, allowed_roots)
        source_path = repo_root / source
        target_path = repo_root / target
        if not source_path.is_file():
            raise SystemExit(f"source file not found: {source}")
        entry: dict[str, Any] = {
            "path": target,
            "source": f"files/{target}",
            "expected_new_sha256": sha256_file(source_path),
        }
        if target_path.exists():
            entry["expected_current_sha256"] = sha256_file(target_path)
        else:
            entry["create_only"] = True
        files.append(entry)

    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "request_id": request_id,
        "allowed_roots": allowed_roots,
        "files": files,
    }
    if allow_workflow_changes:
        if not workflow_change_reason.strip():
            raise SystemExit("--allow-workflow-changes requires --workflow-change-reason")
        manifest["allow_workflow_changes"] = True
        manifest["workflow_change_reason"] = workflow_change_reason.strip()
    return manifest


def write_zip(repo_root: Path, manifest: dict[str, Any], maps: list[tuple[str, str]], output_zip: Path) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("apply_manifest.json", json.dumps(manifest, indent=2, sort_keys=False) + "\n")
        for target, source in maps:
            zf.write(repo_root / source, f"files/{target}")


def validate_zip(zip_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        if "apply_manifest.json" not in names:
            raise SystemExit("ZIP missing root apply_manifest.json")
        if not any(name.startswith("files/") and not name.endswith("/") for name in names):
            raise SystemExit("ZIP missing files/ content")
        if any(name.startswith("/") or ".." in PurePosixPath(name).parts for name in names):
            raise SystemExit("ZIP contains unsafe archive path")
        if any(PurePosixPath(name).name in FORBIDDEN_NAMES or ".part" in name or "chunk" in name for name in names):
            raise SystemExit("ZIP contains forbidden chunk/part artifact")
        manifest = json.loads(zf.read("apply_manifest.json").decode("utf-8"))
        if manifest.get("schema") != SCHEMA:
            raise SystemExit(f"unexpected manifest schema: {manifest.get('schema')!r}")
        for item in manifest.get("files", []):
            source = item.get("source", "")
            if not source.startswith("files/"):
                raise SystemExit(f"manifest source must live under files/: {source}")
            if source not in names:
                raise SystemExit(f"manifest source missing from ZIP: {source}")
    return {"entry_count": len(names), "entries": names}


def write_base64(zip_path: Path, output_b64: Path) -> dict[str, Any]:
    blob = zip_path.read_bytes()
    text = base64.b64encode(blob).decode("ascii") + "\n"
    if TRUNCATION_MARKER in text or any(s in text for s in FORBIDDEN_SUBSTRINGS):
        raise SystemExit("generated base64 contains forbidden marker/substrings")
    output_b64.parent.mkdir(parents=True, exist_ok=True)
    output_b64.write_text(text, encoding="ascii")
    round_trip = base64.b64decode("".join(output_b64.read_text(encoding="ascii").split()), validate=True)
    if round_trip != blob:
        raise SystemExit("base64 round-trip mismatch")
    return {
        "zip_sha256": sha256_bytes(blob),
        "payload_b64_sha256": sha256_file(output_b64),
        "zip_size_bytes": len(blob),
        "payload_b64_size_bytes": output_b64.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--allowed-root", action="append", required=True, dest="allowed_roots")
    parser.add_argument("--include", action="append", required=True, help="TARGET or TARGET=SOURCE, repo-relative")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--allow-workflow-changes", action="store_true")
    parser.add_argument("--workflow-change-reason", default="")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    request_id = safe_request_id(args.request_id)
    allowed_roots = [repo_rel(root) for root in args.allowed_roots]
    maps = [parse_map(raw) for raw in args.include]
    output_dir = Path(args.output_dir).resolve()
    request_dir = output_dir / request_id
    zip_path = request_dir / "payload.zip"
    b64_path = request_dir / "payload.zip.b64"
    report_path = request_dir / "payload_report.json"

    manifest = build_manifest(
        repo_root,
        request_id,
        allowed_roots,
        maps,
        allow_workflow_changes=args.allow_workflow_changes,
        workflow_change_reason=args.workflow_change_reason,
    )
    write_zip(repo_root, manifest, maps, zip_path)
    zip_info = validate_zip(zip_path)
    hash_info = write_base64(zip_path, b64_path)

    with tempfile.TemporaryDirectory() as td:
        extracted = Path(td)
        shutil.unpack_archive(str(zip_path), str(extracted), "zip")
        if not (extracted / "apply_manifest.json").is_file():
            raise SystemExit("post-build unpack validation failed: missing apply_manifest.json")
        if not (extracted / "files").is_dir():
            raise SystemExit("post-build unpack validation failed: missing files/")

    report = {
        "request_id": request_id,
        "staging_path": f".github/chatgpt_staging/in/{request_id}/payload.zip.b64",
        "payload_shape": "single payload.zip.b64",
        "parts_mode": False,
        "zip_path": str(zip_path),
        "payload_b64_path": str(b64_path),
        "manifest": manifest,
        "zip_validation": zip_info,
        "hashes": hash_info,
        "forbidden_shapes": ["payload.zip.b64.parts", "part files", "chunk_manifest.json", "chunk markers"],
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"payload_b64_path": str(b64_path), "report_path": str(report_path), **hash_info}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
