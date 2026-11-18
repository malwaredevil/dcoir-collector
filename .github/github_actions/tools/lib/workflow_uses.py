"""YAML-aware discovery of executable GitHub Actions uses references.

Compose PyYAML nodes without constructing Python objects or interpreting
custom YAML tags. Only job calls and workflow/composite steps are in scope.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from yaml.events import AliasEvent
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

MAX_YAML_BYTES = 1_048_576
MAX_YAML_NODES = 50_000
MAX_YAML_DEPTH = 128
STRING_TAG = "tag:yaml.org,2002:str"
MAPPING_TAG = "tag:yaml.org,2002:map"
SEQUENCE_TAG = "tag:yaml.org,2002:seq"


class _AuditLoader(yaml.BaseLoader):
    """Track alias source lines; do not construct arbitrary YAML objects."""

    def __init__(self, stream: str) -> None:
        super().__init__(stream)
        self.alias_lines: dict[int, list[int]] = {}

    def compose_node(self, parent: Node | None, index: object) -> Node:
        if self.check_event(AliasEvent):
            event = self.peek_event()
            aliased = self.anchors.get(event.anchor)
            if aliased is not None:
                self.alias_lines.setdefault(id(aliased), []).append(
                    event.start_mark.line + 1
                )
        return super().compose_node(parent, index)


def _error(
    path: Path, node: Node | None, message: str, *, line: int | None = None
) -> ValueError:
    if line is None:
        line = node.start_mark.line + 1 if node is not None else 1
    return ValueError(f"{path}:{line}: {message}")


def _load_yaml_document(path: Path) -> tuple[Node, dict[int, list[int]]]:
    raw = path.read_bytes()
    if len(raw) > MAX_YAML_BYTES:
        raise _error(path, None, "YAML input exceeds audit byte limit")
    try:
        text = _normalize_inline_comment_tabs(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        line = raw[:exc.start].count(b"\n") + 1
        raise _error(path, None, "invalid UTF-8 YAML input", line=line) from exc
    loader = _AuditLoader(text)
    try:
        try:
            root = loader.get_single_node()
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None) or getattr(
                exc, "context_mark", None
            )
            line = mark.line + 1 if mark is not None else 1
            message = str(exc)
            if "expected a single document" in message:
                raise _error(
                    path, None, "multiple YAML documents are unsupported",
                    line=line,
                ) from exc
            problem = getattr(exc, "problem", None) or message.splitlines()[0]
            raise _error(path, None, f"invalid YAML: {problem}", line=line) from exc
    finally:
        aliases = {node_id: list(lines) for node_id, lines in loader.alias_lines.items()}
        loader.dispose()
    if root is None:
        raise _error(path, None, "expected YAML mapping root")
    return root, aliases


def _contract_mapping_fields(
    path: Path, node: Node, name: str, aliases: dict[int, list[int]]
) -> dict[str, Node]:
    if not isinstance(node, MappingNode) or node.tag != MAPPING_TAG:
        raise _error(path, node, f"{name} must be a mapping")
    if id(node) in aliases:
        raise _error(
            path, node, f"unsupported YAML alias in {name}",
            line=aliases[id(node)][0],
        )
    fields: dict[str, Node] = {}
    for key, value in node.value:
        if not isinstance(key, ScalarNode) or key.tag != STRING_TAG:
            raise _error(path, key, f"unsupported YAML mapping key in {name}")
        if key.value == "<<":
            raise _error(path, key, f"unsupported YAML merge key in {name}")
        if key.value in fields:
            raise _error(path, key, f"duplicate YAML key {key.value} in {name}")
        if id(key) in aliases:
            raise _error(
                path, key, f"unsupported YAML alias in {name}",
                line=aliases[id(key)][0],
            )
        fields[key.value] = value
    return fields


def _bounded_graph(path: Path, root: Node) -> None:
    seen: set[int] = set()
    stack: list[tuple[Node, int]] = [(root, 1)]
    while stack:
        node, depth = stack.pop()
        if depth > MAX_YAML_DEPTH:
            raise _error(path, node, "YAML nesting exceeds audit depth limit")
        if id(node) in seen:
            continue
        seen.add(id(node))
        if len(seen) > MAX_YAML_NODES:
            raise _error(path, node, "YAML node count exceeds audit limit")
        if isinstance(node, MappingNode):
            for key, value in node.value:
                stack.append((key, depth + 1))
                stack.append((value, depth + 1))
        elif isinstance(node, SequenceNode):
            stack.extend((value, depth + 1) for value in node.value)



def _normalize_inline_comment_tabs(text: str) -> str:
    """Allow tab whitespace immediately before a real YAML inline comment.

    Preserve quoted data and reject tabs in non-comment syntax; YAML itself
    remains the parser and supplies the source line numbers.
    """
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        quote: str | None = None
        escaped = False
        index = 0
        while index < len(line):
            char = line[index]
            if quote == '"':
                if char == "\\" and not escaped:
                    escaped = True
                    index += 1
                    continue
                if char == '"' and not escaped:
                    quote = None
                escaped = False
            elif quote == "'":
                if char == "'":
                    if index + 1 < len(line) and line[index + 1] == "'":
                        index += 2
                        continue
                    quote = None
            elif char in {'"', "'"}:
                quote = char
            elif char == "#" and (index == 0 or line[index - 1].isspace()):
                start = index
                while start > 0 and line[start - 1] in " \t":
                    start -= 1
                line = line[:start] + line[start:index].replace("\t", " ") + line[index:]
                break
            index += 1
        lines.append(line)
    return "".join(lines)


def _scan_references(
    path: Path,
) -> tuple[
    list[tuple[int, str]],
    list[tuple[int, str, frozenset[str], frozenset[str]]],
]:
    """Read executable uses and local reusable caller argument names."""
    root, aliases = _load_yaml_document(path)

    if not isinstance(root, MappingNode):
        raise _error(path, root, "expected YAML mapping root")
    _bounded_graph(path, root)
    executable_seen: set[int] = set()
    references: list[tuple[int, str]] = []
    call_bindings: list[tuple[int, str, frozenset[str], frozenset[str]]] = []

    def fields(node: Node, name: str) -> dict[str, tuple[ScalarNode, Node]]:
        if not isinstance(node, MappingNode) or node.tag != MAPPING_TAG:
            raise _error(path, node, f"{name} must be a mapping")
        if id(node) in executable_seen or id(node) in aliases:
            raise _error(
                path, node, f"unsupported YAML alias in executable {name}",
                line=aliases.get(id(node), [node.start_mark.line + 1])[0],
            )
        executable_seen.add(id(node))
        result: dict[str, tuple[ScalarNode, Node]] = {}
        for key, value in node.value:
            if not isinstance(key, ScalarNode) or key.tag != STRING_TAG:
                raise _error(path, key, f"unsupported YAML mapping key in {name}")
            if key.value == "<<":
                raise _error(path, key, f"unsupported YAML merge key in {name}")
            if key.value in result:
                raise _error(path, key, f"duplicate YAML key {key.value} in {name}")
            result[key.value] = (key, value)
        return result

    def scalar(node: Node, key: ScalarNode, name: str) -> str:
        if not isinstance(node, ScalarNode):
            raise _error(path, key, f"{name} must be a scalar string")
        if node.tag != STRING_TAG:
            raise _error(path, key, f"unsupported YAML tag on {name}")
        value = node.value
        if not value.strip():
            raise _error(path, key, f"{name} must be a nonempty scalar")
        if "${{" in value:
            raise _error(path, key, f"dynamic uses reference is unsupported: {value}")
        return value

    def add_reference(field: tuple[ScalarNode, Node]) -> tuple[int, str]:
        key, value = field
        reference = (key.start_mark.line + 1, scalar(value, key, "uses value"))
        references.append(reference)
        return reference

    def binding_names(
        job: dict[str, tuple[ScalarNode, Node]], key: str, job_name: str
    ) -> frozenset[str]:
        if key not in job:
            return frozenset()
        _, node = job[key]
        if key == "secrets" and isinstance(node, ScalarNode):
            if node.tag == STRING_TAG and node.value == "inherit":
                return frozenset()
            raise _error(path, node, f"{job_name} secrets must be a mapping or inherit")
        return frozenset(fields(node, f"{job_name} {key}"))

    def steps(field: tuple[ScalarNode, Node], name: str) -> None:
        key, seq = field
        if not isinstance(seq, SequenceNode) or seq.tag != SEQUENCE_TAG:
            raise _error(path, key, f"{name} steps must be a sequence")
        if id(seq) in aliases:
            raise _error(
                path, seq, f"unsupported YAML alias in executable {name} steps",
                line=aliases[id(seq)][0],
            )
        for step in seq.value:
            if not isinstance(step, MappingNode):
                raise _error(path, step, f"{name} step must be a mapping")
            mapping = fields(step, f"{name} step")
            if "uses" in mapping:
                add_reference(mapping["uses"])

    top = fields(root, "root")
    if "jobs" in top:
        _, jobs_node = top["jobs"]
        jobs = fields(jobs_node, "jobs")
        for job_id, (_, job_node) in jobs.items():
            job = fields(job_node, f"job {job_id}")
            if "uses" in job:
                call_line, call_ref = add_reference(job["uses"])
                if call_ref.startswith("./.github/workflows/"):
                    call_bindings.append((
                        call_line,
                        call_ref,
                        binding_names(job, "with", f"job {job_id}"),
                        binding_names(job, "secrets", f"job {job_id}"),
                    ))
            if "steps" in job:
                steps(job["steps"], f"job {job_id}")
    if "runs" in top:
        _, runs_node = top["runs"]
        runs = fields(runs_node, "runs")
        if "using" in runs:
            using_key, using_node = runs["using"]
            if not isinstance(using_node, ScalarNode) or using_node.tag != STRING_TAG:
                raise _error(path, using_key, "runs.using must be a scalar")
            if using_node.value.lower() == "composite" and "steps" in runs:
                steps(runs["steps"], "composite")
    return (
        sorted(references, key=lambda pair: pair[0]),
        sorted(call_bindings, key=lambda call: call[0]),
    )


def iter_uses_references(path: Path) -> list[tuple[int, str]]:
    """Find executable (key line, reference) pairs, rejecting ambiguity."""
    return _scan_references(path)[0]


def iter_workflow_call_bindings(
    path: Path,
) -> list[tuple[int, str, frozenset[str], frozenset[str]]]:
    """Return local job calls with their YAML-aware with/secrets argument names."""
    return _scan_references(path)[1]


def workflow_call_definition(path: Path) -> tuple[bool, set[str], set[str]]:
    """Read the actual on.workflow_call trigger and declared argument names.

    Quoted and flow-style YAML keys are normalized by BaseLoader. Comment text,
    job descriptions, and unrelated mappings never create workflow_call events.
    """
    root, aliases = _load_yaml_document(path)
    if not isinstance(root, MappingNode):
        raise _error(path, root, "expected YAML mapping root")
    _bounded_graph(path, root)
    top = _contract_mapping_fields(path, root, "root", aliases)
    on_node = top.get("on")
    if on_node is None:
        return False, set(), set()
    if isinstance(on_node, ScalarNode):
        if on_node.tag != STRING_TAG:
            raise _error(path, on_node, "on trigger must be a string")
        return on_node.value == "workflow_call", set(), set()
    if isinstance(on_node, SequenceNode):
        if on_node.tag != SEQUENCE_TAG:
            raise _error(path, on_node, "on triggers must be a sequence")
        found = False
        for event in on_node.value:
            if not isinstance(event, ScalarNode) or event.tag != STRING_TAG:
                raise _error(path, event, "on trigger must be a string")
            if id(event) in aliases:
                raise _error(path, event, "unsupported YAML alias in on triggers")
            if event.value == "workflow_call":
                found = True
        return found, set(), set()
    on_fields = _contract_mapping_fields(path, on_node, "on", aliases)
    call_node = on_fields.get("workflow_call")
    if call_node is None:
        return False, set(), set()
    if isinstance(call_node, ScalarNode):
        if call_node.tag == STRING_TAG and call_node.value == "":
            return True, set(), set()
        raise _error(path, call_node, "on.workflow_call must be a mapping or empty")
    call_fields = _contract_mapping_fields(
        path, call_node, "on.workflow_call", aliases
    )
    inputs_node = call_fields.get("inputs")
    secrets_node = call_fields.get("secrets")
    inputs = (
        set(_contract_mapping_fields(path, inputs_node, "workflow_call inputs", aliases))
        if inputs_node is not None
        else set()
    )
    secrets = (
        set(_contract_mapping_fields(path, secrets_node, "workflow_call secrets", aliases))
        if secrets_node is not None
        else set()
    )
    return True, inputs, secrets


def workflow_call_contract(path: Path) -> tuple[set[str], set[str]]:
    """Return declared workflow_call input and secret names from YAML mappings."""
    _, inputs, secrets = workflow_call_definition(path)
    return inputs, secrets
