def _is_transient_inflight_credit_saturation_error(exc: Exception) -> bool:
    """Return True only for OpenRouter's transient in-flight-credit HTTP 402."""

    message = " ".join(str(exc).lower().split())
    return (
        "http 402" in message
        and "current in-flight requests" in message
        and "retry after in-flight requests settle" in message
    )


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
    transient_saturation_failures: list[tuple[int, dict[str, Any], str]] = []
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
                if _is_transient_inflight_credit_saturation_error(exc):
                    transient_saturation_failures.append((index, context, str(exc)))
                    hardened.write_debug_json_artifact_safely(
                        config,
                        f"responses/per-file/{index:02d}-{safe_artifact_name(path, f'file-{index:02d}')}-transient-saturation.json",
                        {"path": path, "error": str(exc), "recovery": "queued-for-low-concurrency-retry"},
                    )
                    reporter.update(
                        "per-file-result",
                        f"{path}: transient in-flight-credit saturation; queued for bounded recovery",
                    )
                    continue

                failures.append(f"{path}: {str(exc)[:240]}")
                hardened.write_debug_json_artifact_safely(
                    config,
                    f"responses/per-file/{index:02d}-{safe_artifact_name(path, f'file-{index:02d}')}-error.json",
                    {"path": path, "error": str(exc)},
                )
                reporter.update(
                    "per-file-result",
                    f"{path}: failed; coverage will fail closed after remaining files complete",
                )

    low_concurrency_recovered_file_count = 0
    serial_saturation_failures: list[tuple[int, dict[str, Any], str]] = []
    if transient_saturation_failures:
        recovery_workers = min(2, len(transient_saturation_failures))
        reporter.update(
            "per-file-recovery",
            (
                f"parallel wave settled; retrying {len(transient_saturation_failures)} "
                f"transient in-flight-credit saturation failure(s) with recovery concurrency={recovery_workers}"
            ),
        )
        with concurrent.futures.ThreadPoolExecutor(max_workers=recovery_workers) as recovery_executor:
            recovery_future_map = {
                recovery_executor.submit(
                    review_single_file_context,
                    index,
                    context,
                    pr,
                    diff,
                    schema,
                    config,
                    risk_sentinels,
                    review_mode,
                ): (index, context, initial_error)
                for index, context, initial_error in transient_saturation_failures
            }
            for future in concurrent.futures.as_completed(recovery_future_map):
                index, context, initial_error = recovery_future_map[future]
                path = str(context["path"])
                try:
                    results.append(future.result())
                    low_concurrency_recovered_file_count += 1
                    reporter.update("per-file-recovery", f"{path}: recovered at low concurrency")
                except Exception as exc:
                    if _is_transient_inflight_credit_saturation_error(exc):
                        serial_saturation_failures.append((index, context, str(exc)))
                        reporter.update(
                            "per-file-recovery",
                            f"{path}: still saturated; queued for one final serial recovery attempt",
                        )
                        continue
                    failures.append(f"{path}: {str(exc)[:240]}")
                    hardened.write_debug_json_artifact_safely(
                        config,
                        f"responses/per-file/{index:02d}-{safe_artifact_name(path, f'file-{index:02d}')}-error.json",
                        {
                            "path": path,
                            "initial_error": initial_error,
                            "recovery_error": str(exc),
                            "recovery": "low-concurrency-retry-failed",
                        },
                    )
                    reporter.update("per-file-recovery", f"{path}: low-concurrency recovery failed")

    serial_recovered_saturation_file_count = 0
    if serial_saturation_failures:
        reporter.update(
            "per-file-recovery",
            (
                f"low-concurrency recovery wave settled; serially retrying "
                f"{len(serial_saturation_failures)} still-saturated file(s) once"
            ),
        )
        for index, context, recovery_error in serial_saturation_failures:
            path = str(context["path"])
            try:
                results.append(
                    review_single_file_context(
                        index,
                        context,
                        pr,
                        diff,
                        schema,
                        config,
                        risk_sentinels,
                        review_mode,
                    )
                )
                serial_recovered_saturation_file_count += 1
                reporter.update("per-file-recovery", f"{path}: recovered serially")
            except Exception as exc:
                failures.append(f"{path}: {str(exc)[:240]}")
                hardened.write_debug_json_artifact_safely(
                    config,
                    f"responses/per-file/{index:02d}-{safe_artifact_name(path, f'file-{index:02d}')}-error.json",
                    {
                        "path": path,
                        "initial_error": recovery_error,
                        "recovery_error": str(exc),
                        "recovery": "final-serial-retry-failed",
                    },
                )
                reporter.update("per-file-recovery", f"{path}: final serial recovery failed")

    recovered_saturation_file_count = (
        low_concurrency_recovered_file_count + serial_recovered_saturation_file_count
    )
    saturation_recovery = {
        "transient_saturation_file_count": len(transient_saturation_failures),
        "low_concurrency_recovered_file_count": low_concurrency_recovered_file_count,
        "serial_recovered_saturation_file_count": serial_recovered_saturation_file_count,
        "recovered_saturation_file_count": recovered_saturation_file_count,
        "unrecovered_saturation_file_count": len(transient_saturation_failures) - recovered_saturation_file_count,
    }
    hardened.write_debug_json_artifact_safely(
        config,
        "responses/per-file/saturation-recovery.json",
        saturation_recovery,
    )

    if failures:
        hardened.write_debug_json_artifact_safely(
            config,
            "responses/per-file/coverage-failure.json",
            {
                "file_prompt_count": len(contexts),
                "completed_file_prompt_count": len(results),
                "failed_file_count": len(failures),
                "failures": failures,
                **saturation_recovery,
            },
        )
        raise hardened.ReviewQualityError(
            "Per-file first-pass coverage incomplete after bounded recovery: "
            f"{len(failures)}/{len(contexts)} file prompt(s) failed. First failure: {failures[0]}"
        )

    if len(results) != len(contexts):
        raise hardened.ReviewQualityError(
            "Per-file first-pass coverage accounting mismatch: "
            f"completed={len(results)} expected={len(contexts)}"
        )

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
            "failed_file_count": 0,
            "prompt_chars": total_prompt_chars,
            "risk_sentinel_count": len(risk_sentinels),
            "risk_sentinel_digest": hardened.risk_sentinel_digest(risk_sentinels) if risk_sentinels else "",
            "line_index_entries": len(line_index),
            **saturation_recovery,
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
            "failed_file_count": 0,
            "total_prompt_chars": total_prompt_chars,
            **saturation_recovery,
            "result": merged_result,
        },
    )
    hardened.write_debug_json_artifact_safely(
        config,
        "responses/per-file/merged-detector-result.json",
        {
            "file_result_count": len(results),
            "failed_file_count": 0,
            "failures": [],
            **saturation_recovery,
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


