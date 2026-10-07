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
from collections import Counter
from pathlib import Path, PureWindowsPath
from typing import Any

COMPILE_REPORT_NAME = 'compile_dcoir_gemini_bundle_report.json'


class BundleZipContractError(ValueError):
    """Raised when the compiled delivery zip cannot be identified or read."""


def compiled_zip_path(
    output_dir: Path,
    *,
    expected_bundle_name: str,
    expected_bundle_version: str,
) -> Path:
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
    if (
        report.get('bundle_name') != expected_bundle_name
        or report.get('bundle_version') != expected_bundle_version
    ):
        raise BundleZipContractError(
            f'{COMPILE_REPORT_NAME} bundle identity does not match the expected manifest identity '
            f'{expected_bundle_name!r}_{expected_bundle_version!r}'
        )
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
    expected_top_level = zip_path.stem
    expected_prefix = f'{expected_top_level}/'
    unexpected_root_entries = []
    unsafe_member_names = []
    payload_rels = []
    for name in names:
        windows_path = PureWindowsPath(name)
        if not name or '\\' in name or name.startswith('/') or windows_path.drive:
            unsafe_member_names.append(name)
            continue
        if not name.startswith(expected_prefix):
            unexpected_root_entries.append(name)
            continue
        rel = name[len(expected_prefix):]
        if not rel or any(part in ('', '.', '..') for part in rel.split('/')):
            unsafe_member_names.append(name)
            continue
        payload_rels.append(rel)
    duplicate_payload_members = sorted(
        rel for rel, count in Counter(payload_rels).items() if count > 1
    )
    prime_matches = [rel for rel in payload_rels if rel == prime_rel]
    leaked_files = [
        rel
        for rel in payload_rels
        if rel in source_only_files or any(rel.startswith(prefix) for prefix in source_only_dirs)
    ]
    return {
        'success': (
            len(prime_matches) == 1
            and not leaked_files
            and not duplicate_payload_members
            and not unexpected_root_entries
            and not unsafe_member_names
        ),
        'zip_path': str(zip_path),
        'expected_top_level': expected_top_level,
        'entry_count': len(names),
        'prime_agent_entries': prime_matches,
        'duplicate_payload_members': duplicate_payload_members,
        'unexpected_root_entries': unexpected_root_entries,
        'unsafe_member_names': unsafe_member_names,
        'source_only_leaks': leaked_files,
    }
