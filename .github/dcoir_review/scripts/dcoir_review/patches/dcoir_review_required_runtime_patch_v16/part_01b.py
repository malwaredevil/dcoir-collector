def _python_line_imports_urllib_urlopen_alias(text: str) -> bool:
    module = _python_parse_diff_line(text)
    if module is None:
        return bool(re.search(r"^\s*from\s+urllib\.request\s+import\s+.*\burlopen\b", text))
    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.module == "urllib.request":
            return any(alias.name == "urlopen" for alias in node.names)
    return False


def _python_shadowed_name_roots(module: ast.AST) -> set[str]:
    roots: set[str] = set()

    def collect_target(node: ast.AST) -> None:
        if isinstance(node, ast.Name):
            roots.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for item in node.elts:
                collect_target(item)
        elif isinstance(node, ast.Starred):
            collect_target(node.value)

    class _ModuleScopeShadowVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            roots.add(node.name)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            roots.add(node.name)

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            roots.add(node.name)

        def visit_Assign(self, node: ast.Assign) -> None:
            for target in node.targets:
                collect_target(target)
            self.generic_visit(node.value)

        def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
            collect_target(node.target)
            if node.value is not None:
                self.generic_visit(node.value)

        def visit_AugAssign(self, node: ast.AugAssign) -> None:
            collect_target(node.target)
            self.generic_visit(node.value)

        def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
            collect_target(node.target)
            self.generic_visit(node.value)

        def visit_For(self, node: ast.For) -> None:
            collect_target(node.target)
            self.generic_visit(node.iter)
            for statement in node.body:
                self.visit(statement)
            for statement in node.orelse:
                self.visit(statement)

        def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
            collect_target(node.target)
            self.generic_visit(node.iter)
            for statement in node.body:
                self.visit(statement)
            for statement in node.orelse:
                self.visit(statement)

        def visit_With(self, node: ast.With) -> None:
            for item in node.items:
                if item.optional_vars is not None:
                    collect_target(item.optional_vars)
                self.generic_visit(item.context_expr)
            for statement in node.body:
                self.visit(statement)

        def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
            for item in node.items:
                if item.optional_vars is not None:
                    collect_target(item.optional_vars)
                self.generic_visit(item.context_expr)
            for statement in node.body:
                self.visit(statement)

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if node.name:
                roots.add(node.name)
            if node.type is not None:
                self.generic_visit(node.type)
            for statement in node.body:
                self.visit(statement)

    visitor = _ModuleScopeShadowVisitor()
    for statement in getattr(module, "body", []):
        visitor.visit(statement)
    return roots


def _python_prune_shadowed_urlopen_call_names(call_names: set[str], shadowed_roots: set[str]) -> set[str]:
    if not shadowed_roots:
        return call_names
    return {
        call_name
        for call_name in call_names
        if call_name.split(".", 1)[0] not in shadowed_roots
    }


def _python_urllib_urlopen_call_names(text: str) -> set[str]:
    call_names: set[str] = set()
    module = _python_parse_diff_line(text)
    if module is None:
        if _python_line_imports_urllib_urlopen_alias(text):
            call_names.add("urlopen")
        module_alias_match = re.match(r"^\s*import\s+urllib\.request\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\b", text)
        if module_alias_match:
            call_names.add(f"{module_alias_match.group(1)}.urlopen")
        request_alias_match = re.match(r"^\s*from\s+urllib\s+import\s+request\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\b", text)
        if request_alias_match:
            call_names.add(f"{request_alias_match.group(1)}.urlopen")
        urllib_alias_match = re.match(r"^\s*import\s+urllib\s+as\s+([A-Za-z_][A-Za-z0-9_]*)\b", text)
        if urllib_alias_match:
            call_names.add(f"{urllib_alias_match.group(1)}.request.urlopen")
        return call_names
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom):
            if node.module == "urllib.request":
                for alias in node.names:
                    if alias.name == "urlopen":
                        call_names.add(alias.asname or alias.name)
            elif node.module == "urllib":
                for alias in node.names:
                    if alias.name == "request":
                        call_names.add(f"{alias.asname or alias.name}.urlopen")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "urllib.request":
                    call_names.add(f"{alias.asname or alias.name}.urlopen")
                elif alias.name == "urllib":
                    call_names.add(f"{alias.asname or alias.name}.request.urlopen")
    return _python_prune_shadowed_urlopen_call_names(
        call_names,
        _python_shadowed_name_roots(module),
    )


def _iter_diff_python_lines_with_context(diff: str) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    current_path = ""
    inside_hunk = False
    for raw_line in str(diff or "").splitlines():
        if raw_line.startswith("+++ b/"):
            current_path = raw_line[6:]
            inside_hunk = False
            continue
        if raw_line.startswith("@@"):
            inside_hunk = True
            continue
        if not inside_hunk or not current_path or Path(current_path).suffix.lower() != ".py":
            continue
        if raw_line.startswith("\\"):
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            lines.append((current_path, raw_line[1:]))
        elif raw_line.startswith(" "):
            lines.append((current_path, raw_line[1:]))
    return lines


def _python_diff_urllib_urlopen_call_names(diff: str) -> dict[str, set[str]]:
    sources_by_path: dict[str, list[str]] = {}
    for path, text in _iter_diff_python_lines_with_context(diff):
        sources_by_path.setdefault(str(path), []).append(text)
    call_names_by_path: dict[str, set[str]] = {}
    for path, lines in sources_by_path.items():
        call_names = _python_urllib_urlopen_call_names("\n".join(lines))
        call_names_by_path[path] = call_names
    return call_names_by_path


def _python_is_known_urllib_urlopen(
    text: str,
    allow_imported_alias: bool = False,
    known_call_names: set[str] | None = None,
) -> bool:
    call_names = set(known_call_names or ())
    if allow_imported_alias:
        call_names.add("urlopen")
    if not call_names:
        return False
    module = _python_parse_diff_line(text)
    if module is not None:
        return any(
            isinstance(node, ast.Call) and _python_call_name(node.func) in call_names
            for node in ast.walk(module)
        )
    pattern = r"\b(?:" + "|".join(re.escape(name) for name in sorted(call_names, key=len, reverse=True)) + r")\s*\("
    return bool(re.search(pattern, text, re.IGNORECASE))


def _python_is_explicit_file_write(text: str) -> bool:
    module = _python_parse_diff_line(text)
    if module is None:
        return False
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        call_name = _python_call_name(node.func)
        if call_name == "os.open":
            return _python_os_open_uses_write_mode(node)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
            and not _python_is_proven_path_receiver(node.func.value)
            and call_name not in (set(PYTHON_KNOWN_READ_MODE_OPEN_CALLS) | {"os.open"})
        ):
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"write_text", "write_bytes"}:
            return True
        if _python_call_uses_write_mode(node):
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
            if _python_is_known_urllib_urlopen(text):
                return _ORIGINAL_V13_LINE_KIND(path, text)
            if _python_is_explicit_file_write(text):
                return v11.PYTHON_PATH_WRITE
            if _python_parse_diff_line(text) is not None:
                return _ORIGINAL_V13_LINE_KIND(path, text)
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