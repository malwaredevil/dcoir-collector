#!/usr/bin/env python3
"""Single governed OpenAI GPT builder pipeline, parameterized by target specification.

Target modules retain only their governed constants, public build_package
compatibility entrypoint and CLI main. This module owns validation sequencing.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai_builder_behavior_snapshot import validate_behavior_snapshot
from openai_builder_instruction_contract import validate_instruction_cases
from openai_builder_knowledge_projection import validate_knowledge_projections
from openai_builder_package_assembly import PackageSettings, assemble_package_files
from openai_builder_source_contract import (
    load_adapter_source_inputs, read_source_bytes,
    validate_source_target_capabilities,
)
from openai_builder_validation_kernel import (
    validate_behavior_snapshot_pin, validate_projection_manifest_binding,
)


@dataclass(frozen=True)
class BuilderSpec:
    target_id: str
    adapter_schema: str
    source_schema: str
    behavior_schema: str
    knowledge_schema: str
    expected_paths: dict[str, str]
    package_settings: PackageSettings
    runtime_model: str
    knowledge_count: int
    behavior_count: int
    case_count: int
    case_schema: str
    marker_error_policy: str
    section_headings: dict[str, str]
    required_static_markers: tuple[str, ...]
    provider_topology_leaks: tuple[str, ...]
    target_label: str
    projection_label: str
    knowledge_label: str
    profile_error_policy: str
    invalid_generated_root: str
    projection_before_target: bool = False
    adapter_pointer_key: str | None = None
    adapter_pointer_path: str | None = None


def _validate_knowledge_binding(
    projection_manifest: dict[str, Any],
    adapter: dict[str, Any],
    target_manifest: dict[str, Any],
    source_sha: str,
    errors: list[str],
    *,
    spec: BuilderSpec,
) -> None:
    """Preserve target-specific sequencing of the existing contract checks."""
    validate_projection_manifest_binding(
        projection_manifest, adapter, spec.target_id,
        spec.knowledge_count, errors, spec.projection_label,
    )
    if target_manifest.get('source_contract') != adapter.get('source_contract'):
        errors.append('Knowledge target points to the wrong shared source contract')
    if target_manifest.get('source_contract_sha256') != source_sha:
        errors.append('Knowledge target source-contract hash drift')


def run_builder_pipeline(
    repo_root: Path,
    manifest_path: Path,
    check: bool,
    *,
    spec: BuilderSpec,
) -> tuple[list[str], dict[str, Any]]:
    """Run the same ordered build/check pipeline for either governed GPT."""
    repo_root = repo_root.resolve()
    errors: list[str] = []
    inputs = load_adapter_source_inputs(
        repo_root, manifest_path, errors,
        adapter_schema=spec.adapter_schema, target_id=spec.target_id,
        expected_paths=spec.expected_paths, source_schema=spec.source_schema,
        behavior_schema=spec.behavior_schema,
        invalid_generated_root=spec.invalid_generated_root,
    )
    if inputs is None:
        return errors, {'success': False, 'errors': errors}
    (adapter, generated_root, required_paths, source_contract,
     behavior_manifest, knowledge_projection_manifest, target_manifest,
     cases, source_contract_sha) = inputs
    if spec.adapter_pointer_key is not None:
        if source_contract.get(spec.adapter_pointer_key) != spec.adapter_pointer_path:
            errors.append('Shared source contract points to the wrong OpenAI DCOIR adapter')
    if spec.projection_before_target:
        _validate_knowledge_binding(
            knowledge_projection_manifest, adapter, target_manifest,
            source_contract_sha, errors, spec=spec,
        )
    target, capabilities = validate_source_target_capabilities(
        source_contract, adapter, errors,
        target_id=spec.target_id, label=spec.target_label,
        runtime_model=spec.runtime_model,
        profile_error_policy=spec.profile_error_policy,
    )
    coverage = adapter.get('coverage')
    if not isinstance(coverage, list):
        errors.append('Adapter coverage must be an array')
        coverage = []
    behavior_snapshot, snapshot_sha = validate_behavior_snapshot(
        repo_root, source_contract, behavior_manifest, coverage, errors,
        target_id=spec.target_id, expected_count=spec.behavior_count,
        instructions_path=spec.package_settings.expected_outputs['instructions'],
        section_headings=spec.section_headings,
    )
    validate_behavior_snapshot_pin(snapshot_sha, adapter, errors)
    instruction_path = required_paths.get('canonical_instructions_source')
    instructions = read_source_bytes(
        instruction_path, 'canonical Instructions', errors,
    ) if instruction_path else b''
    case_ids = validate_instruction_cases(
        instructions, adapter, cases, errors,
        target_id=spec.target_id, case_schema=spec.case_schema,
        expected_ceiling=spec.package_settings.instruction_ceiling,
        section_headings=spec.section_headings,
        required_static_markers=spec.required_static_markers,
        provider_topology_leaks=spec.provider_topology_leaks,
        expected_cases=spec.case_count,
        marker_error_policy=spec.marker_error_policy,
    )
    if not spec.projection_before_target:
        _validate_knowledge_binding(
            knowledge_projection_manifest, adapter, target_manifest,
            source_contract_sha, errors, spec=spec,
        )
    knowledge_files = validate_knowledge_projections(
        repo_root, target_manifest, errors,
        target_id=spec.target_id, schema=spec.knowledge_schema,
        expected_count=spec.knowledge_count, label=spec.knowledge_label,
    )
    expected_files = assemble_package_files(
        repo_root, generated_root, adapter, target, required_paths,
        instructions, knowledge_files, target_manifest, behavior_snapshot,
        snapshot_sha, case_ids, capabilities, source_contract_sha, errors,
        settings=spec.package_settings, check=check,
    )
    report = {
        'success': not errors,
        'action': 'check' if check else 'materialize',
        'target_id': spec.target_id,
        'behavior_coverage_count': len(behavior_snapshot),
        'behavior_source_snapshot_sha256': snapshot_sha,
        'behavioral_case_count': len(case_ids),
        'knowledge_file_count': len(knowledge_files),
        'generated_file_count': len(expected_files),
        'errors': errors,
    }
    return errors, report
