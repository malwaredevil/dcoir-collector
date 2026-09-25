def build_python_path_alias_context(gh: Any, pr: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, set[str]]:
    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    if not head_sha:
        return {}
    path_alias_context: dict[str, set[str]] = {}
    for item in files:
        path = str(item.get("filename", "")).strip()
        status = str(item.get("status", "")).strip()
        if not path or status in {"removed", "deleted"} or Path(path).suffix.lower() != ".py":
            continue
        try:
            aliases = python_path_constructor_aliases(fetch_pr_file_text(gh, path, head_sha))
        except Exception:
            continue
        if aliases:
            path_alias_context[path] = aliases
    return path_alias_context


def build_python_os_alias_context(gh: Any, pr: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, set[str]]:
    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    if not head_sha:
        return {}
    os_alias_context: dict[str, set[str]] = {}
    for item in files:
        path = str(item.get("filename", "")).strip()
        status = str(item.get("status", "")).strip()
        if not path or status in {"removed", "deleted"} or Path(path).suffix.lower() != ".py":
            continue
        try:
            aliases = python_os_module_aliases(fetch_pr_file_text(gh, path, head_sha))
        except Exception:
            continue
        if aliases:
            os_alias_context[path] = aliases
    return os_alias_context


def build_python_urllib_urlopen_call_context(gh: Any, pr: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, set[str]]:
    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    if not head_sha:
        return {}
    urlopen_call_context: dict[str, set[str]] = {}
    for item in files:
        path = str(item.get("filename", "")).strip()
        status = str(item.get("status", "")).strip()
        if not path or status in {"removed", "deleted"} or Path(path).suffix.lower() != ".py":
            continue
        try:
            call_names = python_urllib_urlopen_call_names(fetch_pr_file_text(gh, path, head_sha))
        except Exception:
            continue
        if call_names:
            urlopen_call_context[path] = call_names
    return urlopen_call_context


def build_python_shadowed_name_context(gh: Any, pr: dict[str, Any], files: list[dict[str, Any]]) -> dict[str, set[str]]:
    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    if not head_sha:
        return {}
    shadowed_name_context: dict[str, set[str]] = {}
    for item in files:
        path = str(item.get("filename", "")).strip()
        status = str(item.get("status", "")).strip()
        if not path or status in {"removed", "deleted"} or Path(path).suffix.lower() != ".py":
            continue
        try:
            module = ast.parse(fetch_pr_file_text(gh, path, head_sha))
        except (SyntaxError, ValueError, TypeError):
            continue
        shadowed_names = python_shadowed_name_roots(module)
        if shadowed_names:
            shadowed_name_context[path] = shadowed_names
    return shadowed_name_context


def python_scoped_shadowed_name_roots_by_line(source: str) -> dict[int, set[str]]:
    module = ast.parse(source)
    by_line: dict[int, set[str]] = {}
    scope_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)

    def collect_scope_bindings(node: ast.AST) -> tuple[set[str], set[str], set[str]]:
        roots: set[str] = set()
        globals_declared: set[str] = set()
        trusted_roots: set[str] = set()

        def collect_target(target: ast.AST) -> None:
            if isinstance(target, ast.Name):
                roots.add(target.id)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for item in target.elts:
                    collect_target(item)
            elif isinstance(target, ast.Starred):
                collect_target(target.value)

        if isinstance(node, scope_types):
            args = node.args
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs):
                roots.add(arg.arg)
            if args.vararg is not None:
                roots.add(args.vararg.arg)
            if args.kwarg is not None:
                roots.add(args.kwarg.arg)

        class Visitor(ast.NodeVisitor):
            def visit_Global(self, item: ast.Global) -> None:
                globals_declared.update(item.names)

            def visit_Nonlocal(self, _item: ast.Nonlocal) -> None:
                # Nonlocal bindings intentionally keep the enclosing scope state.
                return

            def visit_FunctionDef(self, item: ast.FunctionDef) -> None:
                if item is not node:
                    roots.add(item.name)
                    return
                for stmt in item.body:
                    self.visit(stmt)

            def visit_AsyncFunctionDef(self, item: ast.AsyncFunctionDef) -> None:
                if item is not node:
                    roots.add(item.name)
                    return
                for stmt in item.body:
                    self.visit(stmt)

            def visit_ClassDef(self, item: ast.ClassDef) -> None:
                roots.add(item.name)

            def visit_Lambda(self, item: ast.Lambda) -> None:
                if item is node:
                    self.visit(item.body)

            def visit_Import(self, item: ast.Import) -> None:
                for alias in item.names:
                    name = alias.asname or alias.name.rsplit('.', 1)[-1]
                    if alias.name in {'urllib', 'urllib.request'}:
                        trusted_roots.add(name)
                    else:
                        roots.add(name)

            def visit_ImportFrom(self, item: ast.ImportFrom) -> None:
                for alias in item.names:
                    name = alias.asname or alias.name
                    trusted = (item.module == 'urllib.request' and alias.name == 'urlopen') or (
                        item.module == 'urllib' and alias.name == 'request'
                    )
                    if trusted:
                        trusted_roots.add(name)
                    else:
                        roots.add(name)

            def visit_Assign(self, item: ast.Assign) -> None:
                for target in item.targets:
                    collect_target(target)
                self.visit(item.value)

            def visit_AnnAssign(self, item: ast.AnnAssign) -> None:
                collect_target(item.target)
                if item.value is not None:
                    self.visit(item.value)

            def visit_AugAssign(self, item: ast.AugAssign) -> None:
                collect_target(item.target)
                self.visit(item.value)

            def visit_NamedExpr(self, item: ast.NamedExpr) -> None:
                collect_target(item.target)
                self.visit(item.value)

            def visit_For(self, item: ast.For) -> None:
                collect_target(item.target)
                self.generic_visit(item)

            visit_AsyncFor = visit_For

            def visit_With(self, item: ast.With) -> None:
                for entry in item.items:
                    if entry.optional_vars is not None:
                        collect_target(entry.optional_vars)
                self.generic_visit(item)

            visit_AsyncWith = visit_With

            def visit_ExceptHandler(self, item: ast.ExceptHandler) -> None:
                if isinstance(item.name, str):
                    roots.add(item.name)
                self.generic_visit(item)

        Visitor().visit(node)
        roots.difference_update(globals_declared)
        return roots, globals_declared, trusted_roots

    def iter_nested_scopes(node: ast.AST):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, scope_types):
                yield child
                continue
            yield from iter_nested_scopes(child)

    def walk_scope(node: ast.AST, inherited: set[str]) -> None:
        roots, globals_declared, trusted_roots = collect_scope_bindings(node)
        active = set(inherited)
        active.difference_update(globals_declared)
        active.difference_update(trusted_roots)
        active.update(roots)
        start = int(getattr(node, 'lineno', 0) or 0)
        end = int(getattr(node, 'end_lineno', start) or start)
        for line in range(start, end + 1):
            # The innermost lexical scope owns each mapped line. Replacing the
            # enclosing scope state lets local trusted imports and `global`
            # declarations clear inherited shadowing instead of unioning it back.
            by_line[line] = set(active)
        for child in iter_nested_scopes(node):
            walk_scope(child, active)

    for scope in iter_nested_scopes(module):
        walk_scope(scope, set())
    return by_line


def build_python_scoped_shadowed_name_context(
    gh: Any, pr: dict[str, Any], files: list[dict[str, Any]]
) -> dict[str, dict[int, set[str]]]:
    head_sha = str(pr.get('head', {}).get('sha', '') or '')
    if not head_sha:
        return {}
    context: dict[str, dict[int, set[str]]] = {}
    for item in files:
        path = str(item.get('filename', '')).strip()
        status = str(item.get('status', '')).strip()
        if not path or status in {'removed', 'deleted'} or Path(path).suffix.lower() != '.py':
            continue
        try:
            by_line = python_scoped_shadowed_name_roots_by_line(fetch_pr_file_text(gh, path, head_sha))
        except (SyntaxError, ValueError, TypeError):
            continue
        if by_line:
            context[path] = by_line
    return context

def deep_context_priority(item: dict[str, Any]) -> tuple[int, int, int, str]:
    """Prefer substantive source before derived/generated evidence under the deep-context budget."""
    path = str(item.get("filename", "") or "").replace("\\", "/")
    normalized = path.lower()
    derived = int(
        "/generated/" in normalized
        or normalized in {
            ".github/github_actions/workflow_inventory.json",
            ".github/github_actions/workflow_inventory.md",
        }
    )
    family, negative_changes, path_key = per_file_priority(item, "")
    return derived, family, negative_changes, path_key


def build_deep_context_block(gh: Any, pr: dict[str, Any], files: list[dict[str, Any]], config: Any, review_mode: str) -> tuple[str, str]:
    if review_mode == "diff":
        return "", "diff-focused review; no full changed-file context requested"
    head_sha = str(pr.get("head", {}).get("sha", "") or "")
    if not head_sha:
        return "", "deep context requested but PR head SHA was unavailable"

    max_files = max(0, int(getattr(config, "deep_review_max_files", 8)))
    max_file_chars = max(0, int(getattr(config, "deep_review_max_file_chars", 12000)))
    max_total_chars = max(0, int(getattr(config, "deep_review_max_total_chars", 24000)))
    lines = [
        "Deep changed-file context:",
        f"Mode: {review_mode}.",
        "Use this full changed-file context to reason about whole-file behavior and downstream effects, while anchoring actionable findings to changed lines when practical.",
    ]
    included: list[str] = []
    omitted: list[str] = []
    remaining = max_total_chars

    for item in sorted(files, key=deep_context_priority):
        if len(included) >= max_files:
            break
        path = str(item.get("filename", "")).strip()
        status = str(item.get("status", "")).strip()
        if not path:
            continue
        if status in {"removed", "deleted"}:
            omitted.append(f"{path} (deleted)")
            continue
        try:
            text = base.sanitize_text(fetch_pr_file_text(gh, path, head_sha), config)
        except UnicodeDecodeError:
            omitted.append(f"{path} (not utf-8 text)")
            continue
        except Exception as exc:
            omitted.append(f"{path} ({str(exc)[:120]})")
            continue
        truncated = len(text) > max_file_chars
        snippet = text[:max_file_chars]
        if truncated:
            snippet = f"{snippet}\n\n[full-file context truncated for this file]"
        block = f"### {path}\nStatus: {status}; head ref: {head_sha[:12]}\n~~~{language_hint(path)}\n{snippet}\n~~~"
        if len(block) > remaining:
            if not included and remaining > DEEP_CONTEXT_MIN_PARTIAL_CHARS + len(DEEP_CONTEXT_BUDGET_EXHAUSTED_SUFFIX):
                partial = block[: remaining - len(DEEP_CONTEXT_BUDGET_EXHAUSTED_SUFFIX)].rstrip()
                fence_suffix = "\n~~~" if partial.count("~~~") % 2 == 1 else ""
                block = f"{partial}{fence_suffix}\n\n[deep context budget exhausted]"
            else:
                omitted.append(f"{path} (deep context budget)")
                continue
        lines.append(block)
        included.append(f"{path}{' (truncated)' if truncated else ''}")
        remaining -= len(block)
        if remaining <= DEEP_CONTEXT_MIN_PARTIAL_CHARS:
            # Keep a floor for useful context; below this, the next block would
            # usually be a tiny fragment rather than actionable file context.
            break

    if not included:
        return "", f"{review_mode}; no changed-file context included; omitted: {', '.join(omitted) or 'none'}"
    summary = f"{review_mode}; included {len(included)} file context block(s): {', '.join(included[:6])}"
    if len(included) > 6:
        summary += f", and {len(included) - 6} more"
    if omitted:
        summary += f"; omitted {len(omitted)}: {', '.join(omitted[:4])}"
    return "\n\n".join(lines), summary


def truncate_with_balanced_fences(text: str, max_chars: int, marker: str) -> str:
    if len(text) <= max_chars:
        return text
    if max_chars <= len(marker):
        return marker[:max_chars]
    fence_close = "\n~~~"
    partial_limit = max(0, max_chars - len(marker))
    partial = text[:partial_limit].rstrip()
    if partial.count("~~~") % 2 == 1:
        partial_limit = max(0, max_chars - len(marker) - len(fence_close))
        partial = text[:partial_limit].rstrip()
        if partial.count("~~~") % 2 == 1:
            partial = f"{partial}{fence_close}"
    return f"{partial}{marker}"
