#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import unittest
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


from reassemble_powershell_evidence_chunks_test_support import ReassemblePowerShellEvidenceChunksTestSupport

class ReassemblePowerShellEvidenceChunkSafetyTests(ReassemblePowerShellEvidenceChunksTestSupport, unittest.TestCase):
    def test_json_text_slices_are_byte_exact(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            self.replace_json_chunks_with_text_slices(root, slice_size=40)
            source_path = "project_sources/collector/fixture_report.json"
            source_bytes = (root / source_path).read_bytes()
            report, outputs = chunks.validate_chunk_set(self.args(root))

        self.assertTrue(report["validation"]["success"], report["validation"])
        self.assertTrue(report["reconstruction_exact_success"])
        self.assertEqual(outputs[source_path], source_bytes)
        json_report = next(item for item in report["reports"] if item["source_format"] == "json")
        self.assertTrue(json_report["source_sha256_match"])

    def test_json_text_slice_tamper_fails_sha_check(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            self.replace_json_chunks_with_text_slices(root, slice_size=40)
            chunk_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/chunk_000_text.json.txt"
            tampered = bytearray(chunk_path.read_bytes())
            tampered[0] = ord(" ")
            write(chunk_path, bytes(tampered))

            with self.assertRaisesRegex(chunks.ChunkValidationError, "sha256 mismatch"):
                chunks.validate_chunk_set(self.args(root))

    def test_json_text_slice_gap_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            self.replace_json_chunks_with_text_slices(root, slice_size=40)
            manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["chunks"][1]["byte_start"] += 1
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")

            with self.assertRaisesRegex(chunks.ChunkValidationError, "gap or overlap"):
                chunks.validate_chunk_set(self.args(root))

    def test_json_text_slice_manifest_requires_reassembly_mode(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            self.replace_json_chunks_with_text_slices(root, slice_size=40)
            manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.pop("reassembly_mode")
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")

            with self.assertRaisesRegex(chunks.ChunkValidationError, "reassembly_mode"):
                chunks.validate_chunk_set(self.args(root))

    def test_source_hash_mismatch_fails_without_explicit_lossy_flag(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            self.set_json_source_sha(root, "0" * 64)
            report, _outputs = chunks.validate_chunk_set(
                self.args(root, strict_source_hash=False, allow_lossy_json_order_reconstruction=False)
            )

        self.assertFalse(report["validation"]["success"])
        self.assertFalse(report["reconstruction_exact_success"])
        self.assertTrue(any("reconstructed SHA-256" in error for error in report["validation"]["errors"]))

    def test_explicit_lossy_flag_keeps_byte_gap_visible_without_writable_output(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            self.set_json_source_sha(root, "0" * 64)
            report, outputs = chunks.validate_chunk_set(
                self.args(root, strict_source_hash=False, allow_lossy_json_order_reconstruction=True)
            )

        self.assertTrue(report["validation"]["success"], report["validation"])
        self.assertFalse(report["reconstruction_exact_success"])
        self.assertTrue(report["readiness_gaps"])
        self.assertNotIn("project_sources/collector/fixture_report.json", outputs)
        self.assertIn("project_sources/collector/fixture_report.md", outputs)

    def test_lossy_flag_does_not_downgrade_markdown_source_hash_mismatch(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            root_manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "manifest.json"
            root_manifest = json.loads(root_manifest_path.read_text(encoding="utf-8"))
            markdown_report = root_manifest["reports"][1]
            markdown_report["source_sha256"] = "0" * 64
            report_manifest_path = root / markdown_report["manifest_path"]
            report_manifest = json.loads(report_manifest_path.read_text(encoding="utf-8"))
            report_manifest["source_sha256"] = "0" * 64
            write(report_manifest_path, json.dumps(report_manifest, indent=2) + "\n")
            write(root_manifest_path, json.dumps(root_manifest, indent=2) + "\n")

            report, _outputs = chunks.validate_chunk_set(
                self.args(root, strict_source_hash=False, allow_lossy_json_order_reconstruction=True)
            )

        self.assertFalse(report["validation"]["success"])
        self.assertTrue(any("fixture_report.md" in error for error in report["validation"]["errors"]))

    def test_main_refuses_to_write_outputs_when_validation_fails(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            self.set_json_source_sha(root, "0" * 64)
            output_dir = root / "reconstructed"
            with contextlib.redirect_stdout(io.StringIO()):
                status = chunks.main(
                    [
                        "--repo-root",
                        root.as_posix(),
                        "--write-output-dir",
                        output_dir.as_posix(),
                    ]
                )

        self.assertEqual(status, 1)
        self.assertFalse(output_dir.exists())

    def test_chunk_paths_must_stay_inside_chunk_root(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["chunks"][0]["path"] = "project_sources/collector/fixture_report.json"
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")

            with self.assertRaisesRegex(chunks.ChunkValidationError, "inside the chunk root"):
                chunks.validate_chunk_set(self.args(root))

    def test_chunk_index_metadata_mismatch_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            chunk_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/chunk_002.json"
            chunk = json.loads(chunk_path.read_text(encoding="utf-8"))
            chunk["chunk_index"] = 99
            text = json.dumps(chunk, indent=2) + "\n"
            write(chunk_path, text)
            manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["chunks"][2]["bytes"] = len(text.encode("utf-8"))
            manifest["chunks"][2]["sha256"] = sha256(text)
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")

            with self.assertRaisesRegex(chunks.ChunkValidationError, "chunk_index mismatch"):
                chunks.validate_chunk_set(self.args(root))

    def test_key_count_metadata_mismatch_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            chunk_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/chunk_004.json"
            chunk = json.loads(chunk_path.read_text(encoding="utf-8"))
            chunk["key_count"] = 2
            text = json.dumps(chunk, indent=2) + "\n"
            write(chunk_path, text)
            manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["chunks"][4]["bytes"] = len(text.encode("utf-8"))
            manifest["chunks"][4]["sha256"] = sha256(text)
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")

            with self.assertRaisesRegex(chunks.ChunkValidationError, "key_count"):
                chunks.validate_chunk_set(self.args(root))

    def test_missing_chunk_index_metadata_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            chunk_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/chunk_002.json"
            chunk = json.loads(chunk_path.read_text(encoding="utf-8"))
            chunk.pop("chunk_index")
            text = json.dumps(chunk, indent=2) + "\n"
            write(chunk_path, text)
            manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["chunks"][2]["bytes"] = len(text.encode("utf-8"))
            manifest["chunks"][2]["sha256"] = sha256(text)
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")

            with self.assertRaisesRegex(chunks.ChunkValidationError, "chunk_index"):
                chunks.validate_chunk_set(self.args(root))

    def test_missing_key_count_metadata_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            chunk_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/chunk_004.json"
            chunk = json.loads(chunk_path.read_text(encoding="utf-8"))
            chunk.pop("key_count")
            text = json.dumps(chunk, indent=2) + "\n"
            write(chunk_path, text)
            manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["chunks"][4]["bytes"] = len(text.encode("utf-8"))
            manifest["chunks"][4]["sha256"] = sha256(text)
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")

            with self.assertRaisesRegex(chunks.ChunkValidationError, "key_count"):
                chunks.validate_chunk_set(self.args(root))

    def test_duplicate_source_report_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            root_manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "manifest.json"
            root_manifest = json.loads(root_manifest_path.read_text(encoding="utf-8"))
            root_manifest["reports"][1]["source_report"] = root_manifest["reports"][0]["source_report"]
            write(root_manifest_path, json.dumps(root_manifest, indent=2) + "\n")

            with self.assertRaisesRegex(chunks.ChunkValidationError, "duplicate source_report"):
                chunks.validate_chunk_set(self.args(root))

    def test_normalized_duplicate_source_report_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            root_manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "manifest.json"
            root_manifest = json.loads(root_manifest_path.read_text(encoding="utf-8"))
            root_manifest["reports"][1]["source_report"] = "./" + root_manifest["reports"][0]["source_report"]
            markdown_manifest_path = root / root_manifest["reports"][1]["manifest_path"]
            markdown_manifest = json.loads(markdown_manifest_path.read_text(encoding="utf-8"))
            markdown_manifest["source_report"] = root_manifest["reports"][1]["source_report"]
            write(markdown_manifest_path, json.dumps(markdown_manifest, indent=2) + "\n")
            write(root_manifest_path, json.dumps(root_manifest, indent=2) + "\n")

            with self.assertRaisesRegex(chunks.ChunkValidationError, "duplicate source_report"):
                chunks.validate_chunk_set(self.args(root))
