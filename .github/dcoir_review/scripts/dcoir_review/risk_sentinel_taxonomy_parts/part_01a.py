

def _path_expr(path: str) -> str:
    return repr(str(path or ""))


def _validation_for_path(path: str, kind: str = "") -> str:
    lower = str(path or "").lower()
    if lower.endswith((".ps1", ".psm1", ".psd1")):
        ps_path = "'" + str(path or "").replace("'", "''") + "'"
        return (
            "pwsh -NoProfile -Command \"$errors=$null; "
            f"[System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw -LiteralPath {ps_path}), [ref]$errors) | Out-Null; "
            "if ($errors) { throw ($errors | Out-String) }\""
        )
    if lower.endswith((".yml", ".yaml")):
        checks = {
            YAML_PULL_REQUEST_TARGET: "assert 'pull_request_target' not in text",
            YAML_BROAD_WRITE: "assert 'write-all' not in text and not re.search(r'(?m)^\\s*(actions|checks|contents|deployments|id-token|issues|packages|pull-requests|statuses)\\s*:\\s*write\\b', text)",
            YAML_UNTRUSTED_CHECKOUT: "assert 'github.event.pull_request.head' not in text and 'github.head_ref' not in text",
            YAML_SHELL_PIPE: "assert not re.search(r'\\b(curl|wget)\\b[^\\n]*\\|\\s*(bash|sh)\\b', text, re.I)",
            YAML_METADATA_SHELL: "assert not (re.search(r'github\\.event\\.pull_request\\.(body|title|head\\.ref|head\\.sha)', text, re.I) and re.search(r'(\\|\\s*(bash|sh)\\b|\\b(bash|sh)\\s+-c\\b)', text, re.I))",
        }
        check = checks.get(kind, "assert text.strip()")
        script = f"import re; from pathlib import Path; path=Path({_path_expr(path)}); text=path.read_text(encoding='utf-8'); assert path.exists(), path; {check}"
        return f"python3 -c {shlex.quote(script)}"
    if lower.endswith(".py"):
        return f"python3 -m py_compile {shlex.quote(str(path or ''))}"
    return v3._validation_for_path(path, kind)


def _clean_validation(value: Any, path: str, kind: str) -> str:
    if kind in HARD_REQUIRED_KIND_TITLES or kind == YAML_METADATA_SHELL:
        return _validation_for_path(path, kind)
    kept: list[str] = []
    seen: set[str] = set()
    for raw_line in str(value or "").replace("```", "").splitlines():
        line = raw_line.strip()
        if not line or PROSE_VALIDATION_RE.search(line) or not COMMAND_START_RE.match(line):
            continue
        if line in seen:
            continue
        seen.add(line)
        kept.append(line)
    if kept:
        return "\n".join(kept)
    return _validation_for_path(path, kind)


def _note_line_is_code(line: str, language: str) -> bool:
    stripped = line.rstrip()
    if not stripped.strip():
        return False
    if stripped.lstrip().startswith("#") or "${{" in stripped:
        return True
    if language == "yaml" and (YAML_CODE_LINE_RE.match(stripped) or stripped.lstrip().startswith("- ")):
        return True
    if language == "powershell" and POWERSHELL_CODE_LINE_RE.match(stripped):
        return True
    if language == "python" and PYTHON_CODE_LINE_RE.match(stripped):
        return True
    return False


def _format_notes(value: Any, path: str) -> str:
    text = required._clean_public_text(str(value or "").replace("validatation", "validation")).strip()
    if not text or "```" in text:
        return text
    language = _language_hint(path)
    lines = text.splitlines()
    output: list[str] = []
    code_block: list[str] = []

    def flush_code() -> None:
        nonlocal code_block
        if code_block:
            while output and not output[-1].strip():
                output.pop()
            output.append(f"```{language}")
            output.extend(code_block)
            output.append("```")
            code_block = []

    for line in lines:
        if _note_line_is_code(line, language):
            code_block.append(line.rstrip())
            continue
        flush_code()
        output.append(line.rstrip())
    flush_code()
    return DUPLICATE_WHITESPACE_RE.sub("\n\n", "\n".join(output)).strip()


def _exact_remove_matches(finding: dict[str, Any], remove_code: str) -> bool:
    anchored = str(finding.get("_anchored_line_text", "") or "").rstrip()
    candidate = str(remove_code or "").rstrip()
    if not candidate:
        return False
    return bool(anchored) and candidate.strip() == anchored.strip()


def _sanitize_fix_guidance(finding: dict[str, Any]) -> dict[str, Any]:
    raw = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    if not raw:
        return {}
    path = str(finding.get("path", "") or "")
    language = str(raw.get("language") or _language_hint(path)).lower()
    cleaned: dict[str, Any] = {"language": language}
    notes: list[str] = []
    remove_code = v3._strip_fences(raw.get("remove", ""))
    if remove_code:
        if _exact_remove_matches(finding, remove_code):
            cleaned["remove"] = remove_code
        else:
            notes.append("Line-specific removal guidance was omitted because it did not exactly match the anchored line/range.")
    for key in ("replace", "add"):
        value = v3._strip_fences(raw.get(key, ""))
        if value:
            cleaned[key] = value
    if raw.get("notes"):
        notes.append(str(raw.get("notes", "")))
    if notes:
        formatted = _format_notes("\n\n".join(notes), path)
        if formatted:
            cleaned["notes"] = formatted
    return cleaned if any(key in cleaned for key in ("remove", "replace", "add", "notes")) else {}


def _shell_pipe_body(line_text: str) -> str:
    changed = str(line_text or "").strip()
    scheme_note = " over unencrypted HTTP" if "http://" in changed.lower() else ""
    return (
        f"This workflow pipes network-fetched content{scheme_note} directly into a shell. "
        "Download the content to a file, verify a pinned checksum or signature, and execute only verified content."
    )


def _template_fields(kind: str, path: str, line_text: str) -> dict[str, Any]:
    notes = {
        YAML_PULL_REQUEST_TARGET: "Use `pull_request` for untrusted code paths, or keep `pull_request_target` jobs limited to metadata-only operations that do not check out or execute PR-controlled code.",
        YAML_BROAD_WRITE: "Set explicit least-privilege `permissions` for the job or workflow instead of broad write scopes.",
        YAML_UNTRUSTED_CHECKOUT: "Do not check out PR-controlled refs or head SHAs in a privileged workflow context.",
        YAML_SHELL_PIPE: "Replace curl/wget-to-shell with download, verification, and execution of pinned content.",
        PS_ACL: "Grant only the specific identity and filesystem rights the collector needs. Avoid `Everyone` and `FullControl` on collector output or execution paths.",
        PS_PROCESS_LAUNCH: "Use an allowlisted command table and validated arguments, or remove caller-controlled process launch from the collector path.",
        YAML_METADATA_SHELL: "Treat PR title, body, branch, and head metadata as attacker-controlled data. Do not pass it to `bash`, `sh`, or `bash -c`.",
    }
    bodies = {
        YAML_PULL_REQUEST_TARGET: "`pull_request_target` runs with base-repository privileges. Do not execute untrusted PR code in this workflow context.",
        YAML_BROAD_WRITE: "This workflow grants broad write token permissions. Narrow `permissions` to the minimum scopes required.",
        YAML_UNTRUSTED_CHECKOUT: "This privileged workflow checks out PR-controlled code. Do not combine privileged workflow context with PR-controlled refs or head SHAs.",
        YAML_SHELL_PIPE: _shell_pipe_body(line_text),
        PS_ACL: "This PowerShell change grants broad filesystem ACL rights. Narrow the identity and rights to the minimum collector path access required.",
        PS_PROCESS_LAUNCH: "This line launches a caller-controlled executable or argument string. Use an allowlisted command table or remove the launch from the collector path.",
        YAML_METADATA_SHELL: "This workflow passes pull request metadata to a shell. Pull request title, body, and head metadata are attacker-controlled and must not be executed.",
    }
    return {
        "title": HARD_REQUIRED_KIND_TITLES.get(kind, OPTIONAL_KIND_TITLES.get(kind, "Finding")),
        "body": bodies.get(kind, "Review this changed line before merging."),
        "validation": _validation_for_path(path, kind),
        "suggested_replacement": "",
        "fix_guidance": {"language": _language_hint(path), "notes": notes.get(kind, "Use a minimal, evidence-backed fix for this finding.")},
    }


def _env_token_fields(path: str) -> dict[str, Any]:
    return {
        "title": "Environment token forwarded to request-controlled callback",
        "body": "Environment token read from env and forwarded to request-controlled callback. Keep collector tokens server-side and allowlist outbound destinations before sending authorization headers.",
        "validation": _validation_for_path(path, _language_hint(path)),
        "suggested_replacement": "",
        "fix_guidance": {
            "language": _language_hint(path),
            "notes": "Keep the token on the trusted side of the boundary and validate the callback destination against an allowlist before any request is made.",
        },
    }
