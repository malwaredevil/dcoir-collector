#!/usr/bin/env python3
"""PowerShell behavior probes for collector runtime-package validation."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List



def probe_powershell_behavior_shell(shell_path: str, requested_label: str) -> Dict[str, object]:
    result: Dict[str, object] = {
        'path': shell_path,
        'command': Path(shell_path).name,
        'requested_label': requested_label,
        'target': requested_label if requested_label == 'pwsh' else 'powershell_unclassified',
        'edition': '',
        'version': '',
    }
    probe_script = "$PSVersionTable.PSEdition + '|' + $PSVersionTable.PSVersion.ToString()"
    try:
        completed = subprocess.run(
            [shell_path, '-NoProfile', '-Command', probe_script],
            capture_output=True,
            text=True,
            timeout=20,
        )
        result['probe_returncode'] = completed.returncode
        result['probe_stdout'] = completed.stdout[-1000:]
        result['probe_stderr'] = completed.stderr[-1000:]
        if completed.returncode == 0:
            parts = next((line.strip() for line in completed.stdout.splitlines() if line.strip()), '').split('|', 1)
            if len(parts) == 2:
                result['edition'] = parts[0].strip()
                result['version'] = parts[1].strip()
    except Exception as exc:
        result['probe_error'] = str(exc)[-1000:]

    edition = str(result.get('edition', '')).casefold()
    version = str(result.get('version', ''))
    if edition == 'desktop' and version.startswith('5.1'):
        result['target'] = 'windows_powershell_5_1'
    elif edition == 'core':
        result['target'] = 'pwsh' if requested_label == 'pwsh' else 'powershell_core'
    elif requested_label == 'pwsh':
        result['target'] = 'pwsh'
    return result


def get_powershell_behavior_shells() -> List[Dict[str, object]]:
    candidates = [
        ('powershell', shutil.which('powershell') or shutil.which('powershell.exe')),
        ('pwsh', shutil.which('pwsh')),
    ]
    shells: List[Dict[str, object]] = []
    seen_paths = set()
    for requested_label, shell_path in candidates:
        if not shell_path:
            continue
        try:
            stable_path = str(Path(shell_path).resolve(strict=False))
        except Exception:
            stable_path = str(shell_path)
        if stable_path in seen_paths:
            continue
        seen_paths.add(stable_path)
        shells.append(probe_powershell_behavior_shell(shell_path, requested_label))
    return shells


def run_powershell_behavior_script(script: str, available_shells: List[Dict[str, object]]) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    for shell in available_shells:
        label = str(shell.get('target', 'powershell_unclassified'))
        shell_path = str(shell.get('path', ''))
        with tempfile.NamedTemporaryFile('w', suffix='.ps1', encoding='utf-8', delete=False) as handle:
            handle.write(script)
            script_path = Path(handle.name)
        try:
            cmd = [shell_path, '-NoProfile']
            if label != 'windows_powershell_5_1':
                cmd.append('-NonInteractive')
            if label == 'windows_powershell_5_1':
                cmd.extend(['-ExecutionPolicy', 'Bypass'])
            cmd.extend(['-File', str(script_path)])
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            results.append({
                'target': label,
                'requested_label': shell.get('requested_label', ''),
                'command': shell.get('command', Path(shell_path).name),
                'edition': shell.get('edition', ''),
                'version': shell.get('version', ''),
                'status': 'passed' if completed.returncode == 0 else 'failed',
                'returncode': completed.returncode,
                'stdout': completed.stdout[-4000:],
                'stderr': completed.stderr[-4000:],
            })
        except Exception as exc:
            results.append({
                'target': label,
                'requested_label': shell.get('requested_label', ''),
                'command': shell.get('command', Path(shell_path).name),
                'edition': shell.get('edition', ''),
                'version': shell.get('version', ''),
                'status': 'failed',
                'returncode': None,
                'stdout': '',
                'stderr': str(exc)[-4000:],
            })
        finally:
            script_path.unlink(missing_ok=True)
    return results


def finalize_powershell_behavior_result(result: Dict[str, object], shell_results: List[Dict[str, object]]) -> Dict[str, object]:
    result['shell_results'] = shell_results
    failed = [row for row in shell_results if row['status'] == 'failed']
    win51 = next((row for row in shell_results if row['target'] == 'windows_powershell_5_1' and row['status'] == 'passed'), None)
    if failed:
        result['status'] = 'failed'
    elif win51:
        result['status'] = 'passed'
    elif shell_results:
        result['status'] = 'passed_without_windows_powershell_5_1'
    else:
        result['status'] = 'skipped_powershell_unavailable'
    return result


def behavior_base() -> Dict[str, object]:
    return {'available': False, 'status': 'skipped_powershell_unavailable', 'preferred_target': 'windows_powershell_5_1', 'shell_results': []}
