#!/usr/bin/env python3
"""Fail-closed native policy negative/positive CI proof for issue 606."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from powershell_analyzer_cli import build_report
from powershell_analyzer_contract import INVENTORY_SCHEMA_VERSION, sha256_line_ending_stable_file

BAD_FIXTURE = Path('project_sources/collector/fixtures/powershell_analysis/bad/invoke_expression.ps1')
RULE = 'PSAvoidUsingInvokeExpression'


def verify_policy(repo_root: Path, analyzer_command: list[str] | None = None) -> None:
    root = repo_root.resolve()
    if not (root / BAD_FIXTURE).is_file():
        raise RuntimeError(f'required native bad fixture missing: {BAD_FIXTURE}')
    with tempfile.TemporaryDirectory(prefix='.dcoir-policy-ci-', dir=root) as name:
        work = Path(name)
        good = work / 'safe_control.ps1'
        good.write_text("Write-Output 'safe control'\n", encoding='utf-8')
        for kind, path in (('negative', root / BAD_FIXTURE), ('control', good)):
            relative = path.relative_to(root).as_posix()
            inventory_path = work / f'{kind}_inventory.json'
            inventory = {
                'schema_version': INVENTORY_SCHEMA_VERSION,
                'validation': {'success': True, 'errors': []},
                'summary': {'total_surfaces': 1},
                'surfaces': [{
                    'path': relative, 'category': 'collector_runtime_wrapper',
                    'source_type': '.ps1', 'inclusion_decision': 'include',
                    'sha256': sha256_line_ending_stable_file(path),
                }],
            }
            inventory_path.write_text(json.dumps(inventory), encoding='utf-8')
            args = argparse.Namespace(
                repo_root=str(root), inventory=inventory_path.relative_to(root).as_posix(),
                settings='project_sources/collector/PSScriptAnalyzerSettings.psd1',
                json_output='project_sources/collector/powershell_analyzer_report.json',
                markdown_output='project_sources/collector/powershell_analyzer_report.md',
                analyzer_command=list(analyzer_command or []), target_path=[],
                baseline_json=None, timeout_seconds=60, minimum_powershell_version='5.1',
                fail_on_severity='Warning', allow_findings=False,
                expect_finding_rule=RULE if kind == 'negative' else None,
                expect_finding_path=relative if kind == 'negative' else None,
                expect_no_findings=False, no_write=True,
            )
            report, errors, _ = build_report(args)
            if not report or report['summary']['analyzed_count'] != 1 or report['summary']['skipped_target_count'] != 0:
                raise RuntimeError(f'{kind}: native analyzer failed to complete targeted scan: {errors}')
            matches = [f for f in report['findings'] if f['path'] == relative and f['rule_name'] == RULE
                       and f['severity'] == 'Warning' and not f['suppressed_by_baseline']]
            if kind == 'negative':
                if not matches or report['summary']['policy_warning_count'] < 1 or report['summary']['blocking_finding_count'] < 1:
                    raise RuntimeError(f'negative fixture failed to produce blocking {RULE} Warning: {errors}')
                if not errors or any(not e.startswith('unsuppressed analyzer findings at or above Warning:') for e in errors):
                    raise RuntimeError(f'negative fixture did not fail for the expected severity threshold: {errors}')
            else:
                if errors or matches or report['summary']['blocking_finding_count'] != 0 or not report['validation']['success']:
                    raise RuntimeError(f'safe control was not accepted: {errors}')
            print(f'PASS: {kind} native policy fixture, analyzed=1, IEX_Warnings={len(matches)}, '
                  f'blocking={report["summary"]["blocking_finding_count"]}')


def main() -> int:
    try:
        verify_policy(Path(__file__).resolve().parents[3])
        return 0
    except Exception as exc:
        print(f'FAIL: native analyzer policy fixture check: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
