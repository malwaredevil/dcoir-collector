#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from lib.gemini_bundle_validation_common import load_manifest, resolve_repo_root
from lib.gemini_bundle_zip_contract import (
    BundleZipContractError,
    compiled_zip_path,
    inspect_bundle_zip,
)


def run_step(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True)


def write_report(output_dir: Path, report: dict) -> None:
    report_path = output_dir / 'build_dcoir_gemini_release_report.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-root', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--version', default=None)
    ap.add_argument('--skip-validation', action='store_true')
    args = ap.parse_args()

    script_root = Path(__file__).resolve().parent
    source_root = Path(args.source_root).resolve()
    manifest = load_manifest(source_root)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # Maintained knowledge docs live at <repo>/knowledge and are packaged directly by compile_dcoir_gemini_bundle.py.
    repo_root = resolve_repo_root(source_root)

    validate_script = script_root / 'validate_dcoir_gemini_bundle.py'
    scenario_script = script_root / 'validate_dcoir_gemini_behavior_scenarios.py'
    regression_script = script_root / 'validate_dcoir_gemini_output_contract_regressions.py'
    compile_script = script_root / 'compile_dcoir_gemini_bundle.py'
    reassemble_script = script_root / 'reassemble_dcoir_gemini_prime_agent.py'
    adapter_script = (
        repo_root
        / 'project_sources'
        / 'agent_runtime'
        / 'tools'
        / 'materialize_agent_behavior_adapters.py'
    )
    adapter_manifest = (
        repo_root
        / 'project_sources'
        / 'agent_runtime'
        / 'Behavior_Module_Manifest.json'
    )

    steps = []

    adapter_cmd = [
        sys.executable,
        str(adapter_script),
        '--repo-root',
        str(repo_root),
        '--manifest',
        str(adapter_manifest),
        '--target',
        'gemini_dcoir_agent',
        '--check',
    ]
    adapter_proc = run_step(adapter_cmd)
    steps.append({
        'name': 'check_behavior_adapters',
        'cmd': adapter_cmd,
        'returncode': adapter_proc.returncode,
        'stdout': adapter_proc.stdout,
        'stderr': adapter_proc.stderr,
    })
    if adapter_proc.returncode != 0:
        write_report(output_dir, {'success': False, 'stage': 'check_behavior_adapters', 'steps': steps})
        return 1

    reassemble_cmd = [sys.executable, str(reassemble_script), '--source-root', str(source_root), '--output-dir', str(output_dir)]
    reassemble_proc = run_step(reassemble_cmd)
    steps.append({
        'name': 'reassemble_prime_agent',
        'cmd': reassemble_cmd,
        'returncode': reassemble_proc.returncode,
        'stdout': reassemble_proc.stdout,
        'stderr': reassemble_proc.stderr,
    })
    if reassemble_proc.returncode != 0:
        write_report(output_dir, {'success': False, 'stage': 'reassemble_prime_agent', 'steps': steps})
        return 1

    if not args.skip_validation:
        validate_cmd = [sys.executable, str(validate_script), '--source-root', str(source_root), '--output-dir', str(output_dir)]
        if args.version:
            validate_cmd.extend(['--version', args.version])
        validate_proc = run_step(validate_cmd)
        steps.append({
            'name': 'validate',
            'cmd': validate_cmd,
            'returncode': validate_proc.returncode,
            'stdout': validate_proc.stdout,
            'stderr': validate_proc.stderr,
        })
        if validate_proc.returncode != 0:
            write_report(output_dir, {'success': False, 'stage': 'validate', 'steps': steps})
            return 1

        scenario_cmd = [sys.executable, str(scenario_script), '--source-root', str(source_root), '--output-dir', str(output_dir)]
        scenario_proc = run_step(scenario_cmd)
        steps.append({
            'name': 'validate_behavior_scenarios',
            'cmd': scenario_cmd,
            'returncode': scenario_proc.returncode,
            'stdout': scenario_proc.stdout,
            'stderr': scenario_proc.stderr,
        })
        if scenario_proc.returncode != 0:
            write_report(output_dir, {'success': False, 'stage': 'validate_behavior_scenarios', 'steps': steps})
            return 1

        regression_cmd = [sys.executable, str(regression_script), '--source-root', str(source_root), '--output-dir', str(output_dir)]
        regression_proc = run_step(regression_cmd)
        steps.append({
            'name': 'validate_output_contract_regressions',
            'cmd': regression_cmd,
            'returncode': regression_proc.returncode,
            'stdout': regression_proc.stdout,
            'stderr': regression_proc.stderr,
        })
        if regression_proc.returncode != 0:
            write_report(output_dir, {'success': False, 'stage': 'validate_output_contract_regressions', 'steps': steps})
            return 1

    compile_cmd = [sys.executable, str(compile_script), '--source-root', str(source_root), '--output-dir', str(output_dir)]
    if args.version:
        compile_cmd.extend(['--version', args.version])
    compile_proc = run_step(compile_cmd)
    steps.append({
        'name': 'compile',
        'cmd': compile_cmd,
        'returncode': compile_proc.returncode,
        'stdout': compile_proc.stdout,
        'stderr': compile_proc.stderr,
    })

    if compile_proc.returncode != 0:
        write_report(output_dir, {'success': False, 'stage': 'compile', 'steps': steps})
        return 1

    # Inspect and deliver exactly the zip the compiler reported, never one picked by name.
    try:
        zip_contract = inspect_bundle_zip(compiled_zip_path(output_dir), manifest)
    except BundleZipContractError as exc:
        zip_contract = {'success': False, 'error': str(exc)}
    steps.append({'name': 'inspect_gemini_zip_contract', 'returncode': 0 if zip_contract.get('success') else 1, 'report': zip_contract})
    if not zip_contract.get('success'):
        write_report(output_dir, {'success': False, 'stage': 'inspect_gemini_zip_contract', 'steps': steps})
        return 1

    write_report(output_dir, {'success': True, 'stage': 'complete', 'zip_path': zip_contract['zip_path'], 'steps': steps})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
