def detect_python_file_write_path_sentinels(diff: str) -> list[hardened.RiskSentinel]:
    sentinels: list[hardened.RiskSentinel] = []
    assigned_paths: dict[str, list[PythonTrackedPath]] = {}
    assigned_int_bindings: dict[str, list[tuple[ast.AST | None, int]]] = {}
    conditional_block_indents: list[int] = []
    scope_stack: list[PythonScope] = []
    next_scope_id = 0
    path_constructor_names = set(DEFAULT_PYTHON_PATH_CONSTRUCTORS)
    os_module_names = set(DEFAULT_PYTHON_OS_MODULES)
    current_path = ""
    current_hunk = 0
    current_alias_path = ""
    pending_path_assignment: list[PythonDiffLine] = []
    pending_write_statement: list[PythonDiffLine] = []

    def flush_pending_path_assignment() -> None:
        nonlocal pending_path_assignment
        if not pending_path_assignment:
            return
        statement = "\n".join(line.text for line in pending_path_assignment)
        dynamic_target = python_dynamic_path_target(statement, path_constructor_names, os_module_names)
        if dynamic_target:
            push_assigned_path(
                assigned_paths,
                dynamic_target,
                pending_path_assignment[0],
                current_python_scope_id(scope_stack),
            )
        pending_path_assignment = []

    def prune_assigned_int_bindings(active_scope_ids: set[int]) -> None:
        for target, bindings in list(assigned_int_bindings.items()):
            while bindings and bindings[-1][1] not in active_scope_ids:
                bindings.pop()
            if not bindings:
                del assigned_int_bindings[target]

    def pending_write_statement_anchor() -> PythonDiffLine:
        return next(
            (line for line in pending_write_statement if line.is_added),
            pending_write_statement[0],
        )

    def flush_pending_write_statement(overflowed: bool = False) -> None:
        nonlocal pending_write_statement
        if not pending_write_statement:
            return
        has_added_line = any(line.is_added for line in pending_write_statement)
        statement = "\n".join(line.text for line in pending_write_statement)
        current_int_bindings = visible_int_bindings()
        if has_added_line and python_statement_is_complete(statement):
            if python_direct_dynamic_file_write(
                statement,
                path_constructor_names,
                os_module_names,
                current_int_bindings,
            ):
                append_file_write_sentinel(sentinels, pending_write_statement_anchor())
        elif has_added_line and overflowed and python_line_has_explicit_file_write_call(
            statement,
            path_constructor_names,
            os_module_names,
            current_int_bindings,
        ):
            append_file_write_sentinel(sentinels, pending_write_statement_anchor())
        pending_write_statement = []

    def push_assigned_int_binding(target: str, value: ast.AST | None, scope_id: int) -> None:
        bindings = assigned_int_bindings.setdefault(target, [])
        while bindings and bindings[-1][1] == scope_id:
            bindings.pop()
        bindings.append((value, scope_id))

    def visible_int_bindings() -> dict[str, ast.AST | int]:
        visible: dict[str, ast.AST | int] = {}
        for target, bindings in assigned_int_bindings.items():
            if bindings and bindings[-1][0] is not None:
                visible[target] = bindings[-1][0]
        return visible

    def prune_conditional_blocks(indent: int | None) -> None:
        if indent is None:
            return
        while conditional_block_indents and indent <= conditional_block_indents[-1]:
            conditional_block_indents.pop()

    def line_opens_conditional_block(text: str) -> bool:
        stripped = text.lstrip()
        return bool(
            stripped.rstrip().endswith(":")
            and re.match(r"^(?:if|elif|else|for|while|try|except|finally|match|case)\b", stripped)
        )

    def inside_conditional_block(indent: int | None) -> bool:
        return indent is not None and any(indent > block_indent for block_indent in conditional_block_indents)

    def pending_write_statement_accepts_line(indent: int | None, text: str) -> bool:
        if not pending_write_statement:
            return False
        anchor_indent = python_code_line_indent(pending_write_statement[0].text)
        if indent is None or anchor_indent is None:
            return True
        if indent > anchor_indent:
            return True
        return indent == anchor_indent and bool(re.match(r"^[)\]}]", text.strip()))

    for diff_line in iter_python_diff_lines_with_context(diff):
        if is_python_test_file_path(diff_line.path):
            continue
        if diff_line.path != current_alias_path:
            path_constructor_names = set(DEFAULT_PYTHON_PATH_CONSTRUCTORS)
            path_constructor_names.update(PYTHON_PATH_ALIAS_CONTEXT.get(diff_line.path, set()))
            os_module_names = set(DEFAULT_PYTHON_OS_MODULES)
            os_module_names.update(PYTHON_OS_ALIAS_CONTEXT.get(diff_line.path, set()))
            current_alias_path = diff_line.path
        if diff_line.path != current_path:
            flush_pending_path_assignment()
            flush_pending_write_statement()
            current_path = diff_line.path
            current_hunk = diff_line.hunk
            assigned_paths.clear()
            assigned_int_bindings.clear()
            conditional_block_indents.clear()
            scope_stack.clear()
            next_scope_id = seed_python_hunk_scope(scope_stack, diff_line.hunk_context, next_scope_id)
        elif diff_line.hunk != current_hunk:
            flush_pending_path_assignment()
            flush_pending_write_statement()
            conditional_block_indents.clear()
            if not trim_python_scope_stack_to_hunk(scope_stack, diff_line.hunk_context):
                assigned_paths.clear()
                assigned_int_bindings.clear()
                scope_stack.clear()
                next_scope_id = seed_python_hunk_scope(scope_stack, diff_line.hunk_context, next_scope_id)
            current_hunk = diff_line.hunk
        diff_line_indent = python_code_line_indent(diff_line.text)
        prune_conditional_blocks(diff_line_indent)
        pop_python_scopes_for_indent(scope_stack, diff_line_indent)
        active_scope_ids = active_python_scope_ids(scope_stack)
        prune_assigned_paths_for_active_scopes(assigned_paths, active_scope_ids)
        prune_assigned_int_bindings(active_scope_ids)
        if diff_line.inside_multiline_string:
            if pending_write_statement:
                pending_write_statement.append(diff_line)
                if python_statement_is_complete("\n".join(line.text for line in pending_write_statement)):
                    flush_pending_write_statement()
                elif len(pending_write_statement) >= 12:
                    flush_pending_write_statement(overflowed=True)
            continue
        if hardened.is_comment_only_added_line(diff_line.path, diff_line.text):
            if pending_write_statement:
                pending_write_statement.append(diff_line)
                if python_statement_is_complete("\n".join(line.text for line in pending_write_statement)):
                    flush_pending_write_statement()
                elif len(pending_write_statement) >= 12:
                    flush_pending_write_statement(overflowed=True)
            continue
        if pending_write_statement:
            if not pending_write_statement_accepts_line(diff_line_indent, diff_line.text):
                flush_pending_write_statement(overflowed=True)
            else:
                pending_write_statement.append(diff_line)
                if python_statement_is_complete("\n".join(line.text for line in pending_write_statement)):
                    flush_pending_write_statement()
                elif len(pending_write_statement) >= 12:
                    flush_pending_write_statement(overflowed=True)
                continue
        path_constructor_names.update(python_path_constructor_aliases(diff_line.text))
        os_module_names.update(python_os_module_aliases(diff_line.text))
        if pending_path_assignment:
            pending_path_assignment.append(diff_line)
            statement = "\n".join(line.text for line in pending_path_assignment)
            if python_statement_is_complete(statement):
                flush_pending_path_assignment()
            continue
        if python_is_scope_boundary(diff_line.text):
            next_scope_id += 1
            scope_indent = diff_line_indent or 0
            scope_stack.append(PythonScope(scope_indent, python_scope_key(diff_line.text), next_scope_id))
            shadowed_names = python_scope_boundary_shadowed_names(diff_line.text)
            remove_shadowed_assigned_paths(
                assigned_paths,
                shadowed_names,
                diff_line,
                current_python_scope_id(scope_stack),
            )
            for shadowed_name in shadowed_names:
                push_assigned_int_binding(shadowed_name, None, current_python_scope_id(scope_stack))
        current_scope_id = current_python_scope_id(scope_stack)
        dynamic_target = python_dynamic_path_target(diff_line.text, path_constructor_names, os_module_names)
        if dynamic_target:
            push_assigned_path(assigned_paths, dynamic_target, diff_line, current_scope_id)
            if line_opens_conditional_block(diff_line.text):
                conditional_block_indents.append(diff_line_indent or 0)
            continue
        augmented_dynamic_target = python_augmented_dynamic_path_target(diff_line.text, path_constructor_names, os_module_names)
        if augmented_dynamic_target:
            push_assigned_path(assigned_paths, augmented_dynamic_target, diff_line, current_scope_id)
            if line_opens_conditional_block(diff_line.text):
                conditional_block_indents.append(diff_line_indent or 0)
            continue
        if python_path_assignment_start(diff_line.text, path_constructor_names, os_module_names) and not python_statement_is_complete(diff_line.text):
            pending_path_assignment = [diff_line]
            if line_opens_conditional_block(diff_line.text):
                conditional_block_indents.append(diff_line_indent or 0)
            continue
        simple_assignment = python_simple_assignment(diff_line.text)
        if simple_assignment:
            assigned_target, assigned_value = simple_assignment
            push_assigned_int_binding(
                assigned_target,
                None if inside_conditional_block(diff_line_indent) else assigned_value,
                current_scope_id,
            )
        augmented_targets = python_augmented_assignment_targets(diff_line.text)
        assignment_indent = diff_line_indent or 0
        for assigned_target in python_assignment_target_names(diff_line.text):
            keep_exact_target = current_assigned_path(assigned_paths, assigned_target) is not None and (
                assigned_target in augmented_targets
                or python_assignment_value_references_target(
                    diff_line.text,
                    assigned_target,
                )
            )
            if keep_exact_target:
                assignment = current_assigned_path(assigned_paths, assigned_target)
                if diff_line.is_added and assignment is not None and not assignment.is_added:
                    push_assigned_path(assigned_paths, assigned_target, diff_line, current_scope_id)
            else:
                clear_assigned_path_in_scope(assigned_paths, assigned_target, assignment_indent, current_scope_id)
            if not simple_assignment or simple_assignment[0] != assigned_target:
                push_assigned_int_binding(assigned_target, None, current_scope_id)
        current_int_bindings = visible_int_bindings()
        write_target = python_file_write_target(
            diff_line.text,
            path_constructor_names,
            os_module_names,
            current_int_bindings,
        )
        if not write_target:
            write_target = python_wrapped_file_write_target(
                diff_line.text,
                path_constructor_names,
                os_module_names,
                current_int_bindings,
            )
        if not write_target:
            if diff_line.is_added and python_direct_dynamic_file_write(
                diff_line.text,
                path_constructor_names,
                os_module_names,
                current_int_bindings,
            ):
                append_file_write_sentinel(sentinels, diff_line)
            elif (
                re.search(r"\bopen\s*\(", diff_line.text)
                and not python_statement_is_complete(diff_line.text)
            ):
                pending_write_statement = [diff_line]
            if line_opens_conditional_block(diff_line.text):
                conditional_block_indents.append(diff_line_indent or 0)
            continue
        assignment = current_assigned_path(assigned_paths, write_target)
        if not assignment:
            if diff_line.is_added and python_direct_dynamic_file_write(
                diff_line.text,
                path_constructor_names,
                os_module_names,
                current_int_bindings,
            ):
                append_file_write_sentinel(sentinels, diff_line)
            continue
        if not assignment.is_added and not diff_line.is_added:
            if line_opens_conditional_block(diff_line.text):
                conditional_block_indents.append(diff_line_indent or 0)
            continue
        anchor = assignment if assignment.is_added else diff_line
        append_file_write_sentinel(sentinels, anchor)
        if line_opens_conditional_block(diff_line.text):
            conditional_block_indents.append(diff_line_indent or 0)
    flush_pending_path_assignment()
    flush_pending_write_statement()
    return sentinels
