#!/usr/bin/env python3
"""Build the DCOIR PowerShell surface inventory.

The workflow-facing CLI and import facade stays intentionally small while the
implementation lives in connector-sized helper modules next to this file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import powershell_surface_inventory_common as _common
import powershell_surface_inventory_discovery as _discovery
import powershell_surface_inventory_outputs as _outputs
import powershell_surface_inventory_validation as _validation
import powershell_surface_inventory_workflow_yaml as _workflow_yaml
import powershell_surface_inventory_yaml as _yaml

_EXPORT_MODULES: tuple[ModuleType, ...] = (
    _common,
    _yaml,
    _workflow_yaml,
    _discovery,
    _validation,
    _outputs,
)

DEFAULT_JSON_OUTPUT = _common.DEFAULT_JSON_OUTPUT
DEFAULT_MARKDOWN_OUTPUT = _common.DEFAULT_MARKDOWN_OUTPUT
load_json_file = _common.load_json_file
repo_relative_cli_path = _common.repo_relative_cli_path
load_changed_files_from = _discovery.load_changed_files_from
build_inventory = _outputs.build_inventory
write_outputs = _outputs.write_outputs
load_shrink_exceptions = _validation.load_shrink_exceptions

__all__ = sorted(
    {
        "DEFAULT_JSON_OUTPUT",
        "DEFAULT_MARKDOWN_OUTPUT",
        "Path",
        "build_inventory",
        "hashlib",
        "json",
        "load_changed_files_from",
        "load_json_file",
        "load_shrink_exceptions",
        "main",
        "parse_args",
        "repo_relative_cli_path",
        "subprocess",
        "write_outputs",
    }
    | {
        name
        for module in _EXPORT_MODULES
        for name in getattr(module, "__all__", ())
    }
)


def __getattr__(name: str) -> object:
    for module in _EXPORT_MODULES:
        if name in getattr(module, "__all__", ()):
            return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the DCOIR PowerShell surface inventory")
    parser.add_argument("--repo-root", default=".", help="Repository root to scan")
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT.as_posix(), help="JSON inventory output path")
    parser.add_argument("--markdown-output", default=DEFAULT_MARKDOWN_OUTPUT.as_posix(), help="Markdown inventory output path")
    parser.add_argument("--changed-file", action="append", default=[], help="Changed file to classify; may be repeated")
    parser.add_argument("--changed-files-from", help="Newline-delimited changed-file input")
    parser.add_argument("--baseline-json", help="Previous inventory JSON for unexpected-shrink checks")
    parser.add_argument("--shrink-exception-json", help="JSON file with allowed_category_shrink reasons")
    parser.add_argument("--no-write", action="store_true", help="Validate and print JSON without writing artifacts")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    json_output = Path(args.json_output)
    markdown_output = Path(args.markdown_output)
    input_errors: list[str] = []

    changed_files: list[str] | None = None
    if args.changed_file or args.changed_files_from:
        changed_files = list(args.changed_file)
        if args.changed_files_from:
            try:
                changed_files.extend(
                    load_changed_files_from(
                        repo_relative_cli_path(
                            repo_root,
                            args.changed_files_from,
                            "PowerShell surface inventory changed-files input path",
                        )
                    )
                )
            except ValueError as exc:
                input_errors.append(str(exc))

    baseline = None
    shrink_exceptions: dict[str, str] = {}
    try:
        baseline = (
            load_json_file(repo_relative_cli_path(repo_root, args.baseline_json, "PowerShell surface inventory baseline path"))
            if args.baseline_json
            else None
        )
    except ValueError as exc:
        input_errors.append(str(exc))
    try:
        shrink_exceptions = load_shrink_exceptions(
            repo_relative_cli_path(repo_root, args.shrink_exception_json, "PowerShell surface inventory shrink exception path")
            if args.shrink_exception_json
            else None
        )
    except ValueError as exc:
        input_errors.append(str(exc))
    inventory = build_inventory(
        repo_root=repo_root,
        changed_files=changed_files,
        baseline=baseline,
        shrink_exceptions=shrink_exceptions,
        json_output=json_output,
        markdown_output=markdown_output,
    )
    if input_errors:
        inventory["validation"]["errors"] = input_errors + inventory["validation"]["errors"]
        inventory["validation"]["success"] = False

    if not args.no_write:
        output_errors = write_outputs(repo_root, inventory, json_output, markdown_output)
        if output_errors:
            inventory["validation"]["errors"].extend(output_errors)
            inventory["validation"]["success"] = False
            rewrite_errors = write_outputs(repo_root, inventory, json_output, markdown_output)
            for error in rewrite_errors:
                if error not in inventory["validation"]["errors"]:
                    inventory["validation"]["errors"].append(error)
    print(json.dumps(inventory["summary"], indent=2))
    if inventory["validation"]["errors"]:
        for error in inventory["validation"]["errors"]:
            print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
