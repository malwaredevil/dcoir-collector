#!/usr/bin/env python3
"""Static inventory of the active DCOIR Review runtime patch graph.

This is a migration aid for issue #550. It does not execute patch modules or
change review behavior. The inventory starts from the production entrypoint,
expands connector-safe segment layers, follows DCOIR patch-module imports, and
reports source/mutation surfaces that must be dispositioned before cutover.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dcoir_review.entrypoint import DcoirReviewEntrypoint
from dcoir_review.module_loader import LAYER_SEGMENTS

SCHEMA_VERSION = "dcoir_review_architecture_inventory_v1"
PRODUCTION_PATCH_GROUPS = (
    "patch_module_names",
    "terminal_patch_module_names",
    "post_terminal_patch_module_names",
    "candidate_integrity_patch_module_names",
    "stage_local_patch_module_names",
    "execution_policy_patch_module_names",
    "telemetry_patch_module_names",
    "post_telemetry_patch_module_names",
)
NUMBERED_PATCH_RE = re.compile(
    r"^dcoir_review_required_runtime_patch_v(?P<version>\d+)(?:$|_)"
)
MUTATION_FUNCTION_PREFIXES = (
    "apply_pareto_context_module",
    "_patch",
    "patch_",
    "_install",
    "install_",
    "_replace",
    "replace_",
    "_wrap",
    "wrap_",
)
PATCH_MODULE_PREFIXES = (
    "dcoir_review_runtime_patch",
    "dcoir_review_strict_runtime_patch",
    "dcoir_review_required_runtime_patch",
)


def production_patch_groups() -> dict[str, tuple[str, ...]]:
    """Return the ordered patch groups exactly as the production entrypoint sees them."""
    entrypoint = DcoirReviewEntrypoint()
    return {
        group_name: tuple(getattr(entrypoint, group_name))
        for group_name in PRODUCTION_PATCH_GROUPS
    }


def production_patch_sequence() -> tuple[str, ...]:
    """Flatten production patch groups without changing their declared order."""
    return tuple(
        module_name
        for module_names in production_patch_groups().values()
        for module_name in module_names
    )


def _is_patch_module(module_name: str) -> bool:
    return module_name.startswith(PATCH_MODULE_PREFIXES)


def _source_paths_for_module(module_name: str) -> tuple[Path, ...]:
    """Resolve a wrapper/module and any connector-safe segment sources it owns."""
    paths: list[Path] = []
    module_path = Path(*module_name.split("."))
    wrapper = (SCRIPTS / module_path).with_suffix(".py")
    if wrapper.is_file():
        paths.append(wrapper)
    for relative in LAYER_SEGMENTS.get(module_name, ()):
        segment = SCRIPTS / "dcoir_review" / relative
        if segment.is_file():
            paths.append(segment)
    return tuple(dict.fromkeys(paths))


def _expr_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _expr_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Subscript):
        prefix = _expr_name(node.value)
        return f"{prefix}[...]" if prefix else "[...]"
    return ""


def _assignment_targets(node: ast.AST) -> Iterable[ast.AST]:
    if isinstance(node, ast.Assign):
        yield from node.targets
    elif isinstance(node, ast.AnnAssign):
        yield node.target
    elif isinstance(node, ast.AugAssign):
        yield node.target


def _imported_patch_modules(tree: ast.AST) -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_patch_module(alias.name):
                    imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module_name = str(node.module or "")
            if _is_patch_module(module_name):
                imported.add(module_name)
    return imported


def _mutation_surfaces(tree: ast.AST) -> set[str]:
    """Collect conservative attribute-replacement candidates in patch/install functions."""
    mutations: set[str] = set()
    for function in ast.walk(tree):
        if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not function.name.startswith(MUTATION_FUNCTION_PREFIXES):
            continue
        for node in ast.walk(function):
            for target in _assignment_targets(node):
                name = _expr_name(target)
                if "." in name and not name.startswith("self."):
                    mutations.add(name)
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "setattr":
                continue
            if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
                continue
            attribute = node.args[1].value
            if not isinstance(attribute, str) or not attribute:
                continue
            owner = _expr_name(node.args[0]) or "<dynamic>"
            mutations.add(f"setattr:{owner}.{attribute}")
    return mutations


def _parse_source(path: Path) -> tuple[set[str], set[str]]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    return _imported_patch_modules(tree), _mutation_surfaces(tree)


def _numbered_version(module_name: str) -> int | None:
    match = NUMBERED_PATCH_RE.match(module_name)
    return int(match.group("version")) if match is not None else None


def build_inventory() -> dict[str, Any]:
    """Build a deterministic static inventory rooted at active production patches."""
    groups = production_patch_groups()
    roots = production_patch_sequence()
    queue = list(roots)
    seen: set[str] = set()
    modules: dict[str, dict[str, Any]] = {}
    missing_modules: set[str] = set()

    while queue:
        module_name = queue.pop(0)
        if module_name in seen:
            continue
        seen.add(module_name)
        paths = _source_paths_for_module(module_name)
        if not paths:
            missing_modules.add(module_name)
            continue

        imported: set[str] = set()
        mutations: set[str] = set()
        source_records: list[dict[str, Any]] = []
        for path in paths:
            patch_imports, patch_mutations = _parse_source(path)
            imported.update(patch_imports)
            mutations.update(patch_mutations)
            source_records.append(
                {
                    "path": path.relative_to(SCRIPTS).as_posix(),
                    "bytes": len(path.read_bytes().replace(b"\r\n", b"\n")),
                }
            )
        for imported_name in sorted(imported):
            if imported_name not in seen and imported_name not in queue:
                queue.append(imported_name)

        modules[module_name] = {
            "production_root": module_name in roots,
            "numbered_version": _numbered_version(module_name),
            "sources": source_records,
            "patch_imports": sorted(imported),
            "mutation_surfaces": sorted(mutations),
        }

    numbered_versions = [
        version
        for record in modules.values()
        for version in [record.get("numbered_version")]
        if isinstance(version, int)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "production_patch_groups": {
            group_name: list(module_names)
            for group_name, module_names in groups.items()
        },
        "production_patch_sequence": list(roots),
        "production_patch_count": len(roots),
        "inventory_module_count": len(modules),
        "max_numbered_version": max(numbered_versions) if numbered_versions else None,
        "missing_modules": sorted(missing_modules),
        "modules": {
            module_name: modules[module_name]
            for module_name in sorted(modules)
        },
    }


def main() -> None:
    print(json.dumps(build_inventory(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
