"""Canonical repository workflow-file discovery for CI inventory and audits."""
from __future__ import annotations

from pathlib import Path


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
