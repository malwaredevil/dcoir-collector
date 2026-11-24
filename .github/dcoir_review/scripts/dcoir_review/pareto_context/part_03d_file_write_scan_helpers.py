def python_pending_write_statement_anchor(pending_write_statement: list[PythonDiffLine]) -> PythonDiffLine:
    return next((line for line in pending_write_statement if line.is_added), pending_write_statement[0])

def python_prune_conditional_blocks(conditional_block_indents: list[int], indent: int | None) -> None:
    if indent is None:
        return
    while conditional_block_indents and indent <= conditional_block_indents[-1]:
        conditional_block_indents.pop()

def python_inside_conditional_block(conditional_block_indents: list[int], indent: int | None) -> bool:
    return indent is not None and any(indent > block_indent for block_indent in conditional_block_indents)

def python_pending_write_statement_accepts_line(pending_write_statement: list[PythonDiffLine], indent: int | None, text: str) -> bool:
    if not pending_write_statement:
        return False
    anchor_indent = python_code_line_indent(pending_write_statement[0].text)
    if indent is None or anchor_indent is None:
        return True
    if indent > anchor_indent:
        return True
    return indent == anchor_indent and bool(re.match(r"^[)\]}]", text.strip()))
