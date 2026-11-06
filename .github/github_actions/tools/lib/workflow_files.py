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
    if not workflow_dir.exists():
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
    """Find local action metadata under ``repo_root/.github/actions``.

    ``top_level_only`` returns exactly the metadata file the runner would load
    for each direct child action directory; inventory, version and contract
    audits use it. The default recursive mode is a deliberately broader
    superset (any ``action.yml``/``action.yaml`` at any depth, any case) for
    reusable-contract scans.
    """
    action_dir = repo_root / ACTION_DIR
    if not action_dir.is_dir():
        return []
    if top_level_only:
        resolved = (resolve_action_metadata(child) for child in action_dir.iterdir())
        return sorted(path for path in resolved if path is not None)
    return sorted(
        path for path in action_dir.rglob("*")
        if path.is_file() and path.name.lower() in {"action.yml", "action.yaml"}
    )
