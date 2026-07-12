

def _candidate_priority(finding: dict[str, Any]) -> tuple[int, int, int, str, int]:
    path, line, kind = _postable_key(finding)
    if finding.get("_dcoir_v16_aggregate"):
        group = 0
    elif kind in CORE_REQUIRED_KINDS:
        group = 1
    elif kind in OPTIONAL_PRESSURE_KINDS or _is_optional_path(path):
        group = 8
    else:
        group = 5
    family = {"yaml": 0, "python": 1, "powershell": 2, "other": 5, "typescript": 8, "kubernetes": 9}.get(_family(kind), 7)
    return group, family, _kind_rank(kind), path, line


def _quote(path: str) -> str:
    return shlex.quote(path)


def _validation_for_key(kind: str, path: str, line: int = 0) -> str:
    if kind.startswith("python_"):
        return f"python3 -m py_compile {_quote(path)}"
    if kind.startswith("ps_"):
        ps_path = path.replace("'", "''")
        script = (
            "$errors=$null; "
            f"[System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw -LiteralPath '{ps_path}'), [ref]$errors) | Out-Null; "
            "if ($errors) { throw ($errors | Out-String) }"
        )
        return "pwsh -NoProfile -Command " + shlex.quote(script)
    if kind.startswith("yaml_"):
        return "python3 -c " + shlex.quote(f"from pathlib import Path; Path({path!r}).read_text(encoding='utf-8')")
    return _ORIGINAL_V13_VALIDATION_FOR_KEY(kind, path, line)


def _template_for_kind(kind: str) -> tuple[str, str, str]:
    if kind == PYTHON_DYNAMIC_EXEC:
        return (
            "Python executes caller-controlled code",
            "This line evaluates text as Python code.",
            "Replace dynamic evaluation with explicit allowlisted behavior or a safe parser.",
        )
    return _ORIGINAL_V13_TEMPLATE_FOR_KIND(kind)


def _finding_for_sentinel(sentinel: Any) -> dict[str, Any]:
    path, line, kind = _sentinel_key(sentinel)
    title, body, notes = _template_for_kind(kind)
    return {
        "title": title,
        "body": body,
        "severity": "critical" if kind in CORE_REQUIRED_KINDS else "high",
        "confidence": 0.99,
        "path": path,
        "line": line,
        "_anchored_line_text": str(getattr(sentinel, "text", "") or ""),
        "_risk_sentinel_key": [path, line, kind],
        "_risk_sentinel_kind": kind,
        "validation": _validation_for_key(kind, path, line),
        "fix_guidance": {
            "language": "yaml" if kind.startswith("yaml_") else "powershell" if kind.startswith("ps_") else "python" if kind.startswith("python_") else "text",
            "notes": notes,
            "validation": _validation_for_key(kind, path, line),
        },
    }


def _line_label(key: SentinelKey) -> str:
    return f"`{key[0]}:{key[1]}` `{key[2]}`"


def _aggregate_finding(path: str, line: int, kind: str, title: str, body: str, notes: str, keys: list[SentinelKey]) -> dict[str, Any]:
    validation = _validation_for_key(kind, path, line)
    return {
        "title": title,
        "body": body,
        "severity": "critical",
        "confidence": 0.99,
        "path": path,
        "line": line,
        "_risk_sentinel_key": [path, line, kind],
        "_risk_sentinel_kind": kind,
        "covered_risk_sentinel_keys": [[item[0], item[1], item[2]] for item in keys],
        "_dcoir_v16_aggregate": True,
        "validation": validation,
        "fix_guidance": {"language": "yaml" if kind.startswith("yaml_") else "powershell", "notes": notes, "validation": validation},
    }


def _choose_anchor(keys: list[SentinelKey], preferred: tuple[str, ...]) -> SentinelKey:
    for kind in preferred:
        for key in keys:
            if key[2] == kind:
                return key
    return sorted(keys, key=lambda item: (item[0], item[1], _kind_rank(item[2])))[0]


def _aggregate_candidates(core_sentinels: list[Any]) -> list[dict[str, Any]]:
    by_path: dict[str, list[SentinelKey]] = {}
    for sentinel in core_sentinels:
        key = _sentinel_key(sentinel)
        by_path.setdefault(key[0], []).append(key)
    aggregates: list[dict[str, Any]] = []
    for path, keys in by_path.items():
        if _is_workflow_path(path):
            privilege = [key for key in keys if key[2] in {v4.YAML_PULL_REQUEST_TARGET, v4.YAML_BROAD_WRITE, v4.YAML_UNTRUSTED_CHECKOUT}]
            if privilege:
                anchor = _choose_anchor(privilege, (v4.YAML_PULL_REQUEST_TARGET, v4.YAML_BROAD_WRITE, v4.YAML_UNTRUSTED_CHECKOUT))
                detail = ", ".join(_line_label(key) for key in sorted(privilege, key=lambda item: item[1]))
                aggregates.append(
                    _aggregate_finding(
                        anchor[0],
                        anchor[1],
                        anchor[2],
                        "Privileged workflow combines sensitive permissions with PR-controlled code",
                        f"This workflow combines privileged pull request context, write permissions, or PR-controlled checkout. Covered signals: {detail}.",
                        "Split privileged metadata handling from untrusted code checkout/execution and reduce workflow permissions to least privilege.",
                        privilege,
                    )
                )
            metadata = [key for key in keys if key[2] in {v4.YAML_METADATA_SHELL, v10.YAML_TOKEN_TO_PR_URL, v4.YAML_SHELL_PIPE}]
            if metadata:
                anchor = _choose_anchor(metadata, (v4.YAML_METADATA_SHELL, v10.YAML_TOKEN_TO_PR_URL, v4.YAML_SHELL_PIPE))
                detail = ", ".join(_line_label(key) for key in sorted(metadata, key=lambda item: item[1]))
                aggregates.append(
                    _aggregate_finding(
                        anchor[0],
                        anchor[1],
                        anchor[2],
                        "Privileged workflow executes or exfiltrates pull request metadata",
                        f"Pull request metadata reaches shell execution, token-bearing requests, or network-fetched shell execution. Covered signals: {detail}.",
                        "Do not execute PR metadata, do not send repository tokens to PR-controlled URLs, and verify downloaded installers before execution.",
                        metadata,
                    )
                )
        ps_command = [key for key in keys if key[2] in {v4.PS_ACL, v4.PS_PROCESS_LAUNCH, v9.PS_DYNAMIC_EXEC, v13.PS_RUN_KEY_PERSISTENCE}]
        if ps_command:
            anchor = _choose_anchor(ps_command, (v4.PS_ACL, v4.PS_PROCESS_LAUNCH, v9.PS_DYNAMIC_EXEC, v13.PS_RUN_KEY_PERSISTENCE))
            detail = ", ".join(_line_label(key) for key in sorted(ps_command, key=lambda item: item[1]))
            aggregates.append(
                _aggregate_finding(
                    anchor[0],
                    anchor[1],
                    anchor[2],
                    "PowerShell combines broad access, dynamic execution, process launch, or persistence",
                    f"This script contains command execution, broad ACL, process launch, or Run-key persistence risk. Covered signals: {detail}.",
                    "Replace dynamic execution and caller-controlled launches with allowlisted commands, narrow ACLs, and remove Run-key writes unless explicitly governed.",
                    ps_command,
                )
            )
        ps_secret = [key for key in keys if key[2] in {v13.PS_PLAINTEXT_SECURE_STRING, v5.PS_ENV_TOKEN}]
        if ps_secret:
            anchor = _choose_anchor(ps_secret, (v13.PS_PLAINTEXT_SECURE_STRING, v5.PS_ENV_TOKEN))
            detail = ", ".join(_line_label(key) for key in sorted(ps_secret, key=lambda item: item[1]))
            aggregates.append(
                _aggregate_finding(
                    anchor[0],
                    anchor[1],
                    anchor[2],
                    "PowerShell handles plaintext secret material or forwards an environment token",
                    f"Secret material is accepted as plaintext or an environment token is forwarded to a request-controlled callback. Covered signals: {detail}.",
                    "Load secrets from a trusted secret store and allowlist outbound token-bearing destinations.",
                    ps_secret,
                )
            )
    return aggregates


def _coalesce_sentinels(sentinels: list[Any]) -> list[Any]:
    kept: dict[SentinelKey, Any] = {}
    for sentinel in sentinels:
        key = _sentinel_key(sentinel)
        coverage = _coverage_key(key)
        current = kept.get(coverage)
        if current is None:
            kept[coverage] = sentinel
            continue
        current_key = _sentinel_key(current)
        if (_kind_rank(key[2]), key[1]) < (_kind_rank(current_key[2]), current_key[1]):
            kept[coverage] = sentinel
    return list(kept.values())


def _core_sentinels(risk_sentinels: list[Any]) -> list[Any]:
    return _coalesce_sentinels([sentinel for sentinel in risk_sentinels if _sentinel_key(sentinel)[2] in CORE_REQUIRED_KINDS])
