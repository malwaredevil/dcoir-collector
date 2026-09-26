#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = ROOT / 'project_sources/gemini/tools/run_openai_usb_reporting_behavioral_replay.py'
SEMANTIC_SELFTEST_PATH = ROOT / 'project_sources/agent_runtime/tests/score_usb_reporting_behavior_selftest.py'
GEMINI_TOOLS = ROOT / 'project_sources/gemini/tools'
if str(GEMINI_TOOLS) not in sys.path:
    sys.path.insert(0, str(GEMINI_TOOLS))


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    runner = load(RUNNER_PATH, 'run_openai_usb_reporting_behavioral_replay_selftest_target')
    semantic = load(SEMANTIC_SELFTEST_PATH, 'usb_semantic_selftest_support')
    nipr_rows = semantic.module.load_fixture_rows(semantic.NIPR_FIXTURE)
    mixed_rows = semantic.module.load_fixture_rows(semantic.MIXED_FIXTURE)
    final_texts = [semantic._nipr_response(nipr_rows), semantic._mixed_response(mixed_rows)]
    call_index = {'value': 0}

    def fake_caller(api_key, project_id, args, body):
        index = call_index['value']
        call_index['value'] += 1
        if index % 2 == 0:
            text = "What was last week's single overall USB violation count?"
        else:
            text = final_texts[index // 2]
        return {'ok': True, 'response_text': text, 'response_id': f'fake-{index}', 'attempts': [{'attempt': 1, 'status_code': 200}]}

    args = argparse.Namespace(
        fixture=[],
        start_date=semantic.START,
        end_date=semantic.END,
        previous_week_count=semantic.PREVIOUS,
        reasoning_effort='medium',
        max_output_tokens=16384,
        max_retries=1,
        retry_base_seconds=0.0,
        api_base=runner.DEFAULT_API_BASE,
        api_key_env='DCOIR_OPENAI_API_KEY',
        fallback_api_key_env='OPENAI_API_KEY',
        project_id_env='DCOIR_OPENAI_PROJECT_ID',
    )
    report = runner.run_replay(args, caller=fake_caller, api_key_override='test-key', project_id_override='')
    assert report['workflow_verdict'] == 'success', report
    assert report['target_id'] == 'openai_usb_reporting'
    assert report['model_id'] == 'gpt-5.6-terra'
    assert len(report['results']) == 2
    assert all(item['passed'] for item in report['results'])
    assert report['results'][0]['classification_counts'] == {'NIPR': 7, 'SIPR': 0}
    assert report['results'][1]['classification_counts'] == {'NIPR': 5, 'SIPR': 2}
    assert 'Custom GPT WebUI host behavior' in report['unchecked_evidence']

    failed_calls = {'value': 0}

    def failing_caller(api_key, project_id, args, body):
        failed_calls['value'] += 1
        return {
            'ok': False,
            'error': 'http_401',
            'attempts': [{'attempt': 1, 'status_code': 401, 'error_body_excerpt': 'Incorrect API key provided: sk-...'}],
        }

    failed = runner.run_replay(args, caller=failing_caller, api_key_override='test-key', project_id_override='')
    assert failed['workflow_verdict'] == 'failure', failed
    assert failed_calls['value'] == len(failed['results']), 'final call must be skipped after clarification failure'
    for item in failed['results']:
        assert item['clarification']['error'] == 'http_401', item
        assert item['clarification']['attempts'] == [{'attempt': 1, 'status_code': 401}], item
        assert item['final']['error'] == 'not_attempted_after_clarification_failure', item
    print({'success': True, 'fixture_count': len(report['results']), 'model': report['model_id']})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
