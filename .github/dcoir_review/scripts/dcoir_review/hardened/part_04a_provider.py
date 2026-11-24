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


def _record_openrouter_request_telemetry(config: Any, event: dict[str, Any]) -> None:
    history = getattr(config, "_openrouter_request_telemetry_events", None)
    if not isinstance(history, list):
        history = []
    history = [*history, dict(event)]
    setattr(config, "_openrouter_request_telemetry_events", history)

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
    setattr(config, "_openrouter_last_request_telemetry", telemetry)


def _note_openrouter_telemetry_error(config: Any) -> None:
    try:
        current = int(getattr(config, "_openrouter_request_telemetry_error_count", 0) or 0)
    except Exception:
        current = 0
    try:
        setattr(config, "_openrouter_request_telemetry_error_count", max(0, current) + 1)
    except Exception:
        return


def _record_openrouter_attempt_telemetry(config: Any, event: dict[str, Any]) -> None:
    """Best-effort whitelisted attempt routing evidence; never changes retry behavior."""
    if not bool(getattr(config, "openrouter_capture_request_telemetry", False)):
        return
    try:
        try:
            request_attempt_count = int(getattr(config, "_openrouter_request_attempt_count", 0) or 0)
        except (TypeError, ValueError):
            request_attempt_count = 0
        outcome = str(event.get("outcome", "") or "").strip()
        if outcome not in {"success", "retry", "fallback", "terminal_failure"}:
            outcome = "unclassified"
        item = {
            "request_attempt_count": max(0, request_attempt_count),
            "requested_model": str(event.get("requested_model", "") or "")[:160],
            "model_index": int(event.get("model_index", 0) or 0),
            "model_count": int(event.get("model_count", 0) or 0),
            "attempt_in_model": int(event.get("attempt_in_model", 0) or 0),
            "attempt_limit": int(event.get("attempt_limit", 0) or 0),
            "outcome": outcome,
            "failure_class": str(event.get("failure_class", "") or "")[:80],
            "provider": str(event.get("provider", "") or "")[:120],
        }
        http_status = event.get("http_status")
        if isinstance(http_status, int) and not isinstance(http_status, bool):
            item["http_status"] = http_status
        history = getattr(config, "_openrouter_request_attempt_telemetry_events", None)
        if not isinstance(history, list):
            history = []
        setattr(config, "_openrouter_request_attempt_telemetry_events", [*history, item])
    except Exception:
        _note_openrouter_telemetry_error(config)


def _capture_openrouter_response_telemetry(
    config: Any,
    data: dict[str, Any],
    model: str,
    model_used: str,
    service_tier: str,
    finish_reason: str,
    attempt_count: int,
) -> None:
    """Record returned execution metadata without changing response enforcement."""
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
    _record_openrouter_request_telemetry(config, event)
