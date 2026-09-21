from __future__ import annotations

import os
import stat
import tempfile
import uuid
from pathlib import Path
from typing import TextIO


_CAPABILITY_AUTHORITY = object()


class PrivateCaptureRoot:
    __slots__ = (
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
        basename: str,
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
        self.basename = basename
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
    if os.name != "posix" or not getattr(os, "O_NOFOLLOW", 0) or not getattr(os, "O_DIRECTORY", 0):
        raise SystemExit("Secure capture requires POSIX O_NOFOLLOW and O_DIRECTORY support.")
    for operation in (os.open, os.stat, os.rename, os.unlink, os.mkdir, os.rmdir):
        if operation not in os.supports_dir_fd:
            raise SystemExit(
                f"Secure capture requires descriptor-relative {operation.__name__} support."
            )
    if os.stat not in os.supports_follow_symlinks:
        raise SystemExit("Secure capture requires no-follow descriptor-relative stat support.")
    if not Path("/proc/self/fd").is_dir():
        raise SystemExit("Secure capture subprocess handoff requires /proc/self/fd support.")


def _require_capability(private_root: PrivateCaptureRoot) -> PrivateCaptureRoot:
    if not isinstance(private_root, PrivateCaptureRoot):
        raise TypeError("Capture operations require an allocator-issued PrivateCaptureRoot.")
    if private_root.closed:
        raise SystemExit("Capture root capability is already closed.")
    return private_root


def _validate_filename(filename: str) -> str:
    if not filename or Path(filename).name != filename or filename in {".", ".."}:
        raise SystemExit(f"Invalid capture filename: {filename!r}")
    return filename


def _validate_parent_descriptor(private_root: PrivateCaptureRoot) -> os.stat_result:
    root = _require_capability(private_root)
    parent_stat = os.fstat(root.parent_fd)
    if not stat.S_ISDIR(parent_stat.st_mode):
        raise SystemExit("Capture parent descriptor no longer identifies a directory.")
    if _identity(parent_stat) != (root.parent_dev, root.parent_ino):
        raise SystemExit("Capture parent descriptor identity changed.")
    return parent_stat


def _validate_visible_root(private_root: PrivateCaptureRoot) -> os.stat_result:
    root = _require_capability(private_root)
    _validate_parent_descriptor(root)
    root_fd_stat = os.fstat(root.dir_fd)
    if not stat.S_ISDIR(root_fd_stat.st_mode) or _identity(root_fd_stat) != (root.dev, root.ino):
        raise SystemExit("Capture root descriptor identity changed.")
    try:
        visible = os.stat(root.basename, dir_fd=root.parent_fd, follow_symlinks=False)
    except FileNotFoundError as exc:
        raise SystemExit("Allocated capture root entry disappeared.") from exc
    if not stat.S_ISDIR(visible.st_mode) or _identity(visible) != (root.dev, root.ino):
        raise SystemExit("Allocated capture root entry was replaced.")
    return root_fd_stat


def _open_directory_at(parent_fd: int, name: str, expected: tuple[int, int]) -> int:
    fd = os.open(
        name,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
        dir_fd=parent_fd,
    )
    try:
        opened = os.fstat(fd)
        if not stat.S_ISDIR(opened.st_mode) or _identity(opened) != expected:
            raise SystemExit("Directory identity changed while opening descriptor.")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _rmdir_if_identity(parent_fd: int, name: str, expected: tuple[int, int]) -> None:
    current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(current.st_mode) or _identity(current) != expected:
        raise SystemExit("Cleanup directory entry identity changed before removal.")
    # Final removal is deliberately non-recursive. If the name is substituted
    # after the identity check, rmdir cannot destroy a non-empty replacement.
    os.rmdir(name, dir_fd=parent_fd)


def _empty_directory_fd(dir_fd: int) -> None:
    for name in os.listdir(dir_fd):
        current = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
        identity = _identity(current)
        if stat.S_ISDIR(current.st_mode):
            child_fd = _open_directory_at(dir_fd, name, identity)
            try:
                _empty_directory_fd(child_fd)
            finally:
                os.close(child_fd)
            _rmdir_if_identity(dir_fd, name, identity)
        else:
            os.unlink(name, dir_fd=dir_fd)


def _quarantine_and_cleanup(
    parent_fd: int,
    root_fd: int,
    root_name: str,
    root_identity: tuple[int, int],
) -> None:
    parent_stat = os.fstat(parent_fd)
    if not stat.S_ISDIR(parent_stat.st_mode):
        raise SystemExit("Cleanup parent descriptor is not a directory.")
    root_stat = os.fstat(root_fd)
    if not stat.S_ISDIR(root_stat.st_mode) or _identity(root_stat) != root_identity:
        raise SystemExit("Cleanup root descriptor identity mismatch.")

    quarantine_name = f".dcoir-capture-quarantine-{uuid.uuid4().hex}"
    os.mkdir(quarantine_name, 0o700, dir_fd=parent_fd)
    quarantine_stat = os.stat(quarantine_name, dir_fd=parent_fd, follow_symlinks=False)
    quarantine_identity = _identity(quarantine_stat)
    quarantine_fd = _open_directory_at(parent_fd, quarantine_name, quarantine_identity)
    try:
        os.rename(root_name, "root", src_dir_fd=parent_fd, dst_dir_fd=quarantine_fd)
        moved = os.stat("root", dir_fd=quarantine_fd, follow_symlinks=False)
        if not stat.S_ISDIR(moved.st_mode) or _identity(moved) != root_identity:
            raise SystemExit("Quarantined capture root identity mismatch.")
        _empty_directory_fd(root_fd)
        _rmdir_if_identity(quarantine_fd, "root", root_identity)
        try:
            os.stat("root", dir_fd=quarantine_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise SystemExit("Quarantined capture root still exists after cleanup.")
    finally:
        os.close(quarantine_fd)

    _rmdir_if_identity(parent_fd, quarantine_name, quarantine_identity)


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
    root_fd: int | None = None
    root_name = ""
    root_identity: tuple[int, int] | None = None
    try:
        parent_fd_stat = os.fstat(parent_fd)
        if _identity(parent_fd_stat) != _identity(parent_path_stat):
            raise SystemExit("Approved capture parent changed while being opened.")
        private_root_path = Path(tempfile.mkdtemp(prefix="dcoir-openai-capture-", dir=str(parent)))
        root_name = private_root_path.name
        root_path_stat = os.stat(root_name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(root_path_stat.st_mode):
            raise SystemExit("Allocated capture root is not a real directory.")
        root_identity = _identity(root_path_stat)
        root_fd = _open_directory_at(parent_fd, root_name, root_identity)
        os.fchmod(root_fd, 0o700)
        root_fd_stat = os.fstat(root_fd)
        if stat.S_IMODE(root_fd_stat.st_mode) != 0o700:
            raise SystemExit("Allocated capture root did not retain mode 0700.")
        return PrivateCaptureRoot(
            basename=root_name,
            dir_fd=root_fd,
            parent_fd=parent_fd,
            dev=root_fd_stat.st_dev,
            ino=root_fd_stat.st_ino,
            parent_dev=parent_fd_stat.st_dev,
            parent_ino=parent_fd_stat.st_ino,
            _authority=_CAPABILITY_AUTHORITY,
        )
    except BaseException as allocation_error:
        cleanup_error: BaseException | None = None
        try:
            if root_identity is not None and root_name:
                if root_fd is None:
                    root_fd = _open_directory_at(parent_fd, root_name, root_identity)
                _quarantine_and_cleanup(parent_fd, root_fd, root_name, root_identity)
        except BaseException as exc:
            cleanup_error = exc
        finally:
            if root_fd is not None:
                os.close(root_fd)
            os.close(parent_fd)
        if cleanup_error is not None:
            raise allocation_error.with_traceback(allocation_error.__traceback__) from cleanup_error
        raise


def capture_process_path(private_root: PrivateCaptureRoot, filename: str) -> str:
    root = _require_capability(private_root)
    _validate_filename(filename)
    _validate_visible_root(root)
    return f"/proc/self/fd/{root.dir_fd}/{filename}"


def read_capture_text(private_root: PrivateCaptureRoot, filename: str) -> str:
    root = _require_capability(private_root)
    _validate_filename(filename)
    _validate_visible_root(root)
    fd = os.open(
        filename,
        os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
        dir_fd=root.dir_fd,
    )
    try:
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode):
            raise SystemExit("Capture source is not a regular file.")
        _validate_visible_root(root)
        with os.fdopen(fd, "r", encoding="utf-8") as fh:
            fd = -1
            return fh.read()
    finally:
        if fd >= 0:
            os.close(fd)


def open_capture_text_exclusive(private_root: PrivateCaptureRoot, filename: str) -> TextIO:
    root = _require_capability(private_root)
    _validate_filename(filename)
    _validate_visible_root(root)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    fd: int | None = None
    created = False
    try:
        fd = os.open(filename, flags, 0o600, dir_fd=root.dir_fd)
        created = True
        os.fchmod(fd, 0o600)
        file_stat = os.fstat(fd)
        if not stat.S_ISREG(file_stat.st_mode) or stat.S_IMODE(file_stat.st_mode) != 0o600:
            raise SystemExit("Capture destination did not retain regular-file mode 0600.")
        _validate_visible_root(root)
        return os.fdopen(fd, "w", encoding="utf-8")
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
    try:
        _validate_visible_root(root)
        _quarantine_and_cleanup(root.parent_fd, root.dir_fd, root.basename, (root.dev, root.ino))
    finally:
        if not root.closed:
            os.close(root.dir_fd)
            os.close(root.parent_fd)
            root._closed = True
