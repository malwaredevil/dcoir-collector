from __future__ import annotations

import json
from pathlib import Path

from lib.gemini_bundle_path_safety import validate_bundle_identity, validate_manifest_paths
from lib.gemini_bundle_validation_common import (
    derive_bundle_version,
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

REPORT_NAME = 'validate_dcoir_gemini_bundle_report.json'


def _write_report(
    output_dir: Path,
    source_root: Path,
    repo_root: Path,
    manifest: object,
    checks: dict[str, object],
    warnings: list[str],
    errors: list[str],
    effective_version: object,
) -> int:
    identity = manifest if isinstance(manifest, dict) else {}
    success = not errors
    report = {
        'success': success,
        'source_root': str(source_root),
        'repo_root': str(repo_root),
        'bundle_name': identity.get('bundle_name'),
        'bundle_version': effective_version,
        'checks': checks,
        'warnings': warnings,
        'errors': errors,
    }
    (output_dir / REPORT_NAME).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if success else 1


def validate_bundle(
    source_root: Path,
    output_dir: Path,
    version_override: str | None = None,
) -> int:
    source_root = source_root.resolve()
    repo_root = resolve_repo_root(source_root)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, object] = {}

    def finish(manifest: object, effective_version: object = None) -> int:
        return _write_report(
            output_dir, source_root, repo_root, manifest, checks, warnings, errors, effective_version
        )

    try:
        manifest = load_manifest(source_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        checks['manifest_readable'] = False
        errors.append(f'Gemini bundle manifest could not be read: {type(exc).__name__}')
        return finish(None)

    # Path containment and archive identity are checked before any other
    # manifest-derived file access.
    path_errors = validate_manifest_paths(manifest, source_root, repo_root)
    checks['manifest_path_safety'] = not path_errors
    checks['manifest_path_safety_errors'] = path_errors
    if path_errors:
        errors.extend(path_errors)
        return finish(manifest)

    effective_version = derive_bundle_version(source_root, manifest, version_override)
    identity_errors = validate_bundle_identity(manifest.get('bundle_name'), effective_version)
    checks['effective_bundle_version'] = effective_version
    checks['bundle_identity_safety'] = not identity_errors
    if identity_errors:
        errors.extend(identity_errors)
        return finish(manifest, effective_version)

    expected_strategy = 'stored_source_compile_with_direct_knowledge_attachment_generation'
    checks['source_strategy'] = manifest.get('source_strategy')
    if manifest.get('source_strategy') != expected_strategy:
        errors.append(f'source_strategy must be {expected_strategy} for direct Knowledge packaging')

    required_files = validate_required_files(manifest, source_root, checks, errors)
    knowledge_sources = validate_knowledge_inventory(manifest, source_root, repo_root, required_files, checks, errors)
    validate_operator_file_suffixes(source_root, required_files, checks, warnings)
    topology, prime_rel, sub_rel_list = validate_topology(manifest, source_root, checks, errors, warnings)
    validate_runtime_surfaces(source_root, repo_root, topology, prime_rel, sub_rel_list, knowledge_sources, checks, errors, warnings)

    return finish(manifest, effective_version)
