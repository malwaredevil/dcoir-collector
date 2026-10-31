#!/usr/bin/env python3
"""Run Issue #557 cheap Draft validation without importing untrusted source."""
from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def check_python_syntax(root: Path, paths: list[Path]) -> None:
    # Compilation checks syntax but never evaluates imported or top-level code.
    root = root.resolve(strict=True)
    for path in paths:
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Python path is outside the checkout: {path}")
        candidate = root
        for part in path.parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise ValueError(f"Python path contains a symlink: {path}")
        resolved = candidate.resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Python path is outside the checkout: {path}") from exc
        if not stat.S_ISREG(candidate.lstat().st_mode):
            raise ValueError(f"Python path is not a regular file: {path}")
        compile(candidate.read_bytes(), str(path), "exec")


def main() -> int:
    paths = [
        Path(path.decode("utf-8"))
        for path in subprocess.check_output(
            ["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT
        ).split(b"\x00")
        if path
    ]
    check_python_syntax(ROOT, paths)
    print(f"Draft fail-fast: parsed {len(paths)} tracked Python files", flush=True)
    for script in (
        ".github/github_actions/tools/test_pr_validation_lifecycle.py",
        ".github/github_actions/tools/check_workflow_modularization_contracts.py",
    ):
        subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True)
    print("Draft fail-fast: workflow contracts passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
