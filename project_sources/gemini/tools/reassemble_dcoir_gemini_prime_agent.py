#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

MANIFEST_NAME = 'Gemini_Bundle_Source_Manifest.json'


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-root', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()

    source_root = Path(args.source_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle_manifest = load_json(source_root / MANIFEST_NAME)
    mode = bundle_manifest.get('prime_agent_source_mode')
    report = {
        'success': True,
        'source_root': str(source_root),
        'mode': mode,
        'action': 'none',
    }
    if mode != 'chunked_reassembled':
        report_path = output_dir / 'reassemble_dcoir_gemini_prime_agent_report.json'
        report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report, indent=2))
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

    chunk_manifest = load_json(source_root / chunk_manifest_rel)
    target_rel = chunk_manifest['generated_prime_agent_file']
    target_path = source_root / target_rel
    chunks = chunk_manifest.get('chunks', [])
    if not chunks:
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
        path = source_root / entry['path']
        if not path.exists():
            missing.append(entry['path'])
            continue
        text = path.read_text(encoding='utf-8')
        expected = entry.get('sha256')
        actual = sha256_text(text)
        if expected and actual != expected:
            raise SystemExit(f"Chunk sha256 mismatch for {entry['path']}: expected {expected}, got {actual}")
        parts.append(text)
    if missing:
        raise SystemExit('Missing prime agent chunks: ' + ', '.join(missing))

    assembled = ''.join(parts)
    assembled_sha = sha256_text(assembled)
    expected_sha = chunk_manifest.get('reassembly', {}).get('expected_sha256')
    if expected_sha and assembled_sha != expected_sha:
        raise SystemExit(f'Reassembled prime agent sha256 mismatch: expected {expected_sha}, got {assembled_sha}')

    current = target_path.read_text(encoding='utf-8') if target_path.exists() else ''
    current_sha = sha256_text(current) if target_path.exists() else None
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
    report_path = output_dir / 'reassemble_dcoir_gemini_prime_agent_report.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
