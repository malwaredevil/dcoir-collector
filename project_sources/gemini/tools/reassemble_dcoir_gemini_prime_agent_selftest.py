#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name('reassemble_dcoir_gemini_prime_agent.py')


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class GeminiPrimeReassemblyPathSafetyTests(unittest.TestCase):
    def make_fixture(self, base: Path) -> tuple[Path, Path, str]:
        source_root = base / 'bundle_source'
        output_dir = base / 'out'
        chunks_dir = source_root / 'chunks'
        generated_dir = source_root / 'generated'
        chunks_dir.mkdir(parents=True)
        generated_dir.mkdir(parents=True)
        text = 'safe prime content\n'
        chunk_rel = 'chunks/part-001.txt'
        (source_root / chunk_rel).write_text(text, encoding='utf-8')
        chunk_manifest_rel = 'chunks/manifest.json'
        chunk_manifest = {
            'generated_prime_agent_file': 'generated/prime.txt',
            'chunks': [
                {'path': chunk_rel, 'sha256': sha256_text(text)},
            ],
            'reassembly': {'expected_sha256': sha256_text(text)},
        }
        (source_root / chunk_manifest_rel).write_text(
            json.dumps(chunk_manifest),
            encoding='utf-8',
        )
        bundle_manifest = {
            'prime_agent_source_mode': 'chunked_reassembled',
            'prime_agent_chunk_manifest': chunk_manifest_rel,
            'runtime_generated_files': ['generated/prime.txt'],
            'topology': {
                'prime_agent_file': 'generated/prime.txt',
                'prime_agent_chunk_manifest': chunk_manifest_rel,
                'prime_agent_chunk_sources': [chunk_rel],
            },
        }
        (source_root / 'Gemini_Bundle_Source_Manifest.json').write_text(
            json.dumps(bundle_manifest),
            encoding='utf-8',
        )
        return source_root, output_dir, text

    def run_reassembler(self, source_root: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                '--source-root',
                str(source_root),
                '--output-dir',
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding='utf-8'))

    def write_json(self, path: Path, value: dict) -> None:
        path.write_text(json.dumps(value), encoding='utf-8')

    def test_safe_fixture_reassembles_inside_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir, text = self.make_fixture(Path(td))
            proc = self.run_reassembler(source_root, output_dir)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(
                (source_root / 'generated/prime.txt').read_text(encoding='utf-8'),
                text,
            )

    def test_rejects_generated_target_traversal_without_escape_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root, output_dir, _ = self.make_fixture(base)
            manifest_path = source_root / 'chunks/manifest.json'
            manifest = self.read_json(manifest_path)
            manifest['generated_prime_agent_file'] = '../escaped.txt'
            self.write_json(manifest_path, manifest)

            proc = self.run_reassembler(source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('generated_prime_agent_file', proc.stderr)
            self.assertFalse((base / 'escaped.txt').exists())

    def test_rejects_chunk_manifest_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir, _ = self.make_fixture(Path(td))
            bundle_path = source_root / 'Gemini_Bundle_Source_Manifest.json'
            bundle = self.read_json(bundle_path)
            bundle['prime_agent_chunk_manifest'] = '../outside-manifest.json'
            bundle['topology']['prime_agent_chunk_manifest'] = '../outside-manifest.json'
            self.write_json(bundle_path, bundle)

            proc = self.run_reassembler(source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('prime_agent_chunk_manifest', proc.stderr)

    def test_rejects_chunk_source_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root, output_dir, text = self.make_fixture(base)
            outside = base / 'outside.txt'
            outside.write_text(text, encoding='utf-8')
            manifest_path = source_root / 'chunks/manifest.json'
            manifest = self.read_json(manifest_path)
            manifest['chunks'][0]['path'] = '../outside.txt'
            self.write_json(manifest_path, manifest)
            bundle_path = source_root / 'Gemini_Bundle_Source_Manifest.json'
            bundle = self.read_json(bundle_path)
            bundle['topology']['prime_agent_chunk_sources'] = ['../outside.txt']
            self.write_json(bundle_path, bundle)

            proc = self.run_reassembler(source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('prime agent chunk path', proc.stderr)

    def test_rejects_generated_target_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root, output_dir, _ = self.make_fixture(base)
            outside = base / 'outside'
            outside.mkdir()
            link = source_root / 'escape'
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (NotImplementedError, OSError):
                self.skipTest('symlinks are not supported')
            manifest_path = source_root / 'chunks/manifest.json'
            manifest = self.read_json(manifest_path)
            manifest['generated_prime_agent_file'] = 'escape/prime.txt'
            self.write_json(manifest_path, manifest)

            proc = self.run_reassembler(source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('escapes its root', proc.stderr)
            self.assertFalse((outside / 'prime.txt').exists())

    def test_rejects_non_object_chunk_manifest_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir, _ = self.make_fixture(Path(td))
            (source_root / 'chunks/manifest.json').write_text(
                '[]',
                encoding='utf-8',
            )

            proc = self.run_reassembler(source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn(
                'prime_agent_chunk_manifest must contain a JSON object',
                proc.stderr,
            )
            self.assertNotIn('Traceback', proc.stderr)

    def test_rejects_scalar_chunks_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir, _ = self.make_fixture(Path(td))
            manifest_path = source_root / 'chunks/manifest.json'
            manifest = self.read_json(manifest_path)
            manifest['chunks'] = 5
            self.write_json(manifest_path, manifest)

            proc = self.run_reassembler(source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn(
                'prime_agent_chunk_manifest.chunks must be a list',
                proc.stderr,
            )
            self.assertNotIn('Traceback', proc.stderr)

    def assert_target_rejected(self, mutate, expected: str) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir, _ = self.make_fixture(Path(td))
            protected = source_root / 'Gemini_Bundle_Source_Manifest.json'
            mutate(source_root)
            before = protected.read_text(encoding='utf-8')

            proc = self.run_reassembler(source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn(expected, proc.stderr)
            self.assertNotIn('Traceback', proc.stderr)
            self.assertEqual(protected.read_text(encoding='utf-8'), before)

    def test_rejects_contained_target_other_than_declared_prime_agent(self) -> None:
        def mutate(source_root: Path) -> None:
            manifest_path = source_root / 'chunks/manifest.json'
            manifest = self.read_json(manifest_path)
            manifest['generated_prime_agent_file'] = 'Gemini_Bundle_Source_Manifest.json'
            self.write_json(manifest_path, manifest)

        self.assert_target_rejected(
            mutate, 'generated_prime_agent_file must match topology.prime_agent_file'
        )

    def test_rejects_target_missing_from_runtime_generated_files(self) -> None:
        def mutate(source_root: Path) -> None:
            bundle_path = source_root / 'Gemini_Bundle_Source_Manifest.json'
            bundle = self.read_json(bundle_path)
            bundle['runtime_generated_files'] = []
            self.write_json(bundle_path, bundle)

        self.assert_target_rejected(
            mutate, 'generated_prime_agent_file must be listed in runtime_generated_files'
        )

    def test_rejects_bundle_root_as_target(self) -> None:
        def mutate(source_root: Path) -> None:
            manifest_path = source_root / 'chunks/manifest.json'
            manifest = self.read_json(manifest_path)
            manifest['generated_prime_agent_file'] = '.'
            self.write_json(manifest_path, manifest)

        self.assert_target_rejected(mutate, 'not the root itself')


if __name__ == '__main__':
    unittest.main()
