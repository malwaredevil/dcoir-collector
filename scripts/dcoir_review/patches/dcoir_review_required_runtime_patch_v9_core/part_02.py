def _sentinel_key(sentinel: Any) -> SentinelKey:
    path = str(getattr(sentinel, "path", "") or "")
    line = _line_number(getattr(sentinel, "line", 0))
    text = str(getattr(sentinel, "text", "") or "")
    label = str(getattr(sentinel, "label", "") or "")
    detail = str(getattr(sentinel, "detail", "") or "")
    kind = _canonical_kind(_line_kind(path, text) or v5._sentinel_kind(sentinel))
    context = f"{text}\n{label}\n{detail}"
    if kind == getattr(v4, "PYTHON_SSRF", "python_ssrf") and _looks_like_python_env_token_callback(context):
        kind = v5.PYTHON_ENV_TOKEN
    if kind in {"", "unknown"} and _looks_like_python_env_token_callback(context):
        kind = v5.PYTHON_ENV_TOKEN
    if kind in {"", "unknown"} and ("pickle.loads" in _normalize(context) or "pickle.load(" in _normalize(context)):
        kind = PYTHON_PICKLE_LOAD
    return path, line, kind


def _required_sentinels(hardened: Any, risk_sentinels: list[Any]) -> list[Any]:
    required = list(hardened.required_risk_sentinels(risk_sentinels)) if callable(getattr(hardened, "required_risk_sentinels", None)) else []
    seen = {_sentinel_key(item) for item in required}
    for sentinel in risk_sentinels:
        key = _sentinel_key(sentinel)
        if key[2] == PYTHON_PICKLE_LOAD and key not in seen:
            required.append(sentinel)
            seen.add(key)
    return required


def _expected_by_line(hardened: Any, risk_sentinels: list[Any]) -> dict[tuple[str, int], set[str]]:
    expected: dict[tuple[str, int], set[str]] = {}
    for sentinel in _required_sentinels(hardened, risk_sentinels):
        path, line, kind = _sentinel_key(sentinel)
        expected.setdefault((path, line), set()).add(kind)
    return expected


def _semantic_mismatch(finding: dict[str, Any], expected: dict[tuple[str, int], set[str]]) -> bool:
    path, line, kind = _postable_key(finding)
    allowed = expected.get((path, line), set())
    if not allowed:
        return False
    explicit = finding.get("_risk_sentinel_key")
    if isinstance(explicit, (list, tuple)) and len(explicit) == 3 and str(explicit[2]) not in allowed:
        return True
    explicit_kind = str(finding.get("_risk_sentinel_kind", "") or "")
    if explicit_kind and explicit_kind not in allowed:
        return True
    claimed = _claimed_kinds(finding)
    return bool((claimed and any(item not in allowed for item in claimed)) or kind not in allowed)


def _severity_rank(finding: dict[str, Any]) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(str(finding.get("severity", "")).lower(), 4)


def _confidence(finding: dict[str, Any]) -> float:
    try:
        return float(finding.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _spare_priority(finding: dict[str, Any]) -> tuple[int, int, float, str, int]:
    path = str(finding.get("path", "") or "")
    suffix = Path(path.lower()).suffix
    optional = "/optional_" in path.lower() or path.rsplit("/", 1)[-1].startswith("optional_")
    if _postable_key(finding)[2] == PYTHON_PICKLE_LOAD:
        family = 0
    elif not optional and suffix in {".py", ".ps1", ".psm1", ".psd1", ".yml", ".yaml"}:
        family = 1
    elif not optional:
        family = 2
    else:
        family = 3
    return family, _severity_rank(finding), -_confidence(finding), path, _line_number(finding.get("line", 0))


def _dedupe(findings: list[dict[str, Any]], expected: dict[tuple[str, int], set[str]]) -> tuple[list[dict[str, Any]], list[str]]:
    kept: dict[SentinelKey, dict[str, Any]] = {}
    order: list[SentinelKey] = []
    dropped: list[str] = []
    for finding in findings:
        item = v5._normalize_comment_finding(finding)
        key = _postable_key(item)
        if _semantic_mismatch(item, expected):
            dropped.append(f"{key[0]}:{key[1]} expected={','.join(sorted(expected.get((key[0], key[1]), set())))} actual={key[2]}")
            continue
        if key not in kept:
            kept[key] = item
            order.append(key)
        else:
            dropped.append(f"{key[0]}:{key[1]} duplicate {key[2]}")
            if (_severity_rank(item), -_confidence(item)) < (_severity_rank(kept[key]), -_confidence(kept[key])):
                kept[key] = item
    return [kept[key] for key in order], dropped


def _quote_ps_string(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _ps_validation(path: str, check: str, line: int = 0) -> str:
    ps_path = _quote_ps_string(path)
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


def _py_window_doc(path: str, line: int, assertions: str) -> str:
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
    if kind == v5.PS_ENV_TOKEN:
        return _ps_validation(path, "if (($window -match '(?i)\\$env:DCOIR_TOKEN') -and ($window -match '(?i)Authorization|Bearer') -and ($window -match '(?i)Invoke-(RestMethod|WebRequest)|callback')) { throw 'environment token forwarded to request-controlled callback remains' }", line)
    if kind == v4.PS_PROCESS_LAUNCH:
        return _ps_validation(path, "if ($text -match '(?i)Start-Process\\s+-FilePath\\s+\\$[A-Za-z_][A-Za-z0-9_]*') { throw 'caller-controlled Start-Process remains' }")
    if kind == v4.PS_ACL:
        return _ps_validation(path, "if ($text -match '(?i)icacls.*Everyone:F|Everyone.*FullControl|FileSystemAccessRule.*Everyone|Set-Acl') { throw 'broad ACL grant remains' }")
    if kind == PYTHON_PICKLE_LOAD:
        quoted = shlex.quote(path)
        return f"python3 -m py_compile {quoted}\n" + v8._py_here_doc(path, "assert 'pickle.loads' not in text\nassert 'pickle.load(' not in text")
    if kind == v5.PYTHON_ENV_TOKEN:
        quoted = shlex.quote(path)
        checks = "has_env = 'os.getenv' in lower or 'os.environ' in lower\nhas_bearer = 'authorization' in lower or 'bearer' in lower\nhas_callback = 'requests.' in lower or 'callback' in lower\nassert not (has_env and has_bearer and has_callback)"
        return f"python3 -m py_compile {quoted}\n" + _py_window_doc(path, line, checks)
    return v8._validation_for_kind(kind, path)


def _yaml_load_arg(line_text: str) -> str:
    match = re.search(r"yaml\.load\s*\(\s*(?P<arg>[^,\n)]+)", str(line_text or ""))
    if not match:
        return "text"
    arg = match.group("arg").strip()
    return arg if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", arg) else "text"


def _rewrite_validation(findings: list[dict[str, Any]]) -> None:
    for finding in findings:
        path, line, kind = _postable_key(finding)
        validation = _validation_for_key(kind, path, line)
        if validation:
            finding["validation"] = validation
            guidance = finding.get("fix_guidance")
            if isinstance(guidance, dict):
                guidance["validation"] = validation
