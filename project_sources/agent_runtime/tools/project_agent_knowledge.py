#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA = 'dcoir.agent_runtime.knowledge_projection.v1'
SOURCE_CONTRACT_SCHEMA = 'dcoir.agent_runtime.source_contract.v1'
OPENAI_TARGETS = ('openai_dcoir_analyst', 'openai_usb_reporting')
PROVIDER_SPECIFIC_TERMS = (
    'gemini',
    'openai',
    'prime agent',
    'sub-agent',
    'sub agent',
)
BEGIN_PREFIX = b'<!-- DCOIR_SOURCE_BEGIN '
END_PREFIX = b'<!-- DCOIR_SOURCE_END '
MARKER_SUFFIX = b' -->'


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')


def _compact_json(value: Any) -> bytes:
    return json.dumps(
        value, separators=(',', ':'), sort_keys=True, ensure_ascii=True
    ).encode('ascii')


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


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def _is_positive_int(value: Any) -> bool:
    return type(value) is int and value > 0


def _is_nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _resolve_repo_path(
    repo_root: Path,
    value: Any,
    label: str,
    errors: list[str],
    required_root: Path | None = None,
) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f'{label} must be a non-empty repository-relative path')
        return None
    relative = Path(value)
    if relative.is_absolute() or '..' in relative.parts:
        errors.append(f'{label} must not be absolute or contain traversal: {value}')
        return None
    resolved_repo = repo_root.resolve()
    candidate = (resolved_repo / relative).resolve()
    if not candidate.is_relative_to(resolved_repo):
        errors.append(f'{label} escapes the repository: {value}')
        return None
    if required_root is not None and not candidate.is_relative_to(required_root.resolve()):
        errors.append(f'{label} is outside its declared root: {value}')
        return None
    return candidate


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_blob_sha(data: bytes) -> str:
    header = f'blob {len(data)}\0'.encode('ascii')
    return hashlib.sha1(header + data).hexdigest()


def _source_marker(prefix: bytes, metadata: dict[str, Any]) -> bytes:
    return prefix + _compact_json(metadata) + MARKER_SUFFIX + b'\n'


def _projection_bytes(
    target_id: str,
    group_id: str,
    purpose: str,
    sources: list[dict[str, Any]],
) -> bytes:
    header = (
        '# Generated DCOIR Knowledge Projection\n\n'
        '> Generated, non-canonical output. Edit the atomic files under '
        'knowledge/, then rebuild all affected targets.\n\n'
        f'- Target: {target_id}\n'
        f'- Projection group: {group_id}\n'
        f'- Purpose: {purpose}\n'
        f'- Source count: {len(sources)}\n\n'
    ).encode('utf-8')
    parts = [header]
    for source in sources:
        metadata = {
            'bytes': len(source['content']),
            'git_blob_sha': source['git_blob_sha'],
            'id': source['id'],
            'path': source['path'],
            'sha256': source['sha256'],
        }
        if source.get('split_from_id'):
            metadata['split_from_id'] = source['split_from_id']
            metadata['split_from_path'] = source['split_from_path']
        parts.append(_source_marker(BEGIN_PREFIX, metadata))
        parts.append(source['content'])
        parts.append(b'\n')
        parts.append(
            _source_marker(
                END_PREFIX,
                {'id': source['id'], 'sha256': source['sha256']},
            )
        )
        parts.append(b'\n')
    return b''.join(parts)


def recover_projection(data: bytes) -> list[dict[str, Any]]:
    recovered: list[dict[str, Any]] = []
    cursor = 0
    while True:
        begin = data.find(BEGIN_PREFIX, cursor)
        if begin < 0:
            break
        line_end = data.find(b'\n', begin)
        if line_end < 0:
            raise ValueError('Projection begin marker lacks a newline')
        marker = data[begin + len(BEGIN_PREFIX):line_end]
        if not marker.endswith(MARKER_SUFFIX):
            raise ValueError('Malformed projection begin marker')
        metadata = json.loads(marker[:-len(MARKER_SUFFIX)].decode('ascii'))
        byte_count = metadata.get('bytes')
        if not _is_nonnegative_int(byte_count):
            raise ValueError('Projection begin marker has an invalid byte count')
        content_start = line_end + 1
        content_end = content_start + byte_count
        content = data[content_start:content_end]
        if len(content) != byte_count:
            raise ValueError('Projection source content is truncated')
        end_start = content_end + 1
        if data[content_end:content_end + 1] != b'\n':
            raise ValueError('Projection source boundary separator is missing')
        if not data.startswith(END_PREFIX, end_start):
            raise ValueError('Projection source end marker is missing')
        end_line = data.find(b'\n', end_start)
        if end_line < 0:
            raise ValueError('Projection end marker lacks a newline')
        end_marker = data[end_start + len(END_PREFIX):end_line]
        if not end_marker.endswith(MARKER_SUFFIX):
            raise ValueError('Malformed projection end marker')
        end_metadata = json.loads(
            end_marker[:-len(MARKER_SUFFIX)].decode('ascii')
        )
        actual_sha = _sha256(content)
        if actual_sha != metadata.get('sha256'):
            raise ValueError(f"Recovered source sha256 mismatch: {metadata.get('id')}")
        if end_metadata != {
            'id': metadata.get('id'),
            'sha256': metadata.get('sha256'),
        }:
            raise ValueError(f"Projection end marker mismatch: {metadata.get('id')}")
        recovered.append({'metadata': metadata, 'content': content})
        cursor = end_line + 1
    return recovered


def _source_records(
    repo_root: Path,
    source_contract: dict[str, Any],
    knowledge_root: Path,
    errors: list[str],
) -> list[dict[str, Any]]:
    items = source_contract.get('knowledge_items')
    if not isinstance(items, list):
        errors.append('Source contract knowledge_items must be an array')
        return []
    records: list[dict[str, Any]] = []
    ids: list[str] = []
    paths: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            errors.append('Source contract contains a non-object knowledge item')
            continue
        item_id = item.get('id')
        source_path = item.get('source_path')
        if not isinstance(item_id, str) or not item_id:
            errors.append('Knowledge item lacks an id')
            continue
        ids.append(item_id)
        if not isinstance(source_path, str) or not source_path:
            errors.append(f'{item_id} lacks a source_path')
            continue
        paths.append(source_path)
        path = _resolve_repo_path(
            repo_root, source_path, f'{item_id} source_path', errors, knowledge_root
        )
        if path is None:
            continue
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            errors.append(f'Missing canonical knowledge source: {source_path}')
            continue
        expected_blob = item.get('source_git_blob_sha')
        actual_blob = _git_blob_sha(content)
        if expected_blob != actual_blob:
            errors.append(
                f'{item_id} Git blob SHA mismatch: expected {expected_blob}, '
                f'got {actual_blob}'
            )
        applies_to = item.get('applies_to')
        if not isinstance(applies_to, list) or not all(
            isinstance(target_id, str) and target_id for target_id in applies_to
        ):
            errors.append(f'{item_id} applies_to must be a target-id array')
        records.append(
            {
                'id': item_id,
                'path': source_path,
                'git_blob_sha': actual_blob,
                'sha256': _sha256(content),
                'content': content,
                'item': item,
            }
        )
    for duplicate in _duplicates(ids):
        errors.append(f'Duplicate knowledge id: {duplicate}')
    for duplicate in _duplicates(paths):
        errors.append(f'Duplicate knowledge source path: {duplicate}')
    return records


def _projection_source_records(
    repo_root: Path,
    records: list[dict[str, Any]],
    projection_roots: list[Path],
    errors: list[str],
) -> dict[tuple[str, str], dict[str, Any]]:
    unique_sources: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        item = record['item']
        overrides = item.get('target_projection_sources')
        applicable_openai = {
            target_id
            for target_id in OPENAI_TARGETS
            if target_id in (
                item.get('applies_to')
                if isinstance(item.get('applies_to'), list)
                else []
            )
        }
        if item.get('content_class') == 'split':
            if not isinstance(overrides, dict) or set(overrides) != applicable_openai:
                errors.append(
                    f"{record['id']} split source must define projection sources for "
                    f'{sorted(applicable_openai)}'
                )
                continue
        elif overrides is not None:
            errors.append(
                f"{record['id']} target_projection_sources requires split content_class"
            )
            continue
        else:
            continue

        target_records: dict[str, dict[str, Any]] = {}
        for target_id, override in overrides.items():
            if target_id not in OPENAI_TARGETS or not isinstance(override, dict):
                errors.append(
                    f"{record['id']} has an invalid target projection source: {target_id}"
                )
                continue
            override_id = override.get('id')
            override_path_value = override.get('source_path')
            if not isinstance(override_id, str) or not override_id:
                errors.append(f"{record['id']} {target_id} projection source lacks an id")
                continue
            override_path = _resolve_repo_path(
                repo_root,
                override_path_value,
                f"{record['id']} {target_id} projection source_path",
                errors,
            )
            if override_path is None:
                continue
            if not any(
                override_path.is_relative_to(root.resolve())
                for root in projection_roots
            ):
                errors.append(
                    f"{record['id']} {target_id} projection source is outside "
                    'canonical_projection_source_roots'
                )
                continue
            try:
                content = override_path.read_bytes()
            except FileNotFoundError:
                errors.append(
                    f'Missing canonical projection source: {override_path_value}'
                )
                continue
            actual_blob = _git_blob_sha(content)
            expected_blob = override.get('source_git_blob_sha')
            if actual_blob != expected_blob:
                errors.append(
                    f"{record['id']} {target_id} projection Git blob SHA mismatch: "
                    f'expected {expected_blob}, got {actual_blob}'
                )
            if override.get('provider_neutral_required') is not True:
                errors.append(
                    f"{record['id']} {target_id} projection source must require "
                    'provider-neutral content'
                )
            lowered = content.decode('utf-8', errors='replace').casefold()
            leaked = [term for term in PROVIDER_SPECIFIC_TERMS if term in lowered]
            if leaked:
                errors.append(
                    f"{record['id']} {target_id} projection source contains "
                    f'provider-specific terms: {leaked}'
                )
            override_record = {
                'id': override_id,
                'path': override_path.relative_to(repo_root).as_posix(),
                'git_blob_sha': actual_blob,
                'sha256': _sha256(content),
                'content': content,
                'item': item,
                'split_from_id': record['id'],
                'split_from_path': record['path'],
            }
            target_records[target_id] = override_record
            unique_sources[(override_id, override_record['path'])] = override_record
        record['target_projection_records'] = target_records
    return unique_sources


def _validate_gemini_inventory(
    repo_root: Path,
    target: dict[str, Any],
    records: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    bundle_path = _resolve_repo_path(
        repo_root, target.get('bundle_manifest'), 'Gemini bundle_manifest', errors
    )
    if bundle_path is None:
        return {}
    try:
        bundle = _load_json(bundle_path)
    except ValueError as exc:
        errors.append(str(exc))
        return {}
    attachments = bundle.get('knowledge_attachment_sources')
    if not isinstance(attachments, list) or not all(
        isinstance(path, str) and path for path in attachments
    ):
        errors.append('Gemini bundle knowledge_attachment_sources must be a path array')
        attachments = []
    applicable = [
        record for record in records
        if 'gemini_dcoir_agent' in (
            record['item'].get('applies_to')
            if isinstance(record['item'].get('applies_to'), list)
            else []
        )
    ]
    applicable_by_path = {record['path']: record for record in applicable}
    if len(attachments) != target.get('expected_attachment_count'):
        errors.append(
            'Gemini attachment count mismatch: '
            f"expected {target.get('expected_attachment_count')}, got {len(attachments)}"
        )
    for duplicate in _duplicates(attachments):
        errors.append(f'Duplicate Gemini knowledge attachment: {duplicate}')
    if set(attachments) != set(applicable_by_path):
        errors.append('Gemini attachment inventory disagrees with the source contract')
    inventory = []
    for path in attachments:
        record = applicable_by_path.get(path)
        if record is not None:
            inventory.append(
                {
                    'id': record['id'],
                    'path': path,
                    'git_blob_sha': record['git_blob_sha'],
                    'sha256': record['sha256'],
                    'bytes': len(record['content']),
                }
            )
    return {
        'mode': 'direct_canonical_attachments',
        'attachment_count': len(inventory),
        'attachments': inventory,
    }


def project_knowledge(
    repo_root: Path,
    manifest_path: Path,
    check: bool,
) -> tuple[list[str], dict[str, Any]]:
    repo_root = repo_root.resolve()
    errors: list[str] = []
    manifest_path = manifest_path.resolve()
    if not manifest_path.is_relative_to(repo_root):
        return ['Projection manifest must be inside the repository'], {}
    try:
        manifest = _load_json(manifest_path)
    except ValueError as exc:
        return [str(exc)], {}
    if manifest.get('schema') != SCHEMA:
        errors.append('Unsupported knowledge projection manifest schema')
    source_contract_path = _resolve_repo_path(
        repo_root, manifest.get('source_contract'), 'source_contract', errors
    )
    knowledge_root = _resolve_repo_path(
        repo_root,
        manifest.get('canonical_knowledge_root'),
        'canonical_knowledge_root',
        errors,
    )
    generated_root = _resolve_repo_path(
        repo_root, manifest.get('generated_root'), 'generated_root', errors
    )
    projection_root_values = manifest.get('canonical_projection_source_roots')
    projection_roots: list[Path] = []
    if not isinstance(projection_root_values, list) or not projection_root_values:
        errors.append('canonical_projection_source_roots must be a non-empty path array')
    else:
        for index, root_value in enumerate(projection_root_values):
            root = _resolve_repo_path(
                repo_root,
                root_value,
                f'canonical_projection_source_roots[{index}]',
                errors,
            )
            if root is not None:
                projection_roots.append(root)
    if source_contract_path is None or knowledge_root is None or generated_root is None:
        return errors, {}
    if (
        generated_root == repo_root
        or generated_root.is_relative_to(knowledge_root)
        or knowledge_root.is_relative_to(generated_root)
    ):
        errors.append(
            'generated_root must be disjoint from the repository root and canonical knowledge root'
        )
    for projection_root in projection_roots:
        if (
            projection_root == repo_root
            or projection_root.is_relative_to(generated_root)
            or generated_root.is_relative_to(projection_root)
        ):
            errors.append(
                'canonical projection source roots must be disjoint from generated_root'
            )
    try:
        source_contract = _load_json(source_contract_path)
    except ValueError as exc:
        errors.append(str(exc))
        return errors, {}
    if source_contract.get('schema') != SOURCE_CONTRACT_SCHEMA:
        errors.append('Unsupported shared source-contract schema')
    canonical_roots = source_contract.get('canonical_source_roots')
    if (
        not isinstance(canonical_roots, dict)
        or canonical_roots.get('knowledge')
        != manifest.get('canonical_knowledge_root')
    ):
        errors.append(
            'Projection canonical_knowledge_root disagrees with the source contract'
        )
    declared_projection_roots = (
        [canonical_roots.get('shared_knowledge_modules')]
        if isinstance(canonical_roots, dict)
        else []
    )
    if declared_projection_roots != projection_root_values:
        errors.append(
            'Projection source roots disagree with the shared source contract'
        )
    expected_manifest_rel = manifest_path.relative_to(repo_root).as_posix()
    if source_contract.get('knowledge_projection_manifest') != expected_manifest_rel:
        errors.append('Shared source contract points to the wrong projection manifest')
    policy = source_contract.get('knowledge_projection_policy')
    ceiling = manifest.get('strict_file_count_ceiling')
    if not _is_positive_int(ceiling):
        errors.append('strict_file_count_ceiling must be a positive integer')
        ceiling = 0
    if not isinstance(policy, dict) or policy.get('strict_file_count_ceiling') != ceiling:
        errors.append('Projection manifest file ceiling disagrees with source contract')
    records = _source_records(repo_root, source_contract, knowledge_root, errors)
    expected_source_count = manifest.get('expected_canonical_source_count')
    if not _is_positive_int(expected_source_count):
        errors.append('expected_canonical_source_count must be a positive integer')
    elif len(records) != expected_source_count:
        errors.append(
            f'Canonical knowledge count mismatch: expected {expected_source_count}, '
            f'got {len(records)}'
        )
    projection_sources = _projection_source_records(
        repo_root, records, projection_roots, errors
    )
    expected_projection_source_count = manifest.get(
        'expected_projection_source_count'
    )
    if not _is_positive_int(expected_projection_source_count):
        errors.append('expected_projection_source_count must be a positive integer')
    elif len(projection_sources) != expected_projection_source_count:
        errors.append(
            'Canonical projection source count mismatch: expected '
            f'{expected_projection_source_count}, got {len(projection_sources)}'
        )

    groups = source_contract.get('knowledge_projection_groups')
    if not isinstance(groups, list):
        errors.append('Source contract knowledge_projection_groups must be an array')
        groups = []
    group_by_id: dict[str, dict[str, Any]] = {}
    for group in groups:
        if not isinstance(group, dict):
            errors.append('Source contract contains a non-object projection group')
            continue
        group_id = group.get('id')
        if not isinstance(group_id, str) or not group_id:
            errors.append('Projection group lacks an id')
            continue
        if group_id in group_by_id:
            errors.append(f'Duplicate projection group id: {group_id}')
        group_by_id[group_id] = group

    targets = manifest.get('targets')
    if not isinstance(targets, dict):
        errors.append('Projection manifest targets must be an object')
        targets = {}
    expected_targets = {'gemini_dcoir_agent', *OPENAI_TARGETS}
    if set(targets) != expected_targets:
        errors.append(
            f'Projection target disagreement: expected {sorted(expected_targets)}, '
            f'got {sorted(targets)}'
        )

    result_targets: dict[str, Any] = {}
    gemini_target = targets.get('gemini_dcoir_agent')
    if not isinstance(gemini_target, dict) or gemini_target.get('mode') != (
        'direct_canonical_attachments'
    ):
        errors.append('Gemini target must use direct_canonical_attachments')
    else:
        result_targets['gemini_dcoir_agent'] = _validate_gemini_inventory(
            repo_root, gemini_target, records, errors
        )

    source_contract_sha = _sha256(source_contract_path.read_bytes())
    expected_files: dict[Path, bytes] = {}
    output_paths: list[str] = []
    for target_id in OPENAI_TARGETS:
        target = targets.get(target_id)
        if not isinstance(target, dict) or target.get('mode') != 'consolidated_projection':
            errors.append(f'{target_id} must use consolidated_projection')
            continue
        target_manifest_path = _resolve_repo_path(
            repo_root,
            target.get('target_manifest_path'),
            f'{target_id} target_manifest_path',
            errors,
            generated_root,
        )
        target_root = (generated_root / target_id).resolve()
        if (
            target_manifest_path is not None
            and target_manifest_path.parent != target_root
        ):
            errors.append(
                f'{target_id} target_manifest_path must be directly under '
                f'{target_root.relative_to(repo_root).as_posix()}'
            )
        if target_manifest_path is not None and target_manifest_path.suffix != '.json':
            errors.append(f'{target_id} target_manifest_path must end in .json')
        declared_groups = target.get('projection_groups')
        if not isinstance(declared_groups, list):
            errors.append(f'{target_id} projection_groups must be an array')
            continue
        if len(declared_groups) > ceiling:
            errors.append(
                f'{target_id} projection file count {len(declared_groups)} '
                f'exceeds ceiling {ceiling}'
            )
        expected_projection_count = target.get('expected_projection_count')
        if not _is_positive_int(expected_projection_count):
            errors.append(f'{target_id} expected_projection_count must be positive')
        elif len(declared_groups) != expected_projection_count:
            errors.append(
                f'{target_id} projection count mismatch: expected '
                f'{expected_projection_count}, got {len(declared_groups)}'
            )
        group_ids = [
            group.get('id') for group in declared_groups if isinstance(group, dict)
        ]
        orders = [
            group.get('order') for group in declared_groups if isinstance(group, dict)
        ]
        if len(group_ids) != len(declared_groups):
            errors.append(f'{target_id} contains a non-object projection group')
        for duplicate in _duplicates(
            [value for value in group_ids if isinstance(value, str)]
        ):
            errors.append(f'{target_id} has duplicate projection group: {duplicate}')
        if (
            not all(type(order) is int for order in orders)
            or orders != list(range(len(declared_groups)))
        ):
            errors.append(f'{target_id} projection group order must be contiguous')
        contract_group_ids = [
            group.get('id') for group in groups
            if isinstance(group, dict) and group.get('target_id') == target_id
        ]
        if group_ids != contract_group_ids:
            errors.append(
                f'{target_id} projection groups disagree with source contract: '
                f'{group_ids} != {contract_group_ids}'
            )

        group_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
        projection_field = (
            'openai_dcoir_projection_group'
            if target_id == 'openai_dcoir_analyst'
            else 'openai_usb_projection_group'
        )
        for record in records:
            raw_applies = record['item'].get('applies_to')
            applies = raw_applies if isinstance(raw_applies, list) else []
            group_id = record['item'].get(projection_field)
            if target_id in applies:
                if not isinstance(group_id, str) or not group_id:
                    errors.append(f"{record['id']} lacks {projection_field}")
                else:
                    declared_group = group_by_id.get(group_id)
                    if (
                        declared_group is None
                        or declared_group.get('target_id') != target_id
                    ):
                        errors.append(
                            f"{record['id']} references an unknown {projection_field}: "
                            f'{group_id}'
                        )
                    projected_record = record.get(
                        'target_projection_records', {}
                    ).get(target_id, record)
                    group_sources[group_id].append(projected_record)
            elif group_id is not None:
                errors.append(
                    f"{record['id']} declares {projection_field} but does not apply to {target_id}"
                )

        projection_reports = []
        for group_entry in declared_groups:
            if not isinstance(group_entry, dict):
                continue
            group_id = group_entry.get('id')
            contract_group = group_by_id.get(group_id)
            if contract_group is None or contract_group.get('target_id') != target_id:
                errors.append(f'{target_id} references unknown projection group: {group_id}')
                continue
            sources = group_sources.get(group_id, [])
            if not sources:
                errors.append(f'{target_id} projection group has no sources: {group_id}')
            output_path = _resolve_repo_path(
                repo_root,
                group_entry.get('output_path'),
                f'{target_id} {group_id} output_path',
                errors,
                target_root,
            )
            if output_path is None:
                continue
            if output_path.suffix != '.md':
                errors.append(
                    f'{target_id} {group_id} output_path must end in .md'
                )
            output_rel = output_path.relative_to(repo_root).as_posix()
            output_paths.append(output_rel)
            content = _projection_bytes(
                target_id,
                group_id,
                contract_group.get('purpose', ''),
                sources,
            )
            expected_files[output_path] = content
            recovered = recover_projection(content)
            if [entry['content'] for entry in recovered] != [
                source['content'] for source in sources
            ]:
                errors.append(f'{target_id} projection is not losslessly recoverable: {group_id}')
            source_map = [
                {
                    'id': source['id'],
                    'path': source['path'],
                    'git_blob_sha': source['git_blob_sha'],
                    'sha256': source['sha256'],
                    'bytes': len(source['content']),
                    **(
                        {
                            'split_from_id': source['split_from_id'],
                            'split_from_path': source['split_from_path'],
                        }
                        if source.get('split_from_id')
                        else {}
                    ),
                }
                for source in sources
            ]
            projection_reports.append(
                {
                    'id': group_id,
                    'order': group_entry.get('order'),
                    'output_path': output_rel,
                    'sha256': _sha256(content),
                    'bytes': len(content),
                    'source_count': len(sources),
                    'sources': source_map,
                }
            )

        target_report = {
            'schema': 'dcoir.agent_runtime.knowledge_projection.target.v1',
            'projection_contract_version': manifest.get('projection_contract_version'),
            'source_contract': source_contract_path.relative_to(repo_root).as_posix(),
            'source_contract_sha256': source_contract_sha,
            'target_id': target_id,
            'projection_file_count': len(projection_reports),
            'strict_file_count_ceiling': ceiling,
            'projections': projection_reports,
        }
        if target_manifest_path is not None:
            output_paths.append(target_manifest_path.relative_to(repo_root).as_posix())
            expected_files[target_manifest_path] = _json_bytes(target_report)
        result_targets[target_id] = target_report

    for duplicate in _duplicates(output_paths):
        errors.append(f'Duplicate generated output path: {duplicate}')

    expected_path_set = set(expected_files)
    actual_files: set[Path] = set()
    if generated_root.exists():
        for path in generated_root.rglob('*'):
            if path.is_symlink():
                errors.append(
                    'Generated knowledge tree must not contain symlinks: '
                    f'{path.relative_to(repo_root).as_posix()}'
                )
                continue
            if path.is_file():
                resolved_path = path.resolve()
                if not resolved_path.is_relative_to(generated_root):
                    errors.append(
                        'Generated knowledge file escapes generated_root: '
                        f'{path.relative_to(repo_root).as_posix()}'
                    )
                    continue
                actual_files.add(resolved_path)
    stale = sorted(
        path.relative_to(repo_root).as_posix()
        for path in actual_files - expected_path_set
    )
    if stale:
        errors.append(f'Stale generated knowledge files: {stale}')

    if check:
        for output_path, expected in expected_files.items():
            try:
                actual = output_path.read_bytes()
            except FileNotFoundError:
                errors.append(
                    f'Missing generated knowledge file: '
                    f'{output_path.relative_to(repo_root).as_posix()}'
                )
                continue
            if actual != expected:
                errors.append(
                    f'Generated knowledge drift: '
                    f'{output_path.relative_to(repo_root).as_posix()}'
                )
    elif not errors:
        with tempfile.TemporaryDirectory(
            prefix='.knowledge-projection-', dir=repo_root
        ) as stage_dir:
            staging_root = Path(stage_dir).resolve()
            for output_path, expected in expected_files.items():
                with tempfile.NamedTemporaryFile(
                    dir=staging_root, delete=False
                ) as staged_file:
                    staged_file.write(expected)
                    stage_path = Path(staged_file.name).resolve()
                if not stage_path.is_relative_to(staging_root):
                    errors.append('Generated knowledge staging path escaped its root')
                    continue
                if stage_path.read_bytes() != expected:
                    errors.append('Generated knowledge staging write readback failed')
                    continue
                resolved_output = _resolve_repo_path(
                    repo_root,
                    output_path.relative_to(repo_root).as_posix(),
                    'generated output',
                    errors,
                    generated_root,
                )
                if resolved_output is None:
                    continue
                resolved_output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(stage_path, resolved_output)
                if resolved_output.read_bytes() != expected:
                    errors.append(
                        'Generated knowledge write readback failed: '
                        f'{resolved_output.relative_to(repo_root).as_posix()}'
                    )

    report = {
        'success': not errors,
        'schema': manifest.get('schema'),
        'projection_contract_version': manifest.get('projection_contract_version'),
        'action': 'check' if check else 'materialize',
        'canonical_source_count': len(records),
        'canonical_projection_source_count': len(projection_sources),
        'generated_file_count': len(expected_files),
        'targets': result_targets,
        'errors': errors,
    }
    return errors, report


def main() -> int:
    default_repo = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo-root', default=str(default_repo))
    parser.add_argument(
        '--manifest',
        default='project_sources/agent_runtime/Knowledge_Projection_Manifest.json',
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--check', action='store_true')
    action.add_argument('--materialize', action='store_true')
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = repo_root / manifest_path
    errors, report = project_knowledge(
        repo_root, manifest_path.resolve(), check=not args.materialize
    )
    stream = sys.stderr if errors else sys.stdout
    print(json.dumps(report, indent=2), file=stream)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
