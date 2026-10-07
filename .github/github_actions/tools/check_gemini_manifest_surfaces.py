#!/usr/bin/env python3
"""Validate Gemini manifest-governed bundle surfaces before a workflow continues.

This is a CLI over the canonical Gemini bundle validator rules, not a second
validator. It runs the manifest path-safety, bundle identity, inventory,
topology and runtime-surface checks from project_sources/gemini/tools/lib, so
it fails closed on what the bundle validator rejects when full validation is
skipped.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GEMINI_TOOLS_DIR = Path(__file__).resolve().parents[3] / "project_sources" / "gemini" / "tools"
# The Gemini lib modules import each other as "lib.*". This script's own
# directory also has a "lib" package, so the Gemini tools dir must come first.
sys.path.insert(0, str(GEMINI_TOOLS_DIR))

from lib.gemini_bundle_path_safety import validate_bundle_identity, validate_manifest_paths  # noqa: E402
from lib.gemini_bundle_validation_common import derive_bundle_version, load_manifest, resolve_repo_root  # noqa: E402
from lib.gemini_bundle_validation_inventory import (  # noqa: E402
    validate_knowledge_inventory,
    validate_operator_file_suffixes,
    validate_required_files,
)
from lib.gemini_bundle_validation_runtime import validate_runtime_surfaces  # noqa: E402
from lib.gemini_bundle_validation_topology import validate_topology  # noqa: E402


def manifest_surface_errors(source_root: Path) -> tuple[dict, list[str]]:
    """Return (manifest, errors) from the canonical structural manifest checks."""
    try:
        manifest = load_manifest(source_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {}, [f"Gemini bundle manifest could not be read: {type(exc).__name__}"]
    path_errors = validate_manifest_paths(manifest, source_root, resolve_repo_root(source_root))
    if path_errors:
        return manifest if isinstance(manifest, dict) else {}, path_errors
    checks: dict[str, object] = {}
    errors: list[str] = []
    warnings: list[str] = []
    repo_root = resolve_repo_root(source_root)
    effective_version = derive_bundle_version(source_root, manifest)
    errors.extend(validate_bundle_identity(manifest.get("bundle_name"), effective_version))
    expected_strategy = "stored_source_compile_with_direct_knowledge_attachment_generation"
    if manifest.get("source_strategy") != expected_strategy:
        errors.append(f"source_strategy must be {expected_strategy} for direct Knowledge packaging")

    required_files = validate_required_files(manifest, source_root, checks, errors)
    knowledge_sources = validate_knowledge_inventory(
        manifest, source_root, repo_root, required_files, checks, errors
    )
    validate_operator_file_suffixes(source_root, required_files, checks, warnings)
    topology, prime_rel, sub_rel_list = validate_topology(manifest, source_root, checks, errors, warnings)
    validate_runtime_surfaces(
        source_root,
        repo_root,
        topology,
        prime_rel,
        sub_rel_list,
        knowledge_sources,
        checks,
        errors,
        warnings,
    )
    return manifest, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, help="Gemini bundle source root")
    args = parser.parse_args()

    source_root = Path(args.source_root).resolve()
    manifest, errors = manifest_surface_errors(source_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(
        "Gemini manifest surfaces validated: "
        f"required={len(manifest['required_files'])}; "
        f"source-required={len(manifest.get('source_required_files', []))}; "
        f"sub-agents={len(manifest['topology']['sub_agent_files'])}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
