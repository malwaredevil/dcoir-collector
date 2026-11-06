"""Canonical repository workflow and local-action discovery for CI inventory and audits."""
from __future__ import annotations

from pathlib import Path

ACTION_DIR = Path(".github/actions")
# Exact names GitHub Actions resolves for a local action, in lookup order.
ACTION_METADATA_NAMES = ("action.yml", "action.yaml")


def iter_workflow_files(workflow_dir: Path, *, include_reusable: bool = True) -> list[Path]:
    """Return sorted top-level YAML workflows, optionally excluding reusable ones.

    Preserve the legacy semantics of individual workflow inventory/audit
    consumers: top-level files only, lower-case-sensitive `reusable-` prefix,
    and a case-insensitive YAML extension.
    """
    if not workflow_dir.is_dir():
        return []
    return sorted(
        path
        for path in workflow_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in {".yml", ".yaml"}
        and (include_reusable or not path.name.startswith("reusable-"))
    )


def resolve_action_metadata(action_dir: Path) -> Path | None:
    """Return the metadata file GitHub Actions loads for one local action directory.

    The runner looks for exact, case-sensitive ``action.yml`` and then
    ``action.yaml``, so only that single file defines the action. Directory
    entries are compared by exact name to stay correct on case-insensitive
    filesystems.
    """
    if not action_dir.is_dir():
        return None
    names = {entry.name for entry in action_dir.iterdir() if entry.is_file()}
    for name in ACTION_METADATA_NAMES:
        if name in names:
            return action_dir / name
    return None


def iter_action_metadata_files(repo_root: Path, *, top_level_only: bool = False) -> list[Path]:
    """Find the metadata file the runner loads for each local action directory.

    Every directory is resolved through ``resolve_action_metadata``, so shadowed
    ``action.yaml`` copies and mixed-case names are never returned. The only
    difference between modes is depth: ``top_level_only`` covers direct children
    of ``.github/actions`` (inventory and the action-version audit), while the
    default also covers nested action directories that a ``uses:`` path could
    reference (reusable-contract audit).
    """
    action_dir = repo_root / ACTION_DIR
    if not action_dir.is_dir():
        return []
    if top_level_only:
        directories = [child for child in action_dir.iterdir() if child.is_dir()]
    else:
        directories = [action_dir, *(path for path in action_dir.rglob("*") if path.is_dir())]
    resolved = (resolve_action_metadata(directory) for directory in directories)
    return sorted(path for path in resolved if path is not None)
