def _build_repair_prompt(
    base: Any,
    finding: dict[str, Any],
    path: str,
    line: int,
    line_text: str,
    previous_result: dict[str, Any],
    config: Any,
) -> str:
    prompt = f"""
Repair the strict fix synthesis JSON for one DCOIR Review finding.

The previous JSON put prose in one or more code fields. Return the same schema.

Required correction:
- remove_code, replace_code, add_code, and suggested_replacement must contain only exact code/config.
- Move every sentence, label, conceptual instruction, or non-code phrase to notes.
- If no exact code is safe, leave code fields empty.

File: `{path}`
Anchored line: {line}
Current anchored line text:
```text
{base.sanitize_text(line_text, config)}
```

Finding title: {finding.get('title', '')}
Finding body: {finding.get('body', '')}

Previous invalid JSON:
```json
{json.dumps(previous_result, ensure_ascii=False, indent=2)}
```
""".strip()
    prompt = base.sanitize_text(prompt, config)
    max_prompt = int(getattr(config, "max_prompt_chars", len(prompt)))
    return prompt[:max_prompt]


def _strict_normalize_finding_for_comment(finding: dict[str, Any]) -> dict[str, Any]:
    item = dict(finding)
    kind = _semantic_kind(item)
    title = str(item.get("title", "") or "Finding").replace("Deterministic risk sentinel:", "").strip()
    if kind in YAML_REQUIRED_KIND_TITLES:
        title = YAML_REQUIRED_KIND_TITLES[kind]
    item["title"] = _clean_public_text(title or "Finding")
    body = _clean_public_text(str(item.get("body", "") or ""))
    if kind == "python_ssrf":
        body = re.sub(r"\bhardcoded secret\b", "secret or token value", body, flags=re.IGNORECASE)
        body = "\n".join(line for line in body.splitlines() if "syntax error" not in line.lower()).strip()
    item["body"] = body
    item["validation"] = _clean_public_text(str(item.get("validation", "") or ""))
    suggestion = _strip_fences(item.get("suggested_replacement", ""))
    if suggestion and not _strict_code_value_is_valid(suggestion, _language_hint(str(item.get("path", "") or ""))):
        guidance = item.get("fix_guidance") if isinstance(item.get("fix_guidance"), dict) else {}
        item["fix_guidance"] = {**guidance, "notes": "\n\n".join(filter(None, [str(guidance.get("notes", "") or ""), suggestion]))}
        item["suggested_replacement"] = ""
    guidance = _normalize_existing_fix_guidance(item)
    if guidance:
        item["fix_guidance"] = guidance
    else:
        item.pop("fix_guidance", None)
    return item


def _yaml_required_fallback_body(kind: str, sentinel: Any) -> str:
    changed = str(getattr(sentinel, "text", "") or "").strip()
    if kind == "yaml_pull_request_target":
        return "`pull_request_target` runs with base-repository privileges. Do not execute untrusted PR code in this context."
    if kind == "yaml_broad_write":
        return "This workflow grants broad write permissions. Narrow the token permissions to the minimum scopes needed."
    if kind == "yaml_untrusted_checkout":
        return "This privileged workflow checks out untrusted pull request code. Do not combine privileged workflow context with PR-controlled code checkout, branch refs, or head SHAs."
    if kind == "yaml_shell_pipe":
        return f"This workflow pipes network-fetched content into a shell: `{changed}`. Download, verify a pinned checksum or signature, then execute only verified content."
    return "Review this GitHub Actions security boundary before merging."
