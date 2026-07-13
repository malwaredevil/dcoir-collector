def normalize_findings(result: dict[str, Any], config: Config, line_index: dict[tuple[str, int], int]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for item in result.get("findings", []):
        try:
            confidence = float(item.get("confidence", 0))
            line = int(item.get("line", 0))
            path = str(item.get("path", ""))
        except (TypeError, ValueError):
            continue
        if confidence < config.minimum_confidence:
            continue
        if (path, line) not in line_index:
            continue
        findings.append(item)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (severity_order.get(str(f.get("severity", "low")), 9), -float(f.get("confidence", 0))))
    return findings[: config.max_inline_comments]


def is_safe_suggestion(suggestion: str) -> bool:
    text = suggestion.strip()
    if not text:
        return False
    prose_prefixes = ("use ", "replace ", "remove ", "avoid ", "store ", "validate ", "sanitize ", "consider ", "e.g.", "for example")
    lowered = text.lower()
    if lowered.startswith(prose_prefixes):
        return False
    if " should " in lowered or " you should " in lowered:
        return False
    code_signals = ("=", "(", ")", "{", "}", "[", "]", ":", ";", "return ", "throw ", "raise ", "if ", "for ", "while ")
    return any(signal_text in text for signal_text in code_signals)


VALIDATION_COMMAND_PREFIXES = (
    "bandit ",
    "bash ",
    "git ",
    "Invoke-ScriptAnalyzer ",
    "node ",
    "npm ",
    "npx ",
    "pwsh ",
    "powershell ",
    "python ",
    "python3 ",
    "pytest ",
    "ruff ",
    "sh ",
)


def has_balanced_command_quotes(text: str) -> bool:
    quote = ""
    escaped = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in {"\"", "'"}:
            quote = char
    return not quote


def is_validation_command(text: str) -> bool:
    stripped = text.strip()
    return has_balanced_command_quotes(stripped) and any(stripped.startswith(prefix) for prefix in VALIDATION_COMMAND_PREFIXES)


def powershell_double_quoted(value: str) -> str:
    escaped = value.replace("`", "``").replace('"', '`"').replace("$", "`$")
    return f'"{escaped}"'


def extract_validation_commands(validation: str) -> list[str]:
    commands: list[str] = []
    for line in validation.splitlines():
        cleaned = line.strip().strip("-*").strip()
        if cleaned.startswith("```") or not cleaned:
            continue
        if is_validation_command(cleaned):
            commands.append(cleaned)
    for match in re.finditer(r"`([^`\n]+)`", validation):
        candidate = match.group(1).strip()
        if is_validation_command(candidate):
            commands.append(candidate)
    return commands


def default_validation_commands_for_path(path: str) -> list[str]:
    if not path:
        return []
    lower_path = path.lower()
    quoted = shlex.quote(path)
    if lower_path.endswith(".py"):
        return [
            f"python3 -m py_compile {quoted}",
            f"bandit -r {quoted}",
        ]
    if lower_path.endswith((".ps1", ".psm1", ".psd1")):
        ps_path = powershell_double_quoted(path)
        return [
            f"pwsh -NoProfile -Command '$errors=$null; [System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw -LiteralPath {ps_path}), [ref]$errors) | Out-Null; if ($errors) {{ throw ($errors | Out-String) }}'",
            f"pwsh -NoProfile -Command 'Invoke-ScriptAnalyzer -Path {ps_path}'",
        ]
    if lower_path.endswith(".json"):
        return [f"python3 -m json.tool {quoted}"]
    return []


def validation_text_for_finding(finding: dict[str, Any]) -> str:
    path = str(finding.get("path", "")).strip()
    commands = extract_validation_commands(str(finding.get("validation", "")).strip())
    defaults = default_validation_commands_for_path(path)
    combined: list[str] = []
    seen: set[str] = set()
    for command in [*commands, *defaults]:
        if command and command not in seen:
            combined.append(command)
            seen.add(command)
    return "\n".join(combined)


def strip_markdown_fence_lines(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith(("```", "~~~")):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def fix_guidance_value_text(value: Any, config: Config, *, neutralize_mentions: bool = False) -> str:
    return strip_markdown_fence_lines(
        sanitize_github_output(str(value or "").strip(), config, neutralize_mentions=neutralize_mentions)
    )


def language_hint_for_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".bash": "bash",
        ".cjs": "javascript",
        ".js": "javascript",
        ".json": "json",
        ".mjs": "javascript",
        ".ps1": "powershell",
        ".psd1": "powershell",
        ".psm1": "powershell",
        ".py": "python",
        ".sh": "bash",
        ".ts": "typescript",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix, "text")


def clean_fence_language(language: Any, fallback: str = "text") -> str:
    text = str(language or "").strip().lower()
    return text if re.fullmatch(r"[a-z0-9_+.-]{1,32}", text) else fallback


def language_for_fix_guidance(fix_guidance: dict[str, Any], finding: dict[str, Any]) -> str:
    fallback = language_hint_for_path(str(finding.get("path", "") or ""))
    return clean_fence_language(fix_guidance.get("language", ""), fallback)


PROSE_GUIDANCE_PREFIXES = (
    "add ",
    "avoid ",
    "change ",
    "delete ",
    "do not ",
    "ensure ",
    "keep ",
    "move ",
    "native ",
    "replace ",
    "remove ",
    "run ",
    "store ",
    "use ",
    "validate ",
)


def guidance_value_looks_like_code(value: str, language: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    code_signals = (
        "$",
        "=",
        "(",
        ")",
        "{",
        "}",
        "[",
        "]",
        ":",
        ";",
        "|",
        "=>",
        "&&",
        "||",
        "import ",
        "from ",
        "def ",
        "class ",
        "return ",
        "raise ",
        "throw ",
        "if ",
        "for ",
        "while ",
        "on:",
        "permissions:",
        "uses:",
        "run:",
        "set-",
        "invoke-",
        "start-",
        "convertto-",
    )
    has_code_signal = any(signal_text in lowered for signal_text in code_signals)
    if lowered.startswith(PROSE_GUIDANCE_PREFIXES) and not has_code_signal:
        return False
    if language in {"yaml", "json"} and re.search(r"(?m)^\s*[A-Za-z0-9_.-]+\s*:", stripped):
        return True
    return has_code_signal


def append_language_fence(parts: list[str], language: str, value: str) -> None:
    parts.extend(["", f"```{clean_fence_language(language)}", value.rstrip(), "```"])


def append_guidance_value(
    parts: list[str],
    label: str,
    key: str,
    value: str,
    line: int,
    language: str,
) -> None:
    if key == "remove" and line > 0:
        heading = f"**On line {line} remove:**"
    elif key == "remove":
        heading = "**Remove:**"
    elif key == "replace":
        heading = "**Replace with:**"
    elif key == "add" and line > 0:
        heading = f"**Add near line {line}:**"
    else:
        heading = f"**{label}:**"
    parts.extend(["", heading])
    if guidance_value_looks_like_code(value, language):
        append_language_fence(parts, language, value)
    else:
        parts.extend(["", value])


VALIDATION_BODY_HEADING_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*)?validation(?: expected after fix)?(?:\*\*)?\s*:?\s*$",
    re.IGNORECASE,
)


def strip_model_validation_section(text: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if VALIDATION_BODY_HEADING_RE.match(line):
            return "\n".join(lines[:index]).rstrip()
    return text.strip()


def markdown_emphasis_safe_text(value: str) -> str:
    text = " ".join(str(value or "").strip().splitlines())
    return text.replace("*", "\\*")


def build_inline_comment(finding: dict[str, Any], model_used: str, config: Config) -> str:
    title = markdown_emphasis_safe_text(sanitize_github_output(str(finding.get("title", "Finding")).strip(), config))
    severity = markdown_emphasis_safe_text(str(finding.get("severity", "medium")).upper())
    confidence = float(finding.get("confidence", 0))
    body = strip_model_validation_section(sanitize_github_output(str(finding.get("body", "")).strip(), config))
    validation = sanitize_github_output(validation_text_for_finding(finding), config)
    suggestion = sanitize_github_output(str(finding.get("suggested_replacement", "")).rstrip(), config, neutralize_mentions=False)
    fix_guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    path = str(finding.get("path", "") or "")
    try:
        line = int(finding.get("line", 0) or 0)
    except (TypeError, ValueError):
        line = 0
    language = language_for_fix_guidance(fix_guidance, finding) if fix_guidance else language_hint_for_path(path)
    parts = [f"**{severity}: {title}**", "", body]
    if config.include_confidence:
        parts.extend(["", f"Confidence: `{confidence:.2f}`"])
    if suggestion:
        if is_safe_suggestion(suggestion):
            parts.extend(["", "Suggested fix:", "", "```suggestion", suggestion, "```"])
        elif guidance_value_looks_like_code(suggestion, language):
            parts.extend(["", "**Suggested fix guidance:**"])
            append_language_fence(parts, language, suggestion)
        else:
            parts.extend(["", "**Suggested fix guidance:**", "", suggestion])
    if fix_guidance:
        for label, key in (("Remove", "remove"), ("Replace", "replace"), ("Add", "add")):
            value = fix_guidance_value_text(fix_guidance.get(key, ""), config, neutralize_mentions=False)
            if value:
                append_guidance_value(parts, label, key, value, line, language)
        notes = fix_guidance_value_text(fix_guidance.get("notes", ""), config)
        if notes:
            parts.extend(["", "**Notes:**", "", notes])
    if validation:
        parts.extend(["", "**Validation expected after fix:**"])
        append_language_fence(parts, "bash", validation)
    parts.extend(["", f"<sub>{REVIEW_DISPLAY_NAME}</sub>"])
    return github_safe_body("\n".join(parts), limit=12000)


def short_commit(commit_sha: str) -> str:
    return commit_sha[:12] if commit_sha else "unavailable"


def build_review_body(
    result: dict[str, Any],
    findings: list[dict[str, Any]],
    model_used: str,
    config: Config,
    reviewed_commit: str = "",
) -> str:
    summary = sanitize_github_output(str(result.get("summary", f"{REVIEW_DISPLAY_NAME} completed.")).strip(), config)
    event_text = "Review posted with inline findings." if findings else "No high-confidence inline findings were found in the changed diff."
    lines = [
        MARKER,
        f"💡 {REVIEW_DISPLAY_NAME}",
        "Here are some review suggestions for this pull request." if findings else "No high-confidence inline review suggestions were found for this pull request.",
        "",
        f"Reviewed commit: `{short_commit(reviewed_commit)}`",
    ]
    if summary and (not findings or config.post_summary_when_findings):
        lines.extend(["", summary])
    lines.extend(["", f"Result: {event_text}"])
    return github_safe_body(
        "\n".join(lines).strip()
    )


