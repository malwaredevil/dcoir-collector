#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / 'gemini'
    / 'tools'
    / 'reassemble_dcoir_gemini_prime_agent.py'
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class PrimeReassemblyBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source_root = self.root / 'bundle_source'
        self.output_dir = self.root / 'out'
        self.chunk_rel = 'chunks/chunk.md.txt'
        self.chunk_manifest_rel = 'chunks/manifest.json'
        self.target_rel = 'Prime.md.txt'
        self.chunk_text = 'canonical prime behavior\n'
        chunk_path = self.source_root / self.chunk_rel
        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        chunk_path.write_text(self.chunk_text, encoding='utf-8')
        (self.source_root / self.target_rel).write_text(
            self.chunk_text, encoding='utf-8'
        )
        self._write_json(
            self.source_root / self.chunk_manifest_rel,
            {
                'generated_prime_agent_file': self.target_rel,
                'reassembly': {'expected_sha256': sha256_text(self.chunk_text)},
                'chunks': [
                    {
                        'path': self.chunk_rel,
                        'sha256': sha256_text(self.chunk_text),
                    }
                ],
            },
        )
        self.bundle = {
            'prime_agent_source_mode': 'chunked_reassembled',
            'prime_agent_chunk_manifest': self.chunk_manifest_rel,
            'topology': {
                'prime_agent_chunk_manifest': self.chunk_manifest_rel,
                'prime_agent_chunk_sources': [self.chunk_rel],
            },
        }
        self._save_bundle()

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _write_json(path: Path, value: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

    def _save_bundle(self) -> None:
        self._write_json(
            self.source_root / 'Gemini_Bundle_Source_Manifest.json', self.bundle
        )

    def _run(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                '--source-root',
                str(self.source_root),
                '--output-dir',
                str(self.output_dir),
                '--check-only',
            ],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_accepts_bound_manifest_and_sources(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_rejects_runtime_manifest_different_from_topology(self) -> None:
        alternate_rel = 'chunks/alternate.json'
        self._write_json(
            self.source_root / alternate_rel,
            {
                'generated_prime_agent_file': self.target_rel,
                'reassembly': {'expected_sha256': sha256_text(self.chunk_text)},
                'chunks': [
                    {
                        'path': self.chunk_rel,
                        'sha256': sha256_text(self.chunk_text),
                    }
                ],
            },
        )
        self.bundle['prime_agent_chunk_manifest'] = alternate_rel
        self._save_bundle()
        result = self._run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Prime chunk manifest disagreement', result.stderr)

    def test_rejects_topology_sources_different_from_selected_manifest(self) -> None:
        self.bundle['topology']['prime_agent_chunk_sources'] = ['chunks/other.md.txt']
        self._save_bundle()
        result = self._run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Prime chunk source disagreement', result.stderr)


if __name__ == '__main__':
    unittest.main()
