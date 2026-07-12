from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from lib.gemini_bundle_validation_common import (
    load_manifest,
    resolve_repo_root,
)
from lib.gemini_bundle_validation_inventory import (
    validate_knowledge_inventory,
    validate_operator_file_suffixes,
    validate_required_files,
)
from lib.gemini_bundle_validation_runtime import validate_runtime_surfaces
from lib.gemini_bundle_validation_topology import validate_topology


def validate_bundle(source_root: Path, output_dir: Path) -> int:
    source_root = source_root.resolve()
    repo_root = resolve_repo_root(source_root)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(source_root)
    errors: List[str] = []
    warnings: List[str] = []
    checks: Dict[str, object] = {}

    expected_strategy = 'stored_source_compile_with_direct_knowledge_attachment_generation'
    checks['source_strategy'] = manifest.get('source_strategy')
    if manifest.get('source_strategy') != expected_strategy:
        errors.append(f'source_strategy must be {expected_strategy} for direct Knowledge packaging')

    required_files = validate_required_files(manifest, source_root, checks, errors)
    knowledge_sources = validate_knowledge_inventory(manifest, source_root, repo_root, required_files, checks, errors)
    validate_operator_file_suffixes(source_root, required_files, checks, warnings)
    topology, prime_rel, sub_rel_list = validate_topology(manifest, source_root, checks, errors, warnings)
    validate_runtime_surfaces(source_root, repo_root, topology, prime_rel, sub_rel_list, knowledge_sources, checks, errors, warnings)

    success = len(errors) == 0
    report = {
        'success': success,
        'source_root': str(source_root),
        'repo_root': str(repo_root),
        'bundle_name': manifest.get('bundle_name'),
        'bundle_version': manifest.get('bundle_version'),
        'checks': checks,
        'warnings': warnings,
        'errors': errors,
    }
    report_path = output_dir / 'validate_dcoir_gemini_bundle_report.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if success else 1
