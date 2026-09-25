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


def _python_diff_shadowed_name_roots(diff: str) -> dict[str, set[str]]:
    sources_by_path: dict[str, list[str]] = {}
    for path, text in _iter_diff_python_lines_with_context(diff):
        sources_by_path.setdefault(str(path), []).append(text)
    shadowed_names_by_path: dict[str, set[str]] = {}
    for path, lines in sources_by_path.items():
        module = _python_parse_diff_line("\n".join(lines))
        if module is None:
            continue
        shadowed_names = _python_shadowed_name_roots(module)
        if shadowed_names:
            shadowed_names_by_path[path] = shadowed_names
    return shadowed_names_by_path


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
        call_names = _python_prune_shadowed_urlopen_call_names(
            call_names,
            _python_shadowed_name_roots(module),
        )
        if not call_names:
            return False
        return any(
            isinstance(node, ast.Call) and _python_call_name(node.func) in call_names
            for node in ast.walk(module)
        )
    pattern = r"\b(?:" + "|".join(re.escape(name) for name in sorted(call_names, key=len, reverse=True)) + r")\s*\("
    return bool(re.search(pattern, text, re.IGNORECASE))


def _python_is_explicit_file_write(
    text: str,
    path_constructor_names: set[str] | None = None,
    os_module_names: set[str] | None = None,
    shadowed_names: set[str] | None = None,
) -> bool:
    module = _python_parse_diff_line(text)
    if module is None:
        return False
    constructor_names = path_constructor_names or {"Path", "pathlib.Path"}
    os_names = os_module_names or {"os"}
    os_open_names = {f"{name}.open" for name in os_names}
    known_mode_checked = set(PYTHON_KNOWN_READ_MODE_OPEN_CALLS) | os_open_names
    active_shadowed_names = set(shadowed_names or ())
    active_shadowed_names.update(_python_shadowed_name_roots(module))
    for node in ast.walk(module):
        if not isinstance(node, ast.Call):
            continue
        call_name = _python_call_name(node.func)
        if call_name in os_open_names:
            if _python_os_open_uses_write_mode(node, os_names):
                return True
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr == "open":
            value_is_path = _python_is_proven_path_receiver(node.func.value, constructor_names)
            if not value_is_path and call_name not in known_mode_checked:
                return True
            if _python_call_uses_write_mode(node, constructor_names, os_names, active_shadowed_names):
                return True
            continue
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"write_text", "write_bytes"}:
            return True
        if _python_call_uses_write_mode(node, constructor_names, os_names, active_shadowed_names):
            return True
    return False
