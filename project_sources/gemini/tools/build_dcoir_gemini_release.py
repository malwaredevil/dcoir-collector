#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
from pathlib import Path


def run_step(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True)


def write_report(output_dir: Path, report: dict) -> None:
    report_path = output_dir / 'build_dcoir_gemini_release_report.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


def inspect_gemini_zip_contract(output_dir: Path, manifest: dict) -> dict:
    bundle_name = manifest['bundle_name']
    zips = sorted(output_dir.glob(f'{bundle_name}_*.zip'))
    if not zips:
        return {'success': False, 'error': 'no Gemini bundle zip found'}
    zip_path = zips[-1]
    prime_rel = manifest.get('topology', {}).get('prime_agent_file')
    source_only_dirs = tuple(rel.rstrip('/') + '/' for rel in manifest.get('source_only_dirs', []))
    source_only_files = set(manifest.get('source_only_files', []))
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    payload_rels = []
    for name in names:
        parts = name.split('/', 1)
        payload_rels.append(parts[1] if len(parts) == 2 else name)
    prime_matches = [rel for rel in payload_rels if rel == prime_rel]
    leaked_files = [rel for rel in payload_rels if rel in source_only_files or any(rel.startswith(prefix) for prefix in source_only_dirs)]
    return {
        'success': len(prime_matches) == 1 and not leaked_files,
        'zip_path': str(zip_path),
        'prime_agent_entries': prime_matches,
        'source_only_leaks': leaked_files,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-root', required=True)
    ap.add_argument('--output-dir', required=True)
    ap.add_argument('--version', default=None)
    ap.add_argument('--skip-validation', action='store_true')
    args = ap.parse_args()

    script_root = Path(__file__).resolve().parent
    source_root = Path(args.source_root).resolve()
    manifest = json.loads((source_root / 'Gemini_Bundle_Source_Manifest.json').read_text(encoding='utf-8'))
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # source_root is <repo>/project_sources/gemini/bundle_source.
    # Maintained knowledge docs live at <repo>/knowledge and are packaged directly by compile_dcoir_gemini_bundle.py.
    repo_root = source_root.parent.parent.parent

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

    zip_contract = inspect_gemini_zip_contract(output_dir, manifest)
    steps.append({'name': 'inspect_gemini_zip_contract', 'returncode': 0 if zip_contract.get('success') else 1, 'report': zip_contract})
    if not zip_contract.get('success'):
        write_report(output_dir, {'success': False, 'stage': 'inspect_gemini_zip_contract', 'steps': steps})
        return 1

    write_report(output_dir, {'success': True, 'stage': 'complete', 'steps': steps})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
