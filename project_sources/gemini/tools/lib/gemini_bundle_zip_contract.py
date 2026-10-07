"""Single owner of the Gemini delivery-zip identity and contract.

The release build, the production-like harness and the release surfacer all
need "the zip this build produced". It is the archive the compiler reports in
compile_dcoir_gemini_bundle_report.json, never a zip chosen by filename: a glob
over the output directory picks a stale archive whenever an older or
lexicographically later one is still present (for example 3_0_5 sorts after
3_0_10).
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

COMPILE_REPORT_NAME = 'compile_dcoir_gemini_bundle_report.json'


class BundleZipContractError(ValueError):
    """Raised when the compiled delivery zip cannot be identified or read."""


def compiled_zip_path(output_dir: Path) -> Path:
    """Return the zip the compiler reported writing into output_dir."""
    report_path = output_dir / COMPILE_REPORT_NAME
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleZipContractError(
            f'{COMPILE_REPORT_NAME} could not be read: {type(exc).__name__}'
        ) from exc
    zip_value = report.get('zip_path') if isinstance(report, dict) else None
    if not isinstance(zip_value, str) or not zip_value:
        raise BundleZipContractError(f'{COMPILE_REPORT_NAME} does not report a zip_path')
    zip_path = Path(zip_value)
    expected_name = f"{report.get('bundle_name')}_{report.get('bundle_version')}.zip"
    if zip_path.name != expected_name:
        raise BundleZipContractError(
            f'compiled delivery zip name {zip_path.name!r} does not match the reported '
            f'bundle identity {expected_name!r}'
        )
    try:
        inside = zip_path.resolve().parent == output_dir.resolve()
    except (OSError, RuntimeError):
        inside = False
    if not inside:
        raise BundleZipContractError(f'compiled delivery zip is not in the build output directory: {zip_path}')
    if not zip_path.is_file():
        raise BundleZipContractError(f'compiled delivery zip is missing: {zip_path}')
    return zip_path


def inspect_bundle_zip(zip_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Check the delivery zip carries exactly one Prime agent and no source-only files."""
    topology = manifest.get('topology')
    prime_rel = topology.get('prime_agent_file') if isinstance(topology, dict) else None
    source_only_files = set(manifest.get('source_only_files', []))
    source_only_dirs = tuple(rel.rstrip('/') + '/' for rel in manifest.get('source_only_dirs', []))
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = archive.namelist()
    except (OSError, zipfile.BadZipFile) as exc:
        raise BundleZipContractError(
            f'delivery zip could not be read: {zip_path}: {type(exc).__name__}'
        ) from exc
    payload_rels = [name.split('/', 1)[1] if '/' in name else name for name in names]
    prime_matches = [rel for rel in payload_rels if rel == prime_rel]
    leaked_files = [
        rel
        for rel in payload_rels
        if rel in source_only_files or any(rel.startswith(prefix) for prefix in source_only_dirs)
    ]
    return {
        'success': len(prime_matches) == 1 and not leaked_files,
        'zip_path': str(zip_path),
        'entry_count': len(names),
        'prime_agent_entries': prime_matches,
        'source_only_leaks': leaked_files,
    }
