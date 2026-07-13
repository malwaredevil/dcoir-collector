def file_line_text(file_text: str, line_number: int) -> str:
    if line_number <= 0:
        return ""
    lines = file_text.splitlines()
    if line_number > len(lines):
        return ""
    return lines[line_number - 1]


def build_fix_synthesis_prompt(finding: dict[str, Any], path: str, line: int, line_text: str, file_text: str, config: Any) -> str:
    max_file_chars = max(0, int(getattr(config, "per_file_review_max_file_chars", getattr(config, "deep_review_max_file_chars", 12000))))
    visible_text = base.sanitize_text(file_text, config)
    if len(visible_text) > max_file_chars:
        visible_text = f"{visible_text[:max_file_chars]}\n\n[full-file context truncated for fix synthesis]"
    finding_payload = json.dumps(
        {
            "title": finding.get("title", ""),
            "severity": finding.get("severity", ""),
            "confidence": finding.get("confidence", 0),
            "path": path,
            "line": line,
            "body": finding.get("body", ""),
            "validation": finding.get("validation", ""),
        },
        ensure_ascii=False,
        indent=2,
    )
    prompt = f"""
Fix synthesis pass for one already-detected DCOIR Review finding.

Goal:
- Produce a minimal, safe fix for this single finding.
- Do not identify new findings.
- Do not broaden the fix beyond the anchored line unless fallback guidance is needed.
- Use `suggested_replacement` only when the exact replacement for the anchored GitHub review line is safe, syntactically plausible, and does not require modifying other files.
- If a native GitHub suggestion is not safe, leave `suggested_replacement` empty and fill one or more of `remove`, `replace`, and `add` with concise code-oriented guidance.
- Do not include Markdown fences in JSON fields.
- For eval/exec/dynamic code execution findings, do not propose another eval or exec call, even with restricted globals. Prefer removal, ast.literal_eval for literal-only data, a constrained parser/AST allowlist, or an explicit allowlist.
- Do not repeat secret-like literal values.

File: `{path}`
Language: {language_hint(path)}
Anchored line: {line}
Current anchored line text:
```text
{base.sanitize_text(line_text, config)}
```

Finding:
```json
{base.sanitize_text(finding_payload, config)}
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


def verified_suggested_replacement(fix_result: dict[str, Any], file_text: str, line_number: int, config: Any) -> str:
    suggestion = str(fix_result.get("suggested_replacement", "") or "").rstrip()
    if not suggestion:
        return ""
    unsafe_suggestion_markers = ("```", "~~~", "\r", "\n")
    if any(marker in suggestion for marker in unsafe_suggestion_markers):
        return ""
    if len(suggestion) > 1000:
        return ""
    if not base.is_safe_suggestion(suggestion):
        return ""
    original_line = file_line_text(file_text, line_number)
    if not original_line:
        return ""
    if suggestion.strip() == original_line.strip():
        return ""
    lines = file_text.splitlines()
    if line_number <= 0 or line_number > len(lines):
        return ""
    updated_lines = list(lines)
    updated_lines[line_number - 1] = suggestion
    changed_lines = [
        index
        for index, (before, after) in enumerate(zip(lines, updated_lines), start=1)
        if before != after
    ]
    if changed_lines != [line_number]:
        return ""
    return suggestion


PYTHON_DYNAMIC_EXEC_REPLACEMENT_PATTERN = re.compile(r"\b(?:eval|exec)\s*\(")


def is_python_dynamic_exec_fix_scope(finding: dict[str, Any], path: str, line_text: str) -> bool:
    if Path(path).suffix.lower() != ".py":
        return False
    haystack = "\n".join(
        [
            str(finding.get("title", "") or ""),
            str(finding.get("body", "") or ""),
            str(finding.get("validation", "") or ""),
            line_text,
        ]
    ).lower()
    if PYTHON_DYNAMIC_EXEC_REPLACEMENT_PATTERN.search(line_text):
        return True
    return ("eval" in haystack or "exec" in haystack) and (
        "dynamic" in haystack or "code execution" in haystack or "arbitrary code" in haystack
    )


def harden_python_dynamic_exec_fix_result(
    fix_result: dict[str, Any],
    finding: dict[str, Any],
    path: str,
    line_text: str,
) -> dict[str, Any]:
    if not isinstance(fix_result, dict) or not is_python_dynamic_exec_fix_scope(finding, path, line_text):
        return fix_result
    result = dict(fix_result)
    result["suggested_replacement"] = ""
    result["remove"] = str(
        result.get("remove")
        or f"Remove the dynamic Python execution call on the anchored line: {line_text.strip()}"
    ).strip()
    result["replace"] = (
        "Replace the dynamic evaluation with a non-executing parser or explicit allowlist. "
        "Use ast.literal_eval only for literal data; for expression-like input, implement a constrained AST "
        "or grammar allowlist. Do not use eval or exec, even with restricted globals."
    )
    add_text = str(result.get("add", "") or "").strip()
    if not add_text or PYTHON_DYNAMIC_EXEC_REPLACEMENT_PATTERN.search(add_text):
        result["add"] = (
            "Add tests proving os, __import__, open, and filesystem side effects are rejected "
            "without being executed."
        )
    else:
        result["add"] = add_text
    result["notes"] = (
        "Native GitHub suggestion suppressed because the safe repair depends on approved expression semantics; "
        "do not replace eval or exec with another dynamic execution primitive."
    )
    return result


def fix_guidance_from_result(fix_result: dict[str, Any], path: str, config: Any) -> dict[str, str]:
    guidance: dict[str, str] = {"language": language_hint(path)}
    for key in ("remove", "replace", "add", "notes"):
        value = str(fix_result.get(key, "") or "").strip()
        if value:
            guidance[key] = value
    return guidance if any(key in guidance for key in ("remove", "replace", "add", "notes")) else {}


def synthesize_fix_for_finding(
    index: int,
    finding: dict[str, Any],
    file_text: str,
    schema: dict[str, Any],
    config: Any,
) -> dict[str, Any]:
    path = str(finding.get("path", "") or "").strip()
    line = int(finding.get("line", 0) or 0)
    line_text = file_line_text(file_text, line)
    if not path or not line_text:
        return finding
    prompt = build_fix_synthesis_prompt(finding, path, line, line_text, file_text, config)
    artifact_id = safe_artifact_name(f"{path}-{line}", f"fix-{index:02d}")
    hardened.write_debug_text_artifact_safely(config, f"prompts/fix-synthesis/{index:02d}-{artifact_id}.txt", prompt)
    result, model_used, service_tier = hardened.openrouter_review(prompt, schema, config, reporter=None)
    result = harden_python_dynamic_exec_fix_result(result, finding, path, line_text)
    hardened.write_debug_json_artifact_safely(
        config,
        f"responses/fix-synthesis/{index:02d}-{artifact_id}.json",
        {"path": path, "line": line, "model_used": model_used, "service_tier": service_tier, "result": result},
    )
    enriched = dict(finding)
    suggestion = verified_suggested_replacement(result, file_text, line, config)
    if suggestion:
        enriched["suggested_replacement"] = suggestion
    else:
        guidance = fix_guidance_from_result(result, path, config)
        if guidance:
            enriched["fix_guidance"] = guidance
            enriched["suggested_replacement"] = ""
    validation = str(result.get("validation", "") or "").strip()
    if validation:
        enriched["validation"] = validation
    return enriched


def strip_detector_suggested_replacements(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for finding in findings:
        item = dict(finding)
        detector_suggestion = str(item.get("suggested_replacement", "") or "")
        if detector_suggestion.strip():
            item["_detector_suggested_replacement"] = detector_suggestion
            item["suggested_replacement"] = ""
        enriched.append(item)
    return enriched


def synthesize_fixes_for_findings(
    findings: list[dict[str, Any]],
    gh: Any,
    pr: dict[str, Any],
    schema: dict[str, Any],
    config: Any,
    reporter: Any,
) -> list[dict[str, Any]]:
    enriched = strip_detector_suggested_replacements(findings)
    if not getattr(config, "fix_synthesis_enabled", True) or not enriched:
        return enriched
    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    if not head_sha:
        return enriched
    max_findings = max(0, int(getattr(config, "fix_synthesis_max_findings", 8)))
    min_confidence = float(getattr(config, "fix_synthesis_min_confidence", 0.80))
    candidates: list[tuple[int, dict[str, Any]]] = []
    for index, finding in enumerate(enriched):
        try:
            confidence = float(finding.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence >= min_confidence:
            candidates.append((index, finding))
        if len(candidates) >= max_findings:
            break
    if not candidates:
        return enriched

    reporter.update("fix-synthesis", f"building repair guidance for {len(candidates)} finding(s)")
    file_cache: dict[str, str] = {}
    failures: list[str] = []
    for _index, finding in candidates:
        path = str(finding.get("path", "") or "").strip()
        if not path or path in file_cache:
            continue
        try:
            file_cache[path] = fetch_pr_file_text(gh, path, head_sha)
        except Exception as exc:
            failures.append(f"{path}: {str(exc)[:160]}")

    max_workers = min(max(1, int(getattr(config, "per_file_review_concurrency", 4))), max(1, len(candidates)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {}
        for ordinal, (index, finding) in enumerate(candidates, start=1):
            path = str(finding.get("path", "") or "").strip()
            file_text = file_cache.get(path)
            if not file_text:
                continue
            future = executor.submit(synthesize_fix_for_finding, ordinal, finding, file_text, schema, config)
            future_map[future] = index
        for future in concurrent.futures.as_completed(future_map):
            index = future_map[future]
            try:
                enriched[index] = future.result()
            except Exception as exc:
                path = str(enriched[index].get("path", "") or "")
                failures.append(f"{path}: {str(exc)[:160]}")
    if failures:
        hardened.write_debug_json_artifact_safely(config, "responses/fix-synthesis/failures.json", {"failures": failures})
        reporter.update("fix-synthesis", f"completed with {len(failures)} fallback-only failure(s)")
    else:
        reporter.update("fix-synthesis", "completed repair guidance pass")
    return enriched


