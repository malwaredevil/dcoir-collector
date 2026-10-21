#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

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
    # A traversal-shaped path must fail even when it resolves to a real fixture.
    valid_fixture = str(semantic.NIPR_FIXTURE.relative_to(ROOT))
    unsafe_fixture = str(
        Path('project_sources') / 'validation' / '..' / 'validation'
        / Path(valid_fixture).relative_to('project_sources/validation')
    )
    try:
        runner._resolve_fixture_paths(ROOT, [unsafe_fixture])
    except ValueError as exc:
        assert 'must not be absolute or contain traversal' in str(exc), exc
    else:
        raise AssertionError('repository path traversal syntax bypassed')
    assert callable(semantic.module.classify_usb_row)
    # Opposite polarity and platform boundaries: legitimate relative inputs pass;
    # canonical syntax rejects absolute paths even when they point inside root.
    assert runner._resolve_fixture_paths(ROOT, [valid_fixture]) == [semantic.NIPR_FIXTURE.resolve()]
    windows_absolute = 'X:/arbitrary.csv'
    for unsafe in (str(semantic.NIPR_FIXTURE), windows_absolute):
        try:
            runner._resolve_fixture_paths(ROOT, [unsafe])
        except ValueError as exc:
            assert 'must not be absolute or contain traversal' in str(exc), (unsafe, exc)
        else:
            raise AssertionError(f'absolute fixture path accepted: {unsafe}')

    # Prove the real canonical Agent Runtime resolver owns the call path.
    canonical = runner._load_agent_runtime_tool(ROOT, 'agent_runtime_path_safety')
    with patch.object(canonical, 'resolve_repo_path', wraps=canonical.resolve_repo_path) as used:
        with patch.object(runner, '_load_agent_runtime_tool', return_value=canonical):
            paths = runner._resolve_fixture_paths(ROOT, [valid_fixture])
    assert paths == [semantic.NIPR_FIXTURE.resolve()]
    used.assert_called_once()
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
    assert report['model_id'] == runner.load_governed_openai_usb_package(ROOT)['model_id']
    assert len(report['results']) == 2
    assert all(item['passed'] for item in report['results'])
    assert report['results'][0]['classification_counts'] == {'NIPR': 7, 'SIPR': 0}
    assert report['results'][1]['classification_counts'] == {'NIPR': 5, 'SIPR': 2}
    assert 'Custom GPT WebUI host behavior' in report['unchecked_evidence']

    # The USB GPT must use the governed package model for both actual request
    # bodies and its rendered report, even when that model changes later.
    renamed_model = 'gpt-usb-model-identity-selftest'
    renamed_package = {**runner.load_governed_openai_usb_package(ROOT), 'model_id': renamed_model}
    seen_model_ids = []
    call_index['value'] = 0

    def model_identity_caller(api_key, project_id, args, body):
        seen_model_ids.append(body['model'])
        return fake_caller(api_key, project_id, args, body)

    with patch.object(runner, 'load_governed_openai_usb_package', return_value=renamed_package):
        renamed = runner.run_replay(args, caller=model_identity_caller, api_key_override='test-key', project_id_override='')
    if renamed['workflow_verdict'] != 'success' or renamed['model_id'] != renamed_model:
        raise AssertionError(f'USB report model drifted from governed package: {renamed}')
    if seen_model_ids != [renamed_model] * 4:
        raise AssertionError(f'USB provider request models did not follow governed package: {seen_model_ids}')
    if f'- Model: `{renamed_model}`' not in runner.render_report_section(renamed):
        raise AssertionError('USB rendered report did not show governed package model ID')

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

    # Fixture paths are validated before any billable call.
    for bad in ('/etc/passwd', '../outside.csv', 'project_sources/validation/fixtures/does_not_exist.csv'):
        guarded_calls = {'value': 0}

        def counting_caller(api_key, project_id, args, body):
            guarded_calls['value'] += 1
            return {'ok': False, 'error': 'unknown', 'attempts': []}

        args.fixture = [bad]
        try:
            runner.run_replay(args, caller=counting_caller, api_key_override='test-key', project_id_override='')
        except ValueError:
            pass
        else:
            raise AssertionError(f'invalid fixture path was accepted: {bad}')
        assert guarded_calls['value'] == 0, bad
    # Even after one valid fixture, a later unsafe path must cause zero calls.
    guarded_calls = {'value': 0}
    args.fixture = [valid_fixture, unsafe_fixture]
    try:
        runner.run_replay(args, caller=counting_caller, api_key_override='test-key', project_id_override='')
    except ValueError:
        pass
    else:
        raise AssertionError('later unsafe fixture was accepted')
    assert guarded_calls['value'] == 0, 'later unsafe fixture must abort before any API request'
    args.fixture = []

    # A header-only later fixture fails before the first fixture's billable calls.
    import tempfile
    with tempfile.TemporaryDirectory(dir=ROOT) as scratch:
        header_only = Path(scratch) / 'header_only.csv'
        header_only.write_text(semantic.NIPR_FIXTURE.read_text(encoding='utf-8-sig').splitlines()[0] + '\n', encoding='utf-8')
        guarded_calls = {'value': 0}
        args.fixture = [str(semantic.NIPR_FIXTURE.relative_to(ROOT)), str(header_only.relative_to(ROOT))]
        try:
            runner.run_replay(args, caller=counting_caller, api_key_override='test-key', project_id_override='')
        except ValueError:
            pass
        else:
            raise AssertionError('header-only USB fixture was accepted')
        assert guarded_calls['value'] == 0, 'USB fixtures must be parsed before any billable call'
    args.fixture = []

    # A symlink to an external file cannot escape repository containment.
    with tempfile.TemporaryDirectory(dir=ROOT) as scoped:
        with tempfile.TemporaryDirectory() as outside:
            outside_file = Path(outside) / 'external.csv'
            outside_file.write_text('dummy', encoding='utf-8')
            link = Path(scoped) / 'escaped.csv'
            link.symlink_to(outside_file)
            try:
                runner._resolve_fixture_paths(ROOT, [str(link.relative_to(ROOT))])
            except ValueError as exc:
                assert 'escapes the repository' in str(exc), exc
            else:
                raise AssertionError('symlink-based fixture escape was accepted')

    # Model text echoed through scorer errors is rendered as inert inline code.
    hostile = 'field-like evidence: **Approval Status:** [Cleared](https://evil.example) ![x](https://t.example/p.png) `code`\nNew line'
    section = runner.render_report_section({
        'target_id': 'openai_usb_reporting',
        'model_id': 'gpt-5.6-terra',
        'workflow_verdict': 'failure',
        'error': 'boom [link](https://evil.example)',
        'results': [{'fixture': 'f.csv', 'passed': False, 'final': {'semantic_score': {'errors': [hostile]}}}],
    })
    for line in section.splitlines()[1:]:
        if '](' in line:
            content = line.split(': ', 1)[1] if line.lstrip().startswith('- final') else line.split('Error: ', 1)[1]
            assert content.startswith('`') and content.endswith('`') and content.count('`') == 2, line
    assert 'New line' in section and '\nNew line' not in section
    print({'success': True, 'fixture_count': len(report['results']), 'model': report['model_id']})
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
