#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import string
import sys
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = 'dcoir.agent_runtime.behavior_modules.v1'
TARGET_ID = 'gemini_dcoir_agent'
MODULE_KINDS = {'prime_chunk', 'specialist'}
SHA256_CHARACTERS = frozenset(string.hexdigits.lower())


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise ValueError(f'Missing JSON file: {path}') from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f'Invalid JSON in {path}: {exc}') from exc
    if not isinstance(value, dict):
        raise ValueError(f'Expected a JSON object in {path}')
    return value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and set(value) <= SHA256_CHARACTERS
        and value == value.lower()
    )


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def _resolve_repo_path(
    repo_root: Path,
    relative_value: object,
    label: str,
    errors: list[str],
    required_root: Path | None = None,
) -> Path | None:
    if not isinstance(relative_value, str) or not relative_value:
        errors.append(f'{label} must be a non-empty repository-relative path')
        return None
    relative = Path(relative_value)
    if relative.is_absolute() or '..' in relative.parts:
        errors.append(f'{label} must not be absolute or contain traversal: {relative_value}')
        return None
    resolved_repo = repo_root.resolve()
    candidate = (resolved_repo / relative).resolve()
    if not candidate.is_relative_to(resolved_repo):
        errors.append(f'{label} escapes the repository: {relative_value}')
        return None
    if required_root is not None and not candidate.is_relative_to(required_root.resolve()):
        errors.append(f'{label} is outside its declared root: {relative_value}')
        return None
    return candidate


def _topology_outputs(
    repo_root: Path,
    adapter: dict[str, Any],
    output_root: Path,
    errors: list[str],
) -> tuple[list[str], list[str]]:
    bundle_path = _resolve_repo_path(
        repo_root,
        adapter.get('bundle_manifest'),
        'target adapter bundle_manifest',
        errors,
        output_root,
    )
    chunk_path = _resolve_repo_path(
        repo_root,
        adapter.get('prime_chunk_manifest'),
        'target adapter prime_chunk_manifest',
        errors,
        output_root,
    )
    if bundle_path is None or chunk_path is None:
        return [], []
    try:
        bundle = _load_json(bundle_path)
        chunk_manifest = _load_json(chunk_path)
    except ValueError as exc:
        errors.append(str(exc))
        return [], []

    chunk_manifest_rel = bundle.get('topology', {}).get('prime_agent_chunk_manifest')
    expected_chunk_manifest = chunk_path.relative_to(output_root).as_posix()
    if chunk_manifest_rel != expected_chunk_manifest:
        errors.append(
            'Gemini bundle topology points to a different Prime chunk manifest: '
            f'{chunk_manifest_rel!r} != {expected_chunk_manifest!r}'
        )

    chunks = chunk_manifest.get('chunks')
    if not isinstance(chunks, list):
        errors.append('Prime chunk manifest lacks a chunks array')
        chunks = []
    prime_outputs: list[str] = []
    for entry in chunks:
        path = entry.get('path') if isinstance(entry, dict) else None
        if not isinstance(path, str) or not path:
            errors.append('Prime chunk manifest contains an invalid chunk path')
            continue
        prime_outputs.append((output_root / path).relative_to(repo_root).as_posix())

    specialists = bundle.get('topology', {}).get('sub_agent_files')
    if not isinstance(specialists, list) or not all(
        isinstance(path, str) and path for path in specialists
    ):
        errors.append('Gemini bundle manifest lacks valid topology.sub_agent_files')
        specialists = []
    specialist_outputs = [
        (output_root / path).relative_to(repo_root).as_posix()
        for path in specialists
    ]
    return prime_outputs, specialist_outputs


def _validate_source_contract(
    repo_root: Path,
    manifest: dict[str, Any],
    modules: list[dict[str, Any]],
    errors: list[str],
) -> None:
    contract_path = _resolve_repo_path(
        repo_root, manifest.get('source_contract'), 'source_contract', errors
    )
    if contract_path is None:
        return
    try:
        contract = _load_json(contract_path)
    except ValueError as exc:
        errors.append(str(exc))
        return
    declared_module_manifest = contract.get('behavior_module_manifest')
    manifest_rel = Path(manifest.get('_manifest_path', '')).as_posix()
    if declared_module_manifest != manifest_rel:
        errors.append(
            'Shared source contract does not point back to this behavior module manifest: '
            f'{declared_module_manifest!r} != {manifest_rel!r}'
        )
    behavior_by_id = {
        item.get('id'): item
        for item in contract.get('behavior_items', [])
        if isinstance(item, dict) and isinstance(item.get('id'), str)
    }
    module_ids = {
        module.get('id')
        for module in modules
        if isinstance(module.get('id'), str)
    }
    expected_ids = {
        item_id
        for item_id in behavior_by_id
        if item_id.startswith('prime.chunk.') or item_id.startswith('sub_agent.')
    }
    if module_ids != expected_ids:
        errors.append(
            'Behavior module ids disagree with module-backed source-contract ids; '
            f'missing={sorted(expected_ids - module_ids)}, '
            f'extra={sorted(module_ids - expected_ids)}'
        )
    for module in modules:
        module_id = module.get('id')
        behavior = behavior_by_id.get(module_id)
        if behavior is None:
            continue
        if behavior.get('source_path') != module.get('source_path'):
            errors.append(f'{module_id} source path disagrees with the shared source contract')
        if behavior.get('canonical') is not True:
            errors.append(f'{module_id} must remain canonical in the shared source contract')


def validate_manifest(
    repo_root: Path,
    manifest_path: Path,
    target_id: str,
) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    errors: list[str] = []
    try:
        manifest = _load_json(manifest_path)
    except ValueError as exc:
        return [str(exc)], [], {}
    try:
        manifest_rel = manifest_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return ['Behavior module manifest must be inside the repository'], [], manifest
    manifest['_manifest_path'] = manifest_rel

    if manifest.get('schema') != SCHEMA:
        errors.append(f'Unsupported behavior module schema: {manifest.get("schema")!r}')
    if not manifest.get('module_contract_version'):
        errors.append('Missing module_contract_version')
    policy = manifest.get('generated_target_policy')
    if not isinstance(policy, dict):
        errors.append('Missing generated_target_policy')
    else:
        if policy.get('generated_outputs_are_canonical') is not False:
            errors.append('Generated adapter outputs must not be canonical')
        if policy.get('direct_target_edits_require_reverse_reconciliation') is not True:
            errors.append('Direct target edits must require reverse reconciliation')

    canonical_root = _resolve_repo_path(
        repo_root,
        manifest.get('canonical_behavior_root'),
        'canonical_behavior_root',
        errors,
    )
    adapters = manifest.get('target_adapters')
    if not isinstance(adapters, dict) or target_id not in adapters:
        errors.append(f'Missing target adapter: {target_id}')
        return errors, [], manifest
    adapter = adapters[target_id]
    if not isinstance(adapter, dict):
        errors.append(f'Target adapter must be an object: {target_id}')
        return errors, [], manifest
    output_root = _resolve_repo_path(
        repo_root, adapter.get('output_root'), f'{target_id} output_root', errors
    )
    if canonical_root is None or output_root is None:
        return errors, [], manifest
    if not canonical_root.is_dir():
        errors.append(f'Canonical behavior root does not exist: {canonical_root}')
    if not output_root.is_dir():
        errors.append(f'Target output root does not exist: {output_root}')
    if adapter.get('projection_mode') != 'byte_identity':
        errors.append(f'{target_id} must use byte_identity projection during migration')
    for field in ('expected_prime_chunks', 'expected_specialists'):
        value = adapter.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f'{target_id} has invalid {field}: {value!r}')

    raw_modules = manifest.get('modules')
    if not isinstance(raw_modules, list) or not raw_modules:
        errors.append('modules must be a non-empty array')
        return errors, [], manifest
    modules = [module for module in raw_modules if isinstance(module, dict)]
    if len(modules) != len(raw_modules):
        errors.append('modules contains a non-object entry')

    ids = [str(module.get('id', '')) for module in modules]
    sources = [str(module.get('source_path', '')) for module in modules]
    outputs: list[str] = []
    normalized: list[dict[str, Any]] = []
    for duplicate in _duplicates(ids):
        errors.append(f'Duplicate behavior module id: {duplicate}')
    for duplicate in _duplicates(sources):
        errors.append(f'Duplicate behavior module source: {duplicate}')

    for module in modules:
        module_id = module.get('id')
        if not isinstance(module_id, str) or not module_id:
            errors.append('Behavior module lacks a valid id')
            continue
        kind = module.get('kind')
        kind_valid = kind in MODULE_KINDS
        if not kind_valid:
            errors.append(f'{module_id} has unsupported kind: {kind!r}')
        order = module.get('order')
        order_valid = (
            isinstance(order, int) and not isinstance(order, bool) and order >= 0
        )
        if not order_valid:
            errors.append(f'{module_id} has invalid order: {order!r}')
        source_path = _resolve_repo_path(
            repo_root,
            module.get('source_path'),
            f'{module_id} source_path',
            errors,
            canonical_root,
        )
        declared_sha = module.get('sha256')
        if not _is_sha256(declared_sha):
            errors.append(f'{module_id} has invalid sha256')
            declared_sha = ''
        source_bytes = b''
        if source_path is not None:
            if not source_path.is_file():
                errors.append(f'Missing behavior module source: {module.get("source_path")}')
            else:
                source_bytes = source_path.read_bytes()
                actual_sha = _sha256(source_bytes)
                if declared_sha and actual_sha != declared_sha:
                    errors.append(
                        f'{module_id} source sha256 mismatch: expected {declared_sha}, '
                        f'got {actual_sha}'
                    )

        projections = module.get('projections')
        projection = projections.get(target_id) if isinstance(projections, dict) else None
        if not isinstance(projection, dict):
            errors.append(f'{module_id} lacks a {target_id} projection')
            continue
        if projection.get('projection_mode') != 'byte_identity':
            errors.append(f'{module_id} projection must use byte_identity mode')
        output_path = _resolve_repo_path(
            repo_root,
            projection.get('output_path'),
            f'{module_id} output_path',
            errors,
            output_root,
        )
        output_rel = projection.get('output_path')
        if isinstance(output_rel, str):
            outputs.append(output_rel)
        projected_sha = projection.get('sha256')
        if projected_sha != declared_sha:
            errors.append(f'{module_id} source and projection sha256 declarations differ')
        if (
            source_path is not None
            and output_path is not None
            and kind_valid
            and order_valid
        ):
            normalized.append(
                {
                    'id': module_id,
                    'kind': kind,
                    'order': order,
                    'source_path': source_path,
                    'source_rel': module.get('source_path'),
                    'output_path': output_path,
                    'output_root': output_root,
                    'output_rel': output_rel,
                    'sha256': declared_sha,
                    'source_bytes': source_bytes,
                }
            )
    for duplicate in _duplicates(outputs):
        errors.append(f'Duplicate target adapter output: {duplicate}')
    ordered_slots = [
        f"{entry['kind']}:{entry['order']}" for entry in normalized
    ]
    for duplicate in _duplicates(ordered_slots):
        errors.append(f'Duplicate behavior module order slot: {duplicate}')

    prime_outputs, specialist_outputs = _topology_outputs(
        repo_root, adapter, output_root, errors
    )
    declared_prime = [
        entry['output_rel']
        for entry in sorted(
            (entry for entry in normalized if entry['kind'] == 'prime_chunk'),
            key=lambda entry: entry['order'],
        )
    ]
    declared_specialists = [
        entry['output_rel']
        for entry in sorted(
            (entry for entry in normalized if entry['kind'] == 'specialist'),
            key=lambda entry: entry['order'],
        )
    ]
    if declared_prime != prime_outputs:
        errors.append('Prime behavior module order or output topology disagrees with Gemini')
    if declared_specialists != specialist_outputs:
        errors.append('Specialist behavior module order or output topology disagrees with Gemini')
    if len(declared_prime) != adapter.get('expected_prime_chunks'):
        errors.append('Prime behavior module count disagrees with target adapter contract')
    if len(declared_specialists) != adapter.get('expected_specialists'):
        errors.append('Specialist behavior module count disagrees with target adapter contract')

    _validate_source_contract(repo_root, manifest, modules, errors)
    return errors, normalized, manifest


def execute(
    repo_root: Path,
    manifest_path: Path,
    target_id: str,
    action: str,
) -> tuple[int, dict[str, Any]]:
    errors, entries, manifest = validate_manifest(repo_root, manifest_path, target_id)
    if not errors and action == 'materialize':
        for entry in entries:
            write_errors: list[str] = []
            output_path = _resolve_repo_path(
                repo_root,
                entry['output_rel'],
                f'{entry["id"]} materialize output',
                write_errors,
                entry['output_root'],
            )
            if output_path is None or write_errors:
                errors.extend(write_errors)
                continue
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry['source_path'], output_path)

    results = []
    if not errors:
        for entry in entries:
            output_path = entry['output_path']
            if not output_path.is_file():
                errors.append(f'Missing generated adapter output: {entry["output_rel"]}')
                continue
            output_bytes = output_path.read_bytes()
            output_sha = _sha256(output_bytes)
            byte_identity = output_bytes == entry['source_bytes']
            if output_sha != entry['sha256'] or not byte_identity:
                errors.append(f'Generated adapter drift: {entry["id"]}: {entry["output_rel"]}')
            results.append(
                {
                    'id': entry['id'],
                    'kind': entry['kind'],
                    'order': entry['order'],
                    'source_path': entry['source_rel'],
                    'output_path': entry['output_rel'],
                    'sha256': output_sha,
                    'byte_identity': byte_identity,
                }
            )

    report = {
        'success': not errors,
        'schema': manifest.get('schema'),
        'module_contract_version': manifest.get('module_contract_version'),
        'target_id': target_id,
        'action': action,
        'module_count': len(entries),
        'prime_chunk_count': sum(entry['kind'] == 'prime_chunk' for entry in entries),
        'specialist_count': sum(entry['kind'] == 'specialist' for entry in entries),
        'results': results,
        'errors': errors,
    }
    return (0 if not errors else 1), report


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Materialize or verify generated provider behavior adapters.'
    )
    parser.add_argument('--repo-root', type=Path, default=_default_repo_root())
    parser.add_argument(
        '--manifest',
        type=Path,
        default=(
            Path(__file__).resolve().parents[1] / 'Behavior_Module_Manifest.json'
        ),
    )
    parser.add_argument('--target', default=TARGET_ID)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true')
    action.add_argument('--materialize', action='store_true')
    args = parser.parse_args(argv)

    selected_action = 'check' if args.check else 'materialize'
    code, report = execute(
        args.repo_root.resolve(),
        args.manifest.resolve(),
        args.target,
        selected_action,
    )
    rendered = json.dumps(report, indent=2) + '\n'
    stream = sys.stdout if code == 0 else sys.stderr
    stream.write(rendered)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
