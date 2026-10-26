#!/usr/bin/env python3
"""Hostile and safe-control tests for shared OpenAI generated-package IO."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import openai_package_output_kernel as kernel
import build_openai_dcoir_analyst as dcoir
import build_openai_usb_reporting as usb


def fixture():
    temp = tempfile.TemporaryDirectory(prefix='openai-package-io-test-')
    repo = Path(temp.name)
    root = repo / 'generated' / 'package'
    files = {
        root / 'Instructions.md': b'approved instructions',
        root / 'GPT_Configuration.json': b'{"ok":true}',
        root / 'manifest.json': b'{"id":"source"}',
    }
    return temp, repo, root, files


def reconcile(repo, root, files, check):
    errors = []
    kernel.reconcile_generated_package(
        repo, root, files, errors, check=check,
        staging_prefix='.openai-synth-',
    )
    return errors


def main():
    assert dcoir.reconcile_generated_package is kernel.reconcile_generated_package
    assert usb.reconcile_generated_package is kernel.reconcile_generated_package
    temp, repo, root, files = fixture()
    try:
        errors = reconcile(repo, root, files, True)
        assert len(errors) == 3 and all('Missing generated' in e for e in errors), errors
        assert reconcile(repo, root, files, False) == []
        assert reconcile(repo, root, files, True) == []
        assert {p: p.read_bytes() for p in files} == files
        assert reconcile(repo, root, files, False) == []
        original_read = Path.read_bytes
        first = next(iter(files))
        def unreadable(path):
            if path == first:
                raise PermissionError('denied')
            return original_read(path)
        with mock.patch.object(Path, 'read_bytes', unreadable):
            errors = reconcile(repo, root, files, True)
        assert any('Unreadable generated package file:' in e and 'PermissionError' in e for e in errors), errors

        original_iter = Path.iterdir
        def unreadable_inventory(path):
            if path == root:
                raise OSError('denied')
            return original_iter(path)
        with mock.patch.object(Path, 'iterdir', unreadable_inventory):
            errors = reconcile(repo, root, files, True)
        assert any('inventory could not be read' in e for e in errors), errors

        stale = root / 'extra.md'
        stale.write_bytes(b'stale')
        errors = reconcile(repo, root, files, False)
        assert any('Stale generated package files' in e for e in errors), errors
        stale.unlink()
    finally:
        temp.cleanup()

    temp, repo, root, files = fixture()
    try:
        original_read = Path.read_bytes
        def corrupt_stage(path):
            if path.parent.name.startswith('.openai-synth-'):
                return b'corrupted'
            return original_read(path)
        with mock.patch.object(Path, 'read_bytes', corrupt_stage):
            errors = reconcile(repo, root, files, False)
        assert 'Generated package staging readback failed' in errors, errors
        assert not root.exists(), 'corrupt stage must not write any output'

        with mock.patch.object(kernel.shutil, 'copyfile', side_effect=PermissionError('denied')):
            errors = reconcile(repo, root, files, False)
        assert len(errors) == 1 and 'write/readback failed' in errors[0] and 'PermissionError' in errors[0], errors
        assert not any(p.exists() for p in files)
        with mock.patch.object(kernel.tempfile, 'TemporaryDirectory', side_effect=PermissionError('denied')):
            errors = reconcile(repo, root, files, False)
        assert any('staging root failed' in e for e in errors), errors

        target = next(iter(files))
        def corrupt_written(path):
            if path == target:
                return b'wrong postwrite'
            return original_read(path)
        with mock.patch.object(Path, 'read_bytes', corrupt_written):
            errors = reconcile(repo, root, files, False)
        assert len(errors) == 1 and 'write readback failed' in errors[0], errors
        assert not all(p.exists() for p in files), 'must stop after first failed output readback'
    finally:
        temp.cleanup()

    temp, repo, root, files = fixture()
    outside = tempfile.TemporaryDirectory(prefix='openai-io-external-')
    try:
        assert reconcile(repo, root, files, False) == []
        external = Path(outside.name) / 'secret.txt'
        external.write_text('external data')
        link = next(iter(files))
        link.unlink()
        try:
            link.symlink_to(external)
        except (OSError, NotImplementedError):
            print('symlink test skipped: unavailable')
        else:
            original_read = Path.read_bytes
            def prevent_external_read(path):
                if path == link:
                    raise AssertionError('symlink file must not be read')
                return original_read(path)
            with mock.patch.object(Path, 'read_bytes', prevent_external_read):
                errors = reconcile(repo, root, files, True)
            assert any('must not contain symlinks' in e for e in errors), errors
            assert external.read_text() == 'external data'
    finally:
        temp.cleanup()
        outside.cleanup()
    # A prior manifest error must prohibit all generated-root disk traversal.
    temp, repo, root, files = fixture()
    try:
        initial = ['governed source is invalid']
        with mock.patch.object(Path, 'iterdir', side_effect=AssertionError('unexpected inventory')):
            kernel.reconcile_generated_package(
                repo, root, files, initial, check=True, staging_prefix='.openai-synth-',
            )
        assert initial == ['governed source is invalid'], initial
    finally:
        temp.cleanup()

    # An expected directory must be an error, not an uncaught IsADirectoryError.
    temp, repo, root, files = fixture()
    try:
        assert reconcile(repo, root, files, False) == []
        target = next(iter(files))
        target.unlink()
        target.mkdir()
        errors = reconcile(repo, root, files, True)
        assert any('Unreadable generated package file' in e and 'IsADirectoryError' in e
                   for e in errors), errors
    finally:
        temp.cleanup()

    # Reject expected destinations outside the repository before touching them.
    temp, repo, root, files = fixture()
    outside = tempfile.TemporaryDirectory(prefix='openai-io-outside-')
    try:
        destination = Path(outside.name) / 'external.txt'
        errors = reconcile(repo, root, {destination: b'external'}, False)
        assert any('must remain inside repository' in e for e in errors), errors
        assert not destination.exists()
    finally:
        temp.cleanup()
        outside.cleanup()

    # A symlinked ancestor directory is as unsafe as a symlinked file.
    temp, repo, root, files = fixture()
    outside = tempfile.TemporaryDirectory(prefix='openai-io-ancestor-')
    try:
        root.mkdir(parents=True)
        hidden = Path(outside.name) / 'external'
        hidden.mkdir()
        (hidden / 'Instructions.md').write_bytes(b'private content')
        linkdir = root / 'nested'
        try:
            linkdir.symlink_to(hidden, target_is_directory=True)
        except (OSError, NotImplementedError):
            print('ancestor symlink test skipped: unavailable')
        else:
            guarded_path = linkdir / 'Instructions.md'
            original_read = Path.read_bytes
            def guard_parent(path):
                if path == guarded_path:
                    raise AssertionError('symlink ancestor must not be traversed')
                return original_read(path)
            with mock.patch.object(Path, 'read_bytes', guard_parent):
                errors = reconcile(repo, root, {guarded_path: b'expected'}, True)
            assert any('must not contain symlinks' in e for e in errors), errors
            assert (hidden / 'Instructions.md').read_bytes() == b'private content'
    finally:
        temp.cleanup()
        outside.cleanup()

    print('PASS: shared package IO source owners, staging, errors and symlink fail-closed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
