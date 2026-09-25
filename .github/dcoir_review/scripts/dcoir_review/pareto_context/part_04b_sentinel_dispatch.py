def is_python_test_file_path(path: str) -> bool:
    normalized = str(path or "").replace("\\", "/").lower()
    name = normalized.rsplit("/", 1)[-1]
    return normalized.endswith(".py") and (
        name.startswith("test_")
        or name.endswith("_test.py")
        or "/test/" in normalized
        or "/tests/" in normalized
    )


def detect_github_actions_yaml_sentinels(diff: str) -> list[hardened.RiskSentinel]:
    sentinels: list[hardened.RiskSentinel] = []
    seen: set[tuple[str, int, str]] = set()
    for changed_line in hardened.iter_added_diff_lines(diff):
        if Path(changed_line.path).suffix.lower() not in {".yml", ".yaml"}:
            continue
        if hardened.is_comment_only_added_line(changed_line.path, changed_line.text):
            continue
        line_text = changed_line.text
        if GITHUB_ACTIONS_WRITE_PERMISSION_RE.search(line_text):
            key = (changed_line.path, changed_line.line, GITHUB_ACTIONS_BROAD_WRITE_PERMISSION_LABEL)
            if key not in seen:
                seen.add(key)
                sentinels.append(
                    hardened.RiskSentinel(
                        path=changed_line.path,
                        line=changed_line.line,
                        label=GITHUB_ACTIONS_BROAD_WRITE_PERMISSION_LABEL,
                        detail=GITHUB_ACTIONS_BROAD_WRITE_PERMISSION_DETAIL,
                        text=changed_line.text,
                    )
                )
        if GITHUB_ACTIONS_UNTRUSTED_CHECKOUT_REF_RE.search(line_text):
            key = (changed_line.path, changed_line.line, GITHUB_ACTIONS_UNTRUSTED_CHECKOUT_REF_LABEL)
            if key not in seen:
                seen.add(key)
                sentinels.append(
                    hardened.RiskSentinel(
                        path=changed_line.path,
                        line=changed_line.line,
                        label=GITHUB_ACTIONS_UNTRUSTED_CHECKOUT_REF_LABEL,
                        detail=GITHUB_ACTIONS_UNTRUSTED_CHECKOUT_REF_DETAIL,
                        text=changed_line.text,
                    )
                )
    return sentinels


def detect_risk_sentinels(diff: str, max_anchors: int | None = None) -> list[hardened.RiskSentinel]:
    diff_fixture_added_lines = python_diff_fixture_added_line_keys(diff)
    urllib_urlopen_call_names_by_path = python_diff_urllib_urlopen_call_names(diff)
    shadowed_name_roots_by_path = python_diff_shadowed_name_roots(diff)
    skipped_test_file_write_labels = {
        FILE_WRITE_PATH_LABEL,
        "Python request-controlled file write",
        "Python writes to a request-controlled filesystem path",
    }
    legacy_sentinels: list[hardened.RiskSentinel] = []
    for sentinel in _original_detect_risk_sentinels(diff, None):
        if (sentinel.path, sentinel.line) in diff_fixture_added_lines:
            continue
        if sentinel.label in skipped_test_file_write_labels:
            if is_python_test_file_path(sentinel.path):
                continue
            if Path(sentinel.path).suffix.lower() == ".py":
                path_constructor_names = set(DEFAULT_PYTHON_PATH_CONSTRUCTORS)
                path_constructor_names.update(PYTHON_PATH_ALIAS_CONTEXT.get(sentinel.path, set()))
                os_module_names = set(DEFAULT_PYTHON_OS_MODULES)
                os_module_names.update(PYTHON_OS_ALIAS_CONTEXT.get(sentinel.path, set()))
                known_call_names = urllib_urlopen_call_names_by_path.get(sentinel.path)
                statement_text = python_diff_statement_text_for_anchor(diff, sentinel.path, sentinel.line, sentinel.text)
                is_known_urlopen = python_line_is_known_urllib_urlopen(
                    statement_text,
                    known_call_names=known_call_names,
                )
                if (
                    (is_known_urlopen or re.search(r"\b(?:write_text|write_bytes|open)\s*\(", statement_text))
                    and not python_line_has_explicit_file_write_call(
                        statement_text,
                        path_constructor_names,
                        os_module_names,
                        known_call_names=known_call_names,
                        shadowed_names=shadowed_name_roots_by_path.get(sentinel.path),
                    )
                ):
                    # Historical string matching treated parseable, non-writing
                    # ``open`` lookalikes (for example ``urlopen`` and read-only
                    # ``open(..., "r")``) as filesystem writes. Drop only these
                    # lexical false positives and keep other legacy sentinels
                    # unless dedicated replacement coverage already exists.
                    continue
        legacy_sentinels.append(sentinel)

    combined = [
        *detect_python_file_write_path_sentinels(diff),
        *detect_python_dynamic_exec_sentinels(diff),
        *detect_github_actions_yaml_sentinels(diff),
        *legacy_sentinels,
    ]
    deduped: list[hardened.RiskSentinel] = []
    seen: set[tuple[str, int, str]] = set()
    for sentinel in combined:
        key = (sentinel.path, sentinel.line, sentinel.label)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(sentinel)
    return hardened.select_risk_sentinels(deduped, max_anchors)


hardened.detect_risk_sentinels = detect_risk_sentinels


def python_line_imports_urllib_urlopen_alias(text: str) -> bool:
    module = python_parse_diff_line(text)
    if module is None:
        return bool(re.search(r"^\s*from\s+urllib\.request\s+import\s+.*\burlopen\b", text))
    for node in module.body:
        if isinstance(node, ast.ImportFrom) and node.module == "urllib.request":
            return any(alias.name == "urlopen" for alias in node.names)
    return False


def python_shadowed_name_roots(module: ast.AST) -> set[str]:
    roots: set[str] = set()

    def collect_target(node: ast.AST) -> None:
        if isinstance(node, ast.Name):
            roots.add(node.id)
        elif isinstance(node, ast.Attribute):
            collect_target(node.value)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for item in node.elts:
                collect_target(item)
        elif isinstance(node, ast.Starred):
            collect_target(node.value)

    def collect_arguments(node: ast.arguments) -> None:
        for argument in (
            *node.posonlyargs,
            *node.args,
            *node.kwonlyargs,
        ):
            roots.add(argument.arg)
        if node.vararg is not None:
            roots.add(node.vararg.arg)
        if node.kwarg is not None:
            roots.add(node.kwarg.arg)

    class _ModuleScopeShadowVisitor(ast.NodeVisitor):
        def visit_Import(self, node: ast.Import) -> None:
            for alias in node.names:
                imported_name = alias.asname or alias.name.rsplit(".", 1)[-1]
                if alias.name not in {"urllib", "urllib.request"}:
                    roots.add(imported_name)

        def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
            for alias in node.names:
                imported_name = alias.asname or alias.name
                if not (
                    node.module == "urllib.request"
                    and alias.name == "urlopen"
                ) and not (
                    node.module == "urllib"
                    and alias.name == "request"
                ):
                    roots.add(imported_name)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            roots.add(node.name)
            collect_arguments(node.args)
            for statement in node.body:
                self.visit(statement)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            roots.add(node.name)
            collect_arguments(node.args)
            for statement in node.body:
                self.visit(statement)

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

        def visit_Lambda(self, node: ast.Lambda) -> None:
            collect_arguments(node.args)
            self.visit(node.body)

        def _visit_comprehension_generators(self, generators: list[ast.comprehension]) -> None:
            for generator in generators:
                collect_target(generator.target)
                self.visit(generator.iter)
                for if_clause in generator.ifs:
                    self.visit(if_clause)

        def visit_ListComp(self, node: ast.ListComp) -> None:
            self._visit_comprehension_generators(node.generators)
            self.visit(node.elt)

        def visit_SetComp(self, node: ast.SetComp) -> None:
            self._visit_comprehension_generators(node.generators)
            self.visit(node.elt)

        def visit_DictComp(self, node: ast.DictComp) -> None:
            self._visit_comprehension_generators(node.generators)
            self.visit(node.key)
            self.visit(node.value)

        def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
            self._visit_comprehension_generators(node.generators)
            self.visit(node.elt)

    visitor = _ModuleScopeShadowVisitor()
    for statement in getattr(module, "body", []):
        visitor.visit(statement)
    return roots


def python_prune_shadowed_urlopen_call_names(call_names: set[str], shadowed_roots: set[str]) -> set[str]:
    if not shadowed_roots:
        return call_names
    return {
        call_name
        for call_name in call_names
        if call_name.split(".", 1)[0] not in shadowed_roots
    }


def python_urllib_urlopen_call_names(text: str) -> set[str]:
    call_names: set[str] = set()
    module = python_parse_diff_line(text)
    if module is None:
        if python_line_imports_urllib_urlopen_alias(text):
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
    return python_prune_shadowed_urlopen_call_names(
        call_names,
        python_shadowed_name_roots(module),
    )


def python_diff_urllib_urlopen_call_names(diff: str) -> dict[str, set[str]]:
    sources_by_path: dict[str, list[str]] = {}
    for diff_line in iter_python_diff_lines_with_context(diff):
        if Path(diff_line.path).suffix.lower() == ".py":
            sources_by_path.setdefault(diff_line.path, []).append(diff_line.text)
    call_names_by_path: dict[str, set[str]] = {}
    for path, lines in sources_by_path.items():
        call_names = python_urllib_urlopen_call_names("\n".join(lines))
        call_names.update(PYTHON_URLLIB_URLOPEN_CALL_CONTEXT.get(path, set()))
        call_names_by_path[path] = call_names
    return call_names_by_path


def python_diff_statement_text_for_anchor(diff: str, path: str, line: int, fallback_text: str) -> str:
    matching_lines = [diff_line for diff_line in iter_python_diff_lines_with_context(diff) if diff_line.path == path]
    for index, diff_line in enumerate(matching_lines):
        if diff_line.line != line:
            continue
        statement_lines = [diff_line.text]
        statement = diff_line.text
        if python_statement_is_complete(statement):
            return statement
        for next_line in matching_lines[index + 1:]:
            if next_line.hunk != diff_line.hunk:
                break
            statement_lines.append(next_line.text)
            statement = "\n".join(statement_lines)
            if python_statement_is_complete(statement) or len(statement_lines) >= 12:
                return statement
        return statement
    return fallback_text


def python_line_is_known_urllib_urlopen(
    text: str,
    allow_imported_alias: bool = False,
    known_call_names: set[str] | None = None,
) -> bool:
    call_names = set(known_call_names or ())
    if allow_imported_alias:
        call_names.add("urlopen")
    if not call_names:
        return False
    module = python_parse_diff_line(text)
    if module is not None:
        call_names = python_prune_shadowed_urlopen_call_names(
            call_names,
            python_shadowed_name_roots(module),
        )
        if not call_names:
            return False
        for node in ast.walk(module):
            if isinstance(node, ast.Call) and python_call_name(node.func) in call_names:
                return True
        return False
    pattern = r"\b(?:" + "|".join(re.escape(name) for name in sorted(call_names, key=len, reverse=True)) + r")\s*\("
    return bool(re.search(pattern, text))
