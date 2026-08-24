#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXPECTED_TARGET_IDS = {
    'gemini_dcoir_agent',
    'openai_dcoir_analyst',
    'openai_usb_reporting',
}
OPENAI_TARGET_IDS = {'openai_dcoir_analyst', 'openai_usb_reporting'}
UNAVAILABLE_OPENAI_CAPABILITIES = {
    'web_search',
    'code_interpreter_data_analysis',
    'canvas',
    'image_generation',
    'apps',
    'actions',
    'live_elastic_access',
    'live_collector_execution',
    'github_supabase_connectors',
    'persistent_cross_conversation_memory',
}
BEHAVIOR_REQUIRED_FIELDS = {
    'id',
    'source_path',
    'source_section',
    'responsibility',
    'content_class',
    'authority_class',
    'canonical',
    'applies_to',
    'target_dispositions',
    'provider_specific_differences',
    'downstream_dependencies',
    'validation_classes',
    'source_map_required',
    'reverse_reconciliation_required',
    'unresolved_operator_decision',
}
KNOWLEDGE_REQUIRED_FIELDS = {
    'id',
    'source_path',
    'content_class',
    'canonical',
    'applies_to',
    'gemini_attachment_disposition',
    'openai_dcoir_projection_group',
    'openai_usb_projection_group',
    'source_boundary_hash_required',
    'duplicate_or_overlap_notes',
    'consolidation_validation',
}
ALLOWED_KNOWLEDGE_CONTENT_CLASSES = {
    'runtime_reference',
    'instruction_source',
    'maintainer_only',
    'split',
}
GEMINI_KNOWLEDGE_CLASSIFICATIONS = {
    'knowledge/Knowledge - Gemini - AI Prompt and Agent Design.md': 'maintainer_only',
    'knowledge/Knowledge - Gemini - Agent Topology and Routing.md': 'maintainer_only',
    'knowledge/Knowledge - Gemini - Output Contract and Command-Lane Discipline.md': 'split',
    'knowledge/Knowledge - Gemini - Runtime Bundle and Source Tree.md': 'maintainer_only',
}
MATRIX_ID_PATTERN = re.compile(
    r'<!--\s*contract-(behavior|knowledge|stale)-id:([^\s]+)\s*-->'
)


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


def _matrix_ids(matrix_path: Path) -> dict[str, list[str]]:
    try:
        text = matrix_path.read_text(encoding='utf-8')
    except FileNotFoundError as exc:
        raise ValueError(f'Missing ownership matrix: {matrix_path}') from exc
    result: dict[str, list[str]] = {'behavior': [], 'knowledge': [], 'stale': []}
    for kind, item_id in MATRIX_ID_PATTERN.findall(text):
        result[kind].append(item_id)
    return result


def _expected_inventory(
    repo_root: Path,
) -> tuple[list[str], list[str], list[str], list[str]]:
    bundle_root = repo_root / 'project_sources' / 'gemini' / 'bundle_source'
    bundle = _load_json(bundle_root / 'Gemini_Bundle_Source_Manifest.json')
    chunk_manifest_rel = bundle.get('topology', {}).get('prime_agent_chunk_manifest')
    if not isinstance(chunk_manifest_rel, str) or not chunk_manifest_rel:
        raise ValueError('Gemini bundle manifest lacks topology.prime_agent_chunk_manifest')
    chunks = _load_json(bundle_root / chunk_manifest_rel).get('chunks')
    if not isinstance(chunks, list):
        raise ValueError('Prime chunk manifest lacks a chunks array')

    prime_paths = []
    for chunk in chunks:
        path = chunk.get('path') if isinstance(chunk, dict) else None
        if not isinstance(path, str) or not path:
            raise ValueError('Prime chunk manifest contains a chunk without a path')
        prime_paths.append((Path('project_sources/gemini/bundle_source') / path).as_posix())

    sub_agents = bundle.get('topology', {}).get('sub_agent_files')
    if not isinstance(sub_agents, list) or not all(isinstance(path, str) for path in sub_agents):
        raise ValueError('Gemini bundle manifest lacks valid topology.sub_agent_files')
    sub_agent_paths = [
        (Path('project_sources/gemini/bundle_source') / path).as_posix()
        for path in sub_agents
    ]

    knowledge_paths = bundle.get('knowledge_attachment_sources')
    if not isinstance(knowledge_paths, list) or not all(isinstance(path, str) for path in knowledge_paths):
        raise ValueError('Gemini bundle manifest lacks valid knowledge_attachment_sources')
    legacy_authority_paths = bundle.get('behavioral_authority')
    if not isinstance(legacy_authority_paths, list) or not all(
        isinstance(path, str) for path in legacy_authority_paths
    ):
        raise ValueError('Gemini bundle manifest lacks valid behavioral_authority')
    return prime_paths, sub_agent_paths, knowledge_paths, legacy_authority_paths


def _check_exact_source_coverage(
    errors: list[str],
    expected: list[str],
    mapped: list[str],
    label: str,
) -> None:
    counts = Counter(mapped)
    for source_path in expected:
        if counts[source_path] != 1:
            errors.append(
                f'{label} source is not mapped exactly once: {source_path} '
                f'(mapped {counts[source_path]} times)'
            )


def validate_contract(
    manifest_path: Path,
    matrix_path: Path,
    repo_root: Path,
) -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    try:
        manifest = _load_json(manifest_path)
        matrix_ids = _matrix_ids(matrix_path)
        (
            expected_prime,
            expected_sub_agents,
            expected_knowledge,
            expected_stale,
        ) = _expected_inventory(repo_root)
    except ValueError as exc:
        return [str(exc)], {}

    if manifest.get('schema') != 'dcoir.agent_runtime.source_contract.v1':
        errors.append('Unsupported or missing source-contract schema')
    if not manifest.get('source_contract_version'):
        errors.append('Missing source_contract_version')

    declared_target_ids = manifest.get('target_ids')
    targets = manifest.get('targets')
    behaviors = manifest.get('behavior_items')
    knowledge = manifest.get('knowledge_items')
    stale = manifest.get('stale_source_references')
    groups = manifest.get('knowledge_projection_groups')
    if not isinstance(declared_target_ids, list):
        declared_target_ids = []
        errors.append('target_ids must be an array')
    if not isinstance(targets, list):
        targets = []
        errors.append('targets must be an array')
    if not isinstance(behaviors, list):
        behaviors = []
        errors.append('behavior_items must be an array')
    if not isinstance(knowledge, list):
        knowledge = []
        errors.append('knowledge_items must be an array')
    if not isinstance(stale, list):
        stale = []
        errors.append('stale_source_references must be an array')
    if not isinstance(groups, list):
        groups = []
        errors.append('knowledge_projection_groups must be an array')

    target_ids = [target.get('id') for target in targets if isinstance(target, dict)]
    for duplicate in _duplicates([value for value in target_ids if isinstance(value, str)]):
        errors.append(f'Duplicate target id: {duplicate}')
    if set(target_ids) != EXPECTED_TARGET_IDS:
        errors.append(
            'Target ids must be exactly: ' + ', '.join(sorted(EXPECTED_TARGET_IDS))
        )
    if set(declared_target_ids) != EXPECTED_TARGET_IDS or _duplicates(
        [value for value in declared_target_ids if isinstance(value, str)]
    ):
        errors.append('target_ids must contain each required target exactly once')

    stable_ids = [
        item.get('id')
        for collection in (behaviors, knowledge, stale)
        for item in collection
        if isinstance(item, dict) and isinstance(item.get('id'), str)
    ]
    for duplicate in _duplicates(stable_ids):
        errors.append(f'Duplicate stable item id: {duplicate}')

    target_by_id = {
        target.get('id'): target
        for target in targets
        if isinstance(target, dict) and isinstance(target.get('id'), str)
    }
    for target_id, target in target_by_id.items():
        if not target.get('output_owner'):
            errors.append(f'{target_id} lacks explicit target output ownership')
        if not isinstance(target.get('generated_outputs'), list):
            errors.append(f'{target_id} lacks a generated_outputs array')
    for target_id in OPENAI_TARGET_IDS:
        target = target_by_id.get(target_id)
        if not target:
            continue
        capabilities = target.get('capabilities')
        if not isinstance(capabilities, dict):
            errors.append(f'{target_id} lacks a capabilities object')
            continue
        for capability in sorted(UNAVAILABLE_OPENAI_CAPABILITIES):
            if capabilities.get(capability) is not False:
                errors.append(
                    f'{target_id} claims unavailable capability or omits explicit false: '
                    f'{capability}'
                )
        optional_lookup = target.get('optional_future_capabilities', {}).get('public_lookup', {})
        if optional_lookup.get('current_available') is not False:
            errors.append(f'{target_id} must mark optional future public lookup unavailable')

    policy = manifest.get('generated_artifact_policy')
    if not isinstance(policy, dict):
        errors.append('Missing generated_artifact_policy')
    else:
        if policy.get('generated_outputs_are_canonical') is not False:
            errors.append('Generated outputs must not be canonical')
        if policy.get('reverse_reconciliation_required') is not True:
            errors.append('Direct target hotfixes require reverse reconciliation')
        if not policy.get('reconciliation_rule'):
            errors.append('Missing direct-target reverse-reconciliation rule')

    mapped_behavior_paths: list[str] = []
    authority_by_path: dict[str, list[tuple[str, Any]]] = defaultdict(list)
    stale_paths = {
        item.get('source_path')
        for item in stale
        if isinstance(item, dict) and item.get('status') in {'missing_retired_reference', 'retired'}
    }
    stale_mapped_paths: list[str] = []
    stale_required_fields = {
        'id',
        'source_path',
        'status',
        'live_evidence',
        'replacement_authority',
        'runtime_cleanup',
    }
    for item in stale:
        if not isinstance(item, dict):
            errors.append('stale_source_references contains a non-object')
            continue
        item_id = item.get('id', '<missing-id>')
        missing = sorted(stale_required_fields - set(item))
        if missing:
            errors.append(
                f'{item_id} lacks required stale-reference fields: {", ".join(missing)}'
            )
        source_path = item.get('source_path')
        if isinstance(source_path, str):
            stale_mapped_paths.append(source_path)
        if item.get('status') not in {'missing_retired_reference', 'retired'}:
            errors.append(f'{item_id} lacks an explicit stale or retired disposition')
    for item in behaviors:
        if not isinstance(item, dict):
            errors.append('behavior_items contains a non-object')
            continue
        item_id = item.get('id', '<missing-id>')
        missing = sorted(BEHAVIOR_REQUIRED_FIELDS - set(item))
        if missing:
            errors.append(f'{item_id} lacks required behavior fields: {", ".join(missing)}')
        source_path = item.get('source_path')
        if isinstance(source_path, str):
            mapped_behavior_paths.append(source_path)
            authority_by_path[source_path].append(
                (str(item.get('authority_class')), item.get('split_disposition'))
            )
        if item.get('source_map_required') is not True:
            errors.append(f'{item_id} lacks required source-map metadata')
        if item.get('reverse_reconciliation_required') is not True:
            errors.append(f'{item_id} lacks required reverse-reconciliation metadata')
        if item.get('authority_class') == 'generated' and item.get('canonical') is True:
            errors.append(f'Generated output is marked canonical: {item_id}')
        dispositions = item.get('target_dispositions')
        if not isinstance(dispositions, dict) or set(dispositions) != EXPECTED_TARGET_IDS:
            errors.append(f'{item_id} must disposition all three targets')
        if isinstance(source_path, str) and item.get('canonical') is True:
            if not (repo_root / source_path).is_file() and source_path not in stale_paths:
                errors.append(f'Missing canonical source path without stale disposition: {source_path}')

    mapped_knowledge_paths: list[str] = []
    group_by_id: dict[str, dict[str, Any]] = {}
    groups_by_target: dict[str, set[str]] = defaultdict(set)
    for group in groups:
        if not isinstance(group, dict):
            errors.append('knowledge_projection_groups contains a non-object')
            continue
        group_id = group.get('id')
        target_id = group.get('target_id')
        if not isinstance(group_id, str) or not isinstance(target_id, str):
            errors.append('Knowledge projection group lacks id or target_id')
            continue
        if group_id in group_by_id:
            errors.append(f'Duplicate knowledge projection group id: {group_id}')
        group_by_id[group_id] = group
        groups_by_target[target_id].add(group_id)

    ceiling = manifest.get('knowledge_projection_policy', {}).get(
        'strict_file_count_ceiling'
    )
    if not isinstance(ceiling, int) or ceiling < 1:
        errors.append('strict_file_count_ceiling must be a positive integer')
    else:
        for target_id in OPENAI_TARGET_IDS:
            count = len(groups_by_target[target_id])
            if count > ceiling:
                errors.append(
                    f'Knowledge projection group ceiling exceeded for {target_id}: '
                    f'{count} > {ceiling}'
                )

    for item in knowledge:
        if not isinstance(item, dict):
            errors.append('knowledge_items contains a non-object')
            continue
        item_id = item.get('id', '<missing-id>')
        missing = sorted(KNOWLEDGE_REQUIRED_FIELDS - set(item))
        if missing:
            errors.append(f'{item_id} lacks required knowledge fields: {", ".join(missing)}')
        source_path = item.get('source_path')
        if isinstance(source_path, str):
            mapped_knowledge_paths.append(source_path)
            authority_by_path[source_path].append(
                (str(item.get('content_class')), item.get('split_disposition'))
            )
            if not (repo_root / source_path).is_file():
                errors.append(f'Missing canonical knowledge source: {source_path}')
        if item.get('canonical') is not True:
            errors.append(f'Knowledge source must remain canonical: {item_id}')
        if item.get('content_class') not in ALLOWED_KNOWLEDGE_CONTENT_CLASSES:
            errors.append(f'{item_id} has unsupported knowledge content_class')
        expected_class = GEMINI_KNOWLEDGE_CLASSIFICATIONS.get(source_path)
        if expected_class and item.get('content_class') != expected_class:
            errors.append(
                f'{item_id} must classify {source_path} as {expected_class}'
            )
        if item.get('source_boundary_hash_required') is not True:
            errors.append(f'Knowledge source lacks boundary/hash requirement: {item_id}')
        for field, target_id in (
            ('openai_dcoir_projection_group', 'openai_dcoir_analyst'),
            ('openai_usb_projection_group', 'openai_usb_reporting'),
        ):
            group_id = item.get(field)
            if group_id is None:
                continue
            group = group_by_id.get(group_id)
            if not group:
                errors.append(f'{item_id} refers to unknown projection group: {group_id}')
            elif group.get('target_id') != target_id:
                errors.append(
                    f'{item_id} uses projection group {group_id} for the wrong target'
                )
            if target_id not in item.get('applies_to', []):
                errors.append(
                    f'{item_id} has projection group {group_id} but omits {target_id} '
                    'from applies_to'
                )

    for source_path, entries in authority_by_path.items():
        classes = {authority for authority, _ in entries}
        if len(classes) > 1 and not all(split for _, split in entries):
            errors.append(
                f'Conflicting authority classes without explicit split disposition: {source_path}'
            )

    ioc_contract = manifest.get('ioc_enrichment_contract')
    if not isinstance(ioc_contract, dict):
        errors.append('Missing ioc_enrichment_contract')
    else:
        source_ids = ioc_contract.get('behavior_source_ids')
        behavior_ids = {
            item.get('id') for item in behaviors if isinstance(item, dict)
        }
        if not isinstance(source_ids, list) or not source_ids:
            errors.append('IOC enrichment contract lacks behavior_source_ids')
        else:
            for source_id in source_ids:
                if source_id not in behavior_ids:
                    errors.append(
                        f'IOC enrichment contract refers to unknown behavior id: {source_id}'
                    )

    _check_exact_source_coverage(errors, expected_prime, mapped_behavior_paths, 'Prime')
    _check_exact_source_coverage(errors, expected_sub_agents, mapped_behavior_paths, 'Sub-agent')
    _check_exact_source_coverage(errors, expected_knowledge, mapped_knowledge_paths, 'Knowledge')
    _check_exact_source_coverage(errors, expected_stale, stale_mapped_paths, 'Stale authority')

    expected_matrix = {
        'behavior': {
            item.get('id') for item in behaviors if isinstance(item, dict) and item.get('id')
        },
        'knowledge': {
            item.get('id') for item in knowledge if isinstance(item, dict) and item.get('id')
        },
        'stale': {
            item.get('id') for item in stale if isinstance(item, dict) and item.get('id')
        },
    }
    for kind, expected_ids in expected_matrix.items():
        actual = matrix_ids[kind]
        duplicates = _duplicates(actual)
        if duplicates:
            errors.append(f'Duplicate {kind} ids in ownership matrix: {", ".join(duplicates)}')
        if set(actual) != expected_ids:
            missing = sorted(expected_ids - set(actual))
            extra = sorted(set(actual) - expected_ids)
            errors.append(
                f'Manifest/matrix {kind} id disagreement; '
                f'missing={missing or []}, extra={extra or []}'
            )

    stats = {
        'targets': len(targets),
        'behavior_items': len(behaviors),
        'prime_chunks': len(expected_prime),
        'sub_agents': len(expected_sub_agents),
        'knowledge_items': len(knowledge),
        'stale_references': len(expected_stale),
        'projection_groups': len(groups),
    }
    return errors, stats


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    source_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description='Validate the provider-neutral DCOIR agent source contract.'
    )
    parser.add_argument(
        '--manifest',
        type=Path,
        default=source_root / 'Shared_Agent_Source_Manifest.json',
    )
    parser.add_argument(
        '--matrix',
        type=Path,
        default=source_root / 'docs' / 'Behavior_Ownership_Matrix.md',
    )
    parser.add_argument('--repo-root', type=Path, default=_default_repo_root())
    parser.add_argument('--json', action='store_true', dest='json_output')
    args = parser.parse_args(argv)

    errors, stats = validate_contract(
        args.manifest.resolve(),
        args.matrix.resolve(),
        args.repo_root.resolve(),
    )
    payload = {'valid': not errors, 'stats': stats, 'errors': errors}
    if args.json_output:
        print(json.dumps(payload, indent=2))
    elif errors:
        print('Shared agent source contract validation failed:', file=sys.stderr)
        for error in errors:
            print(f'- {error}', file=sys.stderr)
    else:
        print('Shared agent source contract validation passed.')
        print(json.dumps(stats, sort_keys=True))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
