#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path
from typing import Iterable

from lib.gemini_bundle_path_safety import validate_manifest_paths

MANIFEST_NAME = 'Gemini_Bundle_Source_Manifest.json'
EXCLUDE = {'.DS_Store'}
DEFAULT_GENERATED_KNOWLEDGE_DIR = '02_PRIME_AGENT_ATTACHMENTS'


def load_manifest(source_root: Path) -> dict:
    return json.loads((source_root / MANIFEST_NAME).read_text(encoding='utf-8'))


def derive_bundle_version(source_root: Path, manifest: dict) -> str:
    index_rel = manifest.get('topology', {}).get('generated_index_file')
    if index_rel:
        index_path = source_root / index_rel
        if index_path.exists():
            text = index_path.read_text(encoding='utf-8', errors='ignore')
            match = re.search(r'(?m)^Bundle version:\s*([0-9_]+)\s*$', text)
            if match:
                return match.group(1)
    return manifest['bundle_version']


def resolve_repo_root(source_root: Path) -> Path:
    # source_root is <repo>/project_sources/gemini/bundle_source.
    return source_root.parent.parent.parent


def generated_attachment_name(source_rel: str) -> str:
    name = Path(source_rel).name
    if not name.endswith('.md'):
        raise ValueError(f'Knowledge attachment source must be a markdown file: {source_rel}')
    return name + '.txt'


def is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def iter_source_files(source_root: Path, generated_dir: str, source_only_files: set[str], source_only_dirs: set[str]) -> Iterable[Path]:
    generated_root = source_root / generated_dir
    source_only_dir_paths = [source_root / rel for rel in source_only_dirs]
    for path in sorted(source_root.rglob('*')):
        if not path.is_file():
            continue
        if path.name in EXCLUDE:
            continue
        rel = path.relative_to(source_root).as_posix()
        if rel in source_only_files:
            continue
        if any(is_under(path, root) for root in source_only_dir_paths):
            continue
        if is_under(path, generated_root):
            continue
        yield path


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
    version = args.version or derive_bundle_version(source_root, manifest)
    bundle_name = manifest['bundle_name']
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

    zip_path = output_dir / f"{bundle_name}_{version}.zip"
    count = 0
    generated_knowledge_files = []
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in iter_source_files(source_root, generated_dir, source_only_files, source_only_dirs):
            rel = path.relative_to(source_root)
            arc = Path(top_level) / rel
            zf.write(path, arc.as_posix())
            count += 1

        for rel in knowledge_sources:
            source_path = repo_root / rel
            text = source_path.read_text(encoding='utf-8')
            if not text.endswith('\n'):
                text += '\n'
            generated_rel = Path(generated_dir) / generated_attachment_name(rel)
            arc = Path(top_level) / generated_rel
            zf.writestr(arc.as_posix(), text)
            generated_knowledge_files.append(generated_rel.as_posix())
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
