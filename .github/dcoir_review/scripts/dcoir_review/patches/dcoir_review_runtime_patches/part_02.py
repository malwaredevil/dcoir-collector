def _normalize_finding_for_comment(finding: dict[str, Any]) -> dict[str, Any]:
    item = dict(finding)
    kind = _semantic_kind(item)
    title = str(item.get("title", "") or "")
    body = str(item.get("body", "") or "")
    if kind and ("deterministic risk sentinel" in title.lower() or "deterministic risk sentinel" in body.lower()):
        item["title"] = _KIND_TITLES.get(kind, title.replace("Deterministic risk sentinel:", "").strip() or "Finding")
    else:
        item["title"] = title.replace("Deterministic risk sentinel:", "").strip() or title
    item["title"] = _clean_user_text(str(item.get("title", "") or "Finding"))
    cleaned_body = _clean_user_text(body)
    if cleaned_body:
        item["body"] = cleaned_body
    elif kind:
        item["body"] = _KIND_DEFAULT_NOTES.get(kind, _KIND_TITLES.get(kind, "Review the changed line for this security issue."))
    item["validation"] = _clean_user_text(str(item.get("validation", "") or ""))
    suggestion = str(item.get("suggested_replacement", "") or "").strip()
    if suggestion and _guidance_value_is_prose(suggestion, _language_hint_for_path(str(item.get("path", "") or ""))):
        item["suggested_replacement"] = ""
        guidance = item.get("fix_guidance") if isinstance(item.get("fix_guidance"), dict) else {}
        guidance = dict(guidance)
        guidance["notes"] = "\n\n".join(filter(None, [str(guidance.get("notes", "") or "").strip(), suggestion]))
        item["fix_guidance"] = guidance
    fix_guidance = _normalize_fix_guidance(item)
    if fix_guidance:
        item["fix_guidance"] = fix_guidance
    elif "fix_guidance" in item:
        item.pop("fix_guidance", None)
    return item


def _fix_result_has_invalid_code_fields(result: dict[str, Any], finding: dict[str, Any], path: str) -> bool:
    kind = _semantic_kind({**finding, "path": path, "fix_guidance": result})
    language = _language_hint_for_path(path)
    for key in ("remove", "replace", "add"):
        value = _strip_markdown_fence_lines(str(result.get(key, "") or ""))
        if not value:
            continue
        if _is_mismatched_python_dynamic_guidance(kind, value):
            return True
        if patched_guidance_value_looks_like_code(value, language):
            continue
        if _extract_code_candidate(value, language):
            return True
        return True
    return False


def _build_fix_repair_prompt(
    finding: dict[str, Any],
    path: str,
    line: int,
    line_text: str,
    previous_result: dict[str, Any],
    config: Any,
) -> str:
    payload = json.dumps(previous_result, ensure_ascii=False, indent=2)
    prompt = f"""
Repair the fix synthesis JSON for one DCOIR Review finding.

Return the same JSON schema. Do not identify new findings.

Strict field rules:
- suggested_replacement: exact single-line replacement code for the anchored line only, or empty string.
- remove, replace, add: raw code or config snippets only. No prose, labels, Markdown fences, or sentences.
- notes: prose explanation belongs here.
- validation: exact commands only.
- If exact replacement code is not known, leave code fields empty and put the guidance in notes.
- Do not recommend eval, exec, or dynamic execution unless the original changed line already contains eval(...) or exec(...), and even then recommend removing it.

File: `{path}`
Anchored line: {line}
Current anchored line text:
```text
{line_text}
```

Finding title: {finding.get('title', '')}
Finding body: {finding.get('body', '')}

Previous invalid JSON:
```json
{payload}
```
""".strip()
    try:
        return str(config.max_prompt_chars and prompt[: config.max_prompt_chars])
    except Exception:
        return prompt


def _strict_fix_guidance_from_result(result: dict[str, Any], finding: dict[str, Any], path: str) -> dict[str, str]:
    synthetic = dict(finding)
    synthetic["path"] = path
    synthetic["fix_guidance"] = {
        "language": _language_hint_for_path(path),
        "remove": str(result.get("remove", "") or ""),
        "replace": str(result.get("replace", "") or ""),
        "add": str(result.get("add", "") or ""),
        "notes": str(result.get("notes", "") or ""),
    }
    return _normalize_fix_guidance(synthetic)


def _patch_base_formatter_module(module: Any) -> None:
    module.guidance_value_looks_like_code = patched_guidance_value_looks_like_code
    original = getattr(module, "_dcoir_original_build_inline_comment", None)
    if original is None and hasattr(module, "build_inline_comment"):
        original = module.build_inline_comment
        module._dcoir_original_build_inline_comment = original
    if callable(original):

        def patched_build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
            return original(_normalize_finding_for_comment(finding), model_used, config)

        module.build_inline_comment = patched_build_inline_comment


def _patched_dynamic_exec_scope(finding: dict[str, Any], path: str, line_text: str) -> bool:
    if Path(path).suffix.lower() != ".py":
        return False
    if PYTHON_DYNAMIC_EXEC_CALL_RE.search(line_text or ""):
        return True
    haystack = "\n".join(
        [
            str(finding.get("title", "") or ""),
            str(finding.get("body", "") or ""),
            str(finding.get("validation", "") or ""),
        ]
    )
    return bool(PYTHON_DYNAMIC_EXEC_CALL_RE.search(haystack))
