#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
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
PROVIDER_SPECIFIC_PROJECTION_TERMS = (
    'gemini',
    'openai',
    'prime agent',
    'sub-agent',
    'sub agent',
)
MATRIX_ID_PREFIXES = {
    'behavior': '<!-- contract-behavior-id:',
    'knowledge': '<!-- contract-knowledge-id:',
    'stale': '<!-- contract-stale-id:',
}
MATRIX_SECTION_HEADERS = {
    'Target Capability Boundary': [
        'Target',
        'Output owner',
        'Instruction mode',
        'Knowledge mode',
        'Current live lookup',
        'Current external actions',
    ],
    'Behavior Ownership': [
        'Stable id',
        'Source / section',
        'Class',
        'Gemini',
        'OpenAI DCOIR',
        'OpenAI USB',
        'Responsibility',
    ],
    'Behavior Control Details': [
        'Stable id',
        'Applies to',
        'Provider differences',
        'Dependencies',
        'Validation',
        'Reverse sync',
        'Decision',
    ],
    'Knowledge Disposition': [
        'Stable id',
        'Canonical source',
        'Class',
        'Gemini attachment',
        'DCOIR projection',
        'USB projection',
        'Boundary/hash and overlap rule',
    ],
    'Stale Behavioral Authority References': [
        'Stable id',
        'Missing path',
        'Status',
        'Replacement authority',
        'Runtime action',
    ],
}


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


def _normalize_matrix_value(value: str) -> str:
    return ' '.join(value.replace('`', '').split())


def _markdown_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith('|') or not stripped.endswith('|'):
        return None
    values: list[str] = []
    current: list[str] = []
    escaped = False
    for character in stripped[1:-1]:
        if escaped:
            if character != '|':
                current.append('\\')
            current.append(character)
            escaped = False
        elif character == '\\':
            escaped = True
        elif character == '|':
            values.append(''.join(current))
            current = []
        else:
            current.append(character)
    if escaped:
        current.append('\\')
    values.append(''.join(current))
    return [_normalize_matrix_value(value) for value in values]


def _matrix_contract(
    matrix_path: Path,
) -> tuple[dict[str, list[str]], dict[str, list[dict[str, str]]], list[str]]:
    try:
        text = matrix_path.read_text(encoding='utf-8')
    except FileNotFoundError as exc:
        raise ValueError(f'Missing ownership matrix: {matrix_path}') from exc
    result: dict[str, list[str]] = {'behavior': [], 'knowledge': [], 'stale': []}
    tables = {section: [] for section in MATRIX_SECTION_HEADERS}
    active_section: str | None = None
    observed_headers: set[str] = set()
    parse_errors: list[str] = []
    for line in text.splitlines():
        marker = line.strip()
        if marker.startswith('## '):
            active_section = marker[3:].strip()
            continue
        for kind, prefix in MATRIX_ID_PREFIXES.items():
            if marker.startswith(prefix) and marker.endswith(' -->'):
                item_id = marker[len(prefix):-4].strip()
                if item_id:
                    result[kind].append(item_id)
                break
        cells = _markdown_cells(line)
        if cells is None or active_section not in MATRIX_SECTION_HEADERS:
            continue
        expected_header = MATRIX_SECTION_HEADERS[active_section]
        if cells == expected_header:
            observed_headers.add(active_section)
            continue
        if all(cell and set(cell) <= {'-', ':'} for cell in cells):
            continue
        if active_section not in observed_headers:
            parse_errors.append(f'Missing matrix table header: {active_section}')
            continue
        if len(cells) != len(expected_header):
            parse_errors.append(
                f'Matrix row in {active_section} has {len(cells)} cells; '
                f'expected {len(expected_header)}'
            )
            continue
        tables[active_section].append(dict(zip(expected_header, cells)))
    for section in MATRIX_SECTION_HEADERS:
        if section not in observed_headers:
            parse_errors.append(f'Missing matrix table: {section}')
    return result, tables, parse_errors


def _compare_matrix_rows(
    errors: list[str],
    section: str,
    expected_rows: list[dict[str, str]],
    actual_rows: list[dict[str, str]],
    key: str,
) -> None:
    expected_by_key = {row[key]: row for row in expected_rows}
    actual_keys = [row.get(key, '') for row in actual_rows]
    for duplicate in _duplicates(actual_keys):
        errors.append(f'Duplicate matrix row in {section}: {duplicate}')
    actual_by_key = {row.get(key, ''): row for row in actual_rows}
    if set(actual_by_key) != set(expected_by_key):
        missing = sorted(set(expected_by_key) - set(actual_by_key))
        extra = sorted(set(actual_by_key) - set(expected_by_key))
        errors.append(
            f'Manifest/matrix {section} row disagreement; '
            f'missing={missing or []}, extra={extra or []}'
        )
    for row_key in sorted(set(expected_by_key) & set(actual_by_key)):
        expected = expected_by_key[row_key]
        actual = actual_by_key[row_key]
        for field, expected_value in expected.items():
            normalized_expected = _normalize_matrix_value(expected_value)
            if actual.get(field) != normalized_expected:
                errors.append(
                    f'Manifest/matrix {section} mismatch for {row_key} field '
                    f'{field}: expected {normalized_expected!r}, '
                    f'got {actual.get(field)!r}'
                )


def _approved_source_roots(
    errors: list[str], manifest: dict[str, Any], repo_root: Path
) -> list[Path]:
    declared = manifest.get('canonical_source_roots')
    if not isinstance(declared, dict) or not declared:
        errors.append('canonical_source_roots must be a non-empty object')
        return []
    resolved_repo = repo_root.resolve()
    roots: list[Path] = []
    for root_id, value in declared.items():
        if not isinstance(value, str) or not value:
            errors.append(f'Invalid canonical source root: {root_id}')
            continue
        relative = Path(value)
        if relative.is_absolute() or '..' in relative.parts:
            errors.append(f'Canonical source root must be repository-relative: {value}')
            continue
        candidate = (resolved_repo / relative).resolve()
        if not candidate.is_relative_to(resolved_repo):
            errors.append(f'Canonical source root escapes repository: {value}')
            continue
        roots.append(candidate)
    return roots


def _canonical_source_path(
    errors: list[str],
    repo_root: Path,
    approved_roots: list[Path],
    item_id: str,
    source_path: str,
) -> Path | None:
    relative = Path(source_path)
    if relative.is_absolute() or '..' in relative.parts:
        errors.append(
            f'Canonical source path must be repository-relative without traversal: '
            f'{item_id}: {source_path}'
        )
        return None
    resolved_repo = repo_root.resolve()
    candidate = (resolved_repo / relative).resolve()
    if not candidate.is_relative_to(resolved_repo):
        errors.append(f'Canonical source path escapes repository: {item_id}: {source_path}')
        return None
    if not any(candidate.is_relative_to(root) for root in approved_roots):
        errors.append(
            f'Canonical source path is outside approved source roots: '
            f'{item_id}: {source_path}'
        )
        return None
    return candidate


def _git_blob_sha(data: bytes) -> str:
    header = f'blob {len(data)}\0'.encode('ascii')
    return hashlib.sha1(header + data).hexdigest()


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


def _behavior_module_inventory(
    errors: list[str],
    manifest: dict[str, Any],
    repo_root: Path,
    approved_source_roots: list[Path],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    manifest_rel = manifest.get('behavior_module_manifest')
    if not isinstance(manifest_rel, str) or not manifest_rel:
        errors.append('Missing behavior_module_manifest')
        return [], [], []
    manifest_path = _canonical_source_path(
        errors,
        repo_root,
        approved_source_roots,
        'behavior_module_manifest',
        manifest_rel,
    )
    if manifest_path is None:
        return [], [], []
    try:
        module_manifest = _load_json(manifest_path)
    except ValueError as exc:
        errors.append(str(exc))
        return [], [], []
    if module_manifest.get('schema') != 'dcoir.agent_runtime.behavior_modules.v1':
        errors.append('Unsupported behavior module manifest schema')
    if module_manifest.get('source_contract') != manifest_path.parent.joinpath(
        'Shared_Agent_Source_Manifest.json'
    ).relative_to(repo_root).as_posix():
        errors.append('Behavior module manifest points to the wrong shared source contract')
    modules = module_manifest.get('modules')
    if not isinstance(modules, list):
        errors.append('Behavior module manifest modules must be an array')
        return [], [], []

    normalized: list[dict[str, Any]] = []
    module_ids: list[str] = []
    source_paths: list[str] = []
    output_paths: list[str] = []
    prime_outputs: list[str] = []
    specialist_outputs: list[str] = []
    canonical_root_value = module_manifest.get('canonical_behavior_root')
    canonical_root = _canonical_source_path(
        errors,
        repo_root,
        approved_source_roots,
        'canonical_behavior_root',
        canonical_root_value,
    ) if isinstance(canonical_root_value, str) else None
    if canonical_root is None:
        errors.append('Behavior module manifest lacks a valid canonical_behavior_root')

    for module in modules:
        if not isinstance(module, dict):
            errors.append('Behavior module manifest contains a non-object')
            continue
        module_id = module.get('id')
        source_path = module.get('source_path')
        kind = module.get('kind')
        if not isinstance(module_id, str) or not module_id:
            errors.append('Behavior module lacks an id')
            continue
        module_ids.append(module_id)
        if not isinstance(source_path, str):
            errors.append(f'{module_id} lacks a source_path')
            continue
        source_paths.append(source_path)
        source_candidate = _canonical_source_path(
            errors,
            repo_root,
            approved_source_roots,
            module_id,
            source_path,
        )
        if (
            source_candidate is not None
            and canonical_root is not None
            and not source_candidate.is_relative_to(canonical_root)
        ):
            errors.append(f'{module_id} source is outside canonical_behavior_root')
        declared_sha = module.get('sha256')
        if source_candidate is not None and source_candidate.is_file():
            actual_sha = hashlib.sha256(source_candidate.read_bytes()).hexdigest()
            if declared_sha != actual_sha:
                errors.append(
                    f'{module_id} source sha256 mismatch: '
                    f'expected {declared_sha}, got {actual_sha}'
                )
        else:
            errors.append(f'Missing canonical behavior module source: {source_path}')

        projections = module.get('projections')
        projection = (
            projections.get('gemini_dcoir_agent')
            if isinstance(projections, dict)
            else None
        )
        if not isinstance(projection, dict):
            errors.append(f'{module_id} lacks a Gemini projection')
            continue
        output_path = projection.get('output_path')
        if not isinstance(output_path, str):
            errors.append(f'{module_id} lacks a Gemini output_path')
            continue
        output_paths.append(output_path)
        output_candidate = _canonical_source_path(
            errors,
            repo_root,
            approved_source_roots,
            f'{module_id} Gemini output',
            output_path,
        )
        if projection.get('projection_mode') != 'byte_identity':
            errors.append(f'{module_id} Gemini projection is not byte_identity')
        if projection.get('sha256') != declared_sha:
            errors.append(f'{module_id} source and projection sha256 differ')
        if (
            source_candidate is not None
            and source_candidate.is_file()
            and output_candidate is not None
            and output_candidate.is_file()
            and source_candidate.read_bytes() != output_candidate.read_bytes()
        ):
            errors.append(f'{module_id} Gemini adapter output has drifted')
        elif output_candidate is not None and not output_candidate.is_file():
            errors.append(f'Missing Gemini behavior adapter output: {output_path}')
        if kind == 'prime_chunk':
            prime_outputs.append(output_path)
        elif kind == 'specialist':
            specialist_outputs.append(output_path)
        else:
            errors.append(f'{module_id} has unsupported behavior module kind: {kind}')
        normalized.append(module)

    for label, values in (
        ('behavior module id', module_ids),
        ('behavior module source', source_paths),
        ('Gemini behavior adapter output', output_paths),
    ):
        for duplicate in _duplicates(values):
            errors.append(f'Duplicate {label}: {duplicate}')
    return normalized, prime_outputs, specialist_outputs


def validate_contract(
    manifest_path: Path,
    matrix_path: Path,
    repo_root: Path,
) -> tuple[list[str], dict[str, int]]:
    repo_root = repo_root.resolve()
    errors: list[str] = []
    try:
        manifest = _load_json(manifest_path)
        matrix_ids, matrix_tables, matrix_parse_errors = _matrix_contract(matrix_path)
        (
            expected_prime,
            expected_sub_agents,
            expected_knowledge,
            expected_gemini_authority,
        ) = _expected_inventory(repo_root)
    except ValueError as exc:
        return [str(exc)], {}

    if manifest.get('schema') != 'dcoir.agent_runtime.source_contract.v1':
        errors.append('Unsupported or missing source-contract schema')
    if not manifest.get('source_contract_version'):
        errors.append('Missing source_contract_version')
    errors.extend(matrix_parse_errors)
    approved_source_roots = _approved_source_roots(errors, manifest, repo_root)
    (
        behavior_modules,
        mapped_prime_outputs,
        mapped_specialist_outputs,
    ) = _behavior_module_inventory(
        errors, manifest, repo_root, approved_source_roots
    )

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
        applies_to = item.get('applies_to')
        if isinstance(dispositions, dict) and isinstance(applies_to, list):
            for target_id in ('openai_dcoir_analyst',):
                if target_id not in applies_to:
                    continue
                disposition = dispositions.get(target_id)
                target = target_by_id.get(target_id)
                if not isinstance(disposition, dict) or not isinstance(target, dict):
                    errors.append(f'{item_id} lacks a valid {target_id} disposition')
                    continue
                if disposition.get('owner') != target.get('output_owner'):
                    errors.append(
                        f'{item_id} {target_id} disposition owner disagrees with target'
                    )
                generated_outputs = target.get('generated_outputs')
                if (
                    not isinstance(generated_outputs, list)
                    or disposition.get('generated_output') not in generated_outputs
                ):
                    errors.append(
                        f'{item_id} {target_id} disposition output disagrees with target'
                    )
        if isinstance(source_path, str) and item.get('canonical') is True:
            candidate = _canonical_source_path(
                errors, repo_root, approved_source_roots, str(item_id), source_path
            )
            if (
                candidate is not None
                and not candidate.is_file()
                and source_path not in stale_paths
            ):
                errors.append(f'Missing canonical source path without stale disposition: {source_path}')

    behavior_by_id = {
        item.get('id'): item
        for item in behaviors
        if isinstance(item, dict) and isinstance(item.get('id'), str)
    }
    module_ids = {
        module.get('id')
        for module in behavior_modules
        if isinstance(module.get('id'), str)
    }
    expected_module_ids = {
        item_id
        for item_id in behavior_by_id
        if item_id.startswith('prime.chunk.') or item_id.startswith('sub_agent.')
    }
    if module_ids != expected_module_ids:
        errors.append(
            'Behavior module/source-contract id disagreement; '
            f'missing={sorted(expected_module_ids - module_ids)}, '
            f'extra={sorted(module_ids - expected_module_ids)}'
        )
    for module in behavior_modules:
        module_id = module.get('id')
        behavior_item = behavior_by_id.get(module_id)
        if behavior_item is None:
            continue
        if behavior_item.get('source_path') != module.get('source_path'):
            errors.append(f'{module_id} source path disagrees with behavior module manifest')
        if behavior_item.get('authority_class') != 'canonical_shared_behavior':
            errors.append(f'{module_id} must use canonical_shared_behavior authority')

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
            candidate = _canonical_source_path(
                errors, repo_root, approved_source_roots, str(item_id), source_path
            )
            if candidate is not None and not candidate.is_file():
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
        target_projection_sources = item.get('target_projection_sources')
        applicable_openai = {
            target_id
            for target_id in OPENAI_TARGET_IDS
            if target_id in (
                item.get('applies_to')
                if isinstance(item.get('applies_to'), list)
                else []
            )
        }
        if item.get('content_class') == 'split':
            if (
                not isinstance(target_projection_sources, dict)
                or set(target_projection_sources) != applicable_openai
            ):
                errors.append(
                    f'{item_id} split source must define projection sources for '
                    f'{sorted(applicable_openai)}'
                )
            else:
                for target_id, projection_source in target_projection_sources.items():
                    if not isinstance(projection_source, dict):
                        errors.append(
                            f'{item_id} has a malformed projection source for {target_id}'
                        )
                        continue
                    projection_id = projection_source.get('id')
                    projection_path = projection_source.get('source_path')
                    if not isinstance(projection_id, str) or not projection_id:
                        errors.append(
                            f'{item_id} projection source for {target_id} lacks an id'
                        )
                    if not isinstance(projection_path, str):
                        errors.append(
                            f'{item_id} projection source for {target_id} lacks a path'
                        )
                        continue
                    projection_candidate = _canonical_source_path(
                        errors,
                        repo_root,
                        approved_source_roots,
                        f'{item_id}:{target_id}',
                        projection_path,
                    )
                    if projection_candidate is None or not projection_candidate.is_file():
                        errors.append(
                            f'Missing canonical projection source: {projection_path}'
                        )
                        continue
                    projection_content = projection_candidate.read_bytes()
                    actual_blob = _git_blob_sha(projection_content)
                    if projection_source.get('source_git_blob_sha') != actual_blob:
                        errors.append(
                            f'{item_id} projection source Git blob SHA mismatch for '
                            f'{target_id}'
                        )
                    if projection_source.get('provider_neutral_required') is not True:
                        errors.append(
                            f'{item_id} projection source for {target_id} must require '
                            'provider-neutral content'
                        )
                    lowered = projection_content.decode(
                        'utf-8', errors='replace'
                    ).casefold()
                    leaked = [
                        term
                        for term in PROVIDER_SPECIFIC_PROJECTION_TERMS
                        if term in lowered
                    ]
                    if leaked:
                        errors.append(
                            f'{item_id} projection source for {target_id} contains '
                            f'provider-specific terms: {leaked}'
                        )
        elif target_projection_sources is not None:
            errors.append(
                f'{item_id} target_projection_sources requires split content_class'
            )
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

    _check_exact_source_coverage(
        errors, expected_prime, mapped_prime_outputs, 'Prime adapter'
    )
    _check_exact_source_coverage(
        errors, expected_sub_agents, mapped_specialist_outputs, 'Sub-agent adapter'
    )
    _check_exact_source_coverage(errors, expected_knowledge, mapped_knowledge_paths, 'Knowledge')
    declared_gemini_authority = manifest.get('gemini_behavioral_authority_sources')
    if declared_gemini_authority != expected_gemini_authority:
        errors.append(
            'Shared contract Gemini authority sources disagree with the live Gemini '
            'bundle manifest'
        )
    if any(path in stale_paths for path in expected_gemini_authority):
        errors.append('Live Gemini behavioral authority still contains a retired source')

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

    target_rows = []
    for target in targets:
        if not isinstance(target, dict) or not isinstance(target.get('id'), str):
            continue
        runtime_dependent = target.get('runtime_dependent_capabilities', [])
        capabilities = target.get('capabilities')
        if not isinstance(capabilities, dict):
            capabilities = {}
        live_lookup = (
            'Runtime-dependent; never assumed'
            if isinstance(runtime_dependent, list) and 'web_search' in runtime_dependent
            else 'Unavailable'
        )
        target_rows.append(
            {
                'Target': target['id'],
                'Output owner': str(target.get('output_owner', '')),
                'Instruction mode': str(target.get('instruction_mode', '')),
                'Knowledge mode': str(target.get('knowledge_mode', '')),
                'Current live lookup': live_lookup,
                'Current external actions': (
                    'Unavailable unless returned execution evidence exists'
                    if capabilities.get('actions') is False
                    else 'Available'
                ),
            }
        )
    _compare_matrix_rows(
        errors,
        'Target Capability Boundary',
        target_rows,
        matrix_tables['Target Capability Boundary'],
        'Target',
    )

    behavior_rows = []
    behavior_control_rows = []
    for item in behaviors:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            continue
        dispositions = item.get('target_dispositions', {})
        if not isinstance(dispositions, dict):
            dispositions = {}
        target_modes = {}
        for target_id in EXPECTED_TARGET_IDS:
            target_disposition = dispositions.get(target_id)
            target_modes[target_id] = (
                target_disposition.get('mode', '')
                if isinstance(target_disposition, dict)
                else ''
            )
        applies_to = item.get('applies_to')
        dependencies = item.get('downstream_dependencies')
        validation_classes = item.get('validation_classes')
        behavior_rows.append(
            {
                'Stable id': item['id'],
                'Source / section': (
                    f"{item.get('source_path', '')} / {item.get('source_section', '')}"
                ),
                'Class': str(item.get('content_class', '')),
                'Gemini': str(target_modes['gemini_dcoir_agent']),
                'OpenAI DCOIR': str(target_modes['openai_dcoir_analyst']),
                'OpenAI USB': str(target_modes['openai_usb_reporting']),
                'Responsibility': str(item.get('responsibility', '')),
            }
        )
        behavior_control_rows.append(
            {
                'Stable id': item['id'],
                'Applies to': ', '.join(
                    applies_to if isinstance(applies_to, list) else []
                ),
                'Provider differences': str(
                    item.get('provider_specific_differences', '')
                ),
                'Dependencies': '; '.join(
                    dependencies if isinstance(dependencies, list) else []
                ),
                'Validation': '; '.join(
                    validation_classes if isinstance(validation_classes, list) else []
                ),
                'Reverse sync': (
                    'Required'
                    if item.get('reverse_reconciliation_required') is True
                    else 'Not required'
                ),
                'Decision': (
                    'None'
                    if item.get('unresolved_operator_decision') is None
                    else str(item.get('unresolved_operator_decision'))
                ),
            }
        )
    _compare_matrix_rows(
        errors,
        'Behavior Ownership',
        behavior_rows,
        matrix_tables['Behavior Ownership'],
        'Stable id',
    )
    _compare_matrix_rows(
        errors,
        'Behavior Control Details',
        behavior_control_rows,
        matrix_tables['Behavior Control Details'],
        'Stable id',
    )

    knowledge_rows = []
    for item in knowledge:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            continue
        boundary_rule = (
            'Preserve ordered source boundary and SHA-256; '
            if item.get('source_boundary_hash_required') is True
            else ''
        ) + str(item.get('duplicate_or_overlap_notes', ''))
        gemini_disposition = str(item.get('gemini_attachment_disposition', ''))
        if gemini_disposition == 'include_direct_from_canonical_source':
            gemini_disposition = 'include'
        knowledge_rows.append(
            {
                'Stable id': item['id'],
                'Canonical source': str(item.get('source_path', '')),
                'Class': str(item.get('content_class', '')),
                'Gemini attachment': gemini_disposition,
                'DCOIR projection': str(
                    item.get('openai_dcoir_projection_group') or 'excluded'
                ),
                'USB projection': str(
                    item.get('openai_usb_projection_group') or 'excluded'
                ),
                'Boundary/hash and overlap rule': boundary_rule,
            }
        )
    _compare_matrix_rows(
        errors,
        'Knowledge Disposition',
        knowledge_rows,
        matrix_tables['Knowledge Disposition'],
        'Stable id',
    )

    stale_rows = []
    for item in stale:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str):
            continue
        stale_rows.append(
            {
                'Stable id': item['id'],
                'Missing path': str(item.get('source_path', '')),
                'Status': str(item.get('status', '')),
                'Replacement authority': str(item.get('replacement_authority', '')),
                'Runtime action': str(item.get('runtime_cleanup', '')),
            }
        )
    _compare_matrix_rows(
        errors,
        'Stale Behavioral Authority References',
        stale_rows,
        matrix_tables['Stale Behavioral Authority References'],
        'Stable id',
    )

    stats = {
        'targets': len(targets),
        'behavior_items': len(behaviors),
        'prime_chunks': len(expected_prime),
        'sub_agents': len(expected_sub_agents),
        'knowledge_items': len(knowledge),
        'stale_references': len(stale),
        'behavior_modules': len(behavior_modules),
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
