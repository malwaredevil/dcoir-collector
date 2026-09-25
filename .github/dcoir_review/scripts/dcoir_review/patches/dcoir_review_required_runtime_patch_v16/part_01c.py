def _python_diff_import_alias_context(diff: str) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    sources_by_path: dict[str, list[str]] = {}
    for path, text in _iter_diff_python_lines_with_context(diff):
        sources_by_path.setdefault(path, []).append(text)
    path_aliases: dict[str, set[str]] = {}
    os_aliases: dict[str, set[str]] = {}
    for path, lines in sources_by_path.items():
        module = _python_parse_diff_line("\n".join(lines))
        if module is None:
            continue
        shadowed_roots = _python_shadowed_name_roots(module)
        path_names: set[str] = set()
        os_names: set[str] = set()
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom) and node.module == "pathlib":
                for alias in node.names:
                    if alias.name == "Path":
                        name = alias.asname or alias.name
                        if name not in shadowed_roots:
                            path_names.add(name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.asname or alias.name
                    if alias.name == "pathlib" and root not in shadowed_roots:
                        path_names.add(f"{root}.Path")
                    elif alias.name == "os" and root not in shadowed_roots:
                        os_names.add(root)
        if path_names:
            path_aliases[path] = path_names
        if os_names:
            os_aliases[path] = os_names
    return path_aliases, os_aliases


def _python_has_known_file_open_call(
    text: str,
    path_constructor_names: set[str],
    os_module_names: set[str],
) -> bool:
    module = _python_parse_diff_line(text)
    if module is None:
        return False
    os_open_names = {f"{name}.open" for name in os_module_names}
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        call_name = _python_call_name(node.func)
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            return True
        if call_name in PYTHON_KNOWN_READ_MODE_OPEN_CALLS or call_name in os_open_names:
            return True
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
            and _python_is_proven_path_receiver(node.func.value, path_constructor_names)
        ):
            return True
    return False


def _line_kind(path: str, text: str) -> str:
    suffix = Path(str(path or "").lower()).suffix
    lower = _normalize(text)
    if _is_workflow_path(path):
        if PR_METADATA_TOKEN_RE.search(lower):
            return v10.YAML_TOKEN_TO_PR_URL
        if "pull_request_target" in lower:
            return v4.YAML_PULL_REQUEST_TARGET
        if "write-all" in lower or re.search(r"\b[a-z_-]+\s*:\s*write\b", lower):
            return v4.YAML_BROAD_WRITE
        if "github.event.pull_request.head" in lower or "github.head_ref" in lower:
            return v4.YAML_UNTRUSTED_CHECKOUT
        if ("curl" in lower or "wget" in lower) and ("| sh" in lower or "| bash" in lower):
            return v4.YAML_SHELL_PIPE
        if "github.event.pull_request" in lower and any(token in lower for token in ("bash -lc", "sh -c", "run:", "shell:")):
            return v4.YAML_METADATA_SHELL
    if suffix == ".py":
        if "pickle.loads" in lower or "pickle.load(" in lower:
            return v9.PYTHON_PICKLE_LOAD
        if "yaml.load" in lower:
            return v5.PYTHON_YAML_LOAD
        if PYTHON_BUILTIN_DYNAMIC_EXEC_RE.search(lower):
            return PYTHON_DYNAMIC_EXEC
        if "shell=true" in lower or "os.system(" in lower or "os.popen(" in lower:
            return v5.PYTHON_SHELL_EXEC
        if ("requests." in lower or "urlopen" in lower) and (
            "authorization" in lower or "bearer" in lower or "dcoir_token" in lower or "callback" in lower
        ):
            return v5.PYTHON_ENV_TOKEN
        if "extractall" in lower:
            return v11.PYTHON_ARCHIVE_EXTRACT
        if any(token in lower for token in ("write_text(", "write_bytes(", ".open(", "open(")):
            constructor_names = {"Path", "pathlib.Path"}
            constructor_names.update(PYTHON_PATH_ALIAS_CONTEXT.get(path, set()))
            os_module_names = {"os"}
            os_module_names.update(PYTHON_OS_ALIAS_CONTEXT.get(path, set()))
            shadowed_names = PYTHON_SHADOWED_NAME_CONTEXT.get(path)
            if _python_is_known_urllib_urlopen(
                text,
                known_call_names=PYTHON_URLLIB_URLOPEN_CALL_CONTEXT.get(path),
            ):
                fallback = _ORIGINAL_V13_LINE_KIND(path, text)
                return "" if fallback == v11.PYTHON_PATH_WRITE else fallback
            if _python_is_explicit_file_write(text, constructor_names, os_module_names, shadowed_names):
                return v11.PYTHON_PATH_WRITE
            if _python_has_known_file_open_call(text, constructor_names, os_module_names):
                fallback = _ORIGINAL_V13_LINE_KIND(path, text)
                return "" if fallback == v11.PYTHON_PATH_WRITE else fallback
            return v11.PYTHON_PATH_WRITE
    if suffix in {".ps1", ".psm1", ".psd1"}:
        if "invoke-expression" in lower or re.search(r"\biex\b", lower):
            return v9.PS_DYNAMIC_EXEC
        if "convertto-securestring" in lower and "-asplaintext" in lower:
            return v13.PS_PLAINTEXT_SECURE_STRING
        if "filesystemaccessrule" in lower or "set-acl" in lower:
            return v4.PS_ACL
        if "start-process" in lower:
            return v4.PS_PROCESS_LAUNCH
        if ("invoke-webrequest" in lower or "invoke-restmethod" in lower) and (
            "authorization" in lower or "bearer" in lower or "$env:dcoir_token" in lower
        ):
            return v5.PS_ENV_TOKEN
        if "currentversion\\run" in lower:
            return v13.PS_RUN_KEY_PERSISTENCE
    if suffix in {".ts", ".tsx", ".js", ".jsx"}:
        if ".innerhtml" in lower or ".outerhtml" in lower or "insertadjacenthtml" in lower:
            return v13.TS_INNER_HTML
        if "settimeout(" in lower or "setinterval(" in lower or "new function(" in lower:
            return v13.TS_DYNAMIC_EXECUTION
    return _ORIGINAL_V13_LINE_KIND(path, text)


def _sentinel_key(sentinel: Any) -> SentinelKey:
    path = str(getattr(sentinel, "path", "") or "")
    line = _line_number(getattr(sentinel, "line", 0))
    text = str(getattr(sentinel, "text", "") or "")
    kind = _line_kind(path, text) or _ORIGINAL_V13_SENTINEL_KEY(sentinel)[2]
    return path, line, kind


def _postable_key(finding: dict[str, Any]) -> SentinelKey:
    raw = finding.get("_risk_sentinel_key")
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        return str(raw[0] or ""), _line_number(raw[1]), str(raw[2] or "")
    path, line, kind = _ORIGINAL_V13_POSTABLE_KEY(finding)
    text = "\n".join(str(finding.get(name, "") or "") for name in ("_anchored_line_text", "title", "body", "description"))
    return path, line, _line_kind(path, text) or kind


def _coverage_key(key: SentinelKey) -> SentinelKey:
    path, line, kind = key
    if kind in {v4.YAML_BROAD_WRITE, v11.PYTHON_ARCHIVE_EXTRACT}:
        return path, 0, kind
    return path, line, kind


def _coverage_from_finding(finding: dict[str, Any]) -> set[SentinelKey]:
    keys = {_coverage_key(_postable_key(finding))}
    raw_keys = finding.get("covered_risk_sentinel_keys")
    if isinstance(raw_keys, list):
        for raw in raw_keys:
            if isinstance(raw, (list, tuple)) and len(raw) == 3:
                keys.add(_coverage_key((str(raw[0] or ""), _line_number(raw[1]), str(raw[2] or ""))))
    return {key for key in keys if key[0] and key[2]}


def _kind_rank(kind: str) -> int:
    order = {
        v10.YAML_TOKEN_TO_PR_URL: 0,
        v4.YAML_METADATA_SHELL: 1,
        v4.YAML_SHELL_PIPE: 2,
        v4.YAML_PULL_REQUEST_TARGET: 3,
        v4.YAML_BROAD_WRITE: 4,
        v4.YAML_UNTRUSTED_CHECKOUT: 5,
        v9.PYTHON_PICKLE_LOAD: 10,
        v5.PYTHON_YAML_LOAD: 11,
        PYTHON_DYNAMIC_EXEC: 12,
        v5.PYTHON_SHELL_EXEC: 13,
        v5.PYTHON_ENV_TOKEN: 14,
        v11.PYTHON_ARCHIVE_EXTRACT: 15,
        v11.PYTHON_PATH_WRITE: 16,
        v9.PS_DYNAMIC_EXEC: 20,
        v4.PS_PROCESS_LAUNCH: 21,
        v5.PS_ENV_TOKEN: 22,
        v13.PS_RUN_KEY_PERSISTENCE: 23,
        v4.PS_ACL: 24,
        v13.PS_PLAINTEXT_SECURE_STRING: 25,
        v13.TS_INNER_HTML: 80,
        v13.TS_DYNAMIC_EXECUTION: 81,
    }
    return order.get(str(kind or ""), 99)


def _family(kind: str) -> str:
    if kind.startswith("yaml_"):
        return "yaml"
    if kind.startswith("python_"):
        return "python"
    if kind.startswith("ps_"):
        return "powershell"
    if kind.startswith("ts_"):
        return "typescript"
    if kind.startswith("k8s_"):
        return "kubernetes"
    return "other"