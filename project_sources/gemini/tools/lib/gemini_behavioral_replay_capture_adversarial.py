from __future__ import annotations

import os
import shutil
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
    validation_root = Path("project_sources/validation").resolve()
    validation_root.mkdir(parents=True, exist_ok=True)
    displaced = validation_root.with_name(
        f"{validation_root.name}.dcoir-allocation-test-{uuid.uuid4().hex}"
    )
    if displaced.exists():
        raise SystemExit("Descriptor-allocation test displacement path already exists.")

    real_uuid4 = capture_paths.uuid.uuid4
    private_root: PrivateCaptureRoot | None = None
    swapped = False
    replacement_created = False

    def swap_visible_parent_then_uuid():
        nonlocal swapped, replacement_created
        if not swapped:
            validation_root.rename(displaced)
            swapped = True
            validation_root.mkdir(mode=0o700)
            replacement_created = True
        return real_uuid4()

    replacement_had_residue = False
    capture_paths.uuid.uuid4 = swap_visible_parent_then_uuid
    try:
        private_root = capture_paths.allocate_private_capture_root(validation_root)
        if not swapped:
            raise SystemExit("Descriptor-allocation test did not swap the visible parent.")
        replacement_had_residue = any(validation_root.iterdir())
        if replacement_had_residue:
            raise SystemExit("Capture allocation touched the replacement visible parent.")
        displaced_stat = os.stat(displaced, follow_symlinks=False)
        if _identity(displaced_stat) != (private_root.parent_dev, private_root.parent_ino):
            raise SystemExit("Capture parent capability did not remain bound to the displaced directory.")
        root_stat = os.stat(
            private_root.basename,
            dir_fd=private_root.parent_fd,
            follow_symlinks=False,
        )
        if _identity(root_stat) != (private_root.dev, private_root.ino):
            raise SystemExit("Capture root was not created beneath the validated parent descriptor.")
    finally:
        capture_paths.uuid.uuid4 = real_uuid4
        if private_root is not None and not private_root.closed:
            cleanup_private_capture_root(private_root)
        if replacement_created and validation_root.exists():
            replacement_had_residue = replacement_had_residue or any(validation_root.iterdir())
            shutil.rmtree(validation_root)
        if swapped and displaced.exists():
            displaced.rename(validation_root)
        if replacement_had_residue:
            raise SystemExit("Replacement visible parent gained unexpected allocation residue.")


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
