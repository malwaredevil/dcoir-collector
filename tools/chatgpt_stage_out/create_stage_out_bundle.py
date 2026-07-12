#!/usr/bin/env python3
"""Validate a ChatGPT stage-out request and create the output bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import zipfile
from typing import Any

SCHEMA = "dcoir.chatgpt_staging.stage_out_request.v1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_rel(path: str, allowed_roots: list[str]) -> bool:
    pure = pathlib.PurePosixPath(path)
    if path.startswith("/") or ".." in pure.parts:
        return False
    return any(path == root.rstrip("/") or path.startswith(root.rstrip("/") + "/") for root in allowed_roots)


def load_request(request_path: pathlib.Path) -> dict[str, Any]:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    schema = request.get("schema")
    if schema != SCHEMA:
        raise SystemExit(f"stage-out request schema must be {SCHEMA}, got {schema!r}")
    if not request.get("allowed_roots"):
        raise SystemExit("allowed_roots is required for live stage-out requests")
    return request


def tracked_paths() -> list[str]:
    return subprocess.check_output(["git", "ls-files"], text=True).splitlines()


def tracked_blob_sha(path: str) -> str:
    output = subprocess.check_output(["git", "ls-files", "-s", "--", path], text=True).split()
    return output[1] if len(output) > 1 else "UNTRACKED"


def select_paths(request: dict[str, Any]) -> list[str]:
    allowed_roots = [str(root) for root in request.get("allowed_roots") or []]
    exact_paths = request.get("exact_paths") or []
    search_terms = request.get("search_terms") or []
    max_matches = int(request.get("max_matches_per_term", 20))

    selected: list[str] = []
    for path in exact_paths:
        if not safe_rel(path, allowed_roots):
            raise SystemExit(f"Unsafe or disallowed path: {path}")
        if not pathlib.Path(path).is_file():
            raise SystemExit(f"Requested file not found: {path}")
        selected.append(path)

    for term in search_terms:
        term_lower = str(term).lower()
        count = 0
        for path in tracked_paths():
            if count >= max_matches:
                break
            if term_lower in path.lower() and safe_rel(path, allowed_roots) and pathlib.Path(path).is_file():
                selected.append(path)
                count += 1

    selected = sorted(set(selected))
    if not selected:
        raise SystemExit("No files selected")
    return selected


def write_bundle(request_path: pathlib.Path, out_dir: pathlib.Path, request: dict[str, Any], selected: list[str]) -> None:
    chunk_lines = int(request.get("chunk_lines", 200))
    include_files_copy = bool(request.get("include_files_copy", True))
    allowed_roots = request.get("allowed_roots") or []
    request_id = request["request_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "files").mkdir(parents=True, exist_ok=True)
    (out_dir / "chunks").mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "request_id": request_id,
        "request_path": str(request_path),
        "mode": request.get("mode", "zip_first_with_chunks_fallback"),
        "allowed_roots": allowed_roots,
        "files": [],
    }
    markdown = [
        "# ChatGPT stage-out manifest",
        "",
        f"- request_id: `{request_id}`",
        f"- request_path: `{request_path}`",
        "",
        "## Files",
        "",
    ]

    zip_path = out_dir / "staged_files.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, path in enumerate(selected, 1):
            source = pathlib.Path(path)
            data = source.read_bytes()
            sha256 = sha256_bytes(data)
            blob_sha = tracked_blob_sha(path)
            if include_files_copy:
                copied = out_dir / "files" / path
                copied.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, copied)
            archive.write(source, arcname=path)
            text = source.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines()
            chunks: list[str] = []
            for chunk_no, start in enumerate(range(0, len(lines), chunk_lines), 1):
                chunk_name = f"{index:03d}__{source.name}__chunk{chunk_no:03d}.txt"
                chunk_path = out_dir / "chunks" / chunk_name
                header = [
                    f"original_path: {path}",
                    f"blob_sha: {blob_sha}",
                    f"sha256: {sha256}",
                    f"chunk: {chunk_no}",
                    f"line_start: {start + 1}",
                    f"line_end: {min(start + chunk_lines, len(lines))}",
                    "---",
                ]
                chunk_path.write_text("\n".join(header + lines[start : start + chunk_lines]) + "\n", encoding="utf-8")
                chunks.append(str(chunk_path.relative_to(out_dir)))
            entry = {
                "path": path,
                "bytes": len(data),
                "lines": len(lines),
                "blob_sha": blob_sha,
                "sha256": sha256,
                "chunks": chunks,
            }
            manifest["files"].append(entry)
            markdown.append(
                f"- `{path}` | bytes={len(data)} | lines={len(lines)} | "
                f"blob_sha=`{blob_sha}` | sha256=`{sha256}`"
            )

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out_dir / "manifest.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request_path")
    parser.add_argument("out_dir")
    args = parser.parse_args(argv)

    request_path = pathlib.Path(args.request_path)
    out_dir = pathlib.Path(args.out_dir)
    request = load_request(request_path)
    selected = select_paths(request)
    write_bundle(request_path, out_dir, request, selected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
