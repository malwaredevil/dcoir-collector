[CmdletBinding()]
param()

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$requestedBranch = 'issue-519-openrouter-run-telemetry'
$expectedHead = 'd9c406b6a0b528b4eca1ccd3ceeef4917610254a'
$repo = [string]$env:DCOIR_REPO_ROOT
$downloads = [string]$env:DCOIR_DOWNLOADS_DIR
if ([string]::IsNullOrWhiteSpace($repo)) { throw 'DCOIR_REPO_ROOT is missing' }
if ([string]::IsNullOrWhiteSpace($downloads)) { throw 'DCOIR_DOWNLOADS_DIR is missing' }
New-Item -ItemType Directory -Force -Path $downloads | Out-Null

$remoteLine = (& git -C $repo ls-remote origin "refs/heads/$requestedBranch" | Select-Object -First 1)
if ([string]::IsNullOrWhiteSpace([string]$remoteLine)) { throw "Could not resolve $requestedBranch" }
$remoteSha = ([string]$remoteLine -split '\s+')[0].Trim()
if ($remoteSha -ne $expectedHead) { throw "PR branch moved before final Copilot fixes: expected=$expectedHead actual=$remoteSha" }

$worktree = Join-Path $env:RUNNER_TEMP ('dcoir-pr520-copilot-final-' + $expectedHead.Substring(0,12))
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

    $patcher = Join-Path $env:RUNNER_TEMP 'patch_issue519_copilot_final.py'
    @'
from pathlib import Path

root = Path.cwd()
provider_path = root / '.github/dcoir_review/scripts/dcoir_review/hardened/part_04a_provider.py'
v54_path = root / '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py'
test_path = root / '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py'
entrypoint_path = root / '.github/dcoir_review/scripts/dcoir_review/entrypoint.py'

provider = provider_path.read_text(encoding='utf-8')
v54 = v54_path.read_text(encoding='utf-8')
test = test_path.read_text(encoding='utf-8')
entrypoint = entrypoint_path.read_text(encoding='utf-8')

def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one match, found {count}')
    return text.replace(old, new, 1)

# Provider: keep attempt/retry/fallback evidence as a fail-soft side channel.
provider = replace_once(
    provider,
    '''def _capture_openrouter_response_telemetry(\n''',
    '''def _note_openrouter_telemetry_error(config: Any) -> None:\n    try:\n        current = int(getattr(config, "_openrouter_request_telemetry_error_count", 0) or 0)\n    except Exception:\n        current = 0\n    try:\n        setattr(config, "_openrouter_request_telemetry_error_count", max(0, current) + 1)\n    except Exception:\n        return\n\n\ndef _record_openrouter_attempt_telemetry(config: Any, event: dict[str, Any]) -> None:\n    """Best-effort whitelisted attempt routing evidence; never changes retry behavior."""\n    if not bool(getattr(config, "openrouter_capture_request_telemetry", False)):\n        return\n    try:\n        try:\n            request_attempt_count = int(getattr(config, "_openrouter_request_attempt_count", 0) or 0)\n        except (TypeError, ValueError):\n            request_attempt_count = 0\n        outcome = str(event.get("outcome", "") or "").strip()\n        if outcome not in {"success", "retry", "fallback", "terminal_failure"}:\n            outcome = "unclassified"\n        item = {\n            "request_attempt_count": max(0, request_attempt_count),\n            "requested_model": str(event.get("requested_model", "") or "")[:160],\n            "model_index": int(event.get("model_index", 0) or 0),\n            "model_count": int(event.get("model_count", 0) or 0),\n            "attempt_in_model": int(event.get("attempt_in_model", 0) or 0),\n            "attempt_limit": int(event.get("attempt_limit", 0) or 0),\n            "outcome": outcome,\n            "failure_class": str(event.get("failure_class", "") or "")[:80],\n            "provider": str(event.get("provider", "") or "")[:120],\n        }\n        http_status = event.get("http_status")\n        if isinstance(http_status, int) and not isinstance(http_status, bool):\n            item["http_status"] = http_status\n        history = getattr(config, "_openrouter_request_attempt_telemetry_events", None)\n        if not isinstance(history, list):\n            history = []\n        setattr(config, "_openrouter_request_attempt_telemetry_events", [*history, item])\n    except Exception:\n        _note_openrouter_telemetry_error(config)\n\n\ndef _capture_openrouter_response_telemetry(\n''',
    'provider attempt telemetry helpers',
)

provider = replace_once(
    provider,
    '''                result, model_used, service_tier = openrouter_request_once(prompt, schema, config, ignored_providers, model)\n                if reporter:\n''',
    '''                result, model_used, service_tier = openrouter_request_once(prompt, schema, config, ignored_providers, model)\n                _record_openrouter_attempt_telemetry(\n                    config,\n                    {\n                        "requested_model": model,\n                        "model_index": model_index,\n                        "model_count": len(config.model_stack),\n                        "attempt_in_model": attempt,\n                        "attempt_limit": attempts,\n                        "outcome": "success",\n                    },\n                )\n                if reporter:\n''',
    'provider success attempt record',
)

provider = replace_once(
    provider,
    '''                retryable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504} or is_transient_inflight_credit_402(\n                    exc.code,\n                    message,\n                )\n                if retryable and attempt < attempts:\n''',
    '''                retryable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504} or is_transient_inflight_credit_402(\n                    exc.code,\n                    message,\n                )\n                attempt_outcome = (\n                    "retry"\n                    if retryable and attempt < attempts\n                    else ("fallback" if model_index < len(config.model_stack) else "terminal_failure")\n                )\n                _record_openrouter_attempt_telemetry(\n                    config,\n                    {\n                        "requested_model": model,\n                        "model_index": model_index,\n                        "model_count": len(config.model_stack),\n                        "attempt_in_model": attempt,\n                        "attempt_limit": attempts,\n                        "outcome": attempt_outcome,\n                        "failure_class": "http_error",\n                        "http_status": exc.code,\n                        "provider": provider,\n                    },\n                )\n                if retryable and attempt < attempts:\n''',
    'provider HTTP attempt record',
)

provider = replace_once(
    provider,
    '''            except RuntimeError as exc:\n                last_error = str(exc)\n                if "empty response" in last_error.lower() and attempt < attempts:\n                    delay = min(2**attempt, retry_cap)\n                    if reporter:\n                        reporter.update("openrouter-retry", f"{last_error}; retrying in {delay:.0f}s")\n                    time.sleep(delay)\n                    continue\n                break\n''',
    '''            except RuntimeError as exc:\n                last_error = str(exc)\n                empty_response = "empty response" in last_error.lower()\n                attempt_outcome = (\n                    "retry"\n                    if empty_response and attempt < attempts\n                    else ("fallback" if model_index < len(config.model_stack) else "terminal_failure")\n                )\n                _record_openrouter_attempt_telemetry(\n                    config,\n                    {\n                        "requested_model": model,\n                        "model_index": model_index,\n                        "model_count": len(config.model_stack),\n                        "attempt_in_model": attempt,\n                        "attempt_limit": attempts,\n                        "outcome": attempt_outcome,\n                        "failure_class": "empty_response" if empty_response else "runtime_error",\n                    },\n                )\n                if empty_response and attempt < attempts:\n                    delay = min(2**attempt, retry_cap)\n                    if reporter:\n                        reporter.update("openrouter-retry", f"{last_error}; retrying in {delay:.0f}s")\n                    time.sleep(delay)\n                    continue\n                break\n''',
    'provider RuntimeError attempt record',
)

provider = replace_once(
    provider,
    '''            except json.JSONDecodeError:\n                last_error = "OpenRouter returned invalid JSON"\n                if attempt < attempts:\n                    delay = min(2**attempt, retry_cap)\n                    if reporter:\n                        reporter.update("openrouter-retry", f"{last_error}; retrying in {delay:.0f}s")\n                    time.sleep(delay)\n                    continue\n                break\n''',
    '''            except json.JSONDecodeError:\n                last_error = "OpenRouter returned invalid JSON"\n                attempt_outcome = (\n                    "retry"\n                    if attempt < attempts\n                    else ("fallback" if model_index < len(config.model_stack) else "terminal_failure")\n                )\n                _record_openrouter_attempt_telemetry(\n                    config,\n                    {\n                        "requested_model": model,\n                        "model_index": model_index,\n                        "model_count": len(config.model_stack),\n                        "attempt_in_model": attempt,\n                        "attempt_limit": attempts,\n                        "outcome": attempt_outcome,\n                        "failure_class": "invalid_json",\n                    },\n                )\n                if attempt < attempts:\n                    delay = min(2**attempt, retry_cap)\n                    if reporter:\n                        reporter.update("openrouter-retry", f"{last_error}; retrying in {delay:.0f}s")\n                    time.sleep(delay)\n                    continue\n                break\n''',
    'provider JSON attempt record',
)

# v54: shared error accounting lives on the same sink already shared by shallow configs.
v54 = replace_once(
    v54,
    '''    def __init__(self) -> None:\n        self._lock = threading.Lock()\n        self._calls: list[dict[str, Any]] = []\n        self._events: list[dict[str, Any]] = []\n\n    def add_call(self, call: dict[str, Any], events: list[dict[str, Any]]) -> None:\n        with self._lock:\n            self._calls.append(dict(call))\n            self._events.extend(dict(item) for item in events)\n\n    def snapshot(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:\n        with self._lock:\n            return (\n                [dict(item) for item in self._calls],\n                [dict(item) for item in self._events],\n            )\n''',
    '''    def __init__(self) -> None:\n        self._lock = threading.Lock()\n        self._calls: list[dict[str, Any]] = []\n        self._events: list[dict[str, Any]] = []\n        self._error_count = 0\n\n    def add_call(self, call: dict[str, Any], events: list[dict[str, Any]]) -> None:\n        with self._lock:\n            self._calls.append(dict(call))\n            self._events.extend(dict(item) for item in events)\n\n    def add_errors(self, count: int = 1) -> None:\n        try:\n            parsed = int(count)\n        except (TypeError, ValueError):\n            parsed = 1\n        if parsed <= 0:\n            return\n        with self._lock:\n            self._error_count += parsed\n\n    def error_count(self) -> int:\n        with self._lock:\n            return max(0, int(self._error_count))\n\n    def snapshot(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:\n        with self._lock:\n            return (\n                [dict(item) for item in self._calls],\n                [dict(item) for item in self._events],\n            )\n''',
    'shared sink error count',
)

v54 = replace_once(
    v54,
    '''def _telemetry_error_count(config: Any) -> int:\n    try:\n        value = int(getattr(config, ERROR_COUNT_ATTR, 0) or 0)\n    except Exception:\n        return 0\n    return max(0, value)\n\n\ndef _note_telemetry_error(config: Any) -> None:\n    """Best-effort error accounting that must itself never affect review behavior."""\n    try:\n        setattr(config, ERROR_COUNT_ATTR, _telemetry_error_count(config) + 1)\n    except Exception:\n        # Error accounting is advisory; never let it alter review behavior.\n        return\n''',
    '''def _telemetry_error_count(config: Any) -> int:\n    try:\n        sink = getattr(config, SINK_ATTR, None)\n    except Exception:\n        sink = None\n    if isinstance(sink, RunTelemetrySink):\n        try:\n            return sink.error_count()\n        except Exception:\n            return 0\n    try:\n        value = int(getattr(config, ERROR_COUNT_ATTR, 0) or 0)\n    except Exception:\n        return 0\n    return max(0, value)\n\n\ndef _note_telemetry_error(config: Any) -> None:\n    """Best-effort shared error accounting that must never affect review behavior."""\n    try:\n        sink = getattr(config, SINK_ATTR, None)\n    except Exception:\n        sink = None\n    if isinstance(sink, RunTelemetrySink):\n        try:\n            sink.add_errors(1)\n            return\n        except Exception:\n            return\n    try:\n        setattr(config, ERROR_COUNT_ATTR, _telemetry_error_count(config) + 1)\n    except Exception:\n        # Error accounting is advisory; never let it alter review behavior.\n        return\n''',
    'shared error helpers',
)

v54 = replace_once(
    v54,
    '''def normalize_event(raw: Any, stage: str, call_outcome: str) -> dict[str, Any]:\n''',
    '''def normalize_event(raw: Any, stage: str, attempt_outcome: str = "attempt_outcome_missing") -> dict[str, Any]:\n''',
    'normalize event signature',
)
v54 = replace_once(
    v54,
    '''        "call_outcome": call_outcome,\n''',
    '''        "attempt_outcome": attempt_outcome,\n''',
    'normalize event attempt outcome field',
)

old_drain_start = v54.index('def _drain_call(')
old_drain_end = v54.index('\n\ndef _sum_metric', old_drain_start)
new_drain = '''def normalize_attempt(raw: Any) -> dict[str, Any]:\n    item = raw if isinstance(raw, dict) else {}\n    try:\n        attempt = int(item.get("request_attempt_count", 0) or 0)\n    except (TypeError, ValueError):\n        attempt = 0\n    outcome = str(item.get("outcome", "") or "").strip()\n    if outcome not in {"success", "retry", "fallback", "terminal_failure"}:\n        outcome = "unclassified"\n    normalized = {\n        "attempt": max(0, attempt),\n        "outcome": outcome,\n        "requested_model": str(item.get("requested_model", "") or "")[:160],\n        "provider": str(item.get("provider", "") or "")[:120],\n        "failure_class": str(item.get("failure_class", "") or "")[:80],\n    }\n    for key in ("model_index", "model_count", "attempt_in_model", "attempt_limit"):\n        try:\n            normalized[key] = max(0, int(item.get(key, 0) or 0))\n        except (TypeError, ValueError):\n            normalized[key] = 0\n    http_status = item.get("http_status")\n    if isinstance(http_status, int) and not isinstance(http_status, bool):\n        normalized["http_status"] = http_status\n    return normalized\n\n\ndef _drain_call(config: Any, sink: RunTelemetrySink, stage: str, outcome: str) -> None:\n    history = getattr(config, "_openrouter_request_telemetry_events", None)\n    raw_events = history if isinstance(history, list) else []\n    events = [normalize_event(item, stage) for item in raw_events]\n    attempt_history = getattr(config, "_openrouter_request_attempt_telemetry_events", None)\n    raw_attempts = attempt_history if isinstance(attempt_history, list) else []\n    detailed_attempts = [normalize_attempt(item) for item in raw_attempts]\n    try:\n        provider_errors = int(getattr(config, "_openrouter_request_telemetry_error_count", 0) or 0)\n    except (TypeError, ValueError):\n        provider_errors = 0\n    if provider_errors > 0:\n        sink.add_errors(provider_errors)\n    try:\n        attempts = int(getattr(config, "_openrouter_request_attempt_count", 0) or 0)\n    except (TypeError, ValueError):\n        attempts = 0\n    attempts = max(0, attempts)\n\n    response_map: dict[int, dict[str, Any]] = {}\n    for event in events:\n        raw_attempt = _finite_number(event.get("request_attempt_count"))\n        if isinstance(raw_attempt, int) and 1 <= raw_attempt <= attempts:\n            response_map.setdefault(raw_attempt, event)\n\n    detailed_map: dict[int, dict[str, Any]] = {}\n    for attempt in detailed_attempts:\n        attempt_number = attempt.get("attempt")\n        if isinstance(attempt_number, int) and 1 <= attempt_number <= attempts:\n            detailed_map[attempt_number] = attempt\n\n    attempt_records: list[dict[str, Any]] = []\n    for attempt_number in range(1, attempts + 1):\n        response = response_map.get(attempt_number)\n        detailed = detailed_map.get(attempt_number)\n        if isinstance(detailed, dict):\n            record = dict(detailed)\n        else:\n            record = {\n                "attempt": attempt_number,\n                "outcome": "attempt_outcome_missing",\n                "requested_model": "",\n                "provider": "",\n                "failure_class": "",\n                "model_index": 0,\n                "model_count": 0,\n                "attempt_in_model": 0,\n                "attempt_limit": 0,\n            }\n        if isinstance(response, dict):\n            response["attempt_outcome"] = str(record.get("outcome", "attempt_outcome_missing"))\n            for key in ("requested_model", "served_model", "provider", "service_tier", "finish_reason"):\n                value = str(response.get(key, "") or "")\n                if value:\n                    record[key] = value\n        attempt_records.append(record)\n\n    for event in events:\n        raw_attempt = _finite_number(event.get("request_attempt_count"))\n        if not isinstance(raw_attempt, int) or raw_attempt not in response_map:\n            event["attempt_outcome"] = "attempt_outcome_missing"\n\n    observed_attempts = len(response_map)\n    sink.add_call(\n        {\n            "stage": stage,\n            "outcome": outcome,\n            "request_attempts": attempts,\n            "response_events": observed_attempts,\n            "attempts_without_response_telemetry": max(0, attempts - observed_attempts),\n            "attempt_records": attempt_records,\n        },\n        events,\n    )\n'''
v54 = v54[:old_drain_start] + new_drain + v54[old_drain_end:]

v54 = replace_once(
    v54,
    '''def summarize_sink(config: Any) -> dict[str, Any]:\n''',
    '''def _category_counts(events: list[dict[str, Any]], key: str) -> Counter[str]:\n    return Counter(str(item.get(key, "") or "").strip() or "unknown" for item in events)\n\n\ndef _category_coverage(events: list[dict[str, Any]], key: str) -> dict[str, int]:\n    observed = sum(1 for item in events if str(item.get(key, "") or "").strip())\n    return {"observed_events": observed, "missing_events": len(events) - observed}\n\n\ndef summarize_sink(config: Any) -> dict[str, Any]:\n''',
    'category coverage helpers',
)

v54 = replace_once(
    v54,
    '''    stage_attempt_outcomes: dict[str, Counter[str]] = {}\n    stage_events: dict[str, list[dict[str, Any]]] = {}\n''',
    '''    stage_attempt_outcomes: dict[str, Counter[str]] = {}\n    stage_attempt_models: dict[str, Counter[str]] = {}\n    attempt_requested_models: Counter[str] = Counter()\n    stage_events: dict[str, list[dict[str, Any]]] = {}\n''',
    'attempt model counters init',
)

v54 = replace_once(
    v54,
    '''        if isinstance(attempts, list):\n            for attempt in attempts:\n                if isinstance(attempt, dict):\n                    counter[str(attempt.get("outcome", "unclassified"))] += 1\n''',
    '''        if isinstance(attempts, list):\n            model_counter = stage_attempt_models.setdefault(stage, Counter())\n            for attempt in attempts:\n                if isinstance(attempt, dict):\n                    counter[str(attempt.get("outcome", "unclassified"))] += 1\n                    requested_model = str(attempt.get("requested_model", "") or "").strip() or "unknown"\n                    model_counter[requested_model] += 1\n                    attempt_requested_models[requested_model] += 1\n''',
    'attempt model counters accumulation',
)

old_categories = '''    providers = Counter(\n        str(item.get("provider", "")) for item in events if str(item.get("provider", ""))\n    )\n    service_tiers = Counter(\n        str(item.get("service_tier", "") or "").strip() or "unknown"\n        for item in events\n    )\n    requested_models = Counter(\n        str(item.get("requested_model", ""))\n        for item in events\n        if str(item.get("requested_model", ""))\n    )\n    served_models = Counter(\n        str(item.get("served_model", ""))\n        for item in events\n        if str(item.get("served_model", ""))\n    )\n    finish_reasons = Counter(\n        str(item.get("finish_reason", ""))\n        for item in events\n        if str(item.get("finish_reason", ""))\n    )\n'''
new_categories = '''    providers = _category_counts(events, "provider")\n    service_tiers = _category_counts(events, "service_tier")\n    requested_models = _category_counts(events, "requested_model")\n    served_models = _category_counts(events, "served_model")\n    finish_reasons = _category_counts(events, "finish_reason")\n'''
v54 = replace_once(v54, old_categories, new_categories, 'global unknown categories')

v54 = replace_once(
    v54,
    '''                "attempt_outcomes": dict(sorted(stage_attempt_outcomes.get(stage, Counter()).items())),\n                "metrics": {\n''',
    '''                "attempt_outcomes": dict(sorted(stage_attempt_outcomes.get(stage, Counter()).items())),\n                "attempt_requested_models": dict(sorted(stage_attempt_models.get(stage, Counter()).items())),\n                "metrics": {\n''',
    'per-stage attempt models',
)

old_stage_categories = '''                "providers": dict(\n                    sorted(\n                        Counter(\n                            str(item.get("provider", ""))\n                            for item in stage_events.get(stage, [])\n                            if str(item.get("provider", ""))\n                        ).items()\n                    )\n                ),\n                "requested_models": dict(\n                    sorted(\n                        Counter(\n                            str(item.get("requested_model", ""))\n                            for item in stage_events.get(stage, [])\n                            if str(item.get("requested_model", ""))\n                        ).items()\n                    )\n                ),\n                "served_models": dict(\n                    sorted(\n                        Counter(\n                            str(item.get("served_model", ""))\n                            for item in stage_events.get(stage, [])\n                            if str(item.get("served_model", ""))\n                        ).items()\n                    )\n                ),\n                "finish_reasons": dict(\n                    sorted(\n                        Counter(\n                            str(item.get("finish_reason", ""))\n                            for item in stage_events.get(stage, [])\n                            if str(item.get("finish_reason", ""))\n                        ).items()\n                    )\n                ),\n                "service_tiers": dict(\n                    sorted(\n                        Counter(\n                            str(item.get("service_tier", "") or "").strip() or "unknown"\n                            for item in stage_events.get(stage, [])\n                        ).items()\n                    )\n                ),\n'''
new_stage_categories = '''                "providers": dict(sorted(_category_counts(stage_events.get(stage, []), "provider").items())),\n                "requested_models": dict(sorted(_category_counts(stage_events.get(stage, []), "requested_model").items())),\n                "served_models": dict(sorted(_category_counts(stage_events.get(stage, []), "served_model").items())),\n                "finish_reasons": dict(sorted(_category_counts(stage_events.get(stage, []), "finish_reason").items())),\n                "service_tiers": dict(sorted(_category_counts(stage_events.get(stage, []), "service_tier").items())),\n                "metadata_coverage": {\n                    key: _category_coverage(stage_events.get(stage, []), key)\n                    for key in ("provider", "service_tier", "requested_model", "served_model", "finish_reason")\n                },\n'''
v54 = replace_once(v54, old_stage_categories, new_stage_categories, 'per-stage unknown categories')

v54 = replace_once(
    v54,
    '''        "providers": dict(sorted(providers.items())),\n        "service_tiers": dict(sorted(service_tiers.items())),\n        "requested_models": dict(sorted(requested_models.items())),\n        "served_models": dict(sorted(served_models.items())),\n        "finish_reasons": dict(sorted(finish_reasons.items())),\n''',
    '''        "providers": dict(sorted(providers.items())),\n        "service_tiers": dict(sorted(service_tiers.items())),\n        "requested_models": dict(sorted(requested_models.items())),\n        "served_models": dict(sorted(served_models.items())),\n        "finish_reasons": dict(sorted(finish_reasons.items())),\n        "attempt_requested_models": dict(sorted(attempt_requested_models.items())),\n        "metadata_coverage": {\n            key: _category_coverage(events, key)\n            for key in ("provider", "service_tier", "requested_model", "served_model", "finish_reason")\n        },\n''',
    'global category coverage',
)

v54 = replace_once(
    v54,
    '''    finish_reasons = summary.get("finish_reasons") if isinstance(summary.get("finish_reasons"), dict) else {}\n    recoveries = (\n''',
    '''    finish_reasons = summary.get("finish_reasons") if isinstance(summary.get("finish_reasons"), dict) else {}\n    attempt_requested_models = (\n        summary.get("attempt_requested_models")\n        if isinstance(summary.get("attempt_requested_models"), dict)\n        else {}\n    )\n    metadata_coverage = (\n        summary.get("metadata_coverage") if isinstance(summary.get("metadata_coverage"), dict) else {}\n    )\n    recoveries = (\n''',
    'compact attempt and coverage inputs',
)

v54 = replace_once(
    v54,
    '''    recovery_text = category(recoveries)\n    attempt_outcome_text = (\n''',
    '''    recovery_text = category(recoveries)\n    attempt_model_text = category(attempt_requested_models)\n    metadata_missing_text = ",".join(\n        f"{name}:{int(data.get('missing_events', 0) or 0)}"\n        for name, data in sorted(metadata_coverage.items())\n        if isinstance(data, dict)\n    ) or "none"\n    attempt_outcome_text = (\n''',
    'compact coverage text',
)

v54 = replace_once(
    v54,
    '''            f"attempt_outcomes={attempt_outcome_text}",\n            f"providers={provider_text}",\n''',
    '''            f"attempt_outcomes={attempt_outcome_text}",\n            f"attempt_models={attempt_model_text}",\n            f"metadata_missing={metadata_missing_text}",\n            f"providers={provider_text}",\n''',
    'compact attempt models and missing coverage',
)

v54 = replace_once(
    v54,
    '''            staged._openrouter_request_telemetry_events = []\n            staged._openrouter_request_attempt_count = 0\n            staged._openrouter_last_request_telemetry = {}\n''',
    '''            staged._openrouter_request_telemetry_events = []\n            staged._openrouter_request_attempt_telemetry_events = []\n            staged._openrouter_request_telemetry_error_count = 0\n            staged._openrouter_request_attempt_count = 0\n            staged._openrouter_last_request_telemetry = {}\n''',
    'reset detailed attempt telemetry',
)

v54 = replace_once(
    v54,
    '''        "_openrouter_request_telemetry_events",\n        "_openrouter_request_attempt_count",\n        "_openrouter_last_request_telemetry",\n''',
    '''        "_openrouter_request_telemetry_events",\n        "_openrouter_request_attempt_telemetry_events",\n        "_openrouter_request_telemetry_error_count",\n        "_openrouter_request_attempt_count",\n        "_openrouter_last_request_telemetry",\n''',
    'copy detailed attempt telemetry',
)

# Entrypoint: if v54 rolls back after a partial install, still emit one explicit bounded unavailable marker.
entrypoint = replace_once(
    entrypoint,
    '''    def run(self) -> None:\n        review_module = self.import_module(self.review_module_name)\n        self.apply_runtime_patches(review_module)\n        review_module.main()\n''',
    '''    def _emit_telemetry_patch_unavailable(self, review_module: ModuleType) -> None:\n        try:\n            errors = getattr(review_module, "_dcoir_v54_patch_errors", ())\n        except Exception:\n            return\n        if not isinstance(errors, (tuple, list)) or not errors:\n            return\n        safe_errors = []\n        for value in errors:\n            cleaned = "".join(\n                char for char in str(value) if char.isalnum() or char in {"-", "_", "."}\n            )[:48]\n            if cleaned:\n                safe_errors.append(cleaned)\n        detail = ",".join(safe_errors) or "unknown"\n        message = (\n            "schema=dcoir_openrouter_run_telemetry_v1; telemetry_status=unavailable; "\n            f"patch_errors={detail}"\n        )[:600]\n        try:\n            base = getattr(review_module, "base", None)\n            emit = getattr(base, "emit_status", None)\n            if callable(emit):\n                emit("openrouter-telemetry", message)\n        except Exception:\n            return\n\n    def run(self) -> None:\n        review_module = self.import_module(self.review_module_name)\n        try:\n            self.apply_runtime_patches(review_module)\n            review_module.main()\n        finally:\n            self._emit_telemetry_patch_unavailable(review_module)\n''',
    'entrypoint unavailable telemetry marker',
)

# Selftest: teach the synthetic provider about detailed attempt outcomes.
test = replace_once(
    test,
    '''        if "fail-call" in text:\n            config._openrouter_request_attempt_count = 2\n            config._openrouter_request_telemetry_events = []\n            raise RuntimeError("synthetic transport failure")\n''',
    '''        if "fail-call" in text:\n            config._openrouter_request_attempt_count = 2\n            config._openrouter_request_telemetry_events = []\n            config._openrouter_request_attempt_telemetry_events = [\n                {\n                    "request_attempt_count": 1,\n                    "requested_model": "model-a",\n                    "model_index": 1,\n                    "model_count": 2,\n                    "attempt_in_model": 1,\n                    "attempt_limit": 2,\n                    "outcome": "retry",\n                    "failure_class": "empty_response",\n                },\n                {\n                    "request_attempt_count": 2,\n                    "requested_model": "model-a",\n                    "model_index": 1,\n                    "model_count": 2,\n                    "attempt_in_model": 2,\n                    "attempt_limit": 2,\n                    "outcome": "terminal_failure",\n                    "failure_class": "runtime_error",\n                },\n            ]\n            raise RuntimeError("synthetic transport failure")\n''',
    'selftest failed attempt detail',
)

test = replace_once(
    test,
    '''        config._openrouter_request_telemetry_events = [raw]\n        config._openrouter_last_request_telemetry = {\n''',
    '''        if "retry-call" in text:\n            config._openrouter_request_attempt_telemetry_events = [\n                {\n                    "request_attempt_count": 1,\n                    "requested_model": "model-a",\n                    "model_index": 1,\n                    "model_count": 2,\n                    "attempt_in_model": 1,\n                    "attempt_limit": 2,\n                    "outcome": "retry",\n                    "failure_class": "empty_response",\n                },\n                {\n                    "request_attempt_count": 2,\n                    "requested_model": "model-a",\n                    "model_index": 1,\n                    "model_count": 2,\n                    "attempt_in_model": 2,\n                    "attempt_limit": 2,\n                    "outcome": "success",\n                },\n            ]\n        else:\n            config._openrouter_request_attempt_telemetry_events = [\n                {\n                    "request_attempt_count": 1,\n                    "requested_model": "model-a",\n                    "model_index": 1,\n                    "model_count": 2,\n                    "attempt_in_model": 1,\n                    "attempt_limit": 1,\n                    "outcome": "success",\n                }\n            ]\n        config._openrouter_request_telemetry_events = [raw]\n        config._openrouter_last_request_telemetry = {\n''',
    'selftest success/retry attempt detail',
)

test = replace_once(
    test,
    '''    assert summary["stages"]["primary-semantic"]["attempt_outcomes"] == {\n        "response_telemetry_missing": 1,\n        "response_telemetry_observed": 1,\n    }\n''',
    '''    assert summary["stages"]["primary-semantic"]["attempt_outcomes"] == {\n        "retry": 1,\n        "success": 1,\n    }\n    assert summary["stages"]["primary-semantic"]["attempt_requested_models"] == {"model-a": 2}\n    assert summary["attempt_requested_models"] == {"model-a": 2}\n''',
    'selftest retry outcomes',
)

test = replace_once(
    test,
    '''    assert summary["stages"]["primary-semantic"]["attempt_outcomes"] == {\n        "response_telemetry_missing": 3,\n        "response_telemetry_observed": 1,\n    }\n''',
    '''    assert summary["stages"]["primary-semantic"]["attempt_outcomes"] == {\n        "retry": 2,\n        "success": 1,\n        "terminal_failure": 1,\n    }\n''',
    'selftest failed outcomes',
)

test = replace_once(
    test,
    '''    assert missing["cost"] is None\n\n    # The existing terminal progress surface is the durable production output;\n''',
    '''    assert missing["cost"] is None\n\n    # Missing categorical response metadata is explicit, not silently filtered.\n    missing_config = fake.load_pareto_context_config("unused")\n    missing_sink = getattr(missing_config, v54.SINK_ATTR)\n    missing_event = v54.normalize_event(\n        {"usage": {}}, "primary-semantic", "success"\n    )\n    missing_sink.add_call(\n        {\n            "stage": "primary-semantic",\n            "outcome": "success",\n            "request_attempts": 1,\n            "response_events": 1,\n            "attempts_without_response_telemetry": 0,\n            "attempt_records": [\n                {"attempt": 1, "outcome": "success", "requested_model": "model-a"}\n            ],\n        },\n        [missing_event],\n    )\n    missing_summary = v54.summarize_sink(missing_config)\n    assert missing_summary["providers"] == {"unknown": 1}\n    assert missing_summary["requested_models"] == {"unknown": 1}\n    assert missing_summary["served_models"] == {"unknown": 1}\n    assert missing_summary["finish_reasons"] == {"unknown": 1}\n    assert missing_summary["service_tiers"] == {"unknown": 1}\n    assert missing_summary["metadata_coverage"]["provider"] == {\n        "observed_events": 0, "missing_events": 1\n    }\n    assert "metadata_missing=" in v54.compact_summary(missing_summary)\n\n    # Errors raised on shallow stage projections must surface on the root config.\n    error_config = fake.load_pareto_context_config("unused")\n    shallow_error_config = copy.copy(error_config)\n    v54._note_telemetry_error(shallow_error_config)\n    assert v54._telemetry_error_count(error_config) == 1\n    assert v54.summarize_sink(error_config)["telemetry_status"] == "partial"\n\n    # The existing terminal progress surface is the durable production output;\n''',
    'selftest missing categories and shared errors',
)

test = replace_once(
    test,
    '''    assert "attempt_outcomes=" in telemetry_updates[0]\n    assert "requested_models=" in telemetry_updates[0]\n''',
    '''    assert "attempt_outcomes=" in telemetry_updates[0]\n    assert "attempt_models=" in telemetry_updates[0]\n    assert "metadata_missing=" in telemetry_updates[0]\n    assert "requested_models=" in telemetry_updates[0]\n''',
    'selftest durable attempt fields',
)

test = replace_once(
    test,
    '''    broken_module = SimpleNamespace(\n        hardened=SimpleNamespace(),\n        load_pareto_context_config=lambda _path: SimpleNamespace(model="sentinel"),\n    )\n''',
    '''    unavailable_updates: list[tuple[str, str]] = []\n    broken_module = SimpleNamespace(\n        hardened=SimpleNamespace(),\n        base=SimpleNamespace(\n            emit_status=lambda stage, message: unavailable_updates.append((stage, message))\n        ),\n        load_pareto_context_config=lambda _path: SimpleNamespace(model="sentinel"),\n    )\n''',
    'selftest unavailable capture surface',
)

test = replace_once(
    test,
    '''    assert broken_module.load_pareto_context_config is original_loader\n    assert not hasattr(broken_module, v54.LOAD_STORAGE)\n\n    print("dcoir_review_required_runtime_patch_v54_selftest: PASS")\n''',
    '''    assert broken_module.load_pareto_context_config is original_loader\n    assert not hasattr(broken_module, v54.LOAD_STORAGE)\n    entrypoint._emit_telemetry_patch_unavailable(broken_module)\n    assert len(unavailable_updates) == 1\n    assert unavailable_updates[0][0] == "openrouter-telemetry"\n    assert "telemetry_status=unavailable" in unavailable_updates[0][1]\n    assert "openrouter-review" in unavailable_updates[0][1]\n    assert "progress-reporter" in unavailable_updates[0][1]\n\n    # Provider-side attempt telemetry itself is bounded and prompt-free.\n    provider_probe = copy.copy(production_config)\n    provider_probe.openrouter_capture_request_telemetry = True\n    provider_probe._openrouter_request_attempt_count = 1\n    review.hardened._record_openrouter_attempt_telemetry(\n        provider_probe,\n        {\n            "requested_model": "model-a",\n            "model_index": 1,\n            "model_count": 2,\n            "attempt_in_model": 1,\n            "attempt_limit": 4,\n            "outcome": "fallback",\n            "failure_class": "http_error",\n            "http_status": 503,\n            "provider": "Provider A",\n            "prompt": "SECRET_PROMPT_MUST_NOT_SURVIVE",\n        },\n    )\n    provider_attempt = provider_probe._openrouter_request_attempt_telemetry_events[0]\n    assert provider_attempt["outcome"] == "fallback"\n    assert provider_attempt["http_status"] == 503\n    assert "prompt" not in provider_attempt\n\n    print("dcoir_review_required_runtime_patch_v54_selftest: PASS")\n''',
    'selftest unavailable marker and provider attempt whitelist',
)

provider_path.write_text(provider, encoding='utf-8')
v54_path.write_text(v54, encoding='utf-8')
test_path.write_text(test, encoding='utf-8')
entrypoint_path.write_text(entrypoint, encoding='utf-8')
'@ | Set-Content -LiteralPath $patcher -Encoding UTF8

    & python $patcher
    if ($LASTEXITCODE -ne 0) { throw "patcher failed: $LASTEXITCODE" }

    $changedPython = @(
        '.github/dcoir_review/scripts/dcoir_review/hardened/part_04a_provider.py',
        '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54.py',
        '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py',
        '.github/dcoir_review/scripts/dcoir_review/entrypoint.py'
    )
    & python -m py_compile @changedPython
    if ($LASTEXITCODE -ne 0) { throw 'changed-file py_compile failed' }

    & python '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v54_selftest.py'
    if ($LASTEXITCODE -ne 0) { throw 'v54 selftest failed' }
    & python '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v47_selftest.py'
    if ($LASTEXITCODE -ne 0) { throw 'v47 selftest failed' }
    & python '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v48_selftest.py'
    if ($LASTEXITCODE -ne 0) { throw 'v48 selftest failed' }
    & python '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v52_selftest.py'
    if ($LASTEXITCODE -ne 0) { throw 'v52 selftest failed' }
    & python '.github/dcoir_review/scripts/dcoir_review_required_runtime_patch_v53_selftest.py'
    if ($LASTEXITCODE -ne 0) { throw 'v53 selftest failed' }
    & python '.github/dcoir_review/scripts/openrouter_pr_review_hardened_selftest.py'
    if ($LASTEXITCODE -ne 0) { throw 'hardened provider selftest failed' }
    & python '.github/dcoir_review/scripts/dcoir_review_architecture_b_benchmark_selftest.py'
    if ($LASTEXITCODE -ne 0) { throw 'Architecture-B benchmark selftest failed' }
    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw 'git diff --check failed' }

    $changed = @(& git status --porcelain=v1)
    if ($changed.Count -ne 4) { throw "Expected exactly 4 changed files, found $($changed.Count): $($changed -join ', ')" }

    & git config user.name 'ChatGPT'
    & git config user.email 'noreply@openai.com'
    & git add -- @changedPython
    & git commit -m 'Resolve final v54 telemetry review gaps'
    if ($LASTEXITCODE -ne 0) { throw "git commit failed: $LASTEXITCODE" }
    $newHead = (& git rev-parse HEAD).Trim()
    & git push origin "HEAD:refs/heads/$requestedBranch"
    if ($LASTEXITCODE -ne 0) { throw "git push failed: $LASTEXITCODE" }

    @{
        schema='dcoir.issue519.pr520_copilot_final_fixes.v1'
        previous_head=$expectedHead
        new_head=$newHead
        branch=$requestedBranch
        changed_files=4
        py_compile='pass'
        v54_selftest='pass'
        v47_selftest='pass'
        v48_selftest='pass'
        v52_selftest='pass'
        v53_selftest='pass'
        hardened_selftest='pass'
        architecture_b_benchmark='pass'
        git_diff_check='pass'
        inference_credentials_removed=$true
    } | ConvertTo-Json -Depth 4 | Out-File -LiteralPath (Join-Path $downloads 'issue519-pr520-copilot-final-fixes-v1-receipt.json') -Encoding utf8
    Write-Host "PR #520 final Copilot fixes pushed: $newHead"
}
finally {
    Set-Location -LiteralPath $repo
    if (Test-Path -LiteralPath $worktree) { & git -C $repo worktree remove --force $worktree 2>$null }
}
