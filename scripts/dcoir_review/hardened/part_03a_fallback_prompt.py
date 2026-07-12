def risk_sentinel_fallback_finding(sentinel: RiskSentinel, config: Any) -> dict[str, Any]:
    severity = "high" if sentinel.label in RISK_SENTINEL_HIGH_SEVERITY_LABELS else "medium"
    return {
        "title": f"Deterministic risk sentinel: {sentinel.label}",
        "severity": severity,
        "confidence": 0.99,
        "path": sentinel.path,
        "line": sentinel.line,
        "body": (
            f"This changed line matched dcoir-review's deterministic `{sentinel.label}` sentinel. "
            f"{sentinel.detail}. Treat this as actionable unless the code constrains the input and side effect "
            "before this line; otherwise replace the primitive with a bounded, validated implementation and add "
            "readback validation for the narrowed behavior."
        ),
        "suggested_replacement": "",
        "validation": primary_validation_command(config),
    }


def add_risk_sentinel_fallback_findings(
    findings: list[dict[str, Any]],
    risk_sentinels: list[RiskSentinel],
    config: Any,
    unanchored_findings: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    uncovered = uncovered_risk_sentinels(findings, risk_sentinels, config, unanchored_findings)
    if not uncovered:
        return findings
    inline_limit = int(getattr(config, "max_inline_comments", 12))
    if inline_limit <= 0:
        return findings
    required_uncovered = required_risk_sentinels(uncovered)
    fallback_source = required_uncovered if required_uncovered else uncovered
    fallback_findings = [risk_sentinel_fallback_finding(sentinel, config) for sentinel in fallback_source[:inline_limit]]
    if len(findings) + len(fallback_findings) <= inline_limit:
        augmented = [*findings, *fallback_findings]
    else:
        existing_budget = max(0, inline_limit - len(fallback_findings))
        existing_findings = select_findings_for_inline(findings, existing_budget)
        augmented = [*existing_findings, *fallback_findings]
    return select_findings_for_inline(augmented, inline_limit)


def append_with_budget(prefix: str, suffix: str, max_chars: int) -> str:
    separator = "\n\n"
    if len(prefix) + len(separator) + len(suffix) <= max_chars:
        return f"{prefix}{separator}{suffix}"
    truncation_marker = "\n\n[context truncated by reviewer]"
    if len(suffix) + len(truncation_marker) >= max_chars:
        retained_suffix = max(0, max_chars - len(truncation_marker))
        return f"{suffix[:retained_suffix]}{truncation_marker}"
    retained = max(0, max_chars - len(separator) - len(suffix) - len(truncation_marker))
    return f"{prefix[:retained]}{truncation_marker}{separator}{suffix}"


def powershell_double_quoted(value: str) -> str:
    escaped = value.replace("`", "``").replace('"', '`"').replace("$", "`$")
    return f'"{escaped}"'


def validation_hint_for_path(path: str) -> str:
    quoted = shlex.quote(path)
    ps_path = powershell_double_quoted(path)
    lower_path = path.lower()
    if lower_path.endswith(".py"):
        return (
            f"- `{path}`: validate with `python3 -m py_compile {quoted}` plus the nearest Python selftest or unit test "
            "that imports or exercises the changed function."
        )
    if lower_path.endswith(".ps1") or lower_path.endswith(".psm1") or lower_path.endswith(".psd1"):
        return (
            f"- `{path}`: validate with `pwsh -NoProfile -Command '$errors=$null; [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw -LiteralPath {ps_path}), [ref]$errors) | Out-Null; if ($errors) {{ throw ($errors | Out-String) }}'` "
            "plus the collector PowerShell validation script when collector behavior is touched."
        )
    if lower_path.endswith((".yml", ".yaml")):
        return (
            f"- `{path}`: validate YAML parsing and the affected workflow check; for GitHub Actions changes include "
            "`python3 project_sources/github_actions/tools/build_workflow_inventory.py --check` after regenerating inventory if workflow metadata changed."
        )
    if lower_path.endswith(".json"):
        return f"- `{path}`: validate with `python3 -m json.tool {quoted}` plus the nearest schema or report validator."
    if lower_path.endswith(".md"):
        return f"- `{path}`: validate the rendered Markdown and read back the exact changed section from the PR diff."
    return f"- `{path}`: choose a syntax/static check and a focused behavior check for the changed file, not a generic full-run command."


def validation_hint_block(files: list[dict[str, Any]], max_files: int = 12) -> str:
    paths = []
    seen: set[str] = set()
    for item in files:
        path = str(item.get("filename", "")).strip()
        if not path or path in seen:
            continue
        seen.add(path)
        paths.append(path)
        if len(paths) >= max_files:
            break
    if not paths:
        return ""
    hints = "\n".join(validation_hint_for_path(path) for path in paths)
    return f"Changed-file validation hints:\n{hints}"


def build_prompt(
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    diff: str,
    config: Any,
    risk_sentinels: list[RiskSentinel] | None = None,
) -> str:
    hardening = """
Governed review hardening requirements:
- Do not hide actionable issues only in the summary. Every semantic, Markdown, governance, validation, or review-gate concern must be returned as a finding object.
- For Markdown and governed-source findings, anchor the finding to the nearest changed right-side line that introduced or materially preserves the risky wording.
- If a small suggestion block is not safe, leave suggested_replacement empty and put exact repair steps in the finding body.
- Each finding body must include observed behavior, impact, exact correction guidance, and validation or readback guidance.
- Validation guidance must be specific to the changed file and finding. Prefer syntax/static/security checks or focused tests that exercise the affected file or behavior; do not recommend reviewer-runner selftests unless the changed code is the reviewer runner itself.
- Do not return informational or advisory findings that say the risk is not realized, the changed code does not introduce the risk, or no input reaches the risky path. Put that in a clean summary instead.
- Treat changed tests, fixtures, validation probes, examples, workflow snippets, infrastructure config, and generated-looking files as review targets when they contain executable behavior, security policy, credential handling, or operator guidance. Do not dismiss a finding merely because the file appears non-production.
- Review across languages and file types for command/process execution, dynamic code evaluation, request-controlled path reads/writes/extraction, raw query construction, unsafe deserialization, outbound requests or SSRF, token/secret persistence or forwarding, CI/CD privilege boundaries, broad ACL or permission grants, and container/orchestration privilege escalation.
- Project emphasis: pay extra attention to PowerShell collectors, Python tooling, and GitHub Actions/YAML. For PowerShell inspect Invoke-Expression, Start-Process, Invoke-WebRequest/Invoke-RestMethod, Expand-Archive, Set-Content/Out-File/Copy-Item, Remove-Item, and Set-Acl. For Python inspect subprocess shell usage, unsafe deserialization, archive extraction, request-controlled paths, raw query construction, and secret/env persistence. For GitHub Actions/YAML inspect privileged PR triggers, checkout of untrusted refs, secret/token forwarding, broad permissions, and untrusted event metadata in shell commands.
""".strip()
    validation_hints = validation_hint_block(files)
    if validation_hints:
        hardening = f"{hardening}\n\n{validation_hints}"
    if risk_sentinels and getattr(config, "risk_sentinel_quality_gate", True):
        hardening = f"{hardening}\n\n{risk_sentinel_block(risk_sentinels, config)}"
    separator = "\n\n"
    truncation_marker = "\n\n[context truncated by reviewer]"
    prompt_budget = max(0, config.max_prompt_chars - len(hardening) - len(separator))
    base_budget = max(0, prompt_budget - len(truncation_marker))
    prompt_config = copy.copy(config)
    prompt_config.max_prompt_chars = base_budget
    prompt = base.build_prompt(pr, files, diff, prompt_config)
    combined = f"{hardening}{separator}{prompt}"
    if len(combined) > config.max_prompt_chars:
        retained_chars = max(0, config.max_prompt_chars - len(truncation_marker))
        combined = combined[:retained_chars] + truncation_marker
    return base.sanitize_text(combined, config)


