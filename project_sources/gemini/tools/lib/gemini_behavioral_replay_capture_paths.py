from __future__ import annotations

import os
import shutil
import stat
import tempfile
import uuid
from pathlib import Path
from typing import TextIO


_CAPABILITY_AUTHORITY = object()


class PrivateCaptureRoot:
    __slots__ = (
        "path",
        "parent",
        "basename",
        "dir_fd",
        "parent_fd",
        "dev",
        "ino",
        "parent_dev",
        "parent_ino",
        "_closed",
    )

    def __init__(
        self,
        *,
        path: Path,
        parent: Path,
        dir_fd: int,
        parent_fd: int,
        dev: int,
        ino: int,
        parent_dev: int,
        parent_ino: int,
        _authority: object,
    ) -> None:
        if _authority is not _CAPABILITY_AUTHORITY:
            raise TypeError("PrivateCaptureRoot instances must be allocator-issued.")
        self.path = path
        self.parent = parent
        self.basename = path.name
        self.dir_fd = dir_fd
        self.parent_fd = parent_fd
        self.dev = dev
        self.ino = ino
        self.parent_dev = parent_dev
        self.parent_ino = parent_ino
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed


def _identity(st: os.stat_result) -> tuple[int, int]:
    return st.st_dev, st.st_ino


def _require_fd_capabilities() -> None:
    if not getattr(os, "O_NOFOLLOW", 0) or not getattr(os, "O_DIRECTORY", 0):
        raise SystemExit("Secure capture requires O_NOFOLLOW and O_DIRECTORY support.")
    for operation in (os.open, os.stat, os.rename, os.unlink, os.mkdir, os.rmdir):
        if operation not in os.supports_dir_fd:
            raise SystemExit(
                f"Secure capture requires descriptor-relative {operation.__name__} support."
            )
    if os.stat not in os.supports_follow_symlinks:
        raise SystemExit("Secure capture requires no-follow descriptor-relative stat support.")
    if not getattr(shutil.rmtree, "avoids_symlink_attacks", False):
        raise SystemExit("Secure capture requires symlink-resistant descriptor-relative cleanup.")


def _require_capability(private_root: PrivateCaptureRoot) -> PrivateCaptureRoot:
    if not isinstance(private_root, PrivateCaptureRoot):
        raise TypeError("Capture operations require an allocator-issued PrivateCaptureRoot.")
    if private_root.closed:
        raise SystemExit("Capture root capability is already closed.")
    return private_root


def _validate_parent_identity(private_root: PrivateCaptureRoot) -> os.stat_result:
    root = _require_capability(private_root)
    parent_fd_stat = os.fstat(root.parent_fd)
    if not stat.S_ISDIR(parent_fd_stat.st_mode):
        raise SystemExit("Capture parent descriptor no longer identifies a directory.")
    if _identity(parent_fd_stat) != (root.parent_dev, root.parent_ino):
        raise SystemExit("Capture parent descriptor identity changed.")
    try:
        parent_path_stat = os.stat(root.parent, follow_symlinks=False)
    except FileNotFoundError as exc:
        raise SystemExit("Capture parent path disappeared.") from exc
    if not stat.S_ISDIR(parent_path_stat.st_mode):
        raise SystemExit("Capture parent path no longer identifies a directory.")
    if _identity(parent_path_stat) != (root.parent_dev, root.parent_ino):
        raise SystemExit("Capture parent path no longer matches the allocated parent.")
    return parent_fd_stat


def _validate_root_identity(private_root: PrivateCaptureRoot) -> os.stat_result:
    root = _require_capability(private_root)
    _validate_parent_identity(root)
    root_fd_stat = os.fstat(root.dir_fd)
    if not stat.S_ISDIR(root_fd_stat.st_mode):
        raise SystemExit("Capture root descriptor no longer identifies a directory.")
    if _identity(root_fd_stat) != (root.dev, root.ino):
        raise SystemExit("Capture root descriptor identity changed.")
    try:
        root_path_stat = os.stat(
            root.basename,
            dir_fd=root.parent_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError as exc:
        raise SystemExit("Allocated capture root path disappeared.") from exc
    if not stat.S_ISDIR(root_path_stat.st_mode):
        raise SystemExit("Allocated capture root path is no longer a real directory.")
    if _identity(root_path_stat) != (root.dev, root.ino):
        raise SystemExit("Allocated capture root path was replaced.")
    return root_fd_stat


def allocate_private_capture_root(requested_output_dir: Path) -> PrivateCaptureRoot:
    _require_fd_capabilities()
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

    parent_path_stat = os.stat(parent, follow_symlinks=False)
    if not stat.S_ISDIR(parent_path_stat.st_mode):
        raise SystemExit(f"Approved capture parent is not a directory: {parent}")
    parent_fd = os.open(
        parent,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
    )
    private_root_path: Path | None = None
    root_fd: int | None = None
    root_identity: tuple[int, int] | None = None
    try:
        parent_fd_stat = os.fstat(parent_fd)
        if _identity(parent_fd_stat) != _identity(parent_path_stat):
            raise SystemExit("Approved capture parent changed while being opened.")

        private_root_path = Path(
            tempfile.mkdtemp(prefix="dcoir-openai-capture-", dir=str(parent))
        )
        if private_root_path.parent != parent:
            raise SystemExit(
                f"Private capture root escaped approved parent: {private_root_path}"
            )
        root_path_stat = os.stat(
            private_root_path.name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if not stat.S_ISDIR(root_path_stat.st_mode):
            raise SystemExit("Allocated capture root is not a real directory.")
        root_identity = _identity(root_path_stat)
        root_fd = os.open(
            private_root_path.name,
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_fd,
        )
        root_fd_stat = os.fstat(root_fd)
        if _identity(root_fd_stat) != root_identity:
            raise SystemExit("Allocated capture root changed while being opened.")
        os.fchmod(root_fd, 0o700)
        root_fd_stat = os.fstat(root_fd)
        if stat.S_IMODE(root_fd_stat.st_mode) != 0o700:
            raise SystemExit("Allocated capture root did not retain mode 0700.")

        return PrivateCaptureRoot(
            path=private_root_path,
            parent=parent,
            dir_fd=root_fd,
            parent_fd=parent_fd,
            dev=root_fd_stat.st_dev,
            ino=root_fd_stat.st_ino,
            parent_dev=parent_fd_stat.st_dev,
            parent_ino=parent_fd_stat.st_ino,
            _authority=_CAPABILITY_AUTHORITY,
        )
    except BaseException:
        if root_fd is not None:
            os.close(root_fd)
        if private_root_path is not None and root_identity is not None:
            try:
                current = os.stat(
                    private_root_path.name,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
                if stat.S_ISDIR(current.st_mode) and _identity(current) == root_identity:
                    shutil.rmtree(private_root_path.name, dir_fd=parent_fd)
            except (FileNotFoundError, OSError):
                pass
        os.close(parent_fd)
        raise


def capture_path(private_root: PrivateCaptureRoot, filename: str) -> Path:
    root = _require_capability(private_root)
    if not filename or Path(filename).name != filename or filename in {".", ".."}:
        raise SystemExit(f"Invalid capture filename: {filename!r}")
    _validate_root_identity(root)
    return root.path / filename


def open_capture_text_exclusive(
    private_root: PrivateCaptureRoot,
    filename: str,
) -> TextIO:
    root = _require_capability(private_root)
    capture_path(root, filename)
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    fd: int | None = None
    created = False
    try:
        fd = os.open(filename, flags, 0o600, dir_fd=root.dir_fd)
        created = True
        os.fchmod(fd, 0o600)
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode):
            raise SystemExit("Capture destination is not a regular file.")
        if stat.S_IMODE(file_stat.st_mode) != 0o600:
            raise SystemExit("Capture destination did not retain mode 0600.")
        _validate_root_identity(root)
        stream = os.fdopen(fd, "w", encoding="utf-8")
        fd = None
        return stream
    except BaseException:
        if fd is not None:
            os.close(fd)
        if created:
            try:
                os.unlink(filename, dir_fd=root.dir_fd)
            except FileNotFoundError:
                pass
        raise


def cleanup_private_capture_root(private_root: PrivateCaptureRoot) -> None:
    root = _require_capability(private_root)
    quarantine_name = f".dcoir-capture-quarantine-{uuid.uuid4().hex}"
    try:
        _validate_root_identity(root)
        try:
            os.stat(quarantine_name, dir_fd=root.parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise SystemExit("Capture cleanup quarantine path already exists.")

        os.rename(
            root.basename,
            quarantine_name,
            src_dir_fd=root.parent_fd,
            dst_dir_fd=root.parent_fd,
        )
        quarantine_stat = os.stat(
            quarantine_name,
            dir_fd=root.parent_fd,
            follow_symlinks=False,
        )
        if not stat.S_ISDIR(quarantine_stat.st_mode):
            raise SystemExit("Quarantined capture root is not a real directory.")
        if _identity(quarantine_stat) != (root.dev, root.ino):
            raise SystemExit("Quarantined capture root identity mismatch.")
        root_fd_stat = os.fstat(root.dir_fd)
        if _identity(root_fd_stat) != (root.dev, root.ino):
            raise SystemExit("Capture descriptor changed before recursive cleanup.")
        _validate_parent_identity(root)
        final_quarantine_stat = os.stat(
            quarantine_name,
            dir_fd=root.parent_fd,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(final_quarantine_stat.st_mode)
            or _identity(final_quarantine_stat) != (root.dev, root.ino)
        ):
            raise SystemExit("Capture quarantine changed before recursive cleanup.")

        shutil.rmtree(quarantine_name, dir_fd=root.parent_fd)
        try:
            os.stat(quarantine_name, dir_fd=root.parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise SystemExit("Quarantined capture root still exists after cleanup.")
    finally:
        if not root.closed:
            os.close(root.dir_fd)
            os.close(root.parent_fd)
            root._closed = True


def _assert_replaced_root_is_rejected(private_root: PrivateCaptureRoot) -> None:
    root = _require_capability(private_root)
    displaced_name = f".dcoir-capture-displaced-{uuid.uuid4().hex}"
    replacement_created = False
    displaced = False
    try:
        _validate_root_identity(root)
        os.rename(
            root.basename,
            displaced_name,
            src_dir_fd=root.parent_fd,
            dst_dir_fd=root.parent_fd,
        )
        displaced = True
        os.mkdir(root.basename, 0o700, dir_fd=root.parent_fd)
        replacement_created = True
        try:
            capture_path(root, "replacement_probe.txt")
        except SystemExit:
            pass
        else:
            raise SystemExit("Replaced capture root was accepted.")
    finally:
        if replacement_created:
            os.rmdir(root.basename, dir_fd=root.parent_fd)
        if displaced:
            os.rename(
                displaced_name,
                root.basename,
                src_dir_fd=root.parent_fd,
                dst_dir_fd=root.parent_fd,
            )
    _validate_root_identity(root)


def assert_private_capture_root(private_root: PrivateCaptureRoot) -> None:
    root = _require_capability(private_root)
    sentinel_name = "preexisting_sentinel.txt"
    sentinel = capture_path(root, sentinel_name)
    with open_capture_text_exclusive(root, sentinel_name) as fh:
        fh.write("sentinel\n")
    try:
        with open_capture_text_exclusive(root, sentinel_name) as fh:
            fh.write("modified\n")
    except FileExistsError:
        pass
    else:
        raise SystemExit("Exclusive capture creation overwrote a pre-existing file.")
    if sentinel.read_text(encoding="utf-8") != "sentinel\n" or sentinel.parent != root.path:
        raise SystemExit("Capture sentinel was modified or escaped its private root.")

    try:
        capture_path(root.path, "capability_bypass.txt")  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise SystemExit("Arbitrary Path bypassed the capture capability requirement.")

    _assert_replaced_root_is_rejected(root)
