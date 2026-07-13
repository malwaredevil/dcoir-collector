def build_prompt(pr: dict[str, Any], files: list[dict[str, Any]], diff: str, config: Config) -> str:
    guidance = sanitize_text(load_guidance(config), config)
    changed_files = []
    for item in files[: config.max_files]:
        changed_files.append(
            {
                "filename": sanitized_prompt_value(item.get("filename"), config),
                "status": sanitized_prompt_value(item.get("status"), config),
                "additions": item.get("additions"),
                "deletions": item.get("deletions"),
                "changes": item.get("changes"),
                "patch": sanitized_prompt_value(item.get("patch", ""), config),
            }
        )
    content = f"""
Repository: {sanitize_text(os.environ.get('GITHUB_REPOSITORY', ''), config)}
PR number: {pr.get('number')}
PR title: {sanitized_prompt_value(pr.get('title'), config)}
PR body:
{sanitized_prompt_value(pr.get('body'), config)}

Trusted repository guidance:
{guidance}

Preferred validation commands:
{json.dumps([sanitize_text(str(command), config) for command in config.validation_commands], indent=2)}

Changed file summary:
{json.dumps(changed_files, indent=2)}

Unified diff:
{sanitize_text(extract_relevant_file_patches(diff, config.max_files), config)}

Review task:
Find only high-signal issues in the PR diff. For each finding, give the exact changed file path and right-side line number. Provide a suggested_replacement only when a small GitHub suggestion block would be safe and likely to apply cleanly. Include validation commands that should pass after the fix.
""".strip()
    content = sanitize_text(content, config)
    if len(content) > config.max_prompt_chars:
        content = content[: config.max_prompt_chars] + "\n\n[context truncated by reviewer]"
    return content


def parse_openrouter_error(detail: str) -> dict[str, Any]:
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        return {"message": detail.strip()[:1000]}
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    metadata = error.get("metadata", {}) if isinstance(error, dict) else {}
    message = str(error.get("message", "OpenRouter request failed")) if isinstance(error, dict) else "OpenRouter request failed"
    provider = str(metadata.get("provider_name", "")).strip() if isinstance(metadata, dict) else ""
    retry_after = metadata.get("retry_after_seconds") if isinstance(metadata, dict) else None
    if retry_after is None and isinstance(metadata, dict):
        retry_after = metadata.get("retry_after_seconds_raw")
    return {"message": message, "provider": provider, "retry_after": retry_after}


def build_openrouter_payload(prompt: str, schema: dict[str, Any], config: Config, ignored_providers: list[str], model: str) -> dict[str, Any]:
    provider: dict[str, Any] = {"allow_fallbacks": True, "require_parameters": True}
    clean_ignored = [item for item in ignored_providers if item]
    if clean_ignored:
        provider["ignore"] = clean_ignored
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": read_text(".github/dcoir_review/prompts/openrouter-pr-review-system.md")},
            {"role": "user", "content": prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "openrouter_pr_review", "strict": True, "schema": schema},
        },
        "provider": provider,
        "temperature": 0.2,
    }


def openrouter_request_once(prompt: str, schema: dict[str, Any], config: Config, ignored_providers: list[str], model: str) -> tuple[dict[str, Any], str]:
    api_key = env_required("OPENROUTER_API_KEY")
    payload = build_openrouter_payload(prompt, schema, config, ignored_providers, model)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/DCOIR-Collector/dcoir-collector",
        "X-OpenRouter-Title": REVIEW_DISPLAY_NAME,
    }
    req = urllib.request.Request(OPENROUTER_API, data=json.dumps(payload).encode("utf-8"), method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=180) as response:
        raw = response.read().decode("utf-8")
    data = json.loads(raw)
    model_used = str(data.get("model", model))
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
    return parsed, model_used


def openrouter_review(prompt: str, schema: dict[str, Any], config: Config, reporter: ProgressReporter | None = None) -> tuple[dict[str, Any], str]:
    attempts = max(1, config.openrouter_max_attempts)
    retry_cap = max(1, config.openrouter_retry_max_seconds)
    last_error = "OpenRouter request failed"

    for model_index, model in enumerate(config.model_stack, start=1):
        ignored_providers = [provider_slug(item) for item in config.ignored_providers]
        if reporter:
            reporter.update("openrouter", f"calling model {model_index}/{len(config.model_stack)}: {model}")
        for attempt in range(1, attempts + 1):
            try:
                if reporter:
                    reporter.update("openrouter-attempt", f"model={model}; attempt={attempt}/{attempts}")
                return openrouter_request_once(prompt, schema, config, ignored_providers, model)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                parsed_error = parse_openrouter_error(detail)
                provider = provider_slug(str(parsed_error.get("provider", "")))
                if provider and provider not in ignored_providers:
                    ignored_providers.append(provider)
                retry_after = parsed_error.get("retry_after")
                try:
                    delay = float(retry_after) if retry_after is not None else float(exc.headers.get("Retry-After", ""))
                except (TypeError, ValueError):
                    delay = min(2**attempt, retry_cap)
                delay = min(max(delay, 1.0), float(retry_cap))
                last_error = f"OpenRouter API failed with HTTP {exc.code}: {parsed_error.get('message', 'request failed')}"
                if provider:
                    last_error += f" Provider skipped for retry: {provider}."
                retryable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
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


