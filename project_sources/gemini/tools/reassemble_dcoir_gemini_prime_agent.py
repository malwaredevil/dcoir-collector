#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lib.gemini_bundle_path_safety import (
    UnsafePathError,
    resolve_contained_path,
    validate_manifest_paths,
)
from lib.gemini_bundle_validation_common import MANIFEST_NAME, resolve_repo_root

REPORT_NAME = 'reassemble_dcoir_gemini_prime_agent_report.json'


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read_text_or_exit(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        raise SystemExit(f'{label} could not be read: {type(exc).__name__}') from exc


def load_json_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(read_text_or_exit(path, label))
    except json.JSONDecodeError as exc:
        raise SystemExit(f'{label} could not be read: {type(exc).__name__}') from exc
    if not isinstance(value, dict):
        raise SystemExit(f'{label} must contain a JSON object')
    return value


def write_report(output_dir: Path, report: dict) -> None:
    (output_dir / REPORT_NAME).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


def safe_bundle_path(source_root: Path, value: object, label: str) -> Path:
    try:
        return resolve_contained_path(source_root, value, label)
    except UnsafePathError as exc:
        raise SystemExit(str(exc)) from exc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-root', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()

    source_root = Path(args.source_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle_manifest = load_json_object(source_root / MANIFEST_NAME, 'Gemini bundle manifest')
    path_errors = validate_manifest_paths(
        bundle_manifest,
        source_root,
        resolve_repo_root(source_root),
    )
    if path_errors:
        raise SystemExit(
            'Unsafe Gemini bundle manifest paths: ' + '; '.join(path_errors)
        )

    mode = bundle_manifest.get('prime_agent_source_mode')
    report = {
        'success': True,
        'source_root': str(source_root),
        'mode': mode,
        'action': 'none',
    }
    if mode != 'chunked_reassembled':
        write_report(output_dir, report)
        return 0

    chunk_manifest_rel = bundle_manifest.get('prime_agent_chunk_manifest')
    if not chunk_manifest_rel:
        raise SystemExit('prime_agent_chunk_manifest is required when prime_agent_source_mode=chunked_reassembled')

    topology = bundle_manifest.get('topology')
    if not isinstance(topology, dict):
        raise SystemExit('Bundle topology is required when prime_agent_source_mode=chunked_reassembled')
    topology_manifest_rel = topology.get('prime_agent_chunk_manifest')
    if topology_manifest_rel != chunk_manifest_rel:
        raise SystemExit(
            'Prime chunk manifest disagreement between bundle runtime and topology: '
            f'{chunk_manifest_rel!r} != {topology_manifest_rel!r}'
        )

    chunk_manifest_path = safe_bundle_path(
        source_root,
        chunk_manifest_rel,
        'prime_agent_chunk_manifest',
    )
    chunk_manifest = load_json_object(chunk_manifest_path, 'prime_agent_chunk_manifest')
    target_rel = chunk_manifest.get('generated_prime_agent_file')
    # The only file reassembly may write is the declared runtime-generated
    # Prime agent; anything else would overwrite governed bundle source.
    if target_rel != topology.get('prime_agent_file'):
        raise SystemExit(
            'generated_prime_agent_file must match topology.prime_agent_file: '
            f'{target_rel!r} != {topology.get("prime_agent_file")!r}'
        )
    runtime_generated_files = bundle_manifest.get('runtime_generated_files')
    if not isinstance(runtime_generated_files, list) or target_rel not in runtime_generated_files:
        raise SystemExit(
            'generated_prime_agent_file must be listed in runtime_generated_files: '
            f'{target_rel!r}'
        )
    target_path = safe_bundle_path(
        source_root,
        target_rel,
        'generated_prime_agent_file',
    )
    chunks = chunk_manifest.get('chunks', [])
    if not isinstance(chunks, list) or not chunks:
        raise SystemExit('Prime agent chunk manifest has no chunks')

    selected_chunk_sources = [
        entry.get('path') if isinstance(entry, dict) else None
        for entry in chunks
    ]
    if any(not isinstance(path, str) or not path for path in selected_chunk_sources):
        raise SystemExit('Prime agent chunk manifest contains an invalid chunk path')
    topology_chunk_sources = topology.get('prime_agent_chunk_sources')
    if topology_chunk_sources != selected_chunk_sources:
        raise SystemExit(
            'Prime chunk source disagreement between selected manifest and bundle topology'
        )

    parts = []
    missing = []
    for entry in chunks:
        chunk_rel = entry['path']
        path = safe_bundle_path(source_root, chunk_rel, 'prime agent chunk path')
        if not path.exists():
            missing.append(chunk_rel)
            continue
        text = read_text_or_exit(path, f'Prime agent chunk {chunk_rel}')
        expected = entry.get('sha256')
        actual = sha256_text(text)
        if expected and actual != expected:
            raise SystemExit(
                f"Chunk sha256 mismatch for {chunk_rel}: expected {expected}, got {actual}"
            )
        parts.append(text)
    if missing:
        raise SystemExit('Missing prime agent chunks: ' + ', '.join(missing))

    assembled = ''.join(parts)
    assembled_sha = sha256_text(assembled)
    reassembly = chunk_manifest.get('reassembly')
    expected_sha = reassembly.get('expected_sha256') if isinstance(reassembly, dict) else None
    if expected_sha and assembled_sha != expected_sha:
        raise SystemExit(f'Reassembled prime agent sha256 mismatch: expected {expected_sha}, got {assembled_sha}')

    target_exists = target_path.exists()
    current = read_text_or_exit(target_path, 'generated_prime_agent_file') if target_exists else ''
    current_sha = sha256_text(current) if target_exists else None
    if args.check_only and current != assembled:
        raise SystemExit('Canonical prime agent file does not match chunk reassembly')
    if not args.check_only:
        target_path.write_text(assembled, encoding='utf-8')

    report.update({
        'action': 'checked' if args.check_only else 'reassembled',
        'target': target_rel,
        'chunk_manifest': chunk_manifest_rel,
        'chunk_count': len(chunks),
        'assembled_sha256': assembled_sha,
        'previous_target_sha256': current_sha,
        'matches_previous_target': current == assembled,
    })
    write_report(output_dir, report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
