#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = 'dcoir.agent_runtime.openai_dcoir_adapter.v1'
SOURCE_SCHEMA = 'dcoir.agent_runtime.source_contract.v1'
BEHAVIOR_SCHEMA = 'dcoir.agent_runtime.behavior_modules.v1'
KNOWLEDGE_SCHEMA = 'dcoir.agent_runtime.knowledge_projection.target.v1'
TARGET_ID = 'openai_dcoir_analyst'
EXPECTED_EDITOR_NAME = 'AFRICOM DCOIR Analyst'
EXPECTED_RUNTIME_MODEL = 'GPT-5.4'
EXPECTED_KNOWLEDGE_FILES = 7
EXPECTED_BEHAVIOR_ITEMS = 30
EXPECTED_CASES = 16
EXPECTED_PATHS = {
    'source_contract': 'project_sources/agent_runtime/Shared_Agent_Source_Manifest.json',
    'behavior_module_manifest': 'project_sources/agent_runtime/Behavior_Module_Manifest.json',
    'knowledge_projection_manifest': 'project_sources/agent_runtime/Knowledge_Projection_Manifest.json',
    'knowledge_target_manifest': (
        'project_sources/agent_runtime/generated/knowledge/'
        'openai_dcoir_analyst/manifest.json'
    ),
    'canonical_instructions_source': (
        'project_sources/agent_runtime/provider_adapters/'
        'openai_dcoir_analyst/Instructions.md'
    ),
    'behavioral_cases': (
        'project_sources/agent_runtime/provider_adapters/'
        'openai_dcoir_analyst/Behavioral_Contract_Cases.json'
    ),
    'generated_root': (
        'project_sources/agent_runtime/generated/packages/openai_dcoir_analyst'
    ),
}
EXPECTED_OUTPUTS = {
    'instructions': f"{EXPECTED_PATHS['generated_root']}/Instructions.md",
    'configuration': f"{EXPECTED_PATHS['generated_root']}/GPT_Configuration.json",
    'package_manifest': f"{EXPECTED_PATHS['generated_root']}/manifest.json",
}
SECTION_HEADINGS = {
    'identity_scope': '## Identity and scope',
    'authority_evidence_lanes': '## Authority and evidence lanes',
    'analysis_workflow': '## Analysis workflow',
    'queries_commands_collection': '## Queries, commands, and collection',
    'ioc_encoded_content': '## IOC and encoded content',
    'conclusions_output': '## Conclusions and output',
    'capability_boundaries': '## Capability boundaries',
}
PROVIDER_TOPOLOGY_LEAKS = (
    'you are the prime agent',
    'gemini enterprise prime agent',
    'route intake to session readiness',
    'route to query planner',
    'handoff to sub-agent',
    'sub-agent execution',
)
REQUIRED_DISABLED_CAPABILITIES = (
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
)
REQUIRED_STATIC_MARKERS = (
    'user-provided evidence',
    'uploaded file or artifact evidence',
    'copied query result',
    'DCOIR Collector output',
    'returned public-source material',
    'tool-returned result',
    'unavailable or unverified source state',
    'planned action:',
    'requested action:',
    'executed action:',
    'returned result:',
    'Only a returned result authorizes completion wording',
    'IOC enrichment is optional and additive',
    'Silently omit unavailable or failed enrichment',
    'separate AFRICOM USB Reporting GPT',
)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


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


def _read_bytes(path: Path, label: str, errors: list[str]) -> bytes:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        errors.append(f'Missing {label}: {path}')
        return b''


def _behavior_snapshot(
    repo_root: Path,
    source_contract: dict[str, Any],
    behavior_manifest: dict[str, Any],
    coverage: list[dict[str, Any]],
    errors: list[str],
) -> tuple[list[dict[str, Any]], str]:
    items = source_contract.get('behavior_items')
    modules = behavior_manifest.get('modules')
    if not isinstance(items, list) or not isinstance(modules, list):
        errors.append('Behavior source inventories must be arrays')
        return [], _sha256(_json_bytes([]))
    applicable = [
        item for item in items
        if isinstance(item, dict)
        and TARGET_ID in (
            item.get('applies_to') if isinstance(item.get('applies_to'), list) else []
        )
    ]
    module_by_id = {
        module.get('id'): module for module in modules if isinstance(module, dict)
    }
    coverage_ids = [entry.get('id') for entry in coverage if isinstance(entry, dict)]
    expected_ids = [item.get('id') for item in applicable]
    for duplicate in _duplicates([value for value in coverage_ids if isinstance(value, str)]):
        errors.append(f'Duplicate behavior coverage id: {duplicate}')
    if coverage_ids != expected_ids:
        errors.append(
            'Behavior coverage must exactly match source-contract order: '
            f'{coverage_ids} != {expected_ids}'
        )
    if len(expected_ids) != EXPECTED_BEHAVIOR_ITEMS:
        errors.append(
            f'Expected {EXPECTED_BEHAVIOR_ITEMS} applicable behavior items, '
            f'got {len(expected_ids)}'
        )
    snapshot: list[dict[str, Any]] = []
    for item, coverage_entry in zip(applicable, coverage):
        item_id = item.get('id')
        source_path_value = item.get('source_path')
        source_path = _resolve_repo_path(
            repo_root, source_path_value, f'{item_id} source_path', errors
        )
        if source_path is None:
            continue
        content = _read_bytes(source_path, f'behavior source {item_id}', errors)
        actual_sha = _sha256(content)
        module = module_by_id.get(item_id)
        if module is None:
            errors.append(f'Behavior module manifest lacks {item_id}')
        else:
            if module.get('source_path') != source_path_value:
                errors.append(f'Behavior path disagreement for {item_id}')
            if module.get('sha256') != actual_sha:
                errors.append(f'Behavior source hash drift for {item_id}')
        sections = coverage_entry.get('sections') if isinstance(coverage_entry, dict) else None
        if not isinstance(sections, list) or not sections or not all(
            isinstance(section, str) and section in SECTION_HEADINGS for section in sections
        ):
            errors.append(f'{item_id} has invalid instruction section coverage')
            sections = []
        snapshot.append(
            {
                'id': item_id,
                'source_path': source_path_value,
                'sha256': actual_sha,
                'sections': sections,
            }
        )
    return snapshot, _sha256(_json_bytes(snapshot))


def _validate_instructions(
    instructions: bytes,
    manifest: dict[str, Any],
    cases: dict[str, Any],
    errors: list[str],
) -> list[str]:
    if cases.get('schema') != (
        'dcoir.agent_runtime.openai_dcoir_behavioral_cases.v1'
    ):
        errors.append('Unexpected behavioral cases schema')
    if cases.get('target_id') != TARGET_ID:
        errors.append('Behavioral cases have the wrong target_id')
    if cases.get('live_model_evidence') is not False:
        errors.append('Offline behavioral cases must not claim live model evidence')
    try:
        text = instructions.decode('utf-8')
    except UnicodeDecodeError:
        errors.append('Canonical Instructions must be UTF-8')
        return []
    ceiling = manifest.get('instruction_character_ceiling')
    if type(ceiling) is not int or ceiling <= 0:
        errors.append('instruction_character_ceiling must be a positive integer')
    elif len(text) > ceiling:
        errors.append(f'Instructions exceed character ceiling: {len(text)} > {ceiling}')
    for section_id, heading in SECTION_HEADINGS.items():
        if text.count(heading) != 1:
            errors.append(f'Instructions must contain one {section_id} heading')
    section_positions = [text.find(heading) for heading in SECTION_HEADINGS.values()]
    if any(position < 0 for position in section_positions) or section_positions != sorted(
        section_positions
    ):
        errors.append('Instruction sections must remain in the governed order')
    for marker in REQUIRED_STATIC_MARKERS:
        if marker not in text:
            errors.append(f'Instructions lack required static contract marker: {marker}')
    lower = text.lower()
    for leak in PROVIDER_TOPOLOGY_LEAKS:
        if leak in lower:
            errors.append(f'Provider-topology leakage in Instructions: {leak}')
    case_items = cases.get('cases')
    if not isinstance(case_items, list):
        errors.append('Behavioral cases must be an array')
        return []
    case_ids: list[str] = []
    for case in case_items:
        if not isinstance(case, dict):
            errors.append('Behavioral cases contain a non-object entry')
            continue
        case_id = case.get('id')
        if not isinstance(case_id, str) or not case_id:
            errors.append('Behavioral case lacks an id')
            continue
        case_ids.append(case_id)
        for field in ('scenario', 'expected_behavior'):
            value = case.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f'{case_id} lacks a non-empty {field}')
        markers = case.get('required_markers')
        if not isinstance(markers, list) or not markers or not all(
            isinstance(marker, str) and marker for marker in markers
        ):
            errors.append(f'{case_id} has invalid required_markers')
            continue
        for marker in markers:
            if marker not in text:
                errors.append(f'{case_id} missing Instructions marker: {marker}')
    for duplicate in _duplicates(case_ids):
        errors.append(f'Duplicate behavioral case id: {duplicate}')
    if len(case_ids) != EXPECTED_CASES:
        errors.append(f'Expected {EXPECTED_CASES} behavioral cases, got {len(case_ids)}')
    return case_ids


def _knowledge_files(
    repo_root: Path,
    target_manifest: dict[str, Any],
    errors: list[str],
) -> list[dict[str, Any]]:
    if target_manifest.get('schema') != KNOWLEDGE_SCHEMA:
        errors.append('Unexpected DCOIR knowledge target manifest schema')
    if target_manifest.get('target_id') != TARGET_ID:
        errors.append('Knowledge target manifest has the wrong target_id')
    projections = target_manifest.get('projections')
    if not isinstance(projections, list):
        errors.append('Knowledge target projections must be an array')
        return []
    if len(projections) != EXPECTED_KNOWLEDGE_FILES:
        errors.append(
            f'Expected {EXPECTED_KNOWLEDGE_FILES} DCOIR knowledge files, '
            f'got {len(projections)}'
        )
    ceiling = target_manifest.get('strict_file_count_ceiling')
    if type(ceiling) is not int or len(projections) > ceiling or ceiling > 20:
        errors.append('Knowledge projection count or ceiling is invalid')
    knowledge_root = (
        repo_root / 'project_sources/agent_runtime/generated/knowledge/openai_dcoir_analyst'
    ).resolve()
    result: list[dict[str, Any]] = []
    orders = [entry.get('order') for entry in projections if isinstance(entry, dict)]
    if orders != list(range(len(projections))):
        errors.append('Knowledge projection order must be contiguous')
    for entry in projections:
        if not isinstance(entry, dict):
            errors.append('Knowledge projections contain a non-object entry')
            continue
        path = _resolve_repo_path(
            repo_root,
            entry.get('output_path'),
            f"knowledge projection {entry.get('id')}",
            errors,
            knowledge_root,
        )
        if path is None:
            continue
        if path.is_symlink():
            errors.append(f'Knowledge projection must not be a symlink: {path}')
            continue
        content = _read_bytes(path, 'knowledge projection', errors)
        actual_sha = _sha256(content)
        if actual_sha != entry.get('sha256') or len(content) != entry.get('bytes'):
            errors.append(f"Knowledge projection drift: {entry.get('id')}")
        result.append(
            {
                'id': entry.get('id'),
                'order': entry.get('order'),
                'path': entry.get('output_path'),
                'sha256': actual_sha,
                'bytes': len(content),
            }
        )
    return result


def build_package(
    repo_root: Path, manifest_path: Path, check: bool
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    try:
        manifest = _load_json(manifest_path)
    except ValueError as exc:
        return [str(exc)], {'success': False, 'errors': [str(exc)]}
    if manifest.get('schema') != SCHEMA:
        errors.append(f'Unexpected adapter schema: {manifest.get("schema")}')
    if manifest.get('target_id') != TARGET_ID:
        errors.append(f'Unexpected adapter target: {manifest.get("target_id")}')
    for key, expected in EXPECTED_PATHS.items():
        if manifest.get(key) != expected:
            errors.append(f'{key} must remain bound to {expected}')
    source_base_commit = manifest.get('source_base_commit')
    if not isinstance(source_base_commit, str) or re.fullmatch(
        r'[0-9a-f]{40}', source_base_commit
    ) is None:
        errors.append('source_base_commit must be a lowercase 40-character Git SHA')
    generated_root = _resolve_repo_path(
        repo_root,
        manifest.get('generated_root'),
        'generated_root',
        errors,
        repo_root / EXPECTED_PATHS['generated_root'],
    )
    if generated_root is None:
        generated_root = repo_root / '.invalid-openai-dcoir-generated-root'
    required_paths = {}
    for key in (
        'source_contract', 'behavior_module_manifest',
        'knowledge_projection_manifest', 'knowledge_target_manifest',
        'canonical_instructions_source', 'behavioral_cases',
    ):
        path = _resolve_repo_path(repo_root, manifest.get(key), key, errors)
        if path is not None:
            required_paths[key] = path
    try:
        source_contract = _load_json(required_paths['source_contract'])
        behavior_manifest = _load_json(required_paths['behavior_module_manifest'])
        knowledge_projection_manifest = _load_json(
            required_paths['knowledge_projection_manifest']
        )
        target_manifest = _load_json(required_paths['knowledge_target_manifest'])
        cases = _load_json(required_paths['behavioral_cases'])
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
        return errors, {'success': False, 'errors': errors}
    if source_contract.get('schema') != SOURCE_SCHEMA:
        errors.append('Unexpected shared source contract schema')
    if behavior_manifest.get('schema') != BEHAVIOR_SCHEMA:
        errors.append('Unexpected behavior module manifest schema')
    source_contract_sha = _sha256(required_paths['source_contract'].read_bytes())
    if source_contract.get('openai_dcoir_adapter_manifest') != (
        'project_sources/agent_runtime/provider_adapters/'
        'openai_dcoir_analyst/Adapter_Manifest.json'
    ):
        errors.append('Shared source contract points to the wrong OpenAI DCOIR adapter')
    if knowledge_projection_manifest.get('schema') != (
        'dcoir.agent_runtime.knowledge_projection.v1'
    ):
        errors.append('Unexpected knowledge projection manifest schema')
    knowledge_target_config = knowledge_projection_manifest.get('targets', {}).get(
        TARGET_ID
    )
    if not isinstance(knowledge_target_config, dict):
        errors.append('Knowledge projection manifest lacks the OpenAI DCOIR target')
    else:
        if knowledge_target_config.get('target_manifest_path') != manifest.get(
            'knowledge_target_manifest'
        ):
            errors.append('Knowledge target manifest path disagrees across contracts')
        if knowledge_target_config.get('expected_projection_count') != (
            EXPECTED_KNOWLEDGE_FILES
        ):
            errors.append('Knowledge target projection count disagrees across contracts')
    if target_manifest.get('source_contract') != manifest.get('source_contract'):
        errors.append('Knowledge target points to the wrong shared source contract')
    if target_manifest.get('source_contract_sha256') != source_contract_sha:
        errors.append('Knowledge target source-contract hash drift')
    targets = source_contract.get('targets')
    target = next(
        (item for item in targets if isinstance(item, dict) and item.get('id') == TARGET_ID),
        None,
    ) if isinstance(targets, list) else None
    if not isinstance(target, dict):
        errors.append('Shared source contract lacks the OpenAI DCOIR target')
    else:
        if target.get('provider') != 'openai_webui_bedrock_hosted':
            errors.append('OpenAI DCOIR provider drift')
        if target.get('runtime_model') != EXPECTED_RUNTIME_MODEL:
            errors.append('OpenAI DCOIR runtime model drift')
        if target.get('instruction_mode') != 'static_instructions':
            errors.append('OpenAI DCOIR instruction mode drift')
        if target.get('knowledge_mode') != 'static_knowledge':
            errors.append('OpenAI DCOIR knowledge mode drift')
        if target.get('output_owner') != (
            'project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py'
        ):
            errors.append('OpenAI DCOIR output owner drift')
    capabilities = manifest.get('capabilities')
    if not isinstance(capabilities, dict):
        errors.append('Adapter capabilities must be an object')
        capabilities = {}
    if set(capabilities) != set(REQUIRED_DISABLED_CAPABILITIES):
        errors.append('Adapter capabilities must contain exactly the governed keys')
    target_capabilities = target.get('capabilities') if isinstance(target, dict) else {}
    if not isinstance(target_capabilities, dict) or set(target_capabilities) != set(
        REQUIRED_DISABLED_CAPABILITIES
    ):
        errors.append('Source contract capabilities must contain exactly the governed keys')
    for capability in REQUIRED_DISABLED_CAPABILITIES:
        if capabilities.get(capability) is not False:
            errors.append(f'Unsupported capability must remain false: {capability}')
        if not isinstance(target, dict) or target.get('capabilities', {}).get(capability) is not False:
            errors.append(f'Source contract target capability drift: {capability}')
    coverage = manifest.get('coverage')
    if not isinstance(coverage, list):
        errors.append('Adapter coverage must be an array')
        coverage = []
    behavior_snapshot, snapshot_sha = _behavior_snapshot(
        repo_root, source_contract, behavior_manifest, coverage, errors
    )
    if snapshot_sha != manifest.get('behavior_source_snapshot_sha256'):
        errors.append(
            'Behavior source snapshot drift: expected '
            f"{manifest.get('behavior_source_snapshot_sha256')}, got {snapshot_sha}"
        )
    instruction_path = required_paths.get('canonical_instructions_source')
    instructions = _read_bytes(instruction_path, 'canonical Instructions', errors) if instruction_path else b''
    case_ids = _validate_instructions(instructions, manifest, cases, errors)
    knowledge_files = _knowledge_files(repo_root, target_manifest, errors)
    editor = manifest.get('editor')
    if not isinstance(editor, dict):
        errors.append('Adapter editor configuration must be an object')
        editor = {}
    if editor.get('name') != EXPECTED_EDITOR_NAME:
        errors.append(f'Editor name must remain {EXPECTED_EDITOR_NAME}')
    if not isinstance(editor.get('description'), str) or not editor.get(
        'description'
    ).strip():
        errors.append('Editor description must be a non-empty string')
    starters = editor.get('conversation_starters')
    if not isinstance(starters, list) or len(starters) != 4 or not all(
        isinstance(value, str) and value for value in starters
    ):
        errors.append('Exactly four non-empty conversation starters are required')
    elif len(set(starters)) != len(starters):
        errors.append('Conversation starters must be unique')
    configuration = {
        'schema': 'dcoir.agent_runtime.openai_webui_configuration.v1',
        'target_id': TARGET_ID,
        'name': editor.get('name'),
        'description': editor.get('description'),
        'conversation_starters': starters,
        'runtime_model': target.get('runtime_model') if isinstance(target, dict) else None,
        'instructions_file': manifest.get('generated_outputs', {}).get('instructions'),
        'capabilities': capabilities,
        'knowledge_files': knowledge_files,
    }
    source_hashes: dict[str, dict[str, Any]] = {}
    for key, path in required_paths.items():
        content = _read_bytes(path, f'{key} contract source', errors)
        source_hashes[key] = {
            'path': path.relative_to(repo_root).as_posix(),
            'sha256': _sha256(content),
        }
    expected_files: dict[Path, bytes] = {}
    output_map = manifest.get('generated_outputs')
    if not isinstance(output_map, dict):
        errors.append('generated_outputs must be an object')
        output_map = {}
    for key, expected in EXPECTED_OUTPUTS.items():
        if output_map.get(key) != expected:
            errors.append(f'generated {key} must remain bound to {expected}')
    if isinstance(target, dict) and target.get('generated_outputs') != list(
        EXPECTED_OUTPUTS.values()
    ):
        errors.append('Source contract generated outputs disagree with the adapter')
    output_paths: dict[str, Path] = {}
    for key in ('instructions', 'configuration', 'package_manifest'):
        path = _resolve_repo_path(
            repo_root, output_map.get(key), f'generated {key}', errors, generated_root
        )
        if path is not None:
            output_paths[key] = path
    if 'instructions' in output_paths:
        expected_files[output_paths['instructions']] = instructions
    configuration_bytes = _json_bytes(configuration)
    if 'configuration' in output_paths:
        expected_files[output_paths['configuration']] = configuration_bytes
    package_manifest = {
        'schema': 'dcoir.agent_runtime.openai_dcoir_package.v1',
        'adapter_contract_version': manifest.get('adapter_contract_version'),
        'target_id': TARGET_ID,
        'source_base_commit': manifest.get('source_base_commit'),
        'source_contracts': source_hashes,
        'behavior_source_snapshot_sha256': snapshot_sha,
        'behavior_coverage_count': len(behavior_snapshot),
        'behavior_coverage': behavior_snapshot,
        'behavioral_case_count': len(case_ids),
        'behavioral_case_ids': case_ids,
        'instruction_character_count': len(instructions.decode('utf-8', errors='ignore')),
        'instruction_character_ceiling': manifest.get('instruction_character_ceiling'),
        'knowledge_file_count': len(knowledge_files),
        'strict_knowledge_file_ceiling': target_manifest.get('strict_file_count_ceiling'),
        'knowledge_files': knowledge_files,
        'generated_files': [
            {
                'path': output_map.get('instructions'),
                'sha256': _sha256(instructions),
                'bytes': len(instructions),
            },
            {
                'path': output_map.get('configuration'),
                'sha256': _sha256(configuration_bytes),
                'bytes': len(configuration_bytes),
            },
        ],
        'generated_outputs_are_canonical': False,
        'direct_target_edits_require_reverse_reconciliation': True,
        'live_webui_validation_performed': False,
    }
    if 'package_manifest' in output_paths:
        expected_files[output_paths['package_manifest']] = _json_bytes(package_manifest)
    expected_set = set(expected_files)
    actual_files: set[Path] = set()
    if generated_root.exists():
        for path in generated_root.rglob('*'):
            if path.is_symlink():
                errors.append(f'Generated package must not contain symlinks: {path}')
            elif path.is_file():
                actual_files.add(path.resolve())
    stale = sorted(
        path.relative_to(repo_root).as_posix()
        for path in actual_files - expected_set
    )
    if stale:
        errors.append(f'Stale generated package files: {stale}')
    if check:
        for path, expected in expected_files.items():
            try:
                actual = path.read_bytes()
            except FileNotFoundError:
                errors.append(f'Missing generated package file: {path.relative_to(repo_root)}')
                continue
            if actual != expected:
                errors.append(f'Generated package drift: {path.relative_to(repo_root)}')
    elif not errors:
        with tempfile.TemporaryDirectory(prefix='.openai-dcoir-', dir=repo_root) as temp_dir:
            temp_root = Path(temp_dir).resolve()
            for path, expected in expected_files.items():
                with tempfile.NamedTemporaryFile(dir=temp_root, delete=False) as staged:
                    staged.write(expected)
                    staged_path = Path(staged.name).resolve()
                if not staged_path.is_relative_to(temp_root):
                    errors.append('Generated package staging path escaped its root')
                    continue
                if staged_path.read_bytes() != expected:
                    errors.append('Generated package staging readback failed')
                    continue
                resolved_output = _resolve_repo_path(
                    repo_root,
                    path.relative_to(repo_root).as_posix(),
                    'generated package output',
                    errors,
                    generated_root,
                )
                if resolved_output is None:
                    continue
                resolved_output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(staged_path, resolved_output)
                if resolved_output.read_bytes() != expected:
                    errors.append(f'Generated package write readback failed: {resolved_output}')
    report = {
        'success': not errors,
        'action': 'check' if check else 'materialize',
        'target_id': TARGET_ID,
        'behavior_coverage_count': len(behavior_snapshot),
        'behavior_source_snapshot_sha256': snapshot_sha,
        'behavioral_case_count': len(case_ids),
        'knowledge_file_count': len(knowledge_files),
        'generated_file_count': len(expected_files),
        'errors': errors,
    }
    return errors, report


def main() -> int:
    default_repo = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo-root', default=str(default_repo))
    parser.add_argument(
        '--manifest',
        default=(
            'project_sources/agent_runtime/provider_adapters/'
            'openai_dcoir_analyst/Adapter_Manifest.json'
        ),
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--check', action='store_true')
    action.add_argument('--materialize', action='store_true')
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = repo_root / manifest_path
    errors, report = build_package(
        repo_root, manifest_path.resolve(), check=not args.materialize
    )
    print(json.dumps(report, indent=2), file=sys.stderr if errors else sys.stdout)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
