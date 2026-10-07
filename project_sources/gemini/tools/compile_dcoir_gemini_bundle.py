#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter
from pathlib import Path

from lib.gemini_bundle_path_safety import (
    UnsafePathError,
    resolve_contained_path,
    validate_bundle_identity,
    validate_manifest_paths,
)
from lib.gemini_bundle_validation_common import (
    DEFAULT_GENERATED_KNOWLEDGE_DIR,
    derive_bundle_version,
    generated_attachment_name,
    load_manifest,
    resolve_repo_root,
)

EXCLUDE = {'.DS_Store'}


def is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolves_inside(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root)
    except (OSError, RuntimeError):
        return False


def collect_source_files(
    source_root: Path,
    generated_dir: str,
    source_only_files: set[str],
    source_only_dirs: set[str],
) -> list[Path]:
    """Return the bundle_source files to package, refusing links out of the tree.

    source_root must already be resolved. Symbolic links are rejected outright, and
    every candidate must still resolve inside source_root, which also catches
    Windows junctions that Path.is_symlink() does not report.
    """
    generated_root = source_root / generated_dir
    source_only_dir_paths = [source_root / rel for rel in source_only_dirs]
    unsafe: list[str] = []
    files: list[Path] = []
    for path in sorted(source_root.rglob('*')):
        rel = path.relative_to(source_root).as_posix()
        if path.is_symlink() or not _resolves_inside(path, source_root):
            unsafe.append(rel)
            continue
        if not path.is_file():
            continue
        if path.name in EXCLUDE:
            continue
        if rel in source_only_files:
            continue
        if any(is_under(path, root) for root in source_only_dir_paths):
            continue
        if is_under(path, generated_root):
            continue
        files.append(path)
    if unsafe:
        raise UnsafePathError(
            'bundle_source must not contain symbolic links or entries that resolve '
            'outside it: ' + ', '.join(unsafe)
        )
    return files


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-root', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--version', default=None)
    args = ap.parse_args()

    source_root = Path(args.source_root).resolve()
    repo_root = resolve_repo_root(source_root)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(source_root)
    path_errors = validate_manifest_paths(manifest, source_root, repo_root)
    if path_errors:
        raise SystemExit('Unsafe Gemini bundle manifest paths: ' + '; '.join(path_errors))
    bundle_name = manifest.get('bundle_name')
    version = derive_bundle_version(source_root, manifest, args.version)
    identity_errors = validate_bundle_identity(bundle_name, version)
    if identity_errors:
        raise SystemExit('Unsafe Gemini bundle identity: ' + '; '.join(identity_errors))

    top_level = f"{bundle_name}_{version}"
    generated_dir = manifest.get('generated_knowledge_attachment_dir', DEFAULT_GENERATED_KNOWLEDGE_DIR)
    knowledge_sources = list(manifest.get('knowledge_attachment_sources', []))
    source_only_files = set(manifest.get('source_only_files', []))
    source_only_dirs = set(manifest.get('source_only_dirs', []))
    runtime_generated_files = list(manifest.get('runtime_generated_files', []))
    source_required_files = list(manifest.get('source_required_files', []))

    required = manifest.get('required_files', [])
    missing = []
    for rel in required:
        if rel in EXCLUDE:
            continue
        if not (source_root / rel).exists():
            missing.append(rel)
    for rel in knowledge_sources:
        if not (repo_root / rel).exists():
            missing.append(rel)
    for rel in source_required_files:
        if not (source_root / rel).exists():
            missing.append(rel)
    for rel in runtime_generated_files:
        if not (source_root / rel).exists():
            missing.append(rel)
    if missing:
        raise SystemExit('Missing required source files: ' + ', '.join(missing))

    duplicate_generated_sources = sorted((source_root / generated_dir).glob('Knowledge - *.md.txt'))
    if duplicate_generated_sources:
        dupes = ', '.join(p.relative_to(source_root).as_posix() for p in duplicate_generated_sources)
        raise SystemExit('Duplicate generated knowledge attachment sources still exist in bundle_source and must be deleted: ' + dupes)

    try:
        zip_path = resolve_contained_path(
            output_dir,
            f'{top_level}.zip',
            'bundle archive destination',
        )
        source_files = collect_source_files(
            source_root, generated_dir, source_only_files, source_only_dirs
        )
    except UnsafePathError as exc:
        raise SystemExit(f'Unsafe Gemini bundle output path or source tree: {exc}') from exc

    # Plan every archive member before the zip is opened, so a bad input never
    # leaves a partial archive behind.
    generated_knowledge_files: list[str] = []
    try:
        for rel in knowledge_sources:
            generated_knowledge_files.append(
                (Path(generated_dir) / generated_attachment_name(rel)).as_posix()
            )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    duplicate_names = sorted(
        name for name, total in Counter(generated_knowledge_files).items() if total > 1
    )
    if duplicate_names:
        raise SystemExit(
            'Knowledge attachment sources map to the same archive member: '
            + ', '.join(duplicate_names)
        )

    count = 0
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in source_files:
            arc = Path(top_level) / path.relative_to(source_root)
            zf.write(path, arc.as_posix())
            count += 1

        for rel, generated_rel in zip(knowledge_sources, generated_knowledge_files):
            text = (repo_root / rel).read_text(encoding='utf-8')
            if not text.endswith('\n'):
                text += '\n'
            zf.writestr(f'{top_level}/{generated_rel}', text)
            count += 1

    report = {
        'success': True,
        'source_root': str(source_root),
        'repo_root': str(repo_root),
        'zip_path': str(zip_path),
        'bundle_name': bundle_name,
        'bundle_version': version,
        'top_level_folder': top_level,
        'file_count': count,
        'source_strategy': manifest.get('source_strategy'),
        'prime_agent_source_mode': manifest.get('prime_agent_source_mode'),
        'prime_agent_runtime_mode': manifest.get('prime_agent_runtime_mode'),
        'runtime_generated_files': runtime_generated_files,
        'source_required_files': source_required_files,
        'source_only_files': sorted(source_only_files),
        'source_only_dirs': sorted(source_only_dirs),
        'knowledge_attachment_sources': knowledge_sources,
        'generated_knowledge_attachment_files': generated_knowledge_files,
    }
    report_path = output_dir / 'compile_dcoir_gemini_bundle_report.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
