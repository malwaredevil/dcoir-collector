def build_openrouter_payload(prompt: str, schema: dict[str, Any], config: Any, ignored_providers: list[str], model: str) -> dict[str, Any]:
    provider: dict[str, Any] = {"allow_fallbacks": True, "require_parameters": True}
    clean_ignored = [item for item in ignored_providers if item]
    if clean_ignored:
        provider["ignore"] = clean_ignored

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": base.read_text(".github/dcoir_review/prompts/openrouter-pr-review-system.md")},
            {"role": "user", "content": prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "openrouter_pr_review", "strict": True, "schema": schema},
        },
        "provider": provider,
        "temperature": 0.2,
    }

    fallbacks = getattr(config, "fallback_models", [])
    if fallbacks:
        payload["models"] = [model, *fallbacks]
    route = getattr(config, "openrouter_route", "")
    if route:
        payload["route"] = route
    service_tier = getattr(config, "openrouter_service_tier", "")
    if service_tier:
        payload["service_tier"] = service_tier
    sticky_session = session_id(config)
    if sticky_session:
        payload["session_id"] = sticky_session

    if model == "openrouter/auto":
        plugin: dict[str, Any] = {"id": "auto-router"}
        allowed_models = getattr(config, "auto_allowed_models", [])
        if allowed_models:
            plugin["allowed_models"] = allowed_models
        tradeoff = getattr(config, "auto_cost_quality_tradeoff", None)
        if tradeoff is not None:
            plugin["cost_quality_tradeoff"] = tradeoff
        payload["plugins"] = [plugin]

    return payload


def _response_provider(data: dict[str, Any]) -> str:
    provider = str(data.get("provider", "") or "").strip()
    if provider:
        return provider
    metadata = data.get("openrouter_metadata")
    if not isinstance(metadata, dict):
        return ""
    endpoints = metadata.get("endpoints")
    if not isinstance(endpoints, dict):
        return ""
    available = endpoints.get("available")
    if not isinstance(available, list):
        return ""
    selected = next(
        (item for item in available if isinstance(item, dict) and bool(item.get("selected"))),
        None,
    )
    if not isinstance(selected, dict):
        return ""
    return str(selected.get("provider", "") or selected.get("name", "") or "").strip()


def _response_healing_pipeline(data: dict[str, Any]) -> list[Any]:
    metadata = data.get("openrouter_metadata")
    if not isinstance(metadata, dict):
        return []
    pipeline = metadata.get("pipeline")
    return list(pipeline) if isinstance(pipeline, list) else []


def _record_v47_request_telemetry(config: Any, event: dict[str, Any]) -> None:
    history = getattr(config, "_dcoir_v47_request_telemetry_events", None)
    if not isinstance(history, list):
        history = []
    history = [*history, dict(event)]
    setattr(config, "_dcoir_v47_request_telemetry_events", history)

    aggregate_cost = 0.0
    cost_observed = False
    for item in history:
        value = item.get("cost") if isinstance(item, dict) else None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            aggregate_cost += float(value)
            cost_observed = True

    telemetry = dict(event)
    telemetry["request_events"] = [dict(item) for item in history]
    telemetry["aggregate_cost"] = aggregate_cost if cost_observed else None
    setattr(config, "_dcoir_v47_last_request_telemetry", telemetry)


def openrouter_request_once(
    prompt: str,
    schema: dict[str, Any],
    config: Any,
    ignored_providers: list[str],
    model: str,
) -> tuple[dict[str, Any], str, str]:
    projected_per_file = bool(getattr(config, "dcoir_v47_per_file_projection", False))
    if projected_per_file:
        attempt_count = int(getattr(config, "_dcoir_v47_request_attempt_count", 0) or 0) + 1
        setattr(config, "_dcoir_v47_request_attempt_count", attempt_count)
    else:
        attempt_count = 0

    api_key = base.env_required("OPENROUTER_API_KEY")
    payload = build_openrouter_payload(prompt, schema, config, ignored_providers, model)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/DCOIR-Collector/dcoir-collector",
        "X-OpenRouter-Title": base.REVIEW_DISPLAY_NAME,
    }
    sticky_session = session_id(config)
    if sticky_session:
        headers["X-Session-Id"] = sticky_session

    req = urllib.request.Request(OPENROUTER_API, data=json.dumps(payload).encode("utf-8"), method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=180) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw)

    if projected_per_file:
        if not isinstance(data, dict):
            raise RuntimeError("OpenRouter returned a non-object response")
        choices = data.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        model_used = str(data.get("model", model))
        service_tier = str(data.get("service_tier", "") or "")
        finish_reason = str(choice.get("finish_reason", "") or "").strip() if isinstance(choice, dict) else ""
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        cost = data.get("cost") if data.get("cost") is not None else usage.get("cost")
        pipeline = _response_healing_pipeline(data)
        event = {
            "requested_model": str(model),
            "served_model": model_used,
            "served_model_differs_from_requested": model_used != str(model),
            "provider": _response_provider(data),
            "service_tier": service_tier,
            "finish_reason": finish_reason,
            "usage": usage,
            "cost": cost,
            "request_attempt_count": attempt_count,
            "response_healing_pipeline": pipeline,
            "response_healing_observed": any(
                isinstance(item, dict)
                and (
                    str(item.get("type", "") or "") == "response_healing"
                    or str(item.get("name", "") or "") == "response-healing"
                )
                for item in pipeline
            ),
        }
        _record_v47_request_telemetry(config, event)
        if not isinstance(choice, dict):
            raise RuntimeError("OpenRouter returned an invalid choices payload")
        if bool(getattr(config, "openrouter_require_stop_finish_reason", False)) and finish_reason != "stop":
            reason = finish_reason or "missing"
            raise RuntimeError(f"OpenRouter capped completion did not finish with stop: finish_reason={reason}")
        message = choice.get("message")
        content = message.get("content", "") if isinstance(message, dict) else ""
    else:
        model_used = str(data.get("model", model))
        service_tier = str(data.get("service_tier", "") or "")
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

    if not content:
        raise RuntimeError("OpenRouter returned an empty response")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(1))
    if projected_per_file and not isinstance(parsed, dict):
        raise RuntimeError("OpenRouter structured output did not have an object root")
    return parsed, model_used, service_tier


def is_transient_inflight_credit_402(status_code: int, message: str) -> bool:
    normalized = " ".join(str(message).lower().split())
    return (
        status_code == 402
        and "credit" in normalized
        and "in-flight request" in normalized
        and ("retry after" in normalized or "settle" in normalized)
    )


def openrouter_review(prompt: str, schema: dict[str, Any], config: Any, reporter: Any | None = None) -> tuple[dict[str, Any], str, str]:
    attempts = max(1, config.openrouter_max_attempts)
    retry_cap = max(1, config.openrouter_retry_max_seconds)
    last_error = "OpenRouter request failed"

    for model_index, model in enumerate(config.model_stack, start=1):
        ignored_providers = [base.provider_slug(item) for item in config.ignored_providers]
        if reporter:
            fallback_note = f"; native fallbacks={len(getattr(config, 'fallback_models', []))}"
            reporter.update("openrouter", f"calling model {model_index}/{len(config.model_stack)}: {model}{fallback_note}")
        for attempt in range(1, attempts + 1):
            try:
                if reporter:
                    reporter.update("openrouter-attempt", f"model={model}; attempt={attempt}/{attempts}")
                result, model_used, service_tier = openrouter_request_once(prompt, schema, config, ignored_providers, model)
                if reporter:
                    tier_note = f"; service_tier={service_tier}" if service_tier else ""
                    reporter.update("openrouter-result", f"served model={model_used}{tier_note}")
                return result, model_used, service_tier
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                parsed_error = base.parse_openrouter_error(detail)
                provider = base.provider_slug(str(parsed_error.get("provider", "")))
                if provider and provider not in ignored_providers:
                    ignored_providers.append(provider)
                retry_after = parsed_error.get("retry_after")
                try:
                    delay = float(retry_after) if retry_after is not None else float(exc.headers.get("Retry-After", ""))
                except (TypeError, ValueError):
                    delay = min(2**attempt, retry_cap)
                delay = min(max(delay, 1.0), float(retry_cap))
                message = str(parsed_error.get("message", "request failed"))
                last_error = f"OpenRouter API failed with HTTP {exc.code}: {message}"
                if provider:
                    last_error += f" Provider skipped for retry: {provider}."
                retryable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504} or is_transient_inflight_credit_402(
                    exc.code,
                    message,
                )
                if retryable and attempt < attempts:
                    if reporter:
                        reporter.update("openrouter-retry", f"{last_error} retrying in {delay:.0f}s")
                    time.sleep(delay)
                    continue
                break
            except RuntimeError as exc:
                last_error = str(exc)
                if "empty response" in last_error.lower() and attempt < attempts:
                    delay = min(2**attempt, retry_cap)
                    if reporter:
                        reporter.update("openrouter-retry", f"{last_error}; retrying in {delay:.0f}s")
                    time.sleep(delay)
                    continue
                break
            except json.JSONDecodeError:
                last_error = "OpenRouter returned invalid JSON"
                if attempt < attempts:
                    delay = min(2**attempt, retry_cap)
                    if reporter:
                        reporter.update("openrouter-retry", f"{last_error}; retrying in {delay:.0f}s")
                    time.sleep(delay)
                    continue
                break
        if model_index < len(config.model_stack) and reporter:
            reporter.update("openrouter-fallback", f"model {model} failed; trying next configured model")

    raise RuntimeError(last_error)


