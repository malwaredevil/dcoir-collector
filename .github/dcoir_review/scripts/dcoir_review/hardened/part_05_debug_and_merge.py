def write_debug_text_artifact_safely(config: Any, name: str, text: str) -> None:
    writer = getattr(base, "write_debug_text_artifact", None)
    if writer is None:
        return
    try:
        writer(config, name, text)
    except Exception as exc:
        print(f"WARN: unable to write debug text artifact {name}: {exc}", file=sys.stderr, flush=True)


def write_debug_json_artifact_safely(config: Any, name: str, data: Any) -> None:
    writer = getattr(base, "write_debug_json_artifact", None)
    if writer is None:
        return
    try:
        writer(config, name, data)
    except Exception as exc:
        print(f"WARN: unable to write debug JSON artifact {name}: {exc}", file=sys.stderr, flush=True)


def finding_merge_bucket(finding: dict[str, Any]) -> str:
    text = normalized_quality_text(
        "\n".join(
            [
                str(finding.get("title", "") or ""),
                str(finding.get("body", "") or ""),
                str(finding.get("validation", "") or ""),
            ]
        )
    )
    buckets: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("deserialization", ("pickle", "deserial", "yaml.load", "objectinputstream", "binaryformatter")),
        ("command-execution", ("command injection", "command execution", "shell", "subprocess", "exec", "spawn", "start-process")),
        ("dynamic-code", ("eval", "new function", "dynamic code", "invoke-expression")),
        ("sql", ("sql", "query", "interpolation", "parameter")),
        ("path-write", ("path traversal", "file write", "writefile", "root containment", "arbitrary overwrite")),
        ("archive-extract", ("archive", "extract", "tar", "unpack", "zip slip")),
        ("ssrf-outbound", ("ssrf", "outbound", "callback", "webhook", "urlopen", "invoke-webrequest", "fetch")),
        ("secret-token", ("secret", "token", "authorization", "credential", "exfil")),
        ("workflow-privilege", ("pull_request_target", "workflow", "privileged", "untrusted", "github token")),
        ("acl-permission", ("acl", "permission", "everyone", "fullcontrol")),
        ("kubernetes-privilege", ("kubernetes", "privileged", "hostpath", "hostnetwork", "runasuser")),
        ("delete", ("recursive delete", "rmtree", "remove-item", "deletion")),
        ("logic", ("truthy", "always true", "bypass")),
    )
    for bucket, terms in buckets:
        if any(term in text for term in terms):
            return bucket
    title = normalized_quality_text(str(finding.get("title", "") or ""))
    return title[:80] or "unknown"


def finding_merge_key(finding: dict[str, Any]) -> tuple[str, int, str]:
    path = str(finding.get("path", "") or "").strip()
    try:
        line = int(finding.get("line", 0) or 0)
    except (TypeError, ValueError):
        line = 0
    return (path, line, finding_merge_bucket(finding))


def severity_rank(severity: Any) -> int:
    return {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
    }.get(str(severity or "").strip().lower(), 0)


def finding_quality_score(finding: dict[str, Any]) -> tuple[int, float, int]:
    try:
        confidence = float(finding.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    body_length = len(str(finding.get("body", "") or ""))
    validation_length = len(str(finding.get("validation", "") or ""))
    return (severity_rank(finding.get("severity")), confidence, body_length + validation_length)


def result_findings(result: dict[str, Any]) -> list[dict[str, Any]]:
    raw_findings = result.get("findings", []) if isinstance(result, dict) else []
    if not isinstance(raw_findings, list):
        return []
    return [dict(item) for item in raw_findings if isinstance(item, dict)]


def merge_review_results(initial_result: dict[str, Any], retry_result: dict[str, Any]) -> dict[str, Any]:
    merged: list[dict[str, Any]] = []
    index_by_key: dict[tuple[str, int, str], int] = {}
    for source_result in (initial_result, retry_result):
        for finding in result_findings(source_result):
            key = finding_merge_key(finding)
            if key in index_by_key:
                existing_index = index_by_key[key]
                if finding_quality_score(finding) >= finding_quality_score(merged[existing_index]):
                    merged[existing_index] = finding
                continue
            index_by_key[key] = len(merged)
            merged.append(finding)

    retry_summary = str(retry_result.get("summary", "") if isinstance(retry_result, dict) else "").strip()
    initial_summary = str(initial_result.get("summary", "") if isinstance(initial_result, dict) else "").strip()
    summary = retry_summary or initial_summary
    if initial_summary and retry_summary and normalized_quality_text(initial_summary) != normalized_quality_text(retry_summary):
        summary = (
            f"{retry_summary}\n\n"
            "The review result also preserves distinct actionable findings returned by the first pass when they "
            "remain anchored to changed code."
        )
    return {"summary": summary, "findings": merged}


def openrouter_review_with_quality_retry(
    prompt: str,
    schema: dict[str, Any],
    config: Any,
    reporter: Any | None,
    risk_sentinels: list[RiskSentinel],
    line_index: dict[tuple[str, int], int] | None = None,
) -> tuple[dict[str, Any], str, str]:
    write_debug_text_artifact_safely(config, "prompts/01-initial-prompt.txt", prompt)
    write_debug_json_artifact_safely(
        config,
        "metadata/01-initial-request.json",
        {
            "prompt_chars": len(prompt),
            "risk_sentinel_count": len(risk_sentinels),
            "risk_sentinel_digest": risk_sentinel_digest(risk_sentinels) if risk_sentinels else "",
            "line_index_entries": len(line_index or {}),
        },
    )
    result, model_used, service_tier = openrouter_review(prompt, schema, config, reporter)
    write_debug_json_artifact_safely(
        config,
        "responses/01-initial-result.json",
        {"model_used": model_used, "service_tier": service_tier, "result": result},
    )
    initial_result = result
    retry_reason = review_quality_retry_reason(result, config, risk_sentinels, line_index)
    if retry_reason:
        if reporter:
            safe_reason = sanitize_github_output(retry_reason, config)
            reporter.update("quality-retry", f"{safe_reason}; retrying with stricter actionable-output guidance")
        retry_sentinels = required_risk_sentinels(risk_sentinels) or risk_sentinels
        retry_prompt = build_quality_retry_prompt(prompt, result, retry_sentinels, config, retry_reason)
        write_debug_text_artifact_safely(config, "prompts/02-quality-retry-prompt.txt", retry_prompt)
        write_debug_json_artifact_safely(
            config,
            "metadata/02-quality-retry-request.json",
            {
                "retry_reason": retry_reason,
                "prompt_chars": len(retry_prompt),
                "risk_sentinel_count": len(retry_sentinels),
                "risk_sentinel_digest": risk_sentinel_digest(retry_sentinels) if retry_sentinels else "",
            },
        )
        result, model_used, service_tier = openrouter_review(retry_prompt, schema, config, reporter)
        write_debug_json_artifact_safely(
            config,
            "responses/02-quality-retry-result.json",
            {"model_used": model_used, "service_tier": service_tier, "result": result},
        )
        merged_result = merge_review_results(initial_result=initial_result, retry_result=result)
        write_debug_json_artifact_safely(
            config,
            "responses/03-quality-retry-merged-result.json",
            {
                "model_used": model_used,
                "service_tier": service_tier,
                "initial_finding_count": len(result_findings(initial_result)),
                "retry_finding_count": len(result_findings(result)),
                "merged_finding_count": len(result_findings(merged_result)),
                "result": merged_result,
            },
        )
        result = merged_result
    return result, model_used, service_tier


