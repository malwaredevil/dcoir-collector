def openrouter_review_with_hybrid_first_pass(
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    diff: str,
    schema: dict[str, Any],
    config: Any,
    reporter: Any,
    risk_sentinels: list[hardened.RiskSentinel],
    line_index: dict[tuple[str, int], int],
    deep_context_block: str,
    review_mode: str,
    context_summary: str,
    gh: Any,
) -> tuple[dict[str, Any], str, str]:
    if not should_use_per_file_first_pass(review_mode, config):
        prompt = build_prompt(pr, files, diff, config, risk_sentinels, deep_context_block, review_mode, context_summary)
        return hardened.openrouter_review_with_quality_retry(prompt, schema, config, reporter, risk_sentinels, line_index)

    contexts = build_file_contexts(gh, pr, files, config)
    if not contexts:
        reporter.update("per-file", "no full-file contexts available; using bounded whole-PR prompt")
        prompt = build_prompt(pr, files, diff, config, risk_sentinels, deep_context_block, review_mode, context_summary)
        return hardened.openrouter_review_with_quality_retry(prompt, schema, config, reporter, risk_sentinels, line_index)

    reporter.update("per-file", f"running first-pass detector across {len(contexts)} file prompt(s)")
    per_file_manifest = "\n".join(
        [
            "Per-file first-pass detector prompt manifest.",
            "Individual prompts are written under prompts/per-file/.",
            "",
            *[f"- {context['path']}" for context in contexts],
        ]
    )
    hardened.write_debug_text_artifact_safely(config, "prompts/01-initial-prompt.txt", per_file_manifest)
    hardened.write_debug_json_artifact_safely(
        config,
        "metadata/01-initial-request.json",
        {
            "prompt_mode": "per-file",
            "file_prompt_count": len(contexts),
            "risk_sentinel_count": len(risk_sentinels),
            "risk_sentinel_digest": hardened.risk_sentinel_digest(risk_sentinels) if risk_sentinels else "",
            "line_index_entries": len(line_index),
        },
    )
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    max_workers = max(1, int(getattr(config, "per_file_review_concurrency", 4)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(max_workers, len(contexts))) as executor:
        future_map = {
            executor.submit(
                review_single_file_context,
                index,
                context,
                pr,
                diff,
                schema,
                config,
                risk_sentinels,
                review_mode,
            ): (index, context)
            for index, context in enumerate(contexts, start=1)
        }
        for future in concurrent.futures.as_completed(future_map):
            index, context = future_map[future]
            path = str(context["path"])
            try:
                results.append(future.result())
                reporter.update("per-file-result", f"{path}: completed")
            except Exception as exc:
                failures.append(f"{path}: {str(exc)[:240]}")
                hardened.write_debug_json_artifact_safely(
                    config,
                    f"responses/per-file/{index:02d}-{safe_artifact_name(path, f'file-{index:02d}')}-error.json",
                    {"path": path, "error": str(exc)},
                )
                reporter.update("per-file-result", f"{path}: failed; continuing with remaining files")

    if not results:
        if failures:
            reporter.update("per-file", f"all per-file calls failed; using bounded whole-PR prompt. First failure: {failures[0]}")
        prompt = build_prompt(pr, files, diff, config, risk_sentinels, deep_context_block, review_mode, context_summary)
        return hardened.openrouter_review_with_quality_retry(prompt, schema, config, reporter, risk_sentinels, line_index)

    merged_result = merge_many_review_results([item["result"] for item in results])
    model_used = compact_model_label(results, getattr(config, "model", "openrouter/pareto-code"))
    service_tier = ", ".join(sorted({str(item.get("service_tier", "") or "") for item in results if item.get("service_tier")}))
    total_prompt_chars = sum(int(item.get("prompt_chars") or 0) for item in results)
    hardened.write_debug_json_artifact_safely(
        config,
        "metadata/01-initial-request.json",
        {
            "prompt_mode": "per-file",
            "file_prompt_count": len(contexts),
            "completed_file_prompt_count": len(results),
            "failed_file_count": len(failures),
            "prompt_chars": total_prompt_chars,
            "risk_sentinel_count": len(risk_sentinels),
            "risk_sentinel_digest": hardened.risk_sentinel_digest(risk_sentinels) if risk_sentinels else "",
            "line_index_entries": len(line_index),
        },
    )
    hardened.write_debug_json_artifact_safely(
        config,
        "responses/01-initial-result.json",
        {
            "model_used": model_used,
            "service_tier": service_tier,
            "prompt_mode": "per-file",
            "file_result_count": len(results),
            "failed_file_count": len(failures),
            "total_prompt_chars": total_prompt_chars,
            "result": merged_result,
        },
    )
    hardened.write_debug_json_artifact_safely(
        config,
        "responses/per-file/merged-detector-result.json",
        {
            "file_result_count": len(results),
            "failed_file_count": len(failures),
            "failures": failures,
            "model_used": model_used,
            "service_tier": service_tier,
            "result": merged_result,
        },
    )

    retry_reason = hardened.review_quality_retry_reason(merged_result, config, risk_sentinels, line_index)
    if retry_reason:
        safe_reason = hardened.sanitize_github_output(retry_reason, config)
        reporter.update("quality-retry", f"{safe_reason}; retrying with whole-PR repair prompt")
        aggregate_prompt = build_prompt(pr, files, diff, config, risk_sentinels, deep_context_block, review_mode, context_summary)
        retry_sentinels = hardened.required_risk_sentinels(risk_sentinels) or risk_sentinels
        retry_prompt = hardened.build_quality_retry_prompt(aggregate_prompt, merged_result, retry_sentinels, config, retry_reason)
        hardened.write_debug_text_artifact_safely(config, "prompts/02-quality-retry-prompt.txt", retry_prompt)
        retry_result, retry_model_used, retry_service_tier = hardened.openrouter_review(retry_prompt, schema, config, reporter)
        hardened.write_debug_json_artifact_safely(
            config,
            "responses/02-quality-retry-result.json",
            {"model_used": retry_model_used, "service_tier": retry_service_tier, "result": retry_result},
        )
        initial_summary = str(merged_result.get("summary", "") if isinstance(merged_result, dict) else "").strip()
        retry_summary = str(retry_result.get("summary", "") if isinstance(retry_result, dict) else "").strip()
        merged_result = hardened.merge_review_results(merged_result, retry_result)
        # Preserve the exhausted-retry state across the per-file aggregate boundary.
        # The normalizer uses this marker to keep an ambiguous summary visible in
        # the review body without converting it into a false clean result.
        merged_result["_quality_retry_attempted"] = True
        merged_result["_quality_retry_reason"] = str(retry_reason)
        merged_result["_quality_retry_initial_summary"] = initial_summary
        merged_result["_quality_retry_retry_summary"] = retry_summary
        hardened.write_debug_json_artifact_safely(
            config,
            "responses/03-quality-retry-merged-result.json",
            {
                "model_used": retry_model_used,
                "service_tier": retry_service_tier,
                "merged_finding_count": len(hardened.result_findings(merged_result)),
                "result": merged_result,
            },
        )
        model_used = retry_model_used
        service_tier = retry_service_tier

    return merged_result, model_used, service_tier


