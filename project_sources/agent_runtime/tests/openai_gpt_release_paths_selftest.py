#!/usr/bin/env python3
"""Independent filesystem/path safety checks for the governed OpenAI GPT deployment release."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from openai_gpt_release_test_fixture import (
    SOURCE_COMMIT,
    module,
    stage_repo,
)

def test_unsafe_existing_delivery_root_fails_closed() -> None:
    td, repo = stage_repo()
    try:
        output_dir = repo / "project_sources/validation/out"
        output_dir.mkdir(parents=True, exist_ok=True)
        unsafe = output_dir / module.DELIVERY_ROOT_NAME
        unsafe.write_text("do-not-overwrite\n", encoding="utf-8")
        errors, report = module.build_release(
            repo,
            output_dir,
            repo / "project_sources/validation/parity",
            source_commit=SOURCE_COMMIT,
        )
        assert errors
        assert report["success"] is False
        assert report["zip_path"] is None
        assert any("Unsafe existing delivery root" in error for error in errors), errors
        assert unsafe.is_file()
        assert unsafe.read_text(encoding="utf-8") == "do-not-overwrite\n"
    finally:
        td.cleanup()


def test_existing_delivery_root_symlink_fails_closed_when_supported() -> None:
    td, repo = stage_repo()
    try:
        output_dir = repo / "project_sources/validation/out"
        output_dir.mkdir(parents=True, exist_ok=True)
        target = repo / "project_sources/validation/symlink-target"
        target.mkdir(parents=True, exist_ok=True)
        marker = target / "marker.txt"
        marker.write_text("preserve\n", encoding="utf-8")
        link = output_dir / module.DELIVERY_ROOT_NAME
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        errors, report = module.build_release(
            repo,
            output_dir,
            repo / "project_sources/validation/parity",
            source_commit=SOURCE_COMMIT,
        )
        assert errors
        assert report["success"] is False
        assert report["zip_path"] is None
        assert any("Unsafe existing delivery root" in error for error in errors), errors
        assert link.is_symlink()
        assert marker.read_text(encoding="utf-8") == "preserve\n"
        assert sorted(path.name for path in target.iterdir()) == ["marker.txt"]
    finally:
        td.cleanup()


def test_copy_record_rejects_destination_escape() -> None:
    td, repo = stage_repo()
    try:
        delivery_root = repo / "project_sources/validation/delivery"
        delivery_root.mkdir(parents=True, exist_ok=True)
        source = repo / "source.txt"
        source.write_text("source\n", encoding="utf-8")
        outside = repo / "project_sources/validation/outside.txt"
        errors: list[str] = []
        record = module._copy_record(
            source,
            outside,
            delivery_root,
            repo,
            errors,
        )
        assert record is None
        assert errors
        assert any("escapes its allowed output root" in error for error in errors), errors
        assert not outside.exists()
    finally:
        td.cleanup()


def test_copy_record_rejects_symlink_source_when_supported() -> None:
    td, repo = stage_repo()
    try:
        delivery_root = repo / "project_sources/validation/delivery"
        delivery_root.mkdir(parents=True, exist_ok=True)
        target = repo / "source-target.txt"
        target.write_text("target\n", encoding="utf-8")
        source = repo / "source-link.txt"
        try:
            source.symlink_to(target)
        except (OSError, NotImplementedError):
            return
        destination = delivery_root / "copied.txt"
        errors: list[str] = []
        record = module._copy_record(
            source,
            destination,
            delivery_root,
            repo,
            errors,
        )
        assert record is None
        assert errors
        assert any("Missing or unsafe source file" in error for error in errors), errors
        assert not destination.exists()
    finally:
        td.cleanup()


def test_repo_source_resolver_rejects_symlink_component_when_supported() -> None:
    td, repo = stage_repo()
    try:
        target_dir = repo / "real-source"
        target_dir.mkdir(parents=True, exist_ok=True)
        link_dir = repo / "linked-source"
        try:
            link_dir.symlink_to(target_dir, target_is_directory=True)
        except (OSError, NotImplementedError):
            return
        errors: list[str] = []
        resolved = module._resolve_inside(
            repo,
            "linked-source",
            errors,
            "test source",
        )
        assert resolved is None
        assert errors
        assert any("must not traverse a symlink" in error for error in errors), errors
    finally:
        td.cleanup()


def test_deterministic_zip_rejects_symlinked_delivery_file_when_supported() -> None:
    td, repo = stage_repo()
    try:
        delivery_root = repo / "project_sources/validation/delivery"
        delivery_root.mkdir(parents=True, exist_ok=True)
        (delivery_root / "regular.txt").write_text("regular\n", encoding="utf-8")
        target = repo / "project_sources/validation/outside-target.txt"
        target.write_text("outside\n", encoding="utf-8")
        link = delivery_root / "linked.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            return
        zip_path = repo / "project_sources/validation/delivery.zip"
        errors: list[str] = []
        written = module._write_deterministic_zip(delivery_root, zip_path, errors)
        assert written is False
        assert errors
        assert any("Unsafe symlink in delivery tree" in error for error in errors), errors
        assert not zip_path.exists()
    finally:
        td.cleanup()


def test_existing_report_output_directory_fails_closed() -> None:
    td, repo = stage_repo()
    try:
        output_dir = repo / "project_sources/validation/out"
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "build_openai_gpt_deployment_release_report.json"
        report_path.mkdir()
        errors, report = module.build_release(
            repo,
            output_dir,
            repo / "project_sources/validation/parity",
            source_commit=SOURCE_COMMIT,
        )
        assert errors
        assert report["success"] is False
        assert report["zip_path"] is None
        assert any("build report must be a regular file or absent" in error for error in errors), errors
        assert report_path.is_dir()
        assert not (output_dir / module.DELIVERY_ROOT_NAME).exists()
    finally:
        td.cleanup()


def test_existing_zip_output_directory_fails_closed() -> None:
    td, repo = stage_repo()
    try:
        output_dir = repo / "project_sources/validation/out"
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_name = f"DCOIR_OpenAI_GPT_Deployment_Packages_{SOURCE_COMMIT[:12]}.zip"
        zip_path = output_dir / zip_name
        zip_path.mkdir()
        errors, report = module.build_release(
            repo,
            output_dir,
            repo / "project_sources/validation/parity",
            source_commit=SOURCE_COMMIT,
        )
        assert errors
        assert report["success"] is False
        assert report["zip_path"] is None
        assert any("delivery ZIP must be a regular file or absent" in error for error in errors), errors
        assert zip_path.is_dir()
        assert not (output_dir / module.DELIVERY_ROOT_NAME).exists()
    finally:
        td.cleanup()


def test_output_leaf_symlink_fails_closed_when_supported() -> None:
    td, repo = stage_repo()
    try:
        root = repo / "project_sources/validation/out"
        root.mkdir(parents=True, exist_ok=True)
        target = repo / "project_sources/validation/target.txt"
        target.write_text("preserve\n", encoding="utf-8")
        link = root / "report.json"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            return
        errors: list[str] = []
        safe = module._validate_output_path(root, link, errors, "test output")
        assert safe is None
        assert any("must not be a symlink" in error for error in errors), errors
        assert target.read_text(encoding="utf-8") == "preserve\n"
    finally:
        td.cleanup()


def test_output_escape_is_rejected() -> None:
    td, repo = stage_repo()
    outside = tempfile.TemporaryDirectory(prefix="openai-gpt-release-outside-")
    try:
        errors, report = module.build_release(
            repo,
            Path(outside.name),
            repo / "project_sources/validation/parity",
            source_commit=SOURCE_COMMIT,
        )
        assert errors
        assert report["success"] is False
        assert report["delivery_root"] is None
        assert report["zip_path"] is None
        assert any("output_dir must be" in error for error in errors), errors
        assert not (Path(outside.name) / module.DELIVERY_ROOT_NAME).exists()
    finally:
        outside.cleanup()
        td.cleanup()

TESTS = (
    test_unsafe_existing_delivery_root_fails_closed,
    test_existing_delivery_root_symlink_fails_closed_when_supported,
    test_copy_record_rejects_destination_escape,
    test_copy_record_rejects_symlink_source_when_supported,
    test_repo_source_resolver_rejects_symlink_component_when_supported,
    test_deterministic_zip_rejects_symlinked_delivery_file_when_supported,
    test_existing_report_output_directory_fails_closed,
    test_existing_zip_output_directory_fails_closed,
    test_output_leaf_symlink_fails_closed_when_supported,
    test_output_escape_is_rejected,
)

def main() -> int:
    for test in TESTS:
        test()
    print(json.dumps({"success": True, "tests": [test.__name__ for test in TESTS]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
