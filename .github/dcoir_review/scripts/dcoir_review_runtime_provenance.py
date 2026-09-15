#!/usr/bin/env python3
"""Report final callable provenance after the current DCOIR patch chain is applied.

Issue #550 uses this characterization tool to identify the behavior that must be
moved into canonical responsibility owners before numbered runtime patches are
retired. The script is read-only with respect to GitHub and the filesystem
except for normal Python import side effects in its own process.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dcoir_review.entrypoint import DcoirReviewEntrypoint

SCHEMA_VERSION = "dcoir_review_runtime_provenance_v1"
PATCH_NAME_MARKER = "patch"
REVIEW_MODULE_NAME = "openrouter_pr_review_pareto_context"


def _callable_owner(value: Any) -> dict[str, str] | None:
    if not callable(value):
        return None
    module_name = str(getattr(value, "__module__", "") or "")
    qualname = str(
        getattr(value, "__qualname__", getattr(value, "__name__", "")) or ""
    )
    try:
        source_file = inspect.getsourcefile(value) or ""
    except (OSError, TypeError):
        source_file = ""
    if source_file:
        try:
            source_file = Path(source_file).resolve().relative_to(SCRIPTS).as_posix()
        except (OSError, ValueError):
            source_file = str(source_file)
    return {
        "module": module_name,
        "qualname": qualname,
        "source": source_file,
    }


def _public_callable_snapshot(namespace: Any) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for name in sorted(dir(namespace)):
        if name.startswith("__"):
            continue
        try:
            value = getattr(namespace, name)
        except Exception:
            continue
        owner = _callable_owner(value)
        if owner is not None:
            result[name] = owner
    return result


def _changed_callables(
    before: dict[str, dict[str, str]],
    after: dict[str, dict[str, str]],
) -> dict[str, dict[str, dict[str, str] | None]]:
    changed: dict[str, dict[str, dict[str, str] | None]] = {}
    for name in sorted(set(before) | set(after)):
        before_owner = before.get(name)
        after_owner = after.get(name)
        if before_owner == after_owner:
            continue
        changed[name] = {"before": before_owner, "after": after_owner}
    return changed


def _is_patch_module_name(module_name: str) -> bool:
    return module_name.startswith("dcoir_review_") and PATCH_NAME_MARKER in module_name


def _loaded_patch_module_overrides() -> dict[str, dict[str, dict[str, str]]]:
    """Report callables whose final owner differs from the patch module exposing them."""
    modules: dict[str, dict[str, dict[str, str]]] = {}
    for module_name in sorted(sys.modules):
        if not _is_patch_module_name(module_name):
            continue
        module = sys.modules.get(module_name)
        if not isinstance(module, ModuleType):
            continue
        overrides: dict[str, dict[str, str]] = {}
        for name, owner in _public_callable_snapshot(module).items():
            owner_module = owner.get("module", "")
            if owner_module and owner_module != module_name:
                overrides[name] = owner
        if overrides:
            modules[module_name] = overrides
    return modules


def _namespace_record(namespace: Any) -> dict[str, Any]:
    snapshot = _public_callable_snapshot(namespace)
    patch_owned = {
        name: owner
        for name, owner in snapshot.items()
        if _is_patch_module_name(owner.get("module", ""))
    }
    return {
        "callable_count": len(snapshot),
        "patch_owned_callables": patch_owned,
    }


def build_provenance() -> dict[str, Any]:
    entrypoint = DcoirReviewEntrypoint(review_module_name=REVIEW_MODULE_NAME)
    review_module = entrypoint.import_module(entrypoint.review_module_name)
    hardened = getattr(review_module, "hardened", None)
    base = getattr(review_module, "base", None)

    before_review = _public_callable_snapshot(review_module)
    before_hardened = _public_callable_snapshot(hardened) if hardened is not None else {}
    before_base = _public_callable_snapshot(base) if base is not None else {}

    entrypoint.apply_runtime_patches(review_module)

    after_review = _public_callable_snapshot(review_module)
    after_hardened = _public_callable_snapshot(hardened) if hardened is not None else {}
    after_base = _public_callable_snapshot(base) if base is not None else {}

    return {
        "schema_version": SCHEMA_VERSION,
        "review_module": entrypoint.review_module_name,
        "production_patch_sequence": [
            module_name
            for group_name in (
                "patch_module_names",
                "terminal_patch_module_names",
                "post_terminal_patch_module_names",
                "candidate_integrity_patch_module_names",
                "stage_local_patch_module_names",
                "execution_policy_patch_module_names",
                "telemetry_patch_module_names",
                "post_telemetry_patch_module_names",
            )
            for module_name in getattr(entrypoint, group_name)
        ],
        "changed_surfaces": {
            "review": _changed_callables(before_review, after_review),
            "hardened": _changed_callables(before_hardened, after_hardened),
            "base": _changed_callables(before_base, after_base),
        },
        "final_namespaces": {
            "review": _namespace_record(review_module),
            "hardened": _namespace_record(hardened) if hardened is not None else {},
            "base": _namespace_record(base) if base is not None else {},
        },
        "loaded_patch_module_overrides": _loaded_patch_module_overrides(),
    }


def main() -> None:
    print(json.dumps(build_provenance(), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
