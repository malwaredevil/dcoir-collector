#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = 'dcoir.agent_runtime.release_parity_report.v1'
REPORT_VERSION = '1.0.1'
EXPECTED_TARGET_IDS = (
    'gemini_dcoir_agent',
    'openai_dcoir_analyst',
    'openai_usb_reporting',
)
SHARED_MANIFEST = Path('project_sources/agent_runtime/Shared_Agent_Source_Manifest.json')
BEHAVIOR_MANIFEST = Path('project_sources/agent_runtime/Behavior_Module_Manifest.json')
KNOWLEDGE_MANIFEST = Path('project_sources/agent_runtime/Knowledge_Projection_Manifest.json')
GEMINI_MANIFEST = Path('project_sources/gemini/bundle_source/Gemini_Bundle_Source_Manifest.json')
OPENAI_PACKAGE_MANIFESTS = {
    'openai_dcoir_analyst': Path(
        'project_sources/agent_runtime/generated/packages/openai_dcoir_analyst/manifest.json'
    ),
    'openai_usb_reporting': Path(
        'project_sources/agent_runtime/generated/packages/openai_usb_reporting/manifest.json'
    ),
}
MANUAL_GUIDE = Path('project_sources/agent_runtime/docs/Release_Parity_Deployment_Readback.md')
TARGET_CHECKS = (
    ('shared_source_contract', ('project_sources/agent_runtime/tools/validate_shared_agent_source_contract.py',)),
    ('gemini_behavior_adapter', ('project_sources/agent_runtime/tools/materialize_agent_behavior_adapters.py', '--check')),
    ('knowledge_projection', ('project_sources/agent_runtime/tools/project_agent_knowledge.py', '--check')),
    ('openai_dcoir_package', ('project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py', '--check')),
    ('openai_usb_package', ('project_sources/agent_runtime/tools/build_openai_usb_reporting.py', '--check')),
)
GUIDE_MARKERS = (
    '# Agent Release, Parity, Deployment, and Readback',
    '## Static release/parity gate',
    '## AFRICOM DCOIR Analyst manual deployment',
    '## AFRICOM USB Reporting manual deployment',
    '## Live readback evidence',
    '## Direct-target hotfix reverse reconciliation',
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        errors.append(f'Missing {label}: {path.as_posix()}')
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f'Invalid JSON in {label} {path.as_posix()}: {exc}')
        return {}
    if not isinstance(value, dict):
        errors.append(f'{label} must be a JSON object: {path.as_posix()}')
        return {}
    return value


def _resolve_repo_path(
    repo_root: Path,
    relative_value: str | Path,
    errors: list[str],
    label: str,
    *,
    require_exists: bool = True,
) -> Path | None:
    relative = Path(relative_value)
    if relative.is_absolute() or '..' in relative.parts:
        errors.append(f'{label} must be repository-relative without traversal: {relative_value}')
        return None
    root = repo_root.resolve()
    candidate = (root / relative).resolve(strict=False)
    if not candidate.is_relative_to(root):
        errors.append(f'{label} escapes repository root: {relative_value}')
        return None
    if require_exists and not candidate.exists():
        errors.append(f'Missing {label}: {relative.as_posix()}')
        return None
    return candidate


def _manifest_identity(
    repo_root: Path,
    relative: Path,
    errors: list[str],
    version_field: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = _resolve_repo_path(repo_root, relative, errors, f'manifest {relative.as_posix()}')
    if path is None:
        return {}, {'path': relative.as_posix(), 'sha256': None, 'version': None}
    value = _load_json(path, errors, relative.as_posix())
    return value, {
        'path': relative.as_posix(),
        'sha256': _sha256_file(path),
        'version': value.get(version_field),
        'schema': value.get('schema'),
    }


def resolve_source_commit(repo_root: Path, explicit: str | None = None) -> tuple[str, str]:
    if explicit:
        return explicit, 'explicit_argument'
    reviewed = os.environ.get('AGENT_RUNTIME_REVIEWED_HEAD_SHA')
    if reviewed:
        return reviewed, 'AGENT_RUNTIME_REVIEWED_HEAD_SHA'
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    if event_path:
        try:
            event = json.loads(Path(event_path).read_text(encoding='utf-8'))
            head_sha = event.get('pull_request', {}).get('head', {}).get('sha')
            if isinstance(head_sha, str) and head_sha:
                return head_sha, 'github_event_pull_request_head_sha'
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            print(
                'warning: unable to read pull_request head sha from '
                f'GITHUB_EVENT_PATH ({event_path}): {exc}',
                file=sys.stderr,
            )
    github_sha = os.environ.get('GITHUB_SHA')
    if github_sha:
        return github_sha, 'GITHUB_SHA'
    try:
        completed = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=repo_root, check=False,
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        completed = None
    if completed and completed.returncode == 0 and completed.stdout.strip():
        return completed.stdout.strip(), 'git_rev_parse_head'
    return 'unknown', 'unavailable'


def _target_check_results(repo_root: Path, run_checks: bool) -> tuple[list[dict[str, Any]], list[str]]:
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    for check_id, argv in TARGET_CHECKS:
        stable_command = 'python ' + ' '.join(argv)
        if not run_checks:
            results.append({'id': check_id, 'command': stable_command, 'result': 'not_run'})
            continue
        try:
            completed = subprocess.run(
                [sys.executable, *argv], cwd=repo_root, check=False,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, timeout=180,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f'Target check {check_id} could not run: {exc}')
            results.append({'id': check_id, 'command': stable_command, 'result': 'fail'})
            continue
        result = 'pass' if completed.returncode == 0 else 'fail'
        results.append({'id': check_id, 'command': stable_command, 'result': result})
        if completed.returncode != 0:
            errors.append(f'Target check failed: {check_id} (exit {completed.returncode})')
    return results, errors


def _canonical_behavior_counts(source_manifest: dict[str, Any], errors: list[str]) -> dict[str, int]:
    items = source_manifest.get('behavior_items')
    if not isinstance(items, list):
        errors.append('Shared source manifest behavior_items must be an array')
        return {target_id: 0 for target_id in EXPECTED_TARGET_IDS}
    counts = {target_id: 0 for target_id in EXPECTED_TARGET_IDS}
    for item in items:
        if not isinstance(item, dict) or item.get('canonical') is not True:
            continue
        applies_to = item.get('applies_to')
        if not isinstance(applies_to, list):
            errors.append(f"Behavior item {item.get('id', '<unknown>')} lacks applies_to array")
            continue
        for target_id in EXPECTED_TARGET_IDS:
            counts[target_id] += int(target_id in applies_to)
    return counts


def _governed_differences(source_targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item.get('id'): item for item in source_targets if isinstance(item, dict)}
    differences: list[dict[str, Any]] = []
    for dimension in ('provider', 'runtime_model', 'instruction_mode', 'knowledge_mode'):
        values = {target_id: by_id.get(target_id, {}).get(dimension) for target_id in EXPECTED_TARGET_IDS}
        if len({json.dumps(value, sort_keys=True) for value in values.values()}) > 1:
            differences.append({
                'classification': 'governed_provider_difference',
                'dimension': dimension,
                'values': values,
            })
    runtime_dependent = {
        target_id: by_id.get(target_id, {}).get('runtime_dependent_capabilities', [])
        for target_id in EXPECTED_TARGET_IDS
    }
    if any(runtime_dependent.values()):
        differences.append({
            'classification': 'governed_provider_difference',
            'dimension': 'runtime_dependent_capabilities',
            'values': runtime_dependent,
        })
    return differences


def _validate_guide(repo_root: Path, errors: list[str]) -> dict[str, Any]:
    path = _resolve_repo_path(repo_root, MANUAL_GUIDE, errors, 'manual deployment/readback guide')
    if path is None:
        return {'path': MANUAL_GUIDE.as_posix(), 'sha256': None, 'required_markers_present': False}
    text = path.read_text(encoding='utf-8')
    missing = [marker for marker in GUIDE_MARKERS if marker not in text]
    errors.extend(f'Manual deployment/readback guide missing required marker: {marker}' for marker in missing)
    return {
        'path': MANUAL_GUIDE.as_posix(),
        'sha256': _sha256_file(path),
        'required_markers_present': not missing,
    }


def _openai_target(
    target_id: str,
    target_contract: dict[str, Any],
    package_manifest: dict[str, Any],
    package_identity: dict[str, Any],
    knowledge_target: dict[str, Any],
    expected_behavior_count: int,
    errors: list[str],
) -> dict[str, Any]:
    if package_manifest.get('target_id') != target_id:
        errors.append(f"{target_id} package manifest target_id mismatch: {package_manifest.get('target_id')!r}")
    actual_behavior = package_manifest.get('behavior_coverage_count')
    if actual_behavior != expected_behavior_count:
        errors.append(
            f'{target_id} behavior coverage mismatch: expected {expected_behavior_count}, got {actual_behavior!r}'
        )
    expected_knowledge = knowledge_target.get('expected_projection_count')
    actual_knowledge = package_manifest.get('knowledge_file_count')
    if actual_knowledge != expected_knowledge:
        errors.append(
            f'{target_id} knowledge file count mismatch: expected {expected_knowledge!r}, got {actual_knowledge!r}'
        )
    if package_manifest.get('generated_outputs_are_canonical') is not False:
        errors.append(f'{target_id} package must declare generated_outputs_are_canonical=false')
    if package_manifest.get('direct_target_edits_require_reverse_reconciliation') is not True:
        errors.append(f'{target_id} package must require reverse reconciliation for direct edits')

    generated_files = package_manifest.get('generated_files')
    if not isinstance(generated_files, list):
        errors.append(f'{target_id} generated_files must be an array')
        generated_files = []
    knowledge_files = package_manifest.get('knowledge_files')
    if not isinstance(knowledge_files, list):
        errors.append(f'{target_id} knowledge_files must be an array')
        knowledge_files = []
    live_validated = package_manifest.get('live_webui_validation_performed') is True

    return {
        'id': target_id,
        'provider': target_contract.get('provider'),
        'runtime_model': target_contract.get('runtime_model'),
        'instruction_mode': target_contract.get('instruction_mode'),
        'knowledge_mode': target_contract.get('knowledge_mode'),
        'adapter_contract_version': package_manifest.get('adapter_contract_version'),
        'package_schema': package_manifest.get('schema'),
        'package_manifest': package_identity,
        'package_source_base_commit': package_manifest.get('source_base_commit'),
        'package_source_contract_sha256': package_manifest.get('source_contract_sha256'),
        'behavior': {
            'expected_canonical_items': expected_behavior_count,
            'reported_coverage_count': actual_behavior,
            'reported_source_snapshot_sha256': package_manifest.get('behavior_source_snapshot_sha256'),
        },
        'knowledge': {
            'expected_file_count': expected_knowledge,
            'reported_file_count': actual_knowledge,
            'strict_file_count_ceiling': package_manifest.get('strict_knowledge_file_ceiling'),
            'files': knowledge_files,
        },
        'generated_files': generated_files,
        'generated_file_count': len(generated_files),
        'capabilities': target_contract.get('capabilities', {}),
        'runtime_dependent_capabilities': target_contract.get('runtime_dependent_capabilities', []),
        'manual_deployment_required': package_manifest.get('manual_deployment_required', True) is True,
        'live_webui_validation_performed': live_validated,
        'deployment_readback_state': (
            'live_readback_recorded' if live_validated
            else 'manual_deployment_or_live_readback_pending'
        ),
    }


def _gemini_module_accounting(
    behavior_manifest: dict[str, Any], errors: list[str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    modules = behavior_manifest.get('modules')
    if not isinstance(modules, list):
        errors.append('Behavior module manifest modules must be an array')
        modules = []
    adapters = behavior_manifest.get('target_adapters')
    if not isinstance(adapters, dict):
        errors.append('Behavior module manifest target_adapters must be an object')
        adapters = {}
    adapter = adapters.get('gemini_dcoir_agent')
    if not isinstance(adapter, dict):
        errors.append('Behavior module manifest must define gemini_dcoir_agent target adapter')
        adapter = {}

    expected_prime = adapter.get('expected_prime_chunks')
    expected_specialists = adapter.get('expected_specialists')
    for name, value in (
        ('expected_prime_chunks', expected_prime),
        ('expected_specialists', expected_specialists),
    ):
        if not isinstance(value, int) or value < 0:
            errors.append(f'Gemini behavior adapter {name} must be a non-negative integer')

    expected_total = (
        expected_prime + expected_specialists
        if isinstance(expected_prime, int) and expected_prime >= 0
        and isinstance(expected_specialists, int) and expected_specialists >= 0
        else None
    )
    actual_prime = sum(
        1 for item in modules if isinstance(item, dict) and item.get('kind') == 'prime_chunk'
    )
    actual_specialists = sum(
        1 for item in modules if isinstance(item, dict) and item.get('kind') == 'specialist'
    )
    actual_total = len(modules)
    if expected_total is not None and actual_total != expected_total:
        errors.append(f'gemini_dcoir_agent behavior module mismatch: expected {expected_total}, got {actual_total}')
    if isinstance(expected_prime, int) and expected_prime >= 0 and actual_prime != expected_prime:
        errors.append(f'gemini_dcoir_agent prime chunk mismatch: expected {expected_prime}, got {actual_prime}')
    if isinstance(expected_specialists, int) and expected_specialists >= 0 and actual_specialists != expected_specialists:
        errors.append(
            f'gemini_dcoir_agent specialist mismatch: expected {expected_specialists}, got {actual_specialists}'
        )
    return modules, {
        'expected_module_count': expected_total,
        'reported_module_count': actual_total,
        'expected_prime_chunk_count': expected_prime,
        'reported_prime_chunk_count': actual_prime,
        'expected_specialist_count': expected_specialists,
        'reported_specialist_count': actual_specialists,
    }


def _gemini_target(
    target_contract: dict[str, Any],
    behavior_manifest: dict[str, Any],
    gemini_manifest: dict[str, Any],
    gemini_identity: dict[str, Any],
    knowledge_target: dict[str, Any],
    expected_behavior_count: int,
    errors: list[str],
) -> dict[str, Any]:
    modules, module_accounting = _gemini_module_accounting(behavior_manifest, errors)
    expected_knowledge = knowledge_target.get('expected_attachment_count')
    attachments = gemini_manifest.get('knowledge_attachment_sources')
    if not isinstance(attachments, list):
        errors.append('Gemini knowledge_attachment_sources must be an array')
        attachments = []
    if len(attachments) != expected_knowledge:
        errors.append(
            f'gemini_dcoir_agent knowledge attachment count mismatch: expected {expected_knowledge!r}, got {len(attachments)}'
        )
    required_files = gemini_manifest.get('required_files')
    if not isinstance(required_files, list):
        errors.append('Gemini required_files must be an array')
        required_files = []

    generated_files: list[dict[str, Any]] = []
    for item in modules:
        if not isinstance(item, dict):
            continue
        projection = item.get('projections', {}).get('gemini_dcoir_agent')
        if isinstance(projection, dict) and isinstance(projection.get('output_path'), str):
            generated_files.append({
                'path': projection['output_path'],
                'sha256': projection.get('sha256'),
                'module_id': item.get('id'),
            })

    return {
        'id': 'gemini_dcoir_agent',
        'provider': target_contract.get('provider'),
        'runtime_model': target_contract.get('runtime_model'),
        'instruction_mode': target_contract.get('instruction_mode'),
        'knowledge_mode': target_contract.get('knowledge_mode'),
        'bundle_version': gemini_manifest.get('bundle_version'),
        'bundle_name': gemini_manifest.get('bundle_name'),
        'bundle_manifest': gemini_identity,
        'behavior': {'expected_canonical_items': expected_behavior_count, **module_accounting},
        'knowledge': {
            'expected_file_count': expected_knowledge,
            'reported_file_count': len(attachments),
            'files': attachments,
        },
        'generated_files': generated_files,
        'generated_file_count': len(generated_files),
        'bundle_required_files': required_files,
        'bundle_required_file_count': len(required_files),
        'capabilities': target_contract.get('capabilities', {}),
        'runtime_dependent_capabilities': target_contract.get('runtime_dependent_capabilities', []),
        'manual_deployment_required': False,
        'live_webui_validation_performed': None,
        'deployment_readback_state': 'live_runtime_evidence_not_represented_by_static_repo_report',
    }


def build_release_report(
    repo_root: Path,
    *,
    source_commit: str | None = None,
    run_target_checks: bool = True,
) -> tuple[list[str], dict[str, Any]]:
    repo_root = repo_root.resolve()
    errors: list[str] = []
    commit, commit_basis = resolve_source_commit(repo_root, source_commit)
    source_manifest, source_identity = _manifest_identity(
        repo_root, SHARED_MANIFEST, errors, 'source_contract_version'
    )
    behavior_manifest, behavior_identity = _manifest_identity(
        repo_root, BEHAVIOR_MANIFEST, errors, 'module_contract_version'
    )
    knowledge_manifest, knowledge_identity = _manifest_identity(
        repo_root, KNOWLEDGE_MANIFEST, errors, 'projection_contract_version'
    )
    gemini_manifest, gemini_identity = _manifest_identity(
        repo_root, GEMINI_MANIFEST, errors, 'bundle_version'
    )

    if source_manifest.get('target_ids') != list(EXPECTED_TARGET_IDS):
        errors.append(
            'Shared source target_ids must exactly equal the governed release order '
            f'{list(EXPECTED_TARGET_IDS)!r}; got {source_manifest.get("target_ids")!r}'
        )
    source_targets = source_manifest.get('targets')
    if not isinstance(source_targets, list):
        errors.append('Shared source targets must be an array')
        source_targets = []
    source_by_id = {item.get('id'): item for item in source_targets if isinstance(item, dict)}
    if set(source_by_id) != set(EXPECTED_TARGET_IDS):
        errors.append(f'Shared source targets disagree with governed target ids: {sorted(source_by_id)}')

    knowledge_targets = knowledge_manifest.get('targets')
    if not isinstance(knowledge_targets, dict):
        errors.append('Knowledge projection targets must be an object')
        knowledge_targets = {}
    if set(knowledge_targets) != set(EXPECTED_TARGET_IDS):
        errors.append(
            f'Knowledge projection target ids disagree with governed target ids: {sorted(knowledge_targets)}'
        )
    for target_id, target in knowledge_targets.items():
        if not isinstance(target, dict):
            errors.append(f'Knowledge projection target must be an object: {target_id}')
            continue
        manifest_path = target.get('target_manifest_path') or target.get('bundle_manifest')
        if manifest_path:
            _resolve_repo_path(repo_root, manifest_path, errors, f'{target_id} projection target manifest')

    behavior_counts = _canonical_behavior_counts(source_manifest, errors)
    targets = [
        _gemini_target(
            source_by_id.get('gemini_dcoir_agent', {}), behavior_manifest,
            gemini_manifest, gemini_identity,
            knowledge_targets.get('gemini_dcoir_agent', {}),
            behavior_counts['gemini_dcoir_agent'], errors,
        )
    ]
    for target_id in ('openai_dcoir_analyst', 'openai_usb_reporting'):
        manifest, identity = _manifest_identity(
            repo_root, OPENAI_PACKAGE_MANIFESTS[target_id], errors, 'adapter_contract_version'
        )
        targets.append(_openai_target(
            target_id, source_by_id.get(target_id, {}), manifest, identity,
            knowledge_targets.get(target_id, {}), behavior_counts[target_id], errors,
        ))

    guide = _validate_guide(repo_root, errors)
    check_results, check_errors = _target_check_results(repo_root, run_target_checks)
    errors.extend(check_errors)
    pending_live = [
        {
            'target_id': target['id'],
            'classification': 'pending_live_manual_evidence',
            'state': target['deployment_readback_state'],
        }
        for target in targets
        if target['id'].startswith('openai_')
        and target.get('live_webui_validation_performed') is not True
    ]
    blocking_gaps = [
        {'classification': 'blocking_static_parity_gap', 'message': message}
        for message in errors
    ]
    reverse_required = source_manifest.get('generated_artifact_policy', {}).get(
        'reverse_reconciliation_required'
    ) is True
    report = {
        'schema': SCHEMA,
        'report_version': REPORT_VERSION,
        'source_commit': commit,
        'source_commit_basis': commit_basis,
        'scope': {
            'target_ids': list(EXPECTED_TARGET_IDS),
            'static_repository_evidence_only': True,
            'live_model_parity_claimed': False,
        },
        'source_contracts': {
            'shared_source_contract': source_identity,
            'behavior_module_manifest': behavior_identity,
            'knowledge_projection_manifest': knowledge_identity,
        },
        'targets': targets,
        'governed_provider_differences': _governed_differences(source_targets),
        'blocking_parity_gaps': blocking_gaps,
        'pending_live_evidence': pending_live,
        'target_check_results': check_results,
        'manual_deployment_readback_guide': guide,
        'static_parity_status': 'pass' if not errors else 'fail',
        'live_parity_status': 'pending_manual_readback' if pending_live else 'readback_recorded',
        'reverse_reconciliation_required': reverse_required,
    }
    if not reverse_required:
        message = 'Shared source contract must require reverse reconciliation'
        errors.append(message)
        report['blocking_parity_gaps'].append(
            {'classification': 'blocking_static_parity_gap', 'message': message}
        )
        report['static_parity_status'] = 'fail'
    return errors, report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        '# Agent Release and Parity Report', '',
        f"- Source commit: `{report['source_commit']}` ({report['source_commit_basis']})",
        f"- Static parity: **{report['static_parity_status']}**",
        f"- Live parity: **{report['live_parity_status']}**",
        '- Scope: static repository evidence; live model parity is not claimed.', '',
        '## Source contracts', '',
        '| Contract | Version | SHA-256 |', '| --- | --- | --- |',
    ]
    for name, identity in report['source_contracts'].items():
        lines.append(
            f"| {name} | {identity.get('version') or '-'} | `{identity.get('sha256') or 'missing'}` |"
        )
    lines.extend(['', '## Targets', ''])
    for target in report['targets']:
        lines.extend([
            f"### `{target['id']}`", '',
            f"- Provider: `{target.get('provider')}`",
            f"- Runtime model: `{target.get('runtime_model')}`",
            f"- Instruction mode: `{target.get('instruction_mode')}`",
            f"- Knowledge mode: `{target.get('knowledge_mode')}`",
            f"- Generated/release files: {target.get('generated_file_count')}",
            f"- Knowledge files: {target.get('knowledge', {}).get('reported_file_count')} "
            f"(expected {target.get('knowledge', {}).get('expected_file_count')})",
            f"- Behavior accounting: {json.dumps(target.get('behavior', {}), sort_keys=True)}",
            f"- Deployment/readback: `{target.get('deployment_readback_state')}`", '',
        ])
    lines.extend(['## Governed provider differences', ''])
    differences = report['governed_provider_differences']
    lines.extend(
        f"- `{item['dimension']}`: {json.dumps(item['values'], sort_keys=True)}" for item in differences
    ) if differences else lines.append('- None.')
    lines.extend(['', '## Blocking static parity gaps', ''])
    gaps = report['blocking_parity_gaps']
    lines.extend(f"- {item['message']}" for item in gaps) if gaps else lines.append('- None.')
    lines.extend(['', '## Pending live/manual evidence', ''])
    pending = report['pending_live_evidence']
    lines.extend(f"- `{item['target_id']}`: `{item['state']}`" for item in pending) if pending else lines.append('- None.')
    lines.extend(['', '## Existing target checks', '', '| Check | Result |', '| --- | --- |'])
    lines.extend(f"| `{item['id']}` | `{item['result']}` |" for item in report['target_check_results'])
    guide = report['manual_deployment_readback_guide']
    lines.extend([
        '', '## Manual deployment/readback guide', '',
        f"- Path: `{guide['path']}`",
        f"- SHA-256: `{guide.get('sha256') or 'missing'}`",
        f"- Required guide markers present: `{guide['required_markers_present']}`", '',
        'Live OpenAI parity remains pending until the documented manual deployment and readback evidence is recorded.',
        '',
    ])
    return '\n'.join(lines)


def write_outputs(report: dict[str, Any], output_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / 'agent_release_parity_report.json'
    markdown_path = output_root / 'agent_release_parity_report.md'
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    markdown_path.write_text(render_markdown(report), encoding='utf-8')
    return json_path, markdown_path


def default_output_root(repo_root: Path) -> Path:
    event = os.environ.get('GITHUB_EVENT_NAME', '').lower()
    if event == 'pull_request':
        relative = Path('project_sources/validation/out_validate_on_pr_agent_runtime')
    elif event == 'push':
        relative = Path('project_sources/validation/out_validate_on_push_agent_runtime')
    else:
        relative = Path('project_sources/validation/out_agent_release_parity')
    return repo_root / relative


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Build a deterministic static release, drift, and parity report for all governed agent targets.'
    )
    parser.add_argument('--repo-root', type=Path, default=_default_repo_root())
    parser.add_argument('--source-commit')
    parser.add_argument('--output-root', type=Path)
    parser.add_argument('--no-target-checks', action='store_true')
    parser.add_argument('--json', action='store_true', dest='json_stdout')
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    errors, report = build_release_report(
        repo_root, source_commit=args.source_commit,
        run_target_checks=not args.no_target_checks,
    )
    output_root = args.output_root.resolve() if args.output_root else default_output_root(repo_root)
    json_path, markdown_path = write_outputs(report, output_root)
    payload = {
        'success': not errors,
        'source_commit': report['source_commit'],
        'static_parity_status': report['static_parity_status'],
        'live_parity_status': report['live_parity_status'],
        'json_report': (
            json_path.relative_to(repo_root).as_posix()
            if json_path.is_relative_to(repo_root) else json_path.as_posix()
        ),
        'markdown_report': (
            markdown_path.relative_to(repo_root).as_posix()
            if markdown_path.is_relative_to(repo_root) else markdown_path.as_posix()
        ),
        'errors': errors,
    }
    if args.json_stdout or errors:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"Agent release parity: {report['static_parity_status']}; "
            f"live parity: {report['live_parity_status']}; report: {payload['json_report']}"
        )
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
