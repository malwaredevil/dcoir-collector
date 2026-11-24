# Canonical semantic validation-command rendering for review findings.

_VALIDATION_YAML_PULL_REQUEST_TARGET = "yaml_pull_request_target"
_VALIDATION_YAML_BROAD_WRITE = "yaml_broad_write"
_VALIDATION_YAML_UNTRUSTED_CHECKOUT = "yaml_untrusted_checkout"
_VALIDATION_YAML_SHELL_PIPE = "yaml_shell_pipe"
_VALIDATION_YAML_METADATA_SHELL = "yaml_metadata_shell"
_VALIDATION_PS_ACL = "ps_acl"
_VALIDATION_PS_PROCESS_LAUNCH = "ps_process_launch"
_VALIDATION_PS_ENV_TOKEN = "ps_env_token_callback"
_VALIDATION_PS_OUTBOUND_TOKEN = "ps_outbound_token"
_VALIDATION_PS_DYNAMIC_EXEC = "ps_dynamic_exec"
_VALIDATION_PYTHON_YAML_LOAD = "python_yaml_load"
_VALIDATION_PYTHON_SHELL_EXEC = "python_shell_exec"
_VALIDATION_PYTHON_ENV_TOKEN = "python_env_token_callback"
_VALIDATION_PYTHON_PICKLE_LOAD = "python_pickle_load"

_VALIDATION_WRITE_PERMISSION_RE = re.compile(
    r"^\s*(?:permissions\s*:\s*write-all|"
    r"(?:actions|checks|contents|deployments|id-token|issues|packages|pull-requests|statuses)\s*:\s*write)\b",
    re.IGNORECASE,
)
_VALIDATION_SHELL_PIPE_RE = re.compile(r"\b(?:curl|wget)\b[^\n]*(?:\|\s*(?:bash|sh)\b)", re.IGNORECASE)
_VALIDATION_PR_METADATA_RE = re.compile(
    r"github\.event\.pull_request\.(?:body|title|head\.ref|head\.sha)", re.IGNORECASE
)
_VALIDATION_SHELL_EXEC_RE = re.compile(
    r"(?:\|\s*(?:bash|sh)\b|\b(?:bash|sh)\s+-c\b|\b(?:bash|sh)\b)", re.IGNORECASE
)
_VALIDATION_PS_START_PROCESS_RE = re.compile(r"\bStart-Process\b", re.IGNORECASE)
_VALIDATION_PS_ACL_RE = re.compile(r"\b(?:Set-Acl|FileSystemAccessRule|FullControl|Everyone)\b", re.IGNORECASE)
_VALIDATION_PY_YAML_LOAD_RE = re.compile(
    r"\byaml\.load\s*\([^\n]*(?:Loader\s*=\s*yaml\.Loader|yaml\.Loader)", re.IGNORECASE
)
_VALIDATION_PY_SHELL_EXEC_RE = re.compile(
    r"\bsubprocess\.(?:Popen|run|call|check_call|check_output)\s*\([^\n]*shell\s*=\s*True\b",
    re.IGNORECASE,
)
_VALIDATION_PY_ENV_RE = re.compile(r"\b(?:os\.environ|os\.getenv)\b|DCOIR_TOKEN", re.IGNORECASE)
_VALIDATION_PS_ENV_RE = re.compile(r"\$env:|DCOIR_TOKEN|Environment::GetEnvironmentVariable", re.IGNORECASE)
_VALIDATION_OUTBOUND_RE = re.compile(
    r"callback|Authorization|Bearer|Invoke-WebRequest|Invoke-RestMethod|requests\.(?:get|post|put|request)|urlopen",
    re.IGNORECASE,
)


def _validation_normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _validation_line_number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _validation_canonical_kind(kind: str) -> str:
    if kind == _VALIDATION_PS_OUTBOUND_TOKEN:
        return _VALIDATION_PS_ENV_TOKEN
    return kind


def _validation_line_kind(path: str, text: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    line = str(text or "")
    normalized = _validation_normalize(line)
    if suffix in {".yml", ".yaml"}:
        if "pull_request_target" in normalized:
            return _VALIDATION_YAML_PULL_REQUEST_TARGET
        if _VALIDATION_WRITE_PERMISSION_RE.search(line):
            return _VALIDATION_YAML_BROAD_WRITE
        if "github.event.pull_request.head" in normalized or "github.head_ref" in normalized:
            return _VALIDATION_YAML_UNTRUSTED_CHECKOUT
        if _VALIDATION_SHELL_PIPE_RE.search(line):
            return _VALIDATION_YAML_SHELL_PIPE
        if _VALIDATION_PR_METADATA_RE.search(line) and _VALIDATION_SHELL_EXEC_RE.search(line):
            return _VALIDATION_YAML_METADATA_SHELL
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if re.search(r"\b(?:Invoke-Expression|IEX)\b", line, re.IGNORECASE):
            return _VALIDATION_PS_DYNAMIC_EXEC
        if _VALIDATION_PS_START_PROCESS_RE.search(line):
            return _VALIDATION_PS_PROCESS_LAUNCH
        if _VALIDATION_PS_ACL_RE.search(line):
            return _VALIDATION_PS_ACL
        if _VALIDATION_PS_ENV_RE.search(line) and _VALIDATION_OUTBOUND_RE.search(line):
            return _VALIDATION_PS_ENV_TOKEN
    if suffix == ".py":
        if "pickle.loads" in normalized or "pickle.load(" in normalized:
            return _VALIDATION_PYTHON_PICKLE_LOAD
        if _VALIDATION_PY_YAML_LOAD_RE.search(line):
            return _VALIDATION_PYTHON_YAML_LOAD
        if _VALIDATION_PY_SHELL_EXEC_RE.search(line):
            return _VALIDATION_PYTHON_SHELL_EXEC
        if _VALIDATION_PY_ENV_RE.search(line) and _VALIDATION_OUTBOUND_RE.search(line):
            return _VALIDATION_PYTHON_ENV_TOKEN
    return ""


def _validation_claim_text(finding: dict[str, Any]) -> str:
    guidance = finding.get("fix_guidance") if isinstance(finding.get("fix_guidance"), dict) else {}
    parts = [
        finding.get("title"), finding.get("body"), finding.get("description"),
        finding.get("validation"), finding.get("_anchored_line_text"),
        *(guidance.get(key) for key in ("remove", "replace", "add", "notes")),
    ]
    return _validation_normalize("\n".join(str(part or "") for part in parts))


def _validation_claimed_kinds(finding: dict[str, Any]) -> set[str]:
    path = str(finding.get("path", "") or "")
    text = _validation_claim_text(finding)
    suffix = Path(path.lower()).suffix
    kinds: set[str] = set()
    if suffix == ".py":
        if "pickle.loads" in text or "pickle.load(" in text or ("pickle" in text and "deserial" in text):
            kinds.add(_VALIDATION_PYTHON_PICKLE_LOAD)
        if "yaml.load" in text or "yaml.loader" in text:
            kinds.add(_VALIDATION_PYTHON_YAML_LOAD)
        if "shell=true" in text or ("subprocess" in text and "shell" in text):
            kinds.add(_VALIDATION_PYTHON_SHELL_EXEC)
        if ("os.getenv" in text or "os.environ" in text or "dcoir_token" in text) and (
            "callback" in text or "authorization" in text or "requests." in text
        ):
            kinds.add(_VALIDATION_PYTHON_ENV_TOKEN)
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if "invoke-expression" in text or re.search(r"\biex\b", text, re.IGNORECASE):
            kinds.add(_VALIDATION_PS_DYNAMIC_EXEC)
        if "start-process" in text:
            kinds.add(_VALIDATION_PS_PROCESS_LAUNCH)
        if "set-acl" in text or "filesystemaccessrule" in text or "fullcontrol" in text or "everyone" in text:
            kinds.add(_VALIDATION_PS_ACL)
        if ("$env:" in text or "dcoir_token" in text) and (
            "invoke-webrequest" in text or "invoke-restmethod" in text or "authorization" in text or "callback" in text
        ):
            kinds.add(_VALIDATION_PS_ENV_TOKEN)
    if suffix in {".yml", ".yaml"}:
        shell_context = (
            "shell" in text
            or "command" in text
            or "bash" in text
            or re.search(r"\bsh(?:\s+-c)?\b", text) is not None
        )
        if ("metadata" in text or "pr title" in text or "pull request title" in text or "github.event.pull_request" in text) and shell_context:
            kinds.add(_VALIDATION_YAML_METADATA_SHELL)
        if "github.event.pull_request.head" in text or "github.head_ref" in text or ("untrusted" in text and "checkout" in text):
            kinds.add(_VALIDATION_YAML_UNTRUSTED_CHECKOUT)
        if ("curl" in text or "wget" in text) and ("bash" in text or " sh" in text or "pipe" in text):
            kinds.add(_VALIDATION_YAML_SHELL_PIPE)
        if "write-all" in text or ("permissions" in text and "write" in text) or "broad write" in text:
            kinds.add(_VALIDATION_YAML_BROAD_WRITE)
        if "pull_request_target" in text:
            kinds.add(_VALIDATION_YAML_PULL_REQUEST_TARGET)
    return kinds


def _validation_kind_for_finding(finding: dict[str, Any]) -> str:
    explicit = finding.get("_risk_sentinel_key")
    if isinstance(explicit, (list, tuple)) and len(explicit) == 3:
        return _validation_canonical_kind(str(explicit[2]))
    explicit_kind = str(finding.get("_risk_sentinel_kind", "") or "")
    if explicit_kind:
        return _validation_canonical_kind(explicit_kind)
    claimed = _validation_claimed_kinds(finding)
    for kind in (
        _VALIDATION_YAML_METADATA_SHELL,
        _VALIDATION_YAML_SHELL_PIPE,
        _VALIDATION_YAML_UNTRUSTED_CHECKOUT,
        _VALIDATION_YAML_BROAD_WRITE,
        _VALIDATION_YAML_PULL_REQUEST_TARGET,
        _VALIDATION_PS_PROCESS_LAUNCH,
        _VALIDATION_PS_DYNAMIC_EXEC,
        _VALIDATION_PS_ACL,
        _VALIDATION_PS_ENV_TOKEN,
        _VALIDATION_PYTHON_PICKLE_LOAD,
        _VALIDATION_PYTHON_YAML_LOAD,
        _VALIDATION_PYTHON_SHELL_EXEC,
        _VALIDATION_PYTHON_ENV_TOKEN,
    ):
        if kind in claimed:
            return kind
    anchored = _validation_line_kind(
        str(finding.get("path", "") or ""),
        str(finding.get("_anchored_line_text", "") or ""),
    )
    return _validation_canonical_kind(anchored)


def _validation_py_here_doc(path: str, body: str) -> str:
    return "\n".join(
        [
            "python3 - <<'PY'",
            "from pathlib import Path",
            "import re",
            f"path = Path({path!r})",
            "text = path.read_text(encoding='utf-8')",
            body,
            "PY",
        ]
    )


def _validation_for_kind(kind: str, path: str) -> str:
    quoted = shlex.quote(path)
    if kind == _VALIDATION_YAML_PULL_REQUEST_TARGET:
        return _validation_py_here_doc(path, "assert 'pull_request_target' not in text")
    if kind == _VALIDATION_YAML_BROAD_WRITE:
        return _validation_py_here_doc(
            path,
            "assert 'write-all' not in text\nassert not re.search(r'(?m)^\\s*(actions|checks|contents|deployments|id-token|issues|packages|pull-requests|statuses)\\s*:\\s*write\\b', text)",
        )
    if kind == _VALIDATION_YAML_UNTRUSTED_CHECKOUT:
        return _validation_py_here_doc(path, "assert 'github.event.pull_request.head' not in text\nassert 'github.head_ref' not in text")
    if kind == _VALIDATION_YAML_SHELL_PIPE:
        return _validation_py_here_doc(path, "assert not re.search(r'\\b(curl|wget)\\b[^\\n]*\\|\\s*(bash|sh)\\b', text, re.I)")
    if kind == _VALIDATION_YAML_METADATA_SHELL:
        return _validation_py_here_doc(
            path,
            "metadata = re.search(r'github\\.event\\.pull_request\\.(body|title|head\\.ref|head\\.sha)', text, re.I)\nshell = re.search(r'(\\|\\s*(bash|sh)\\b|\\b(bash|sh)\\s+-c\\b)', text, re.I)\nassert not (metadata and shell)",
        )
    if kind == _VALIDATION_PS_ACL:
        return _validation_ps_command(path, "if ($text -match '(?i)icacls.*Everyone:F|Everyone.*FullControl|FileSystemAccessRule.*Everyone|Set-Acl') { throw 'broad ACL grant remains' }")
    if kind == _VALIDATION_PS_PROCESS_LAUNCH:
        return _validation_ps_command(path, "if ($text -match '(?i)Start-Process\\s+-FilePath\\s+\\$[A-Za-z_][A-Za-z0-9_]*') { throw 'caller-controlled Start-Process remains' }")
    if kind == _VALIDATION_PYTHON_YAML_LOAD:
        return f"python3 -m py_compile {quoted}\n" + _validation_py_here_doc(path, "assert 'yaml.Loader' not in text\nassert 'Loader=yaml.Loader' not in text")
    if kind == _VALIDATION_PYTHON_SHELL_EXEC:
        return f"python3 -m py_compile {quoted}\n" + _validation_py_here_doc(path, "assert 'shell=True' not in text")
    return ""


def _validation_quote_ps_string(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _validation_ps_command(path: str, check: str, line: int = 0) -> str:
    ps_path = _validation_quote_ps_string(path)
    if line:
        setup = (
            f"$p = {ps_path}; $line = {max(1, line)}; $lines = Get-Content -LiteralPath $p; "
            "$start = [Math]::Max(0, $line - 4); $end = [Math]::Min($lines.Count - 1, $line + 2); "
            "$window = ($lines[$start..$end] -join \"`n\"); "
        )
    else:
        setup = f"$p = {ps_path}; $text = Get-Content -Raw -LiteralPath $p; "
    parse = "$all = Get-Content -Raw -LiteralPath $p; $errors = $null; [System.Management.Automation.PSParser]::Tokenize($all, [ref]$errors) | Out-Null; if ($errors) { throw ($errors | Out-String) }"
    return "pwsh -NoProfile -Command " + shlex.quote(setup + check + "; " + parse)


def _validation_py_window_doc(path: str, line: int, assertions: str) -> str:
    return (
        "python3 - <<'PY'\n"
        "from pathlib import Path\n"
        f"path = Path({path!r})\n"
        f"line = {max(1, line)}\n"
        "lines = path.read_text(encoding='utf-8').splitlines()\n"
        "window = '\\n'.join(lines[max(0, line - 4):min(len(lines), line + 3)])\n"
        "lower = window.lower()\n"
        f"{assertions}\n"
        "PY"
    )


def _validation_for_key(kind: str, path: str, line: int = 0) -> str:
    if kind == _VALIDATION_PS_ENV_TOKEN:
        return _validation_ps_command(
            path,
            "if (($window -match '(?i)\\$env:DCOIR_TOKEN') -and ($window -match '(?i)Authorization|Bearer') -and ($window -match '(?i)Invoke-(RestMethod|WebRequest)|callback')) { throw 'environment token forwarded to request-controlled callback remains' }",
            line,
        )
    if kind == _VALIDATION_PS_PROCESS_LAUNCH:
        return _validation_ps_command(path, "if ($text -match '(?i)Start-Process\\s+-FilePath\\s+\\$[A-Za-z_][A-Za-z0-9_]*') { throw 'caller-controlled Start-Process remains' }")
    if kind == _VALIDATION_PS_ACL:
        return _validation_ps_command(path, "if ($text -match '(?i)icacls.*Everyone:F|Everyone.*FullControl|FileSystemAccessRule.*Everyone|Set-Acl') { throw 'broad ACL grant remains' }")
    if kind == _VALIDATION_PYTHON_PICKLE_LOAD:
        quoted = shlex.quote(path)
        return f"python3 -m py_compile {quoted}\n" + _validation_py_here_doc(path, "assert 'pickle.loads' not in text\nassert 'pickle.load(' not in text")
    if kind == _VALIDATION_PYTHON_ENV_TOKEN:
        quoted = shlex.quote(path)
        checks = "has_env = 'os.getenv' in lower or 'os.environ' in lower\nhas_bearer = 'authorization' in lower or 'bearer' in lower\nhas_callback = 'requests.' in lower or 'callback' in lower\nassert not (has_env and has_bearer and has_callback)"
        return f"python3 -m py_compile {quoted}\n" + _validation_py_window_doc(path, line, checks)
    return _validation_for_kind(kind, path)


def validation_text_for_finding(finding: dict[str, Any]) -> str:
    path = str(finding.get("path", "") or "")
    line = _validation_line_number(finding.get("line", 0))
    kind = _validation_kind_for_finding(finding)
    semantic = _validation_for_key(kind, path, line)
    if semantic:
        return semantic

    commands = extract_validation_commands(str(finding.get("validation", "")).strip())
    defaults = default_validation_commands_for_path(path)
    combined: list[str] = []
    seen: set[str] = set()
    for command in [*commands, *defaults]:
        if command and command not in seen:
            combined.append(command)
            seen.add(command)
    return "\n".join(combined)
