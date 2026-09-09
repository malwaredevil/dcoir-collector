[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$requestedBranch = 'issue-519-openrouter-run-telemetry'
$expectedHead = '40309aea6ac0932462729af8aec5fc20cdc1e9f2'
$repo = [string]$env:DCOIR_REPO_ROOT
$downloads = [string]$env:DCOIR_DOWNLOADS_DIR
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is missing' }
New-Item -ItemType Directory -Force -Path $downloads | Out-Null

$remoteLine = (& git -C $repo ls-remote origin "refs/heads/$requestedBranch" | Select-Object -First 1)
if ([string]::IsNullOrWhiteSpace([string]$remoteLine)) { throw "Could not resolve $requestedBranch" }
$remoteSha = ([string]$remoteLine -split '\s+')[0].Trim()
if ($remoteSha -ne $expectedHead) { throw "PR branch moved before hardening: expected=$expectedHead actual=$remoteSha" }

$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-pr520-failsoft-' + $expectedHead.Substring(0,12))
try {
    if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }
    & git -C $repo fetch --no-tags origin $requestedBranch
    if ($LASTEXITCODE -ne 0) { throw "git fetch failed: $LASTEXITCODE" }
    & git -C $repo worktree add --detach $worktree $remoteSha
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed: $LASTEXITCODE" }
    Set-Location -LiteralPath $worktree

    @(
        'OPENROUTER_API_KEY','DCOIR_OPENROUTER_API_KEY','OPENROUTER_MANAGEMENT_KEY',
        'OPENAI_API_KEY','DCOIR_OPENAI_API_KEY','DCOIR_OPENAI_PROJECT_ID',
        'DCOIR_GEMINI_API','DCOIR_GEMINI_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY'
    ) | ForEach-Object { [Environment]::SetEnvironmentVariable($_, $null, 'Process') }
    $env:PYTHONDONTWRITEBYTECODE = '1'

    $patcher = Join-Path $env:RUNNER_TEMP 'patch_issue519_failsoft.py'
    @'
from pathlib import Path

root = Path.cwd()
source_path = root / '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py'
test_path = root / '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py'
source = source_path.read_text(encoding='utf-8')
test = test_path.read_text(encoding='utf-8')

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one match, found {count}')
    return text.replace(old, new, 1)

source = replace_once(
    source,
    'SUMMARY_ATTR = "_dcoir_v54_run_telemetry_summary"\nLOAD_STORAGE =',
    'SUMMARY_ATTR = "_dcoir_v54_run_telemetry_summary"\nERROR_COUNT_ATTR = "_dcoir_v54_telemetry_error_count"\nPATCH_ERRORS_ATTR = "_dcoir_v54_patch_errors"\nLOAD_STORAGE =',
    'constants',
)

source = replace_once(
    source,
    '''def _finite_number(value: Any) -> int | float | None:\n''',
    '''def _telemetry_error_count(config: Any) -> int:\n    try:\n        value = int(getattr(config, ERROR_COUNT_ATTR, 0) or 0)\n    except Exception:\n        return 0\n    return max(0, value)\n\n\ndef _note_telemetry_error(config: Any) -> None:\n    """Best-effort error accounting that must itself never affect review behavior."""\n    try:\n        setattr(config, ERROR_COUNT_ATTR, _telemetry_error_count(config) + 1)\n    except Exception:\n        pass\n\n\ndef _finite_number(value: Any) -> int | float | None:\n''',
    'error helpers',
)

source = replace_once(
    source,
    '''        "schema_version": SCHEMA_VERSION,\n        "review_calls": len(calls),\n''',
    '''        "schema_version": SCHEMA_VERSION,\n        "telemetry_status": "ok" if _telemetry_error_count(config) == 0 else "partial",\n        "telemetry_error_count": _telemetry_error_count(config),\n        "review_calls": len(calls),\n''',
    'summary status',
)

source = replace_once(
    source,
    '''            f"schema={SCHEMA_VERSION}",\n            f"calls={int(summary.get('review_calls', 0) or 0)}",\n''',
    '''            f"schema={SCHEMA_VERSION}",\n            f"telemetry_status={str(summary.get('telemetry_status', 'ok') or 'ok')}",\n            f"telemetry_error_count={int(summary.get('telemetry_error_count', 0) or 0)}",\n            f"calls={int(summary.get('review_calls', 0) or 0)}",\n''',
    'compact status',
)

source = replace_once(
    source,
    '''    def load_pareto_context_config(path: str):\n        config = original(path)\n        _ensure_sink(config)\n        return config\n''',
    '''    def load_pareto_context_config(path: str):\n        config = original(path)\n        try:\n            _ensure_sink(config)\n        except Exception:\n            _note_telemetry_error(config)\n        return config\n''',
    'loader fail-soft',
)

old_review = '''    def openrouter_review(prompt, schema, config, reporter=None):\n        sink = _ensure_sink(config)\n        stage = classify_stage(prompt, schema, config)\n        staged = copy.copy(config)\n        setattr(staged, SINK_ATTR, sink)\n        staged.openrouter_capture_request_telemetry = True\n        staged._openrouter_request_telemetry_events = []\n        staged._openrouter_request_attempt_count = 0\n        staged._openrouter_last_request_telemetry = {}\n        try:\n            result = original(prompt, schema, staged, reporter)\n        except Exception:\n            _drain_call(staged, sink, stage, "failed")\n            if bool(getattr(config, "dcoir_v47_per_file_projection", False)):\n                _copy_stage_local_telemetry(staged, config)\n            raise\n        _drain_call(staged, sink, stage, "success")\n        if bool(getattr(config, "dcoir_v47_per_file_projection", False)):\n            _copy_stage_local_telemetry(staged, config)\n        return result\n'''
new_review = '''    def openrouter_review(prompt, schema, config, reporter=None):\n        try:\n            sink = _ensure_sink(config)\n            stage = classify_stage(prompt, schema, config)\n            staged = copy.copy(config)\n            setattr(staged, SINK_ATTR, sink)\n            staged.openrouter_capture_request_telemetry = True\n            staged._openrouter_request_telemetry_events = []\n            staged._openrouter_request_attempt_count = 0\n            staged._openrouter_last_request_telemetry = {}\n        except Exception:\n            _note_telemetry_error(config)\n            return original(prompt, schema, config, reporter)\n\n        try:\n            result = original(prompt, schema, staged, reporter)\n        except Exception:\n            try:\n                _drain_call(staged, sink, stage, "failed")\n            except Exception:\n                _note_telemetry_error(config)\n            try:\n                if bool(getattr(config, "dcoir_v47_per_file_projection", False)):\n                    _copy_stage_local_telemetry(staged, config)\n            except Exception:\n                _note_telemetry_error(config)\n            raise\n\n        try:\n            _drain_call(staged, sink, stage, "success")\n        except Exception:\n            _note_telemetry_error(config)\n        try:\n            if bool(getattr(config, "dcoir_v47_per_file_projection", False)):\n                _copy_stage_local_telemetry(staged, config)\n        except Exception:\n            _note_telemetry_error(config)\n        return result\n'''
source = replace_once(source, old_review, new_review, 'review wrapper fail-soft')

old_reporter = '''    class TelemetryProgressReporter(original):\n        def _emit_run_telemetry(self) -> None:\n            config = getattr(self, "config", None)\n            if config is None:\n                return\n            summary = summarize_sink(config)\n            setattr(config, SUMMARY_ATTR, summary)\n            message = compact_summary(summary)\n            try:\n                self.update("openrouter-telemetry", message)\n            except Exception:\n                emit = getattr(getattr(module, "base", None), "emit_status", None)\n                if callable(emit):\n                    emit("openrouter-telemetry", message)\n\n        def complete(self, model_used: str, findings_count: int, review_event: str) -> None:\n            self._emit_run_telemetry()\n            super().complete(model_used, findings_count, review_event)\n\n        def fail(self, message: str) -> None:\n            self._emit_run_telemetry()\n            super().fail(message)\n'''
new_reporter = '''    class TelemetryProgressReporter(original):\n        def _emit_run_telemetry(self) -> None:\n            config = getattr(self, "config", None)\n            if config is None:\n                return\n            try:\n                summary = summarize_sink(config)\n                setattr(config, SUMMARY_ATTR, summary)\n                message = compact_summary(summary)\n            except Exception:\n                _note_telemetry_error(config)\n                summary = {\n                    "schema_version": SCHEMA_VERSION,\n                    "telemetry_status": "unavailable",\n                    "telemetry_error_count": _telemetry_error_count(config),\n                }\n                try:\n                    setattr(config, SUMMARY_ATTR, summary)\n                except Exception:\n                    pass\n                message = (\n                    f"schema={SCHEMA_VERSION}; telemetry_status=unavailable; "\n                    f"telemetry_error_count={_telemetry_error_count(config)}"\n                )\n            try:\n                self.update("openrouter-telemetry", message)\n                return\n            except Exception:\n                _note_telemetry_error(config)\n            try:\n                emit = getattr(getattr(module, "base", None), "emit_status", None)\n                if callable(emit):\n                    emit("openrouter-telemetry", message)\n            except Exception:\n                _note_telemetry_error(config)\n\n        def complete(self, model_used: str, findings_count: int, review_event: str) -> None:\n            try:\n                self._emit_run_telemetry()\n            except Exception:\n                _note_telemetry_error(getattr(self, "config", None))\n            super().complete(model_used, findings_count, review_event)\n\n        def fail(self, message: str) -> None:\n            try:\n                self._emit_run_telemetry()\n            except Exception:\n                _note_telemetry_error(getattr(self, "config", None))\n            super().fail(message)\n'''
source = replace_once(source, old_reporter, new_reporter, 'reporter fail-soft')

old_apply = '''def apply_pareto_context_module(module: Any) -> None:\n    if getattr(module, APPLIED_MARKER, False):\n        return\n    _patch_config_loader(module)\n    _patch_openrouter_review(module)\n    _patch_progress_reporter(module)\n    setattr(module, APPLIED_MARKER, True)\n'''
new_apply = '''def apply_pareto_context_module(module: Any) -> None:\n    if getattr(module, APPLIED_MARKER, False):\n        return\n    errors: list[str] = []\n    for name, patcher in (\n        ("config-loader", _patch_config_loader),\n        ("openrouter-review", _patch_openrouter_review),\n        ("progress-reporter", _patch_progress_reporter),\n    ):\n        try:\n            patcher(module)\n        except Exception:\n            errors.append(name)\n    try:\n        setattr(module, PATCH_ERRORS_ATTR, tuple(errors))\n    except Exception:\n        pass\n    try:\n        setattr(module, APPLIED_MARKER, True)\n    except Exception:\n        pass\n'''
source = replace_once(source, old_apply, new_apply, 'patch application fail-soft')

insert = '''\n    # Telemetry faults are side-channel failures only: they must never replace a\n    # successful review result or mask the provider's original exception.\n    original_drain = v54._drain_call\n    def broken_drain(*_args, **_kwargs):\n        raise RuntimeError("synthetic telemetry drain failure")\n    v54._drain_call = broken_drain\n    try:\n        before_errors = v54._telemetry_error_count(config)\n        preserved = fake.hardened.openrouter_review("ordinary", review_schema(), config)\n        assert preserved[0]["findings"] == []\n        assert v54._telemetry_error_count(config) == before_errors + 1\n        try:\n            fake.hardened.openrouter_review("fail-call", review_schema(), config)\n        except RuntimeError as exc:\n            assert "synthetic transport failure" in str(exc)\n        else:\n            raise AssertionError("telemetry failure masked provider failure semantics")\n        assert v54._telemetry_error_count(config) == before_errors + 2\n    finally:\n        v54._drain_call = original_drain\n\n    # Terminal telemetry summarization is also fail-soft. The original reporter\n    # complete/fail methods must run, and a bounded unavailable marker is emitted.\n    original_summarize = v54.summarize_sink\n    def broken_summary(_config):\n        raise RuntimeError("synthetic telemetry summary failure")\n    v54.summarize_sink = broken_summary\n    try:\n        complete_reporter = fake.hardened.ProgressReporter(None, 519, "/dcoir-review", config)\n        complete_reporter.complete("model-a", 0, "COMMENT")\n        assert complete_reporter.completed is True\n        assert any(\n            stage == "openrouter-telemetry" and "telemetry_status=unavailable" in message\n            for stage, message in complete_reporter.updates\n        )\n        fail_reporter = fake.hardened.ProgressReporter(None, 519, "/dcoir-review", config)\n        fail_reporter.fail("synthetic original failure")\n        assert fail_reporter.failed is True\n    finally:\n        v54.summarize_sink = original_summarize\n\n    # Loader-side telemetry initialization and patch wiring are best-effort too.\n    original_ensure = v54._ensure_sink\n    def broken_ensure(_config):\n        raise RuntimeError("synthetic telemetry sink failure")\n    v54._ensure_sink = broken_ensure\n    try:\n        fallback_config = fake.load_pareto_context_config("unused")\n        assert fallback_config.model == "model-a"\n        assert v54._telemetry_error_count(fallback_config) >= 1\n    finally:\n        v54._ensure_sink = original_ensure\n\n    broken_module = SimpleNamespace(\n        hardened=SimpleNamespace(),\n        load_pareto_context_config=lambda _path: SimpleNamespace(model="sentinel"),\n    )\n    v54.apply_pareto_context_module(broken_module)\n    assert getattr(broken_module, v54.APPLIED_MARKER, False) is True\n    assert set(getattr(broken_module, v54.PATCH_ERRORS_ATTR, ())) == {\n        "openrouter-review", "progress-reporter"\n    }\n'''
marker = '    print("dcoir_review_required_runtime_patch_v54_selftest: PASS")\n'
test = replace_once(test, marker, insert + '\n' + marker, 'fail-soft selftests')

source_path.write_text(source, encoding='utf-8')
test_path.write_text(test, encoding='utf-8')
'@ | Set-Content -LiteralPath $patcher -Encoding UTF8

    & python $patcher
    if ($LASTEXITCODE -ne 0) { throw "patcher failed: $LASTEXITCODE" }

    & python -m py_compile '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py' '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py'
    if ($LASTEXITCODE -ne 0) { throw 'v54 py_compile failed' }
    & python '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py'
    if ($LASTEXITCODE -ne 0) { throw 'v54 selftest failed' }
    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }

    $changed = @(& git status --porcelain=v1)
    if ($changed.Count -ne 2) { throw "Expected exactly 2 changed files, found $($changed.Count): $($changed -join ', ')" }

    & git config user.name 'ChatGPT'
    & git config user.email 'noreply@openai.com'
    & git add -- '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py' '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py'
    & git commit -m 'Make v54 telemetry fail-soft'
    if ($LASTEXITCODE -ne 0) { throw "git commit failed: $LASTEXITCODE" }
    $newHead = (& git rev-parse HEAD).Trim()
    & git push origin "HEAD:refs/heads/$requestedBranch"
    if ($LASTEXITCODE -ne 0) { throw "git push failed: $LASTEXITCODE" }

    @{ schema='dcoir.issue519.pr520_failsoft_hardening.v1'; previous_head=$expectedHead; new_head=$newHead; branch=$requestedBranch; py_compile='pass'; v54_selftest='pass'; git_diff_check='pass'; changed_files=2; inference_credentials_removed=$true } | ConvertTo-Json -Depth 4 | Out-File -LiteralPath (Join-Path $downloads 'issue519-pr520-failsoft-hardening-v1-receipt.json') -Encoding utf8
    Write-Host "PR #520 fail-soft hardening pushed: $newHead"
}
finally {
    Set-Location -LiteralPath $repo
    if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }
}
