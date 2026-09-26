#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List

from lib.gemini_behavioral_replay_runner import repo_root_from_script
from lib.openai_dcoir_replay_live import DEFAULT_API_BASE, call_openai_body
from lib.openai_usb_replay_package import load_governed_openai_usb_package

REPORT_NAME = 'openai_usb_reporting_behavioral_replay_run_report.json'
TARGET_ID = 'openai_usb_reporting'
DEFAULT_FIXTURES = (
    'project_sources/validation/fixtures/agent_runtime/usb_reporting/inputs/violations_sanitized_nipr.csv',
    'project_sources/validation/fixtures/agent_runtime/usb_reporting/inputs/violations_sanitized_mixed.csv',
)


def _load_semantic_module(repo_root: Path):
    path = repo_root / 'project_sources/agent_runtime/tools/score_usb_reporting_behavior.py'
    spec = importlib.util.spec_from_file_location('score_usb_reporting_behavior_live', path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Unable to load USB semantic scorer: {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _request_body(package: Dict[str, Any], history: List[Dict[str, str]], user_text: str, args: argparse.Namespace) -> Dict[str, Any]:
    return {
        'model': package['model_id'],
        'instructions': package['instructions'],
        'input': [
            {'role': 'developer', 'content': package['knowledge_context']},
            *history,
            {'role': 'user', 'content': user_text},
        ],
        'reasoning': {'effort': args.reasoning_effort},
        'max_output_tokens': args.max_output_tokens,
        'store': False,
    }


def _initial_prompt(csv_text: str, start_date: str, end_date: str) -> str:
    return (
        'Prepare the weekly USB violations report from the CSV below. '
        f'The reporting window is already confirmed as {start_date} - {end_date}, so do not ask me to confirm the date range. '
        'I have intentionally not supplied last week\'s overall USB violation count yet. '
        'Use the governed weekly USB report workflow and ask only for genuinely missing required information before the final draft.\n\n'
        'CSV:\n' + csv_text.strip()
    )


def _completion_prompt(previous_count: int, start_date: str, end_date: str) -> str:
    return (
        f'Last week\'s single overall USB violation count was {previous_count}. '
        f'The reporting window remains confirmed as {start_date} - {end_date}. '
        'All provided rows belong to that reporting window. '
        'If a source Date cell contains more than one observed Zulu time, preserve the source time expression rather than inventing one time. '
        'Produce the final weekly USB report email draft or drafts now.'
    )


def _safe_response(call: Dict[str, Any], api_key: str) -> str:
    text = str(call.get('response_text') or '') if call.get('ok') else ''
    if api_key and api_key in text:
        return '[redacted-secret-output]'
    return text


def run_replay(
    args: argparse.Namespace,
    *,
    caller: Callable[..., Dict[str, Any]] = call_openai_body,
    api_key_override: str | None = None,
    project_id_override: str | None = None,
) -> Dict[str, Any]:
    repo_root = repo_root_from_script(Path(__file__))
    scorer = _load_semantic_module(repo_root)
    package = load_governed_openai_usb_package(repo_root)
    api_key = api_key_override if api_key_override is not None else (
        os.environ.get(args.api_key_env, '').strip() or os.environ.get(args.fallback_api_key_env, '').strip()
    )
    project_id = project_id_override if project_id_override is not None else os.environ.get(args.project_id_env, '').strip()
    if not api_key:
        raise RuntimeError('OpenAI replay credentials are not configured')

    fixture_paths = [repo_root / path for path in (args.fixture or DEFAULT_FIXTURES)]
    results: list[dict[str, Any]] = []
    overall = True
    for path in fixture_paths:
        csv_text = path.read_text(encoding='utf-8-sig')
        rows = scorer.load_fixture_rows(path)
        history: List[Dict[str, str]] = []

        first_user = _initial_prompt(csv_text, args.start_date, args.end_date)
        first_call = caller(api_key, project_id, args, _request_body(package, history, first_user, args))
        first_text = _safe_response(first_call, api_key)
        clarification_score = scorer.score_clarification_response(first_text)
        history.extend([
            {'role': 'user', 'content': first_user},
            {'role': 'assistant', 'content': first_text},
        ])

        second_user = _completion_prompt(args.previous_week_count, args.start_date, args.end_date)
        second_call = caller(api_key, project_id, args, _request_body(package, history, second_user, args))
        second_text = _safe_response(second_call, api_key)
        final_score = scorer.score_final_response(
            second_text,
            rows,
            start_date=args.start_date,
            end_date=args.end_date,
            previous_count=args.previous_week_count,
        )
        passed = bool(first_call.get('ok')) and bool(second_call.get('ok')) and clarification_score['passed'] and final_score['passed']
        overall = overall and passed
        results.append({
            'fixture': str(path.relative_to(repo_root)),
            'row_count': len(rows),
            'classification_counts': {
                'NIPR': sum(1 for row in rows if scorer._classification(row) == 'NIPR'),
                'SIPR': sum(1 for row in rows if scorer._classification(row) == 'SIPR'),
            },
            'clarification': {
                'call_ok': bool(first_call.get('ok')),
                'response_id': first_call.get('response_id'),
                'attempts': first_call.get('attempts', []),
                'response_text': first_text,
                'semantic_score': clarification_score,
            },
            'final': {
                'call_ok': bool(second_call.get('ok')),
                'response_id': second_call.get('response_id'),
                'attempts': second_call.get('attempts', []),
                'response_text': second_text,
                'semantic_score': final_score,
            },
            'passed': passed,
        })

    return {
        'schema_version': 'openai_usb_reporting_behavioral_replay_v1',
        'target_id': TARGET_ID,
        'workflow_verdict': 'success' if overall else 'failure',
        'model_id': package['model_id'],
        'runtime_name': package['runtime_name'],
        'reasoning_effort': args.reasoning_effort,
        'reporting_window': {'start': args.start_date, 'end': args.end_date},
        'previous_week_count': args.previous_week_count,
        'package_evidence': {
            'instructions_path': package['instructions_path'],
            'instructions_sha256': package['instructions_sha256'],
            'knowledge_files': package['knowledge_files'],
            'package_manifest_sha256': package['package_manifest_sha256'],
            'configuration_sha256': package['configuration_sha256'],
            'behavior_source_snapshot_sha256': package['behavior_source_snapshot_sha256'],
            'source_base_commit': package['source_base_commit'],
            'capabilities': package['capabilities'],
        },
        'checked_evidence': [
            'exact governed OpenAI USB Instructions',
            'exact generated USB Knowledge projection',
            'live GPT-5.6 Terra Responses API output',
            'sanitized governed USB fixture rows',
            'semantic bounded-clarification behavior',
            'semantic final email construction and row/classification fidelity',
        ],
        'unchecked_evidence': [
            'Custom GPT WebUI host behavior',
            'Custom GPT proprietary Knowledge retrieval behavior',
            'live deployed GPT configuration state unless separately read back',
        ],
        'live_environment_fidelity_gap': (
            'This is real GPT-5.6 Terra Responses API evidence using the exact repository Instructions and Knowledge package. '
            'It does not by itself prove the hosted Custom GPT WebUI has been redeployed or behaves identically.'
        ),
        'results': results,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run live GPT-5.6 Terra behavioral replay for the governed AFRICOM USB Reporting package.')
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--fixture', action='append', default=[])
    parser.add_argument('--start-date', default='9/18/2026')
    parser.add_argument('--end-date', default='9/24/2026')
    parser.add_argument('--previous-week-count', type=int, default=6)
    parser.add_argument('--api-key-env', default='DCOIR_OPENAI_API_KEY')
    parser.add_argument('--fallback-api-key-env', default='OPENAI_API_KEY')
    parser.add_argument('--project-id-env', default='DCOIR_OPENAI_PROJECT_ID')
    parser.add_argument('--reasoning-effort', choices=['none', 'low', 'medium', 'high', 'xhigh', 'max'], default='medium')
    parser.add_argument('--max-output-tokens', type=int, default=16384)
    parser.add_argument('--max-retries', type=int, default=4)
    parser.add_argument('--retry-base-seconds', type=float, default=5.0)
    args = parser.parse_args()
    args.api_base = DEFAULT_API_BASE
    if not 2048 <= args.max_output_tokens <= 32768:
        parser.error('--max-output-tokens must be between 2048 and 32768')
    return args


def main() -> int:
    args = _parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    try:
        report = run_replay(args)
    except Exception as exc:
        report = {
            'schema_version': 'openai_usb_reporting_behavioral_replay_v1',
            'target_id': TARGET_ID,
            'workflow_verdict': 'failure',
            'error': f'{type(exc).__name__}: {exc}',
        }
    (output / REPORT_NAME).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report.get('workflow_verdict') == 'success' else 1


if __name__ == '__main__':
    raise SystemExit(main())
