#!/usr/bin/env python3
from __future__ import annotations

import hashlib
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

class ReassemblePowerShellEvidenceChunksTests(ReassemblePowerShellEvidenceChunksTestSupport, unittest.TestCase):
    def test_reassembles_fixture_and_matches_canonical_reports(self) -> None:
        with self.make_repo() as temp:
            report, outputs = chunks.validate_chunk_set(self.args(Path(temp)))

        self.assertTrue(report["validation"]["success"], report["validation"])
        self.assertEqual(report["report_count"], 2)
        self.assertIn("project_sources/collector/fixture_report.json", outputs)
        self.assertTrue(all(item["canonical_parity"]["status"] == "pass" for item in report["reports"]))

    def test_missing_chunk_file_fails_with_path_context(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            (root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/chunk_003.json").unlink()
            with self.assertRaisesRegex(chunks.ChunkValidationError, "missing chunk file"):
                chunks.validate_chunk_set(self.args(root))

    def test_tampered_chunk_fails_sha_check(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            chunk_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/chunk_000.json"
            original = chunk_path.read_text(encoding="utf-8")
            write(chunk_path, original.replace("fixture_v1", "fixture_v2"))
            with self.assertRaisesRegex(chunks.ChunkValidationError, "sha256 mismatch"):
                chunks.validate_chunk_set(self.args(root))

    def test_json_list_gap_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["chunks"][3]["item_start"] = 3
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")
            chunk_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/chunk_003.json"
            chunk = json.loads(chunk_path.read_text(encoding="utf-8"))
            chunk["item_start"] = 3
            text = json.dumps(chunk, indent=2) + "\n"
            write(chunk_path, text)
            manifest["chunks"][3]["bytes"] = len(text.encode("utf-8"))
            manifest["chunks"][3]["sha256"] = sha256(text)
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")

            with self.assertRaisesRegex(chunks.ChunkValidationError, "gap or overlap"):
                chunks.validate_chunk_set(self.args(root))

    def test_json_object_member_collision_fails_closed(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            chunk_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/chunk_005.json"
            chunk = json.loads(chunk_path.read_text(encoding="utf-8"))
            chunk["data"] = {"left": False}
            text = json.dumps(chunk, indent=2) + "\n"
            write(chunk_path, text)
            manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["chunks"][5]["bytes"] = len(text.encode("utf-8"))
            manifest["chunks"][5]["sha256"] = sha256(text)
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")

            with self.assertRaisesRegex(chunks.ChunkValidationError, "duplicate object member"):
                chunks.validate_chunk_set(self.args(root))

    def test_path_traversal_fails_before_file_read(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            manifest_path = root / chunks.DEFAULT_CHUNK_ROOT / "fixture/json/manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["chunks"][0]["path"] = "../outside.json"
            write(manifest_path, json.dumps(manifest, indent=2) + "\n")

            with self.assertRaisesRegex(chunks.ChunkValidationError, "repo-relative without traversal"):
                chunks.validate_chunk_set(self.args(root))

    def test_canonical_mismatch_is_reported_separately(self) -> None:
        with self.make_repo() as temp:
            root = Path(temp)
            write(root / "project_sources/collector/fixture_report.md", "# Stale\n")
            report, _outputs = chunks.validate_chunk_set(self.args(root, strict_source_hash=True))

        markdown_report = next(item for item in report["reports"] if item["source_format"] == "markdown")
        self.assertTrue(report["validation"]["success"])
        self.assertEqual(markdown_report["canonical_parity"]["status"], "mismatch")
        self.assertFalse(markdown_report["canonical_parity"]["source_sha256_match"])
        self.assertFalse(report["canonical_parity_success"])
        self.assertTrue(report["readiness_gaps"])

    def test_skipped_canonical_compare_keeps_readiness_gap_visible(self) -> None:
        with self.make_repo() as temp:
            report, _outputs = chunks.validate_chunk_set(self.args(Path(temp), compare_canonical=False))

        self.assertTrue(report["validation"]["success"], report["validation"])
        self.assertIsNone(report["canonical_parity_success"])
        self.assertIn("canonical reports were not compared", " ".join(report["readiness_gaps"]))
