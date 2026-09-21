from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TextIO


def allocate_private_capture_root(requested_output_dir: Path) -> Path:
    requested = requested_output_dir.resolve()
    validation_root = Path("project_sources/validation").resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if requested == validation_root or requested.is_relative_to(validation_root):
        validation_root.mkdir(parents=True, exist_ok=True)
        parent = validation_root
    elif requested == temp_root or requested.is_relative_to(temp_root):
        parent = temp_root
    else:
        raise SystemExit(f"Capture output root is not approved: {requested}")
    private_root = Path(tempfile.mkdtemp(prefix="dcoir-openai-capture-", dir=str(parent))).resolve()
    if private_root.parent != parent:
        raise SystemExit(f"Private capture root escaped approved parent: {private_root}")
    return private_root


def capture_path(private_root: Path, filename: str) -> Path:
    if not filename or Path(filename).name != filename or filename in {".", ".."}:
        raise SystemExit(f"Invalid capture filename: {filename!r}")
    root = private_root.resolve()
    candidate = root / filename
    if candidate.parent.resolve() != root:
        raise SystemExit(f"Capture path escaped private root: {candidate}")
    return candidate


def open_capture_text_exclusive(private_root: Path, filename: str) -> TextIO:
    path = capture_path(private_root, filename)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    return os.fdopen(fd, "w", encoding="utf-8")


def assert_private_capture_root(private_root: Path) -> None:
    sentinel_name = "preexisting_sentinel.txt"
    sentinel = capture_path(private_root, sentinel_name)
    with open_capture_text_exclusive(private_root, sentinel_name) as fh:
        fh.write("sentinel\n")
    try:
        with open_capture_text_exclusive(private_root, sentinel_name) as fh:
            fh.write("modified\n")
    except FileExistsError:
        pass
    else:
        raise SystemExit("Exclusive capture creation overwrote a pre-existing file.")
    if sentinel.read_text(encoding="utf-8") != "sentinel\n" or sentinel.parent != private_root:
        raise SystemExit("Capture sentinel was modified or escaped its private root.")
