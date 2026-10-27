#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from openai_builder_package_assembly import PackageSettings
from openai_builder_pipeline import BuilderSpec, run_builder_pipeline
import openai_builder_package_assembly as _package_assembly
import openai_builder_source_contract as _source_contract
import openai_builder_validation_kernel as _validation_kernel
import openai_webui_contract as _webui_contract

# Retain existing builder-facing compatibility exports; implementation is shared.
assemble_package_files = _package_assembly.assemble_package_files
_read_bytes = _source_contract.read_source_bytes
validate_projection_manifest_binding = _validation_kernel.validate_projection_manifest_binding
EXPECTED_DESCRIPTION_CHARACTER_CEILING = _webui_contract.DESCRIPTION_CHARACTER_CEILING
EXPECTED_INSTRUCTION_CHARACTER_CEILING = _webui_contract.INSTRUCTION_CHARACTER_CEILING
_contains_lone_surrogate = _webui_contract.contains_lone_surrogate
_webui_character_count = _webui_contract.webui_character_count
_webui_paste_safe_character_count = _webui_contract.webui_paste_safe_character_count


SCHEMA = 'dcoir.agent_runtime.openai_dcoir_adapter.v1'
SOURCE_SCHEMA = 'dcoir.agent_runtime.source_contract.v1'
BEHAVIOR_SCHEMA = 'dcoir.agent_runtime.behavior_modules.v1'
KNOWLEDGE_SCHEMA = 'dcoir.agent_runtime.knowledge_projection.target.v1'
TARGET_ID = 'openai_dcoir_analyst'
EXPECTED_EDITOR_NAME = 'AFRICOM DCOIR Analyst'
EXPECTED_RUNTIME_MODEL = 'GPT-5.6 Terra'
EXPECTED_KNOWLEDGE_FILES = 7
EXPECTED_BEHAVIOR_ITEMS = 30
EXPECTED_CASES = 22
EXPECTED_CASE_SCHEMA = 'dcoir.agent_runtime.openai_dcoir_behavioral_cases.v1'
CASE_MARKER_POLICY = 'aggregate'
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
PACKAGE_SETTINGS = PackageSettings(
    target_id=TARGET_ID,
    package_schema='dcoir.agent_runtime.openai_dcoir_package.v1',
    editor_name=EXPECTED_EDITOR_NAME,
    expected_outputs=EXPECTED_OUTPUTS,
    output_label='OpenAI DCOIR',
    staging_prefix='.openai-dcoir-',
    description_ceiling=EXPECTED_DESCRIPTION_CHARACTER_CEILING,
    instruction_ceiling=EXPECTED_INSTRUCTION_CHARACTER_CEILING,
)
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



TARGET_SPEC = BuilderSpec(
    target_id=TARGET_ID,
    adapter_schema=SCHEMA,
    source_schema=SOURCE_SCHEMA,
    behavior_schema=BEHAVIOR_SCHEMA,
    knowledge_schema=KNOWLEDGE_SCHEMA,
    expected_paths=EXPECTED_PATHS,
    package_settings=PACKAGE_SETTINGS,
    runtime_model=EXPECTED_RUNTIME_MODEL,
    knowledge_count=EXPECTED_KNOWLEDGE_FILES,
    behavior_count=EXPECTED_BEHAVIOR_ITEMS,
    case_count=EXPECTED_CASES,
    case_schema=EXPECTED_CASE_SCHEMA,
    marker_error_policy=CASE_MARKER_POLICY,
    section_headings=SECTION_HEADINGS,
    required_static_markers=REQUIRED_STATIC_MARKERS,
    provider_topology_leaks=PROVIDER_TOPOLOGY_LEAKS,
    target_label='OpenAI DCOIR',
    projection_label='OpenAI DCOIR',
    knowledge_label='DCOIR',
    profile_error_policy='dcoir',
    invalid_generated_root='.invalid-openai-dcoir-generated-root',
    projection_before_target=True,
    adapter_pointer_key='openai_dcoir_adapter_manifest',
    adapter_pointer_path=(
        'project_sources/agent_runtime/provider_adapters/'
        'openai_dcoir_analyst/Adapter_Manifest.json'
    ),
)


def build_package(
    repo_root: Path, manifest_path: Path, check: bool
) -> tuple[list[str], dict[str, Any]]:
    # Preserve the existing public API, now delegated to the shared pipeline.
    return run_builder_pipeline(repo_root, manifest_path, check, spec=TARGET_SPEC)


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
