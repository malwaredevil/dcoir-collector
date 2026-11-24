#!/usr/bin/env python3
"""Write (or --check-only) the runtime-generated Prime agent from its chunks.

The chunk binding and integrity rules live in lib.gemini_prime_agent_chunks,
which the bundle validator shares.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.gemini_bundle_path_safety import validate_manifest_paths
from lib.gemini_bundle_validation_common import MANIFEST_NAME, resolve_repo_root
from lib.gemini_prime_agent_chunks import (
    PrimeChunkPlanError,
    assemble,
    load_chunk_plan,
    sha256_text,
)

REPORT_NAME = 'reassemble_dcoir_gemini_prime_agent_report.json'


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

    try:
        plan = load_chunk_plan(bundle_manifest, source_root)
        assembled = assemble(plan)
    except PrimeChunkPlanError as exc:
        raise SystemExit(str(exc)) from exc
    assembled_sha = sha256_text(assembled)

    target_path = plan.target_path
    target_exists = target_path.exists()
    current = read_text_or_exit(target_path, 'generated_prime_agent_file') if target_exists else ''
    current_sha = sha256_text(current) if target_exists else None
    if args.check_only and current != assembled:
        raise SystemExit('Canonical prime agent file does not match chunk reassembly')
    if not args.check_only:
        target_path.write_text(assembled, encoding='utf-8')

    report.update({
        'action': 'checked' if args.check_only else 'reassembled',
        'target': plan.target_rel,
        'chunk_manifest': plan.chunk_manifest_rel,
        'chunk_count': len(plan.chunks),
        'assembled_sha256': assembled_sha,
        'previous_target_sha256': current_sha,
        'matches_previous_target': current == assembled,
    })
    write_report(output_dir, report)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
