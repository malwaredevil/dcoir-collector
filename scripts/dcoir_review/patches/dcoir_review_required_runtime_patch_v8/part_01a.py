

def _single_line(value: Any) -> str:
    text = str(value or "").strip("\n")
    return text if text and "\n" not in text else ""


def _native_suggestion_replacement(finding: dict[str, Any], base: Any) -> str:
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    remove_code = _single_line(guidance.get("remove", ""))
    replace_code = _single_line(guidance.get("replace", ""))
    if not remove_code or not replace_code:
        return ""
    if not base.guidance_value_looks_like_code(replace_code, base.language_hint_for_path(str(finding.get("path", "") or ""))):
        return ""
    return replace_code.rstrip()


def _patch_inline_comment_renderer(base: Any) -> None:
    original = getattr(base, "_dcoir_required_v8_original_build_inline_comment", None)
    if original is None:
        original = getattr(base, "build_inline_comment", None)
        base._dcoir_required_v8_original_build_inline_comment = original
    if not callable(original):
        return

    def required_v8_build_inline_comment(finding: dict[str, Any], model_used: str, config: Any) -> str:
        item = dict(finding)
        replacement = _native_suggestion_replacement(item, base)
        if replacement and not str(item.get("suggested_replacement", "") or "").strip():
            item["suggested_replacement"] = replacement
            guidance = dict(item.get("fix_guidance") or {})
            guidance["remove"] = ""
            guidance["replace"] = ""
            item["fix_guidance"] = guidance
        return original(item, model_used, config)

    base.build_inline_comment = required_v8_build_inline_comment


def _py_here_doc(path: str, body: str) -> str:
    return "\n".join(["python3 - <<'PY'", "from pathlib import Path", "import re", f"path = Path({path!r})", "text = path.read_text(encoding='utf-8')", body, "PY"])


def _validation_for_kind(kind: str, path: str) -> str:
    quoted = shlex.quote(path)
    if kind == v4.YAML_PULL_REQUEST_TARGET:
        return _py_here_doc(path, "assert 'pull_request_target' not in text")
    if kind == v4.YAML_BROAD_WRITE:
        return _py_here_doc(path, "assert 'write-all' not in text\nassert not re.search(r'(?m)^\\s*(actions|checks|contents|deployments|id-token|issues|packages|pull-requests|statuses)\\s*:\\s*write\\b', text)")
    if kind == v4.YAML_UNTRUSTED_CHECKOUT:
        return _py_here_doc(path, "assert 'github.event.pull_request.head' not in text\nassert 'github.head_ref' not in text")
    if kind == v4.YAML_SHELL_PIPE:
        return _py_here_doc(path, "assert not re.search(r'\\b(curl|wget)\\b[^\\n]*\\|\\s*(bash|sh)\\b', text, re.I)")
    if kind == v4.YAML_METADATA_SHELL:
        return _py_here_doc(path, "metadata = re.search(r'github\\.event\\.pull_request\\.(body|title|head\\.ref|head\\.sha)', text, re.I)\nshell = re.search(r'(\\|\\s*(bash|sh)\\b|\\b(bash|sh)\\s+-c\\b)', text, re.I)\nassert not (metadata and shell)")
    if kind == v4.PS_ACL:
        return f"pwsh -NoProfile -Command '$p = {path!r}; $text = Get-Content -Raw -LiteralPath $p; if ($text -match \"(?i)icacls.*Everyone:F|Everyone.*FullControl|FileSystemAccessRule.*Everyone|Set-Acl\") {{ throw \"broad ACL grant remains\" }}; $errors=$null; [System.Management.Automation.PSParser]::Tokenize($text, [ref]$errors) | Out-Null; if ($errors) {{ throw ($errors | Out-String) }}'"
    if kind == v4.PS_PROCESS_LAUNCH:
        return f"pwsh -NoProfile -Command '$p = {path!r}; $text = Get-Content -Raw -LiteralPath $p; if ($text -match \"(?i)Start-Process\\s+-FilePath\\s+\\$RequestedTool\") {{ throw \"caller-controlled Start-Process remains\" }}; $errors=$null; [System.Management.Automation.PSParser]::Tokenize($text, [ref]$errors) | Out-Null; if ($errors) {{ throw ($errors | Out-String) }}'"
    if kind == v5.PS_ENV_TOKEN:
        return f"pwsh -NoProfile -Command '$p = {path!r}; $text = Get-Content -Raw -LiteralPath $p; if ($text -match \"(?i)Bearer\\s+\\$env:DCOIR_TOKEN|Authorization.*DCOIR_TOKEN\") {{ throw \"environment token callback header remains\" }}; $errors=$null; [System.Management.Automation.PSParser]::Tokenize($text, [ref]$errors) | Out-Null; if ($errors) {{ throw ($errors | Out-String) }}'"
    if kind == v5.PYTHON_YAML_LOAD:
        return f"python3 -m py_compile {quoted}\n" + _py_here_doc(path, "assert 'yaml.Loader' not in text\nassert 'Loader=yaml.Loader' not in text")
    if kind == v5.PYTHON_SHELL_EXEC:
        return f"python3 -m py_compile {quoted}\n" + _py_here_doc(path, "assert 'shell=True' not in text")
    if kind == v5.PYTHON_ENV_TOKEN:
        return f"python3 -m py_compile {quoted}\n" + _py_here_doc(path, "assert not re.search(r'Authorization.*Bearer.*DCOIR_TOKEN|Bearer\\s*\\{?token\\}?', text)")
    if kind == "python_pickle_load":
        return f"python3 -m py_compile {quoted}\n" + _py_here_doc(path, "assert 'pickle.loads' not in text\nassert 'pickle.load(' not in text")
    return ""


def _kind_for_validation(finding: dict[str, Any]) -> str:
    explicit = str(finding.get("_risk_sentinel_kind", "") or "")
    if explicit:
        return explicit
    text = _finding_text(finding)
    if "pickle" in text:
        return "python_pickle_load"
    return v5._semantic_kind(finding)


def _patch_validation_text(base: Any) -> None:
    original = getattr(base, "_dcoir_required_v8_original_validation_text_for_finding", None)
    if original is None:
        original = getattr(base, "validation_text_for_finding", None)
        base._dcoir_required_v8_original_validation_text_for_finding = original
    if not callable(original):
        return

    def required_v8_validation_text_for_finding(finding: dict[str, Any]) -> str:
        path = str(finding.get("path", "") or "")
        validation = _validation_for_kind(_kind_for_validation(finding), path)
        return validation or original(finding)

    base.validation_text_for_finding = required_v8_validation_text_for_finding


def _patch_progress_body(base: Any) -> None:
    original = getattr(base.ProgressReporter, "_dcoir_required_v8_original_body", None)
    if original is None:
        original = getattr(base.ProgressReporter, "_body", None)
        base.ProgressReporter._dcoir_required_v8_original_body = original
    if not callable(original):
        return

    def required_v8_body(self: Any, state: str, final_lines: list[str] | None = None) -> str:
        lines = [
            base.MARKER,
            f"{base.REVIEW_DISPLAY_NAME} {state}.",
            "",
            f"- Command: `{self.command}`.",
            f"- Debug progress: `{str(getattr(self.config, 'debug', False)).lower()}`.",
            *base.workflow_run_status_lines(self.config),
            "- Branch changes: none; this workflow only posts review output.",
            "- Gate role: internal review-assist signal before any separately approved external review request.",
        ]
        if final_lines:
            lines.extend(["", *final_lines])
        lines.extend(["", "Progress:"])
        for stage, message in self.steps[-30:]:
            lines.append(f"- `{base.sanitize_public_identity(stage)}`: {message}")
        return base.github_safe_body("\n".join(lines), limit=18000)

    base.ProgressReporter._body = required_v8_body


def _patch_prompt_review_budget() -> None:
    original = getattr(v6, "_dcoir_required_v8_original_candidate_with_addendum", None)
    if original is None:
        original = getattr(v6, "_candidate_with_addendum", None)
        v6._dcoir_required_v8_original_candidate_with_addendum = original
    if not callable(original):
        return

    def required_v8_candidate_with_addendum(original_prompt: str, addendum: str, config: Any) -> str:
        if "review quality retry" in str(original_prompt or "").lower() and str(addendum or "").strip():
            cleaned = v6._clean_addendum(addendum)
            if not cleaned:
                return original_prompt
            return f"{original_prompt}\n\n{v6.PROMPT_REVIEW_SECTION_TITLE}:\n{cleaned}"
        return original(original_prompt, addendum, config)

    v6._candidate_with_addendum = required_v8_candidate_with_addendum


def apply_pareto_context_module(module: Any) -> None:
    base = getattr(module, "base", None)
    hardened = getattr(module, "hardened", None)
    if base is not None:
        _patch_inline_comment_renderer(base)
        _patch_validation_text(base)
        _patch_progress_body(base)
    _patch_prompt_review_budget()
    if hardened is not None:
        _patch_required_selection(module, hardened)
