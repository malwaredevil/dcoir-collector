#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reassemble_powershell_evidence_chunks as chunks


def write(path: Path, data: bytes | str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8", newline="")


def sha256(value: bytes | str) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


class ReassemblePowerShellEvidenceChunksTestSupport:
    def make_repo(self) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        chunk_root = root / chunks.DEFAULT_CHUNK_ROOT

        json_source = {
            "schema_version": "fixture_v1",
            "summary": {"total": 3},
            "items": [{"id": 1}, {"id": 2}, {"id": 3}],
            "details": {"left": True, "right": False},
        }
        json_text = json.dumps(json_source, indent=2) + "\n"
        markdown_text = "# Fixture Report\n\n- status: pass\n"
        write(root / "project_sources/collector/fixture_report.json", json_text)
        write(root / "project_sources/collector/fixture_report.md", markdown_text)

        json_chunks = [
            {
                "chunk_kind": "json_value",
                "data": "fixture_v1",
                "json_pointer": "/schema_version",
                "report_id": "fixture",
                "schema_version": chunks.CHUNK_SCHEMA_VERSION,
                "source_report": "project_sources/collector/fixture_report.json",
                "source_sha256": sha256(json_text),
            },
            {
                "chunk_kind": "json_value",
                "data": {"total": 3},
                "json_pointer": "/summary",
                "report_id": "fixture",
                "schema_version": chunks.CHUNK_SCHEMA_VERSION,
                "source_report": "project_sources/collector/fixture_report.json",
                "source_sha256": sha256(json_text),
            },
            {
                "chunk_index": 0,
                "chunk_kind": "json_list_items",
                "data": [{"id": 1}, {"id": 2}],
                "item_count": 2,
                "item_start": 0,
                "json_pointer": "/items",
                "report_id": "fixture",
                "schema_version": chunks.CHUNK_SCHEMA_VERSION,
                "source_report": "project_sources/collector/fixture_report.json",
                "source_sha256": sha256(json_text),
            },
            {
                "chunk_index": 1,
                "chunk_kind": "json_list_items",
                "data": [{"id": 3}],
                "item_count": 1,
                "item_start": 2,
                "json_pointer": "/items",
                "report_id": "fixture",
                "schema_version": chunks.CHUNK_SCHEMA_VERSION,
                "source_report": "project_sources/collector/fixture_report.json",
                "source_sha256": sha256(json_text),
            },
            {
                "chunk_index": 0,
                "chunk_kind": "json_object_members",
                "data": {"left": True},
                "json_pointer": "/details",
                "key_count": 1,
                "report_id": "fixture",
                "schema_version": chunks.CHUNK_SCHEMA_VERSION,
                "source_report": "project_sources/collector/fixture_report.json",
                "source_sha256": sha256(json_text),
            },
            {
                "chunk_index": 1,
                "chunk_kind": "json_object_members",
                "data": {"right": False},
                "json_pointer": "/details",
                "key_count": 1,
                "report_id": "fixture",
                "schema_version": chunks.CHUNK_SCHEMA_VERSION,
                "source_report": "project_sources/collector/fixture_report.json",
                "source_sha256": sha256(json_text),
            },
        ]
        json_manifest_chunks = []
        for index, chunk in enumerate(json_chunks):
            rel = chunks.DEFAULT_CHUNK_ROOT / "fixture/json" / f"chunk_{index:03d}.json"
            text = json.dumps(chunk, indent=2) + "\n"
            write(root / rel, text)
            info = {
                "bytes": len(text.encode("utf-8")),
                "chunk_kind": chunk["chunk_kind"],
                "format": "json",
                "path": rel.as_posix(),
                "sha256": sha256(text),
            }
            if "json_pointer" in chunk:
                info["json_pointer"] = chunk["json_pointer"]
            if "chunk_index" in chunk:
                info["chunk_index"] = chunk["chunk_index"]
            if "item_start" in chunk:
                info["item_start"] = chunk["item_start"]
                info["item_count"] = chunk["item_count"]
            if "key_count" in chunk:
                info["key_count"] = chunk["key_count"]
            json_manifest_chunks.append(info)

        markdown_rel = chunks.DEFAULT_CHUNK_ROOT / "fixture/markdown/chunk_000.md"
        write(root / markdown_rel, markdown_text)

        json_manifest = {
            "chunk_count": len(json_manifest_chunks),
            "chunks": json_manifest_chunks,
            "report_id": "fixture",
            "schema_version": chunks.REPORT_MANIFEST_SCHEMA_VERSION,
            "source_bytes": len(json_text.encode("utf-8")),
            "source_format": "json",
            "source_report": "project_sources/collector/fixture_report.json",
            "source_sha256": sha256(json_text),
        }
        markdown_manifest = {
            "chunk_count": 1,
            "chunks": [
                {
                    "bytes": len(markdown_text.encode("utf-8")),
                    "chunk_kind": "markdown_section",
                    "format": "markdown",
                    "path": markdown_rel.as_posix(),
                    "sha256": sha256(markdown_text),
                }
            ],
            "report_id": "fixture",
            "schema_version": chunks.REPORT_MANIFEST_SCHEMA_VERSION,
            "source_bytes": len(markdown_text.encode("utf-8")),
            "source_format": "markdown",
            "source_report": "project_sources/collector/fixture_report.md",
            "source_sha256": sha256(markdown_text),
        }
        json_manifest_rel = chunks.DEFAULT_CHUNK_ROOT / "fixture/json/manifest.json"
        markdown_manifest_rel = chunks.DEFAULT_CHUNK_ROOT / "fixture/markdown/manifest.json"
        write(root / json_manifest_rel, json.dumps(json_manifest, indent=2) + "\n")
        write(root / markdown_manifest_rel, json.dumps(markdown_manifest, indent=2) + "\n")

        root_manifest = {
            "file_count": 4 + len(json_chunks),
            "issue": 349,
            "pull_request": 350,
            "report_count": 2,
            "reports": [
                {
                    "chunk_count": len(json_manifest_chunks),
                    "manifest_path": json_manifest_rel.as_posix(),
                    "report_id": "fixture",
                    "source_bytes": len(json_text.encode("utf-8")),
                    "source_format": "json",
                    "source_report": "project_sources/collector/fixture_report.json",
                    "source_sha256": sha256(json_text),
                },
                {
                    "chunk_count": 1,
                    "manifest_path": markdown_manifest_rel.as_posix(),
                    "report_id": "fixture",
                    "source_bytes": len(markdown_text.encode("utf-8")),
                    "source_format": "markdown",
                    "source_report": "project_sources/collector/fixture_report.md",
                    "source_sha256": sha256(markdown_text),
                },
            ],
            "schema_version": chunks.ROOT_SCHEMA_VERSION,
        }
        write(chunk_root / "manifest.json", json.dumps(root_manifest, indent=2) + "\n")
        return temp

    def args(self, root: Path, **overrides: object) -> argparse.Namespace:
        values: dict[str, object] = {
            "repo_root": root.as_posix(),
            "chunk_root": chunks.DEFAULT_CHUNK_ROOT.as_posix(),
            "strict_source_hash": True,
            "allow_lossy_json_order_reconstruction": False,
            "compare_canonical": True,
            "require_canonical_parity": False,
            "write_output_dir": "",
            "json_output": "",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def replace_json_chunks_with_text_slices(self, root: Path, *, slice_size: int = 64) -> None:
        root_manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "manifest.json"
        root_manifest = json.loads(root_manifest_path.read_text(encoding="utf-8"))
        json_report = root_manifest["reports"][0]
        report_manifest_path = root / json_report["manifest_path"]
        report_manifest = json.loads(report_manifest_path.read_text(encoding="utf-8"))
        for chunk_info in report_manifest["chunks"]:
            (root / chunk_info["path"]).unlink()

        source_bytes = (root / json_report["source_report"]).read_bytes()
        new_chunks = []
        for index, byte_start in enumerate(range(0, len(source_bytes), slice_size)):
            raw = source_bytes[byte_start : byte_start + slice_size]
            byte_end = byte_start + len(raw)
            rel = chunks.DEFAULT_CHUNK_ROOT / "fixture/json" / f"chunk_{index:03d}_text.json.txt"
            write(root / rel, raw)
            new_chunks.append(
                {
                    "byte_end": byte_end,
                    "byte_start": byte_start,
                    "bytes": len(raw),
                    "chunk_index": index,
                    "chunk_kind": "json_text_slice",
                    "format": "json",
                    "path": rel.as_posix(),
                    "sha256": sha256(raw),
                }
            )

        report_manifest["chunk_count"] = len(new_chunks)
        report_manifest["chunks"] = new_chunks
        report_manifest["reassembly_mode"] = "byte_exact_text_slices"
        json_report["chunk_count"] = len(new_chunks)
        root_manifest["file_count"] = sum(1 for path in (root / chunks.DEFAULT_CHUNK_ROOT).rglob("*") if path.is_file())
        write(report_manifest_path, json.dumps(report_manifest, indent=2) + "\n")
        write(root_manifest_path, json.dumps(root_manifest, indent=2) + "\n")

    def set_json_source_sha(self, root: Path, replacement_sha: str) -> None:
        root_manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "manifest.json"
        root_manifest = json.loads(root_manifest_path.read_text(encoding="utf-8"))
        json_report = root_manifest["reports"][0]
        json_report["source_sha256"] = replacement_sha
        report_manifest_path = root / json_report["manifest_path"]
        report_manifest = json.loads(report_manifest_path.read_text(encoding="utf-8"))
        report_manifest["source_sha256"] = replacement_sha
        for chunk_info in report_manifest["chunks"]:
            chunk_path = root / chunk_info["path"]
            chunk = json.loads(chunk_path.read_text(encoding="utf-8"))
            chunk["source_sha256"] = replacement_sha
            text = json.dumps(chunk, indent=2) + "\n"
            write(chunk_path, text)
            chunk_info["bytes"] = len(text.encode("utf-8"))
            chunk_info["sha256"] = sha256(text)
        write(report_manifest_path, json.dumps(report_manifest, indent=2) + "\n")
        write(root_manifest_path, json.dumps(root_manifest, indent=2) + "\n")
