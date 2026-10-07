#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
COMPILE = TOOLS / 'compile_dcoir_gemini_bundle.py'
VALIDATE = TOOLS / 'validate_dcoir_gemini_bundle.py'
MANIFEST = 'Gemini_Bundle_Source_Manifest.json'


class GeminiBundlePathSafetyIntegrationTests(unittest.TestCase):
    def make_fixture(self, base: Path, **updates: object) -> tuple[Path, Path]:
        repo = base / 'repo'
        source_root = repo / 'project_sources' / 'gemini' / 'bundle_source'
        output_dir = base / 'out'
        source_root.mkdir(parents=True)
        manifest = {
            'bundle_name': 'DCOIR_Gemini',
            'bundle_version': 'test',
            'source_strategy': 'stored_source_compile_with_direct_knowledge_attachment_generation',
            'required_files': [MANIFEST],
            'source_required_files': [],
            'runtime_generated_files': [],
            'source_only_files': [],
            'source_only_dirs': [],
            'knowledge_attachment_sources': [],
            'generated_knowledge_attachment_dir': '02_PRIME_AGENT_ATTACHMENTS',
            'topology': {},
        }
        manifest.update(updates)
        (source_root / MANIFEST).write_text(json.dumps(manifest), encoding='utf-8')
        return source_root, output_dir

    def run_tool(self, script: Path, source_root: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(script),
                '--source-root',
                str(source_root),
                '--output-dir',
                str(output_dir),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_compiler_safe_control_accepts_contained_manifest_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(Path(td))
            proc = self.run_tool(COMPILE, source_root, output_dir)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((output_dir / 'DCOIR_Gemini_test.zip').exists())

    def test_compiler_rejects_source_root_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(
                Path(td),
                required_files=[MANIFEST, '../escaped.txt'],
            )
            proc = self.run_tool(COMPILE, source_root, output_dir)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('Unsafe Gemini bundle manifest paths', proc.stderr)
            self.assertIn('required_files', proc.stderr)
            self.assertFalse((output_dir / 'DCOIR_Gemini_test.zip').exists())

    def test_compiler_rejects_repo_root_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(
                Path(td),
                knowledge_attachment_sources=['../escaped.md'],
            )
            proc = self.run_tool(COMPILE, source_root, output_dir)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('knowledge_attachment_sources', proc.stderr)

    def test_validator_reports_path_safety_failure_before_downstream_access(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(
                Path(td),
                required_files=[MANIFEST, '../escaped.txt'],
            )
            proc = self.run_tool(VALIDATE, source_root, output_dir)
            self.assertEqual(proc.returncode, 1)
            report = json.loads(
                (output_dir / 'validate_dcoir_gemini_bundle_report.json').read_text(
                    encoding='utf-8'
                )
            )
            self.assertFalse(report['checks']['manifest_path_safety'])
            self.assertTrue(
                any('required_files' in error for error in report['errors'])
            )

    def test_validator_rejects_generated_dir_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root, output_dir = self.make_fixture(base)
            outside = base / 'outside'
            outside.mkdir()
            (source_root / 'generated-link').symlink_to(
                outside,
                target_is_directory=True,
            )
            manifest_path = source_root / MANIFEST
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            manifest['generated_knowledge_attachment_dir'] = 'generated-link'
            manifest_path.write_text(json.dumps(manifest), encoding='utf-8')

            proc = self.run_tool(VALIDATE, source_root, output_dir)

            self.assertEqual(proc.returncode, 1)
            report = json.loads(
                (output_dir / 'validate_dcoir_gemini_bundle_report.json').read_text(
                    encoding='utf-8'
                )
            )
            self.assertFalse(report['checks']['manifest_path_safety'])
            self.assertTrue(
                any('escapes its root' in error for error in report['errors'])
            )

    def test_compiler_rejects_non_list_manifest_field_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(
                Path(td),
                required_files=None,
            )

            proc = self.run_tool(COMPILE, source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('required_files must be a list', proc.stderr)
            self.assertNotIn('Traceback', proc.stderr)

    def test_validator_reports_non_list_manifest_field_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(
                Path(td),
                knowledge_attachment_sources=7,
            )

            proc = self.run_tool(VALIDATE, source_root, output_dir)

            self.assertEqual(proc.returncode, 1)
            self.assertNotIn('Traceback', proc.stderr)
            report = json.loads(
                (output_dir / 'validate_dcoir_gemini_bundle_report.json').read_text(
                    encoding='utf-8'
                )
            )
            self.assertFalse(report['checks']['manifest_path_safety'])
            self.assertTrue(
                any(
                    'knowledge_attachment_sources must be a list' in error
                    for error in report['errors']
                )
            )


if __name__ == '__main__':
    unittest.main()
