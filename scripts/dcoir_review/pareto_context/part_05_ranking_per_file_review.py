def rank_findings_for_required_budget(findings: list[dict[str, Any]], config: Any) -> list[dict[str, Any]]:
    max_inline = max(0, int(getattr(config, "max_inline_comments", 12)))
    if max_inline <= 0:
        return []
    ranked = sorted(dedupe_findings_for_ranking(findings), key=hardened.severity_sort_key)
    if len(ranked) <= max_inline:
        return ranked
    reserved_budget = min(
        max_inline,
        max(0, int(getattr(config, "required_finding_reserved_budget", min(max_inline, 9)))),
    )
    min_per_family = max(0, int(getattr(config, "required_finding_min_per_family", 2)))
    selected: list[dict[str, Any]] = []
    selected_keys: set[tuple[str, str, str, str]] = set()

    def maybe_select(finding: dict[str, Any]) -> bool:
        key = finding_dedupe_key(finding)
        if key in selected_keys:
            return False
        selected.append(finding)
        selected_keys.add(key)
        return True

    if min_per_family > 0:
        for family in REQUIRED_FINDING_FAMILIES:
            family_count = 0
            for finding in ranked:
                if len(selected) >= reserved_budget or family_count >= min_per_family:
                    break
                if finding_review_family(finding) == family and maybe_select(finding):
                    family_count += 1
    for finding in ranked:
        if len(selected) >= reserved_budget:
            break
        if finding_review_family(finding) in REQUIRED_FINDING_FAMILIES:
            maybe_select(finding)
    for finding in ranked:
        if len(selected) >= max_inline:
            break
        maybe_select(finding)
    return selected


def build_per_file_review_prompt(
    pr: dict[str, Any],
    item: dict[str, Any],
    file_text: str,
    diff: str,
    config: Any,
    path_sentinels: list[hardened.RiskSentinel],
    review_mode: str,
) -> str:
    path = str(item.get("filename", "") or "")
    max_file_chars = max(0, int(getattr(config, "per_file_review_max_file_chars", getattr(config, "deep_review_max_file_chars", 12000))))
    visible_text = base.sanitize_text(file_text, config)
    truncated = len(visible_text) > max_file_chars
    if truncated:
        visible_text = f"{visible_text[:max_file_chars]}\n\n[full-file context truncated for this file]"
    patch = base.sanitize_text(str(item.get("patch", "") or ""), config)
    added_lines = added_diff_lines_for_path(diff, path)
    added_line_block = "\n".join(f"{line.line}: {line.text}" for line in added_lines[:80]) or "(no added lines parsed)"
    sentinel_block = hardened.risk_sentinel_block(path_sentinels, config) if path_sentinels else "No deterministic risk anchors detected for this file."
    prompt = f"""
Context mode: {review_mode}
Per-file detector pass for `{path}`.

Repository: {base.sanitize_text(os.environ.get('GITHUB_REPOSITORY', ''), config)}
PR number: {pr.get('number')}
PR title: {base.sanitized_prompt_value(pr.get('title'), config)}

Specialized review instructions:
{file_specialization(path, file_text)}

Review rules:
- Review this single file deeply using the full file context and the file diff.
- Return only high-signal findings that matter for correctness, security, validation, or DCOIR governance.
- Anchor every finding to a changed RIGHT-side line from this file whenever possible.
- Keep findings generalizable. Do not tune to a known test fixture or exact previous conversation.
- Provide exact correction guidance and validation. Use `suggested_replacement` only when the replacement is exact code for the anchored line.
- If this file has no actionable issue, return an empty findings array and a clean summary.

{sentinel_block}

Changed RIGHT-side lines in this file:
```text
{added_line_block}
```

File diff patch:
```diff
{patch}
```

Full head-file context:
```{language_hint(path)}
{visible_text}
```
""".strip()
    prompt = base.sanitize_text(prompt, config)
    if len(prompt) > config.max_prompt_chars:
        prompt = prompt[: config.max_prompt_chars - len(DEEP_CONTEXT_PROMPT_TRUNCATED_MARKER)] + DEEP_CONTEXT_PROMPT_TRUNCATED_MARKER
    return prompt


def build_file_contexts(gh: Any, pr: dict[str, Any], files: list[dict[str, Any]], config: Any) -> list[dict[str, Any]]:
    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    if not head_sha:
        return []
    contexts: list[dict[str, Any]] = []
    for item in files:
        path = str(item.get("filename", "") or "").strip()
        status = str(item.get("status", "") or "").strip()
        if not path or status in {"removed", "deleted"}:
            continue
        try:
            file_text = fetch_pr_file_text(gh, path, head_sha)
        except UnicodeDecodeError:
            continue
        except Exception:
            continue
        contexts.append({"item": item, "path": path, "text": file_text})
    contexts.sort(key=lambda context: per_file_priority(context["item"], context["text"]))
    return contexts[: max(0, int(getattr(config, "per_file_review_max_files", getattr(config, "deep_review_max_files", 8))))]


def review_single_file_context(
    index: int,
    context: dict[str, Any],
    pr: dict[str, Any],
    diff: str,
    schema: dict[str, Any],
    config: Any,
    risk_sentinels: list[hardened.RiskSentinel],
    review_mode: str,
) -> dict[str, Any]:
    path = str(context["path"])
    path_sentinels = [sentinel for sentinel in risk_sentinels if sentinel.path == path]
    prompt = build_per_file_review_prompt(pr, context["item"], context["text"], diff, config, path_sentinels, review_mode)
    artifact_id = safe_artifact_name(path, f"file-{index:02d}")
    hardened.write_debug_text_artifact_safely(config, f"prompts/per-file/{index:02d}-{artifact_id}.txt", prompt)
    hardened.write_debug_json_artifact_safely(
        config,
        f"metadata/per-file/{index:02d}-{artifact_id}.json",
        {
            "path": path,
            "prompt_chars": len(prompt),
            "risk_sentinel_count": len(path_sentinels),
            "risk_sentinel_digest": hardened.risk_sentinel_digest(path_sentinels) if path_sentinels else "",
        },
    )
    result, model_used, service_tier = hardened.openrouter_review(prompt, schema, config, reporter=None)
    hardened.write_debug_json_artifact_safely(
        config,
        f"responses/per-file/{index:02d}-{artifact_id}.json",
        {"path": path, "model_used": model_used, "service_tier": service_tier, "result": result},
    )
    return {"path": path, "prompt_chars": len(prompt), "result": result, "model_used": model_used, "service_tier": service_tier}


def merge_many_review_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {"summary": "Per-file detector pass completed.", "findings": []}
    for result in results:
        merged = hardened.merge_review_results(merged, result)
    return merged


def compact_model_label(results: list[dict[str, Any]], fallback: str) -> str:
    models: list[str] = []
    seen: set[str] = set()
    for item in results:
        model = str(item.get("model_used", "") or "").strip()
        if model and model not in seen:
            seen.add(model)
            models.append(model)
    if not models:
        return fallback
    if len(models) == 1:
        return models[0]
    return f"per-file model set: {', '.join(models[:3])}{'...' if len(models) > 3 else ''}"


def should_use_per_file_first_pass(review_mode: str, config: Any) -> bool:
    return bool(getattr(config, "per_file_first_pass_review", True)) and review_mode in {"first-pass-deep", "deep-forced"}


