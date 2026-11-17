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


def iter_uses_references(path: Path) -> list[tuple[int, str]]:
    """Find executable (key line, reference) pairs, rejecting ambiguity."""
    raw = path.read_bytes()
    if len(raw) > MAX_YAML_BYTES:
        raise _error(path, None, "YAML input exceeds audit byte limit")
    try:
        text = raw.decode("utf-8")
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
        loader.dispose()

    if not isinstance(root, MappingNode):
        raise _error(path, root, "expected YAML mapping root")
    _bounded_graph(path, root)
    aliases = loader.alias_lines
    executable_seen: set[int] = set()
    references: list[tuple[int, str]] = []

    def fields(
        node: Node, name: str, *, parent_line: int = 1
    ) -> dict[str, tuple[ScalarNode, Node]]:
        if not isinstance(node, MappingNode) or node.tag != MAPPING_TAG:
            raise _error(path, node, f"{name} must be a mapping")
        if id(node) in executable_seen or (
            id(node) in aliases and node.start_mark.line + 1 < parent_line
        ):
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

    def add_reference(field: tuple[ScalarNode, Node]) -> None:
        key, value = field
        references.append((key.start_mark.line + 1, scalar(value, key, "uses value")))

    def steps(field: tuple[ScalarNode, Node], name: str) -> None:
        key, seq = field
        if not isinstance(seq, SequenceNode) or seq.tag != SEQUENCE_TAG:
            raise _error(path, key, f"{name} steps must be a sequence")
        if id(seq) in aliases and seq.start_mark.line + 1 < key.start_mark.line + 1:
            raise _error(
                path, seq, f"unsupported YAML alias in executable {name} steps",
                line=aliases[id(seq)][0],
            )
        for step in seq.value:
            if not isinstance(step, MappingNode):
                raise _error(path, step, f"{name} step must be a mapping")
            mapping = fields(
                step, f"{name} step", parent_line=seq.start_mark.line + 1
            )
            if "uses" in mapping:
                add_reference(mapping["uses"])

    top = fields(root, "root")
    if "jobs" in top:
        jobs_key, jobs_node = top["jobs"]
        jobs = fields(jobs_node, "jobs", parent_line=jobs_key.start_mark.line + 1)
        for job_id, (job_key, job_node) in jobs.items():
            job = fields(
                job_node, f"job {job_id}", parent_line=job_key.start_mark.line + 1
            )
            if "uses" in job:
                add_reference(job["uses"])
            if "steps" in job:
                steps(job["steps"], f"job {job_id}")
    if "runs" in top:
        runs_key, runs_node = top["runs"]
        runs = fields(runs_node, "runs", parent_line=runs_key.start_mark.line + 1)
        if "using" in runs:
            using_key, using_node = runs["using"]
            if not isinstance(using_node, ScalarNode) or using_node.tag != STRING_TAG:
                raise _error(path, using_key, "runs.using must be a scalar")
            if using_node.value.lower() == "composite" and "steps" in runs:
                steps(runs["steps"], "composite")
    return sorted(references, key=lambda pair: pair[0])
