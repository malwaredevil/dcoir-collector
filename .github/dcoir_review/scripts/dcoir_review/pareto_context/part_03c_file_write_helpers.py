def _prune_assigned_int_bindings(
    assigned_int_bindings: dict[str, list[tuple[ast.AST | None, int]]],
    active_scope_ids: set[int],
) -> None:
    for target, bindings in list(assigned_int_bindings.items()):
        while bindings and bindings[-1][1] not in active_scope_ids:
            bindings.pop()
        if not bindings:
            del assigned_int_bindings[target]


def _line_opens_conditional_block(text: str) -> bool:
    stripped = text.lstrip()
    return bool(
        stripped.rstrip().endswith(":")
        and re.match(r"^(?:if|elif|else|for|while|try|except|finally|match|case)\b", stripped)
    )


def set_python_path_alias_context(path_alias_context: dict[str, set[str]] | None) -> None:
    PYTHON_PATH_ALIAS_CONTEXT.clear()
    PYTHON_PATH_ALIAS_CONTEXT.update({
        path: set(aliases)
        for path, aliases in (path_alias_context or {}).items()
        if aliases
    })


def set_python_os_alias_context(os_alias_context: dict[str, set[str]] | None) -> None:
    PYTHON_OS_ALIAS_CONTEXT.clear()
    PYTHON_OS_ALIAS_CONTEXT.update({
        path: set(aliases)
        for path, aliases in (os_alias_context or {}).items()
        if aliases
    })


def set_python_urllib_urlopen_call_context(
    urlopen_call_context: dict[str, set[str]] | None,
) -> None:
    PYTHON_URLLIB_URLOPEN_CALL_CONTEXT.clear()
    PYTHON_URLLIB_URLOPEN_CALL_CONTEXT.update({
        path: set(call_names)
        for path, call_names in (urlopen_call_context or {}).items()
        if call_names
    })
