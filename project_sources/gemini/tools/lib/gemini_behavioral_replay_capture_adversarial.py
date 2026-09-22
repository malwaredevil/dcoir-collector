from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

from . import gemini_behavioral_replay_capture_paths as capture_paths

from .gemini_behavioral_replay_capture_paths import (
    PrivateCaptureRoot,
    _identity,
    _open_directory_at,
    _require_capability,
    _rmdir_if_identity,
    _validate_visible_root,
    capture_process_path,
    cleanup_private_capture_root,
    open_capture_text_exclusive,
    read_capture_text,
)


def _assert_replaced_root_is_rejected(private_root: PrivateCaptureRoot) -> None:
    root = _require_capability(private_root)
    displaced_name = f".dcoir-capture-displaced-{uuid.uuid4().hex}"
    replacement_created = False
    displaced = False
    try:
        _validate_visible_root(root)
        os.rename(root.basename, displaced_name, src_dir_fd=root.parent_fd, dst_dir_fd=root.parent_fd)
        displaced = True
        os.mkdir(root.basename, 0o700, dir_fd=root.parent_fd)
        replacement_created = True
        for operation in (
            lambda: open_capture_text_exclusive(root, "replacement_probe.txt"),
            lambda: read_capture_text(root, "preexisting_sentinel.txt"),
            lambda: capture_process_path(root, "preexisting_sentinel.txt"),
        ):
            try:
                operation()
            except (SystemExit, FileNotFoundError):
                pass
            else:
                raise SystemExit("Replaced capture root was accepted by an I/O helper.")
    finally:
        if replacement_created:
            os.rmdir(root.basename, dir_fd=root.parent_fd)
        if displaced:
            os.rename(displaced_name, root.basename, src_dir_fd=root.parent_fd, dst_dir_fd=root.parent_fd)
    _validate_visible_root(root)


def _assert_identity_bound_final_remove(private_root: PrivateCaptureRoot) -> None:
    root = _require_capability(private_root)
    probe = f".dcoir-remove-probe-{uuid.uuid4().hex}"
    os.mkdir(probe, 0o700, dir_fd=root.dir_fd)
    probe_stat = os.stat(probe, dir_fd=root.dir_fd, follow_symlinks=False)
    original = f"{probe}-original"
    os.rename(probe, original, src_dir_fd=root.dir_fd, dst_dir_fd=root.dir_fd)
    os.mkdir(probe, 0o700, dir_fd=root.dir_fd)
    replacement_fd = _open_directory_at(
        root.dir_fd, probe, _identity(os.stat(probe, dir_fd=root.dir_fd, follow_symlinks=False))
    )
    try:
        sentinel_fd = os.open(
            "sentinel", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=replacement_fd
        )
        os.close(sentinel_fd)
        try:
            _rmdir_if_identity(root.dir_fd, probe, _identity(probe_stat))
        except SystemExit:
            pass
        else:
            raise SystemExit("Identity-bound final removal accepted a substituted directory.")
        if "sentinel" not in os.listdir(replacement_fd):
            raise SystemExit("Substituted cleanup sentinel was deleted.")
        os.unlink("sentinel", dir_fd=replacement_fd)
    finally:
        os.close(replacement_fd)
    os.rmdir(probe, dir_fd=root.dir_fd)
    os.rmdir(original, dir_fd=root.dir_fd)



def _assert_descriptor_bound_allocation() -> None:
    temp_root = Path(tempfile.gettempdir()).resolve()
    sandbox = Path(tempfile.mkdtemp(prefix=".dcoir-allocation-test-", dir=temp_root))
    container_fd = os.open(
        temp_root,
        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
    )
    sandbox_name = sandbox.name
    sandbox_identity = _identity(
        os.stat(sandbox_name, dir_fd=container_fd, follow_symlinks=False)
    )
    displaced_name = f"{sandbox_name}.displaced-{uuid.uuid4().hex}"
    real_uuid4 = capture_paths.uuid.uuid4
    real_tempfile = capture_paths.tempfile
    private_root: PrivateCaptureRoot | None = None
    replacement_identity: tuple[int, int] | None = None
    swapped = False
    failure: BaseException | None = None
    cleanup_error: BaseException | None = None
    restore_error: BaseException | None = None
    preserved_name = ""

    class _SandboxTempfile:
        @staticmethod
        def gettempdir() -> str:
            return str(sandbox)

    def preserve_visible_entry() -> str:
        for _ in range(128):
            candidate = f"{sandbox_name}.preserved-{uuid.uuid4().hex}"
            try:
                os.stat(candidate, dir_fd=container_fd, follow_symlinks=False)
            except FileNotFoundError:
                os.rename(
                    sandbox_name,
                    candidate,
                    src_dir_fd=container_fd,
                    dst_dir_fd=container_fd,
                )
                return candidate
        raise SystemExit("Unable to preserve substituted allocation sandbox entry.")

    def swap_visible_parent_then_uuid():
        nonlocal swapped, replacement_identity
        if not swapped:
            os.rename(
                sandbox_name,
                displaced_name,
                src_dir_fd=container_fd,
                dst_dir_fd=container_fd,
            )
            os.mkdir(sandbox_name, 0o700, dir_fd=container_fd)
            replacement_identity = _identity(
                os.stat(sandbox_name, dir_fd=container_fd, follow_symlinks=False)
            )
            swapped = True
        return real_uuid4()

    capture_paths.tempfile = _SandboxTempfile
    capture_paths.uuid.uuid4 = swap_visible_parent_then_uuid
    try:
        private_root = capture_paths.allocate_private_capture_root(sandbox)
        if not swapped or replacement_identity is None:
            raise SystemExit("Descriptor-allocation test did not swap the visible sandbox.")
        replacement_fd = _open_directory_at(
            container_fd, sandbox_name, replacement_identity
        )
        try:
            if os.listdir(replacement_fd):
                raise SystemExit("Capture allocation touched the replacement sandbox.")
        finally:
            os.close(replacement_fd)
        displaced_stat = os.stat(
            displaced_name, dir_fd=container_fd, follow_symlinks=False
        )
        if _identity(displaced_stat) != sandbox_identity:
            raise SystemExit("Displaced allocation sandbox identity changed.")
        if sandbox_identity != (private_root.parent_dev, private_root.parent_ino):
            raise SystemExit(
                "Capture parent capability did not remain bound to the displaced sandbox."
            )
        root_stat = os.stat(
            private_root.basename,
            dir_fd=private_root.parent_fd,
            follow_symlinks=False,
        )
        if _identity(root_stat) != (private_root.dev, private_root.ino):
            raise SystemExit(
                "Capture root was not created beneath the validated sandbox descriptor."
            )
    except BaseException as exc:
        failure = exc
    finally:
        capture_paths.uuid.uuid4 = real_uuid4
        capture_paths.tempfile = real_tempfile
        if private_root is not None and not private_root.closed:
            try:
                cleanup_private_capture_root(private_root)
            except BaseException as exc:
                cleanup_error = exc
        try:
            if swapped:
                try:
                    visible = os.stat(
                        sandbox_name, dir_fd=container_fd, follow_symlinks=False
                    )
                except FileNotFoundError:
                    visible = None
                if visible is not None:
                    visible_identity = _identity(visible)
                    if (
                        replacement_identity is not None
                        and visible_identity == replacement_identity
                    ):
                        visible_fd = _open_directory_at(
                            container_fd, sandbox_name, replacement_identity
                        )
                        try:
                            visible_entries = os.listdir(visible_fd)
                        finally:
                            os.close(visible_fd)
                        if visible_entries:
                            preserved_name = preserve_visible_entry()
                        else:
                            _rmdir_if_identity(
                                container_fd, sandbox_name, replacement_identity
                            )
                    else:
                        preserved_name = preserve_visible_entry()

                displaced_stat = os.stat(
                    displaced_name, dir_fd=container_fd, follow_symlinks=False
                )
                if _identity(displaced_stat) != sandbox_identity:
                    raise SystemExit(
                        "Displaced allocation sandbox identity changed before restoration."
                    )
                os.rename(
                    displaced_name,
                    sandbox_name,
                    src_dir_fd=container_fd,
                    dst_dir_fd=container_fd,
                )

            try:
                restored = os.stat(
                    sandbox_name, dir_fd=container_fd, follow_symlinks=False
                )
            except FileNotFoundError:
                restored = None
            if restored is not None:
                if _identity(restored) != sandbox_identity:
                    raise SystemExit("Allocation sandbox identity changed during restoration.")
                restored_fd = _open_directory_at(
                    container_fd, sandbox_name, sandbox_identity
                )
                try:
                    restored_entries = os.listdir(restored_fd)
                finally:
                    os.close(restored_fd)
                if restored_entries:
                    raise SystemExit(
                        f"Allocation sandbox retained cleanup residue: {sandbox}"
                    )
                _rmdir_if_identity(container_fd, sandbox_name, sandbox_identity)
        except BaseException as exc:
            restore_error = exc
        finally:
            os.close(container_fd)

    if preserved_name and restore_error is None:
        restore_error = SystemExit(
            f"Unexpected replacement sandbox was preserved at {temp_root / preserved_name}."
        )
    if failure is not None:
        if cleanup_error is not None:
            raise failure from cleanup_error
        if restore_error is not None:
            raise failure from restore_error
        raise failure
    if cleanup_error is not None:
        if restore_error is not None:
            raise cleanup_error from restore_error
        raise cleanup_error
    if restore_error is not None:
        raise restore_error

def _assert_rollback_failure_chaining() -> None:
    real_cleanup = capture_paths._quarantine_and_cleanup
    real_fchmod = capture_paths.os.fchmod

    def cleanup_then_fail(*args, **kwargs):
        real_cleanup(*args, **kwargs)
        raise RuntimeError("synthetic rollback cleanup failure")

    def fail_allocation_fchmod(*_args, **_kwargs):
        raise RuntimeError("synthetic allocation failure")

    capture_paths._quarantine_and_cleanup = cleanup_then_fail
    capture_paths.os.fchmod = fail_allocation_fchmod
    try:
        try:
            capture_paths.allocate_private_capture_root(Path(tempfile.gettempdir()))
        except RuntimeError as exc:
            if str(exc) != "synthetic allocation failure":
                raise
            cause = exc.__cause__
            if not isinstance(cause, RuntimeError) or str(cause) != "synthetic rollback cleanup failure":
                raise SystemExit("Rollback cleanup failure was not chained beneath allocation failure.")
        else:
            raise SystemExit("Synthetic allocation failure did not propagate.")
    finally:
        capture_paths.os.fchmod = real_fchmod
        capture_paths._quarantine_and_cleanup = real_cleanup

def assert_private_capture_root(private_root: PrivateCaptureRoot) -> None:
    root = _require_capability(private_root)
    sentinel_name = "preexisting_sentinel.txt"
    with open_capture_text_exclusive(root, sentinel_name) as fh:
        fh.write("sentinel\n")
    try:
        with open_capture_text_exclusive(root, sentinel_name) as fh:
            fh.write("modified\n")
    except FileExistsError:
        pass
    else:
        raise SystemExit("Exclusive capture creation overwrote a pre-existing file.")
    if read_capture_text(root, sentinel_name) != "sentinel\n":
        raise SystemExit("Capture sentinel was modified.")
    try:
        read_capture_text(Path("."), sentinel_name)  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise SystemExit("Arbitrary Path bypassed the capture capability requirement.")
    _assert_replaced_root_is_rejected(root)
    _assert_identity_bound_final_remove(root)
    _assert_descriptor_bound_allocation()
    _assert_rollback_failure_chaining()
