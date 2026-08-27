#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import project_agent_knowledge as knowledge_projection


SCHEMA = 'dcoir.agent_runtime.gemini_knowledge_consolidation_evaluation.v1'
TARGET_ID = 'gemini_dcoir_agent'
REFERENCE_TARGET_ID = 'openai_dcoir_analyst'
FALLBACK_GROUP_ID = 'gemini_provider_specific'
FALLBACK_GROUP_PURPOSE = (
    'Gemini-only runtime, topology, and maintainer Knowledge preserved from '
    'full canonical sources.'
)
VALID_LIVE_EVIDENCE = ('unavailable', 'pass', 'fail')
SAFE_GROUP_ID_PATTERN = r'^[a-z0-9][a-z0-9_]*$'


def _sha256(data: bytes) -> str:
    return knowledge_projection._sha256(data)


def _file_sha256(
    path: Path, label: str, errors: list[str]
) -> str | None:
    try:
        return _sha256(path.read_bytes())
    except (OSError, RuntimeError) as exc:
        errors.append(f'Unable to hash {label} {path}: {exc}')
        return None


def _load_json(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, RuntimeError) as exc:
        errors.append(f'Unable to read {label} {path}: {exc}')
        return None
    except json.JSONDecodeError as exc:
        errors.append(f'Invalid JSON in {label} {path}: {exc}')
        return None
    if not isinstance(value, dict):
        errors.append(f'{label} must contain a JSON object: {path}')
        return None
    return value


def _resolve_repo_root(repo_root: Path, errors: list[str]) -> Path | None:
    try:
        resolved = repo_root.resolve()
    except (OSError, RuntimeError) as exc:
        errors.append(f'Unable to resolve repository root {repo_root}: {exc}')
        return None
    return resolved


def _resolve_repo_path(
    repo_root: Path,
    value: Any,
    label: str,
    errors: list[str],
) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f'{label} must be a non-empty repository-relative path')
        return None
    relative = Path(value)
    if relative.is_absolute() or '..' in relative.parts:
        errors.append(f'{label} must not be absolute or contain traversal: {value}')
        return None
    try:
        candidate = (repo_root / relative).resolve()
    except (OSError, RuntimeError) as exc:
        errors.append(f'Unable to resolve {label} {value}: {exc}')
        return None
    if not candidate.is_relative_to(repo_root):
        errors.append(f'{label} escapes the repository: {value}')
        return None
    return candidate


def _duplicates(values: list[str]) -> list[str]:
    return sorted(value for value, count in Counter(values).items() if count > 1)


def _source_summary(source: dict[str, Any]) -> dict[str, Any]:
    return {
        'id': source['id'],
        'path': source['path'],
        'git_blob_sha': source['git_blob_sha'],
        'sha256': source['sha256'],
        'bytes': len(source['content']),
        'content_class': source['item'].get('content_class'),
    }


def _candidate_group_order(
    source_contract: dict[str, Any],
    group_sources: dict[str, list[dict[str, Any]]],
    errors: list[str],
) -> list[tuple[str, str]]:
    groups = source_contract.get('knowledge_projection_groups')
    if not isinstance(groups, list):
        errors.append('Source contract knowledge_projection_groups must be an array')
        return []
    ordered: list[tuple[str, str]] = []
    seen: set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            errors.append('Source contract contains a non-object projection group')
            continue
        if group.get('target_id') != REFERENCE_TARGET_ID:
            continue
        group_id = group.get('id')
        purpose = group.get('purpose')
        if not isinstance(group_id, str) or not group_id:
            errors.append('Reference projection group lacks an id')
            continue
        if re.fullmatch(SAFE_GROUP_ID_PATTERN, group_id) is None:
            errors.append(f'Unsafe reference projection group id: {group_id}')
            continue
        if group_id in seen:
            errors.append(f'Duplicate reference projection group id: {group_id}')
            continue
        seen.add(group_id)
        if group_id in group_sources:
            ordered.append(
                (
                    group_id,
                    purpose if isinstance(purpose, str) else '',
                )
            )
    unknown = sorted(
        group_id
        for group_id in group_sources
        if group_id != FALLBACK_GROUP_ID and group_id not in seen
    )
    for group_id in unknown:
        errors.append(f'Unknown Gemini candidate projection group: {group_id}')
    if group_sources.get(FALLBACK_GROUP_ID):
        ordered.append((FALLBACK_GROUP_ID, FALLBACK_GROUP_PURPOSE))
    return ordered


def _render_markdown(report: dict[str, Any]) -> str:
    baseline = report.get('baseline', {})
    candidate = report.get('candidate', {})
    decision = report.get('decision', {})
    lines = [
        '# Gemini Knowledge Consolidation Evaluation',
        '',
        f"- Success: `{str(report.get('success', False)).lower()}`",
        f"- Recommended decision: **{decision.get('recommended', 'REVISE')}**",
        f"- Baseline commit: `{baseline.get('baseline_commit', 'unspecified')}`",
        f"- Active Gemini mode: `{baseline.get('active_mode', 'unknown')}`",
        f"- Active attachment count: {baseline.get('active_attachment_count', 0)}",
        f"- Candidate file count: {candidate.get('file_count', 0)}",
        f"- Candidate source count: {candidate.get('source_count', 0)}",
        f"- Attachment reduction: {candidate.get('attachment_reduction_count', 0)} files "
        f"({candidate.get('attachment_reduction_percent', 0.0):.2f}%)",
        f"- Live candidate evidence: `{decision.get('live_evidence_status', 'unavailable')}`",
        f"- Open live-behavior tracker: `#{decision.get('behavior_tracker_issue', 184)}`",
        '',
        '## Static result',
        '',
        f"- Active projection validation: `{candidate.get('active_projection_validation', 'fail')}`",
        f"- Exact source coverage: `{candidate.get('exact_source_coverage', False)}`",
        f"- Lossless candidate reconstruction: `{candidate.get('lossless_reconstruction', False)}`",
        f"- Active Gemini contract unchanged: `{candidate.get('active_contract_unchanged', False)}`",
        '',
        '## Candidate groups',
        '',
        '| Order | Group | Sources | Bytes | SHA-256 |',
        '| ---: | --- | ---: | ---: | --- |',
    ]
    for group in candidate.get('groups', []):
        lines.append(
            f"| {group.get('order', 0) + 1} | `{group.get('id')}` | "
            f"{group.get('source_count')} | {group.get('bytes')} | "
            f"`{group.get('sha256')}` |"
        )
    lines.extend(['', '## Benefits', ''])
    for benefit in report.get('benefits', []):
        lines.append(f'- {benefit}')
    lines.extend(['', '## Risks and evidence gaps', ''])
    for risk in report.get('risks', []):
        lines.append(f'- {risk}')
    lines.extend(['', '## Decision rationale', ''])
    for rationale in decision.get('rationale', []):
        lines.append(f'- {rationale}')
    if report.get('errors'):
        lines.extend(['', '## Blocking errors', ''])
        for error in report['errors']:
            lines.append(f'- {error}')
    return '\n'.join(lines) + '\n'


def evaluate_consolidation(
    repo_root: Path,
    manifest_path: Path,
    *,
    baseline_commit: str = 'unspecified',
    live_evidence_status: str = 'unavailable',
    live_evidence_run: str | None = None,
    behavior_tracker_issue: int = 184,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if live_evidence_status not in VALID_LIVE_EVIDENCE:
        errors.append(
            'live_evidence_status must be one of '
            + ', '.join(VALID_LIVE_EVIDENCE)
        )
    if live_evidence_status in {'pass', 'fail'} and not live_evidence_run:
        errors.append(
            'live_evidence_run is required when live_evidence_status is pass or fail'
        )
    if type(behavior_tracker_issue) is not int or behavior_tracker_issue <= 0:
        errors.append('behavior_tracker_issue must be a positive integer')

    resolved_repo = _resolve_repo_root(repo_root, errors)
    if resolved_repo is None:
        return errors, {
            'success': False,
            'schema': SCHEMA,
            'errors': errors,
            'decision': {
                'recommended': 'REVISE',
                'live_evidence_status': live_evidence_status,
                'live_evidence_run': live_evidence_run,
                'behavior_tracker_issue': behavior_tracker_issue,
                'rationale': [
                    'Repository-path resolution failed; no static candidate claim is safe.'
                ],
            },
        }

    if manifest_path.is_absolute():
        try:
            resolved_manifest = manifest_path.resolve()
        except (OSError, RuntimeError) as exc:
            errors.append(f'Unable to resolve projection manifest {manifest_path}: {exc}')
            resolved_manifest = None
        if (
            resolved_manifest is not None
            and not resolved_manifest.is_relative_to(resolved_repo)
        ):
            errors.append('Projection manifest must be inside the repository')
            resolved_manifest = None
    else:
        resolved_manifest = _resolve_repo_path(
            resolved_repo,
            manifest_path.as_posix(),
            'projection manifest',
            errors,
        )

    if resolved_manifest is None:
        return errors, {
            'success': False,
            'schema': SCHEMA,
            'errors': errors,
            'decision': {
                'recommended': 'REVISE',
                'live_evidence_status': live_evidence_status,
                'live_evidence_run': live_evidence_run,
                'behavior_tracker_issue': behavior_tracker_issue,
                'rationale': [
                    'Projection-manifest resolution failed; no static candidate claim is safe.'
                ],
            },
        }

    try:
        baseline_errors, baseline_projection = knowledge_projection.project_knowledge(
            resolved_repo, resolved_manifest, check=True
        )
    except (OSError, RuntimeError, ValueError) as exc:
        errors.append(f'Active knowledge projection validation raised: {exc}')
        baseline_errors = [str(exc)]
        baseline_projection = {}
    if baseline_errors:
        errors.extend(
            f'Active projection validation: {error}' for error in baseline_errors
        )

    manifest = _load_json(resolved_manifest, 'projection manifest', errors)
    if manifest is None:
        source_contract = None
        bundle = None
        records: list[dict[str, Any]] = []
        source_contract_path = None
        bundle_path = None
    else:
        source_contract_path = _resolve_repo_path(
            resolved_repo,
            manifest.get('source_contract'),
            'source contract',
            errors,
        )
        source_contract = (
            _load_json(source_contract_path, 'source contract', errors)
            if source_contract_path is not None
            else None
        )
        targets = manifest.get('targets')
        gemini_target = (
            targets.get(TARGET_ID)
            if isinstance(targets, dict)
            else None
        )
        if not isinstance(gemini_target, dict):
            errors.append('Projection manifest lacks gemini_dcoir_agent target')
            bundle_path = None
            bundle = None
        else:
            bundle_path = _resolve_repo_path(
                resolved_repo,
                gemini_target.get('bundle_manifest'),
                'Gemini bundle manifest',
                errors,
            )
            bundle = (
                _load_json(bundle_path, 'Gemini bundle manifest', errors)
                if bundle_path is not None
                else None
            )

        knowledge_root = _resolve_repo_path(
            resolved_repo,
            manifest.get('canonical_knowledge_root'),
            'canonical knowledge root',
            errors,
        )
        records = []
        if source_contract is not None and knowledge_root is not None:
            try:
                records = knowledge_projection._source_records(
                    resolved_repo,
                    source_contract,
                    knowledge_root,
                    errors,
                )
            except (OSError, RuntimeError, ValueError) as exc:
                errors.append(f'Canonical Knowledge inventory raised: {exc}')

    projection_manifest_sha256 = _file_sha256(
        resolved_manifest, 'projection manifest', errors
    )
    source_contract_sha256 = (
        _file_sha256(source_contract_path, 'source contract', errors)
        if source_contract_path is not None
        else None
    )
    bundle_manifest_sha256 = (
        _file_sha256(bundle_path, 'Gemini bundle manifest', errors)
        if bundle_path is not None
        else None
    )

    gemini_records = [
        record
        for record in records
        if TARGET_ID in (
            record['item'].get('applies_to')
            if isinstance(record['item'].get('applies_to'), list)
            else []
        )
    ]
    gemini_ids = [record['id'] for record in gemini_records]
    for duplicate in _duplicates(gemini_ids):
        errors.append(f'Duplicate Gemini candidate source id: {duplicate}')

    active_inventory = (
        baseline_projection.get('targets', {})
        .get(TARGET_ID, {})
        .get('attachments', [])
        if isinstance(baseline_projection, dict)
        else []
    )
    if not isinstance(active_inventory, list):
        active_inventory = []
        errors.append('Active Gemini attachment inventory is unavailable')
    active_ids = [
        entry.get('id')
        for entry in active_inventory
        if isinstance(entry, dict) and isinstance(entry.get('id'), str)
    ]
    active_mode = (
        baseline_projection.get('targets', {})
        .get(TARGET_ID, {})
        .get('mode', 'unknown')
        if isinstance(baseline_projection, dict)
        else 'unknown'
    )
    active_contract_unchanged = active_mode == 'direct_canonical_attachments'
    if not active_contract_unchanged:
        errors.append(
            'Active Gemini knowledge mode is not direct_canonical_attachments'
        )

    group_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    gemini_only_ids: list[str] = []
    for record in gemini_records:
        item = record['item']
        if item.get('gemini_attachment_disposition') != (
            'include_direct_from_canonical_source'
        ):
            errors.append(
                f"{record['id']} has unexpected Gemini attachment disposition: "
                f"{item.get('gemini_attachment_disposition')}"
            )
        group_id = item.get('openai_dcoir_projection_group')
        if group_id is None:
            group_id = FALLBACK_GROUP_ID
            gemini_only_ids.append(record['id'])
        elif not isinstance(group_id, str) or not group_id:
            errors.append(
                f"{record['id']} has invalid openai_dcoir_projection_group"
            )
            continue
        elif re.fullmatch(SAFE_GROUP_ID_PATTERN, group_id) is None:
            errors.append(
                f"{record['id']} has unsafe openai_dcoir_projection_group: {group_id}"
            )
            continue
        group_sources[group_id].append(record)

    ordered_groups = (
        _candidate_group_order(source_contract, group_sources, errors)
        if source_contract is not None
        else []
    )

    candidate_groups: list[dict[str, Any]] = []
    recovered_ids: list[str] = []
    lossless_reconstruction = True
    for order, (group_id, purpose) in enumerate(ordered_groups):
        sources = group_sources[group_id]
        try:
            content = knowledge_projection._projection_bytes(
                'gemini_dcoir_agent_candidate',
                group_id,
                purpose,
                sources,
            )
            recovered = knowledge_projection.recover_projection(content)
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f'Candidate group {group_id} generation/recovery failed: {exc}')
            lossless_reconstruction = False
            continue
        expected_contents = [source['content'] for source in sources]
        recovered_contents = [entry['content'] for entry in recovered]
        recovered_group_ids = [
            entry['metadata'].get('id') for entry in recovered
        ]
        if recovered_contents != expected_contents:
            errors.append(
                f'Candidate group {group_id} is not losslessly recoverable'
            )
            lossless_reconstruction = False
        if recovered_group_ids != [source['id'] for source in sources]:
            errors.append(
                f'Candidate group {group_id} recovered source order/id mismatch'
            )
            lossless_reconstruction = False
        recovered_ids.extend(
            source_id for source_id in recovered_group_ids
            if isinstance(source_id, str)
        )
        candidate_groups.append(
            {
                'id': group_id,
                'order': order,
                'purpose': purpose,
                'virtual_output_path': (
                    'project_sources/agent_runtime/generated/evaluations/'
                    'gemini_knowledge_consolidation/'
                    f'{order + 1:02d}-{group_id.replace("_", "-")}.md'
                ),
                'sha256': _sha256(content),
                'bytes': len(content),
                'source_count': len(sources),
                'content_classes': sorted(
                    {
                        str(source['item'].get('content_class'))
                        for source in sources
                    }
                ),
                'sources': [_source_summary(source) for source in sources],
            }
        )

    exact_source_coverage = (
        Counter(recovered_ids) == Counter(gemini_ids)
        and Counter(gemini_ids) == Counter(active_ids)
        and len(recovered_ids) == len(set(recovered_ids))
    )
    if not exact_source_coverage:
        errors.append(
            'Candidate source coverage does not exactly match the active Gemini inventory'
        )
        lossless_reconstruction = False

    active_total_bytes = sum(
        entry.get('bytes', 0)
        for entry in active_inventory
        if isinstance(entry, dict) and type(entry.get('bytes')) is int
    )
    candidate_total_bytes = sum(
        group['bytes'] for group in candidate_groups
    )
    active_count = len(active_inventory)
    candidate_count = len(candidate_groups)
    reduction_count = max(active_count - candidate_count, 0)
    reduction_percent = (
        (reduction_count / active_count) * 100.0 if active_count else 0.0
    )
    largest_group = max(
        candidate_groups,
        key=lambda group: group['bytes'],
        default=None,
    )

    static_success = (
        not errors
        and exact_source_coverage
        and lossless_reconstruction
        and active_contract_unchanged
    )
    if not static_success:
        recommended = 'REVISE'
        rationale = [
            'Static evaluation contains blocking source, projection, or reconstruction errors.',
            'Do not promote a candidate until the deterministic evaluation is clean.',
        ]
    elif live_evidence_status == 'pass':
        recommended = 'PROMOTE'
        rationale = [
            'The candidate is statically lossless and exactly source-accounted.',
            'A specific live candidate evidence run was supplied as passing.',
            'Repository activation may be considered, while live deployment/readback remains separately governed.',
        ]
    elif live_evidence_status == 'fail':
        recommended = 'DEFER'
        rationale = [
            'The candidate is statically lossless, but live candidate evidence failed.',
            'Retain the current direct Gemini attachment model until the live failure is resolved or dispositioned.',
        ]
    else:
        recommended = 'DEFER'
        rationale = [
            'The candidate is statically lossless, but no live candidate retrieval/behavior evidence exists.',
            f'Issue #{behavior_tracker_issue} still represents unresolved live Gemini behavior risk.',
            'Static file-count reduction is not evidence of equal or better Gemini retrieval behavior.',
        ]

    if baseline_errors:
        file_count_benefit = (
            'Candidate file-count reduction is not claimed because active '
            'projection validation did not pass.'
        )
    elif reduction_count > 0:
        file_count_benefit = (
            f'Candidate reduces runtime Knowledge files from {active_count} to '
            f'{candidate_count} without changing the canonical atomic sources.'
        )
    else:
        file_count_benefit = (
            f'Candidate does not reduce runtime Knowledge files '
            f'({active_count} active; {candidate_count} candidate) while '
            'leaving the canonical atomic sources unchanged.'
        )
    benefits = [
        file_count_benefit,
        'Every candidate source boundary retains id, canonical path, Git blob SHA, SHA-256, and byte count.',
        'Candidate grouping reuses the reviewed OpenAI DCOIR knowledge taxonomy and adds one explicit Gemini-only group.',
    ]
    risks = [
        'Consolidation reduces attachment/source granularity inside the Gemini runtime even when byte-for-byte source recovery is possible.',
        'Static projection checks cannot demonstrate Gemini retrieval selection, grounding quality, or behavioral equivalence.',
        f'Open live behavior tracker #{behavior_tracker_issue} remains independent evidence that current Gemini behavior still needs remediation/disposition.',
    ]
    if largest_group is not None:
        risks.append(
            'Largest candidate group '
            f"`{largest_group['id']}` combines {largest_group['source_count']} "
            f"sources into {largest_group['bytes']} bytes; live retrieval impact is unproven."
        )

    report = {
        'success': static_success,
        'schema': SCHEMA,
        'baseline': {
            'baseline_commit': baseline_commit,
            'projection_manifest': resolved_manifest.relative_to(resolved_repo).as_posix(),
            'projection_manifest_sha256': projection_manifest_sha256,
            'source_contract': (
                source_contract_path.relative_to(resolved_repo).as_posix()
                if source_contract_path is not None
                else None
            ),
            'source_contract_sha256': source_contract_sha256,
            'gemini_bundle_manifest': (
                bundle_path.relative_to(resolved_repo).as_posix()
                if bundle_path is not None
                else None
            ),
            'gemini_bundle_manifest_sha256': bundle_manifest_sha256,
            'gemini_bundle_version': (
                bundle.get('bundle_version') if isinstance(bundle, dict) else None
            ),
            'gemini_bundle_source_strategy': (
                bundle.get('source_strategy') if isinstance(bundle, dict) else None
            ),
            'active_mode': active_mode,
            'active_attachment_count': active_count,
            'active_total_source_bytes': active_total_bytes,
            'active_source_ids': active_ids,
        },
        'candidate': {
            'strategy': 'reuse_openai_dcoir_groups_plus_gemini_provider_specific',
            'active_projection_validation': (
                'pass' if not baseline_errors else 'fail'
            ),
            'active_contract_unchanged': active_contract_unchanged,
            'exact_source_coverage': exact_source_coverage,
            'lossless_reconstruction': lossless_reconstruction,
            'file_count': candidate_count,
            'source_count': len(recovered_ids),
            'candidate_total_bytes_with_markers': candidate_total_bytes,
            'attachment_reduction_count': reduction_count,
            'attachment_reduction_percent': reduction_percent,
            'gemini_only_source_count': len(gemini_only_ids),
            'gemini_only_source_ids': gemini_only_ids,
            'largest_group': (
                {
                    'id': largest_group['id'],
                    'bytes': largest_group['bytes'],
                    'source_count': largest_group['source_count'],
                }
                if largest_group is not None
                else None
            ),
            'groups': candidate_groups,
        },
        'benefits': benefits,
        'risks': risks,
        'decision': {
            'recommended': recommended,
            'live_evidence_status': live_evidence_status,
            'live_evidence_run': live_evidence_run,
            'behavior_tracker_issue': behavior_tracker_issue,
            'promotion_requires_live_candidate_evidence': True,
            'rationale': rationale,
            'next_action': (
                'Retain 28 direct Gemini attachments and reconsider only after '
                'candidate-specific live retrieval/behavior evidence is available.'
                if recommended == 'DEFER'
                else (
                    'Fix static evaluation gaps and rerun before any candidate promotion.'
                    if recommended == 'REVISE'
                    else
                    'Use a separately governed repository/runtime activation and live deployment/readback step.'
                )
            ),
        },
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
    parser.add_argument('--baseline-commit', default='unspecified')
    parser.add_argument(
        '--live-evidence-status',
        choices=VALID_LIVE_EVIDENCE,
        default='unavailable',
    )
    parser.add_argument('--live-evidence-run')
    parser.add_argument('--behavior-tracker-issue', type=int, default=184)
    parser.add_argument('--markdown', action='store_true')
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    manifest_path = Path(args.manifest)
    errors, report = evaluate_consolidation(
        repo_root,
        manifest_path,
        baseline_commit=args.baseline_commit,
        live_evidence_status=args.live_evidence_status,
        live_evidence_run=args.live_evidence_run,
        behavior_tracker_issue=args.behavior_tracker_issue,
    )
    if args.markdown:
        print(_render_markdown(report), end='')
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
