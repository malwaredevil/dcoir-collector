#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

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

    def run_tool(
        self,
        script: Path,
        source_root: Path,
        output_dir: Path,
        *extra_args: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(script),
                '--source-root',
                str(source_root),
                '--output-dir',
                str(output_dir),
                *extra_args,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def read_validator_report(self, output_dir: Path) -> dict:
        return json.loads(
            (output_dir / 'validate_dcoir_gemini_bundle_report.json').read_text(
                encoding='utf-8'
            )
        )

    def test_compiler_safe_control_accepts_contained_manifest_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(Path(td))
            proc = self.run_tool(COMPILE, source_root, output_dir)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((output_dir / 'DCOIR_Gemini_test.zip').exists())

    def test_compiler_safe_control_archive_stays_contained(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(Path(td))
            proc = self.run_tool(COMPILE, source_root, output_dir)
            self.assertEqual(proc.returncode, 0, proc.stderr)

            zip_path = output_dir / 'DCOIR_Gemini_test.zip'
            self.assertTrue(
                zip_path.resolve().is_relative_to(output_dir.resolve())
            )
            with zipfile.ZipFile(zip_path) as zf:
                members = zf.namelist()
            self.assertTrue(members)
            self.assertTrue(
                all(
                    '..' not in PurePosixPath(member).parts
                    and '..' not in PureWindowsPath(member).parts
                    for member in members
                ),
                members,
            )
            self.assertTrue(
                all(
                    member.startswith('DCOIR_Gemini_test/')
                    for member in members
                ),
                members,
            )

    def test_compiler_rejects_unsafe_bundle_name(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root, output_dir = self.make_fixture(
                base,
                bundle_name='../escaped',
            )
            proc = self.run_tool(COMPILE, source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('bundle_name', proc.stderr)
            self.assertEqual(list(base.rglob('*.zip')), [])

    def test_compiler_rejects_unsafe_manifest_bundle_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root, output_dir = self.make_fixture(
                base,
                bundle_version='../../../escaped',
            )
            proc = self.run_tool(COMPILE, source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('bundle_version', proc.stderr)
            self.assertEqual(list(base.rglob('*.zip')), [])

    def test_compiler_rejects_unsafe_cli_bundle_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root, output_dir = self.make_fixture(base)
            proc = self.run_tool(
                COMPILE,
                source_root,
                output_dir,
                '--version',
                '..\\..\\escaped',
            )

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('Unsafe Gemini bundle identity', proc.stderr)
            self.assertIn('bundle_version', proc.stderr)
            self.assertEqual(list(base.rglob('*.zip')), [])

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

    def test_compiler_rejects_backslash_traversal_before_archive_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root, output_dir = self.make_fixture(
                base,
                generated_knowledge_attachment_dir='..\\..\\escaped',
            )
            proc = self.run_tool(COMPILE, source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('generated_knowledge_attachment_dir', proc.stderr)
            self.assertEqual(list(base.rglob('*.zip')), [])

    def test_compiler_rejects_repo_root_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(
                Path(td),
                knowledge_attachment_sources=['../escaped.md'],
            )
            proc = self.run_tool(COMPILE, source_root, output_dir)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('knowledge_attachment_sources', proc.stderr)

    def test_validator_rejects_unsafe_bundle_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(
                Path(td),
                bundle_name='..\\escaped',
            )
            proc = self.run_tool(VALIDATE, source_root, output_dir)

            self.assertEqual(proc.returncode, 1)
            report = self.read_validator_report(output_dir)
            self.assertTrue(report['checks']['manifest_path_safety'])
            self.assertFalse(report['checks']['bundle_identity_safety'])
            self.assertTrue(
                any('bundle_name' in error for error in report['errors'])
            )

    def test_version_override_replaces_unsafe_manifest_version(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(
                Path(td),
                bundle_version='3.0.5-rc/1',
            )
            for script in (VALIDATE, COMPILE):
                with self.subTest(script=script.name):
                    rejected = self.run_tool(script, source_root, output_dir)
                    self.assertNotEqual(rejected.returncode, 0)
                    self.assertNotIn('Traceback', rejected.stderr)

                    accepted = self.run_tool(
                        script, source_root, output_dir, '--version', '3_0_6'
                    )
                    self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertTrue((output_dir / 'DCOIR_Gemini_3_0_6.zip').is_file())
            report = self.read_validator_report(output_dir)
            self.assertEqual(report['checks']['effective_bundle_version'], '3_0_6')

    def test_validator_reports_unreadable_manifest_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(Path(td))
            (source_root / MANIFEST).write_text('{not json', encoding='utf-8')

            proc = self.run_tool(VALIDATE, source_root, output_dir)

            self.assertEqual(proc.returncode, 1)
            self.assertNotIn('Traceback', proc.stderr)
            report = self.read_validator_report(output_dir)
            self.assertFalse(report['checks']['manifest_readable'])
            self.assertIsNone(report['bundle_name'])

    def make_link_or_skip(self, link: Path, target: Path) -> None:
        try:
            link.symlink_to(target, target_is_directory=target.is_dir())
        except (NotImplementedError, OSError):
            self.skipTest('symlinks are not supported')

    def test_compiler_rejects_symlinked_file_escaping_bundle_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root, output_dir = self.make_fixture(base)
            secret = base / 'outside-secret.txt'
            secret.write_text('do not package', encoding='utf-8')
            self.make_link_or_skip(source_root / 'leak.md.txt', secret)

            proc = self.run_tool(COMPILE, source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('leak.md.txt', proc.stderr)
            self.assertNotIn('Traceback', proc.stderr)
            self.assertEqual(list(base.rglob('*.zip')), [])

    def test_compiler_rejects_symlinked_directory_in_bundle_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source_root, output_dir = self.make_fixture(base)
            outside = base / 'outside-dir'
            outside.mkdir()
            (outside / 'secret.md.txt').write_text('do not package', encoding='utf-8')
            self.make_link_or_skip(source_root / 'linked-dir', outside)

            proc = self.run_tool(COMPILE, source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('linked-dir', proc.stderr)
            self.assertEqual(list(base.rglob('*.zip')), [])

    def test_compiler_rejects_bad_knowledge_attachment_before_writing_zip(self) -> None:
        cases = [
            (['docs/notes.txt'], 'must be a markdown file'),
            (['a/Same.md', 'b/Same.md'], 'map to the same archive member'),
        ]
        for sources, marker in cases:
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as td:
                base = Path(td)
                source_root, output_dir = self.make_fixture(
                    base, knowledge_attachment_sources=sources
                )
                repo = source_root.parents[2]
                for rel in sources:
                    (repo / rel).parent.mkdir(parents=True, exist_ok=True)
                    (repo / rel).write_text('knowledge\n', encoding='utf-8')

                proc = self.run_tool(COMPILE, source_root, output_dir)

                self.assertNotEqual(proc.returncode, 0)
                self.assertIn(marker, proc.stderr)
                self.assertNotIn('Traceback', proc.stderr)
                self.assertEqual(list(base.rglob('*.zip')), [])

    def test_validator_reports_path_safety_failure_before_downstream_access(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(
                Path(td),
                required_files=[MANIFEST, '../escaped.txt'],
            )
            proc = self.run_tool(VALIDATE, source_root, output_dir)
            self.assertEqual(proc.returncode, 1)
            report = self.read_validator_report(output_dir)
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
            try:
                (source_root / 'generated-link').symlink_to(
                    outside,
                    target_is_directory=True,
                )
            except (NotImplementedError, OSError):
                self.skipTest('symlinks are not supported')
            manifest_path = source_root / MANIFEST
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            manifest['generated_knowledge_attachment_dir'] = 'generated-link'
            manifest_path.write_text(json.dumps(manifest), encoding='utf-8')

            proc = self.run_tool(VALIDATE, source_root, output_dir)

            self.assertEqual(proc.returncode, 1)
            report = self.read_validator_report(output_dir)
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
            report = self.read_validator_report(output_dir)
            self.assertFalse(report['checks']['manifest_path_safety'])
            self.assertTrue(
                any(
                    'knowledge_attachment_sources must be a list' in error
                    for error in report['errors']
                )
            )

    def test_compiler_rejects_generated_dir_naming_source_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(
                Path(td),
                generated_knowledge_attachment_dir='.',
            )

            proc = self.run_tool(COMPILE, source_root, output_dir)

            self.assertNotEqual(proc.returncode, 0)
            self.assertIn('not the root itself', proc.stderr)
            self.assertNotIn('Traceback', proc.stderr)
            self.assertFalse(list(output_dir.glob('*.zip')))

    def test_validator_reports_non_object_manifest_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source_root, output_dir = self.make_fixture(Path(td))
            (source_root / MANIFEST).write_text('[]', encoding='utf-8')

            proc = self.run_tool(VALIDATE, source_root, output_dir)

            self.assertEqual(proc.returncode, 1)
            self.assertNotIn('Traceback', proc.stderr)
            report = self.read_validator_report(output_dir)
            self.assertFalse(report['checks']['manifest_path_safety'])
            self.assertIsNone(report['bundle_name'])
            self.assertIn(
                'Gemini bundle manifest must be an object', report['errors']
            )


if __name__ == '__main__':
    unittest.main()
