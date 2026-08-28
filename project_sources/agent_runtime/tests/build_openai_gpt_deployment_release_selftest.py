#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py"
SPEC = importlib.util.spec_from_file_location("build_openai_gpt_deployment_release", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("Unable to load build_openai_gpt_deployment_release.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

SOURCE_COMMIT = "a" * 40


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _stage_target(
    repo: Path,
    *,
    target_id: str,
    webui_name: str,
    package_dir: str,
    knowledge_dir: str,
    knowledge_count: int,
) -> None:
    package_root = repo / package_dir
    knowledge_root = repo / knowledge_dir
    instructions = f"# {webui_name}\n\nGoverned instructions.\n".encode()
    _write(package_root / "Instructions.md", instructions)
    knowledge_files = []
    for order in range(knowledge_count):
        name = f"{order + 1:02d}-knowledge-{order + 1}.md"
        data = f"# Knowledge {order + 1}\n\ncontent-{target_id}-{order}\n".encode()
        path = knowledge_root / name
        _write(path, data)
        knowledge_files.append(
            {
                "id": f"knowledge_{order}",
                "order": order,
                "path": path.relative_to(repo).as_posix(),
                "sha256": _sha(data),
                "bytes": len(data),
            }
        )
    config = {
        "schema": "dcoir.agent_runtime.openai_webui_configuration.v1",
        "target_id": target_id,
        "name": webui_name,
        "runtime_model": "GPT-5.4",
        "instructions_file": (Path(package_dir) / "Instructions.md").as_posix(),
        "knowledge_files": knowledge_files,
        "capabilities": {"web_search": False, "image_generation": True},
        "description": "test",
        "conversation_starters": ["Starter one", "Starter two", "Starter three", "Starter four"],
    }
    _write(package_root / "GPT_Configuration.json", module._json_bytes(config))
    package_manifest = {
        "target_id": target_id,
        "instruction_character_count": len(instructions.decode("utf-8")),
        "instruction_character_ceiling": module.INSTRUCTION_CHARACTER_CEILING,
        "description_character_count": len(config["description"]),
        "description_character_ceiling": module.DESCRIPTION_CHARACTER_CEILING,
    }
    _write(package_root / "manifest.json", module._json_bytes(package_manifest))


def stage_repo() -> tuple[tempfile.TemporaryDirectory, Path]:
    td = tempfile.TemporaryDirectory(prefix="openai-gpt-release-selftest-")
    repo = Path(td.name)
    _stage_target(
        repo,
        target_id="openai_dcoir_analyst",
        webui_name="AFRICOM DCOIR Analyst",
        package_dir="project_sources/agent_runtime/generated/packages/openai_dcoir_analyst",
        knowledge_dir="project_sources/agent_runtime/generated/knowledge/openai_dcoir_analyst",
        knowledge_count=7,
    )
    _stage_target(
        repo,
        target_id="openai_usb_reporting",
        webui_name="AFRICOM USB Reporting",
        package_dir="project_sources/agent_runtime/generated/packages/openai_usb_reporting",
        knowledge_dir="project_sources/agent_runtime/generated/knowledge/openai_usb_reporting",
        knowledge_count=2,
    )
    guide = repo / "project_sources/agent_runtime/docs/Release_Parity_Deployment_Readback.md"
    _write(guide, b"# Agent Release, Parity, Deployment, and Readback\n")
    parity_root = repo / "project_sources/validation/parity"
    parity = {
        "source_commit": SOURCE_COMMIT,
        "static_parity_status": "pass",
        "live_parity_status": "pending_manual_readback",
        "blocking_parity_gaps": [],
    }
    _write(parity_root / module.PARITY_JSON, module._json_bytes(parity))
    _write(parity_root / module.PARITY_MD, b"# Agent Release and Parity Report\n")
    return td, repo


def _build(repo: Path, output_name: str):
    return module.build_release(
        repo,
        repo / "project_sources/validation" / output_name,
        repo / "project_sources/validation/parity",
        source_commit=SOURCE_COMMIT,
    )


def test_combined_delivery_and_determinism() -> None:
    td, repo = stage_repo()
    try:
        errors_a, report_a = _build(repo, "out_a")
        errors_b, report_b = _build(repo, "out_b")
        assert not errors_a, errors_a
        assert not errors_b, errors_b
        zip_a = repo / report_a["zip_path"]
        zip_b = repo / report_b["zip_path"]
        assert zip_a.read_bytes() == zip_b.read_bytes()
        with zipfile.ZipFile(zip_a) as zf:
            names = zf.namelist()
        assert f"{module.DELIVERY_ROOT_NAME}/AFRICOM_DCOIR_Analyst/GPT_Configuration.json" in names
        assert f"{module.DELIVERY_ROOT_NAME}/AFRICOM_USB_Reporting/GPT_Configuration.json" in names
        assert f"{module.DELIVERY_ROOT_NAME}/AFRICOM_DCOIR_Analyst/{module.HUMAN_WEBUI_FILENAME}" in names
        assert f"{module.DELIVERY_ROOT_NAME}/AFRICOM_USB_Reporting/{module.HUMAN_WEBUI_FILENAME}" in names
        assert f"{module.DELIVERY_ROOT_NAME}/AFRICOM_DCOIR_Analyst/Instructions.md" not in names
        assert f"{module.DELIVERY_ROOT_NAME}/AFRICOM_USB_Reporting/Instructions.md" not in names
        assert f"{module.DELIVERY_ROOT_NAME}/delivery_manifest.json" in names
        assert sum(name.startswith(f"{module.DELIVERY_ROOT_NAME}/AFRICOM_DCOIR_Analyst/Knowledge/") for name in names) == 7
        assert sum(name.startswith(f"{module.DELIVERY_ROOT_NAME}/AFRICOM_USB_Reporting/Knowledge/") for name in names) == 2
        manifest = json.loads(
            (repo / "project_sources/validation/out_a" / module.DELIVERY_ROOT_NAME / "delivery_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        assert manifest["source_commit"] == SOURCE_COMMIT
        assert manifest["static_parity_status"] == "pass"
        assert manifest["live_model_parity_claimed"] is False
        assert manifest["manual_webui_deployment_required"] is True
        handoff = (
            repo
            / "project_sources/validation/out_a"
            / module.DELIVERY_ROOT_NAME
            / "AFRICOM_DCOIR_Analyst"
            / module.HUMAN_WEBUI_FILENAME
        ).read_text(encoding="utf-8")
        assert "AFRICOM DCOIR Analyst" in handoff
        assert "Character count: **4 / 300**" in handoff
        assert "Governed instructions." in handoff
        assert handoff.index("01-knowledge-1.md") < handoff.index("07-knowledge-7.md")
    finally:
        td.cleanup()


def test_cross_checkout_root_determinism() -> None:
    td_a, repo_a = stage_repo()
    td_b, repo_b = stage_repo()
    try:
        errors_a, report_a = _build(repo_a, "out")
        errors_b, report_b = _build(repo_b, "out")
        assert not errors_a, errors_a
        assert not errors_b, errors_b
        zip_a = repo_a / report_a["zip_path"]
        zip_b = repo_b / report_b["zip_path"]
        assert zip_a.read_bytes() == zip_b.read_bytes()
        manifest_a = json.loads(
            (repo_a / "project_sources/validation/out" / module.DELIVERY_ROOT_NAME / "delivery_manifest.json").read_text(encoding="utf-8")
        )
        for target in manifest_a["targets"]:
            for record in target["package_files"] + target["knowledge_files"]:
                assert not Path(record["source_path"]).is_absolute(), record
                assert not record["source_path"].startswith(repo_a.as_posix()), record
    finally:
        td_b.cleanup()
        td_a.cleanup()


def test_description_limit_fails_closed() -> None:
    td, repo = stage_repo()
    try:
        config_path = repo / "project_sources/agent_runtime/generated/packages/openai_dcoir_analyst/GPT_Configuration.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["description"] = "x" * (module.DESCRIPTION_CHARACTER_CEILING + 1)
        config_path.write_bytes(module._json_bytes(config))
        manifest_path = config_path.parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["description_character_count"] = len(config["description"])
        manifest_path.write_bytes(module._json_bytes(manifest))
        errors, report = _build(repo, "out")
        assert errors
        assert report["success"] is False
        assert any("Description exceeds 300 characters" in error for error in errors), errors
        assert report["zip_path"] is None
    finally:
        td.cleanup()


def test_instruction_limit_fails_closed() -> None:
    td, repo = stage_repo()
    try:
        package_root = repo / "project_sources/agent_runtime/generated/packages/openai_dcoir_analyst"
        instructions_path = package_root / "Instructions.md"
        instructions = "x" * (module.INSTRUCTION_CHARACTER_CEILING + 1)
        instructions_path.write_text(instructions, encoding="utf-8")
        manifest_path = package_root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["instruction_character_count"] = len(instructions)
        manifest_path.write_bytes(module._json_bytes(manifest))
        errors, report = _build(repo, "out")
        assert errors
        assert report["success"] is False
        assert any("Instructions exceed 8000 characters" in error for error in errors), errors
        assert report["zip_path"] is None
    finally:
        td.cleanup()


def test_non_bmp_description_uses_webui_safe_counting() -> None:
    td, repo = stage_repo()
    try:
        config_path = repo / "project_sources/agent_runtime/generated/packages/openai_dcoir_analyst/GPT_Configuration.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["description"] = ("x" * (module.DESCRIPTION_CHARACTER_CEILING - 1)) + "😀"
        assert len(config["description"]) == module.DESCRIPTION_CHARACTER_CEILING
        assert module._webui_character_count(config["description"]) == module.DESCRIPTION_CHARACTER_CEILING + 1
        config_path.write_bytes(module._json_bytes(config))
        manifest_path = config_path.parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["description_character_count"] = module._webui_character_count(config["description"])
        manifest_path.write_bytes(module._json_bytes(manifest))
        errors, report = _build(repo, "out")
        assert errors
        assert report["success"] is False
        assert any("Description exceeds 300 characters" in error for error in errors), errors
        assert report["zip_path"] is None
    finally:
        td.cleanup()


def test_lone_surrogate_description_fails_closed_without_crash() -> None:
    td, repo = stage_repo()
    try:
        config_path = repo / "project_sources/agent_runtime/generated/packages/openai_dcoir_analyst/GPT_Configuration.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["description"] = "surrogate-" + "\ud800"
        assert module._webui_character_count(config["description"]) == 11
        config_path.write_bytes(module._json_bytes(config))
        manifest_path = config_path.parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["description_character_count"] = module._webui_character_count(config["description"])
        manifest_path.write_bytes(module._json_bytes(manifest))
        errors, report = _build(repo, "out")
        assert errors
        assert report["success"] is False
        assert any("lone UTF-16 surrogate" in error for error in errors), errors
        assert report["zip_path"] is None
    finally:
        td.cleanup()


def test_human_markdown_tracks_json_and_instructions() -> None:
    td, repo = stage_repo()
    try:
        errors, report = _build(repo, "out")
        assert not errors, errors
        root = repo / "project_sources/validation/out" / module.DELIVERY_ROOT_NAME / "AFRICOM_USB_Reporting"
        config = json.loads((repo / "project_sources/agent_runtime/generated/packages/openai_usb_reporting/GPT_Configuration.json").read_text(encoding="utf-8"))
        instructions = (repo / "project_sources/agent_runtime/generated/packages/openai_usb_reporting/Instructions.md").read_text(encoding="utf-8")
        handoff = (root / module.HUMAN_WEBUI_FILENAME).read_text(encoding="utf-8")
        assert config["name"] in handoff
        assert config["description"] in handoff
        assert f"`{config['runtime_model']}`" in handoff
        for capability, enabled in config["capabilities"].items():
            label = module.CAPABILITY_LABELS.get(capability, capability.replace("_", " ").title())
            state = "ON" if enabled is True else "OFF" if enabled is False else "UNSPECIFIED"
            assert f"- {label}: **{state}**" in handoff
        for starter in config["conversation_starters"]:
            assert starter in handoff
        assert instructions in handoff
        knowledge_names = [Path(item["path"]).name for item in config["knowledge_files"]]
        positions = [handoff.index(name) for name in knowledge_names]
        assert positions == sorted(positions)
        target = next(item for item in report["targets"] if item["target_id"] == "openai_usb_reporting")
        assert target["operator_handoff_file"]["delivery_path"].endswith(module.HUMAN_WEBUI_FILENAME)
    finally:
        td.cleanup()


def test_knowledge_drift_fails_closed() -> None:
    td, repo = stage_repo()
    try:
        path = repo / "project_sources/agent_runtime/generated/knowledge/openai_usb_reporting/01-knowledge-1.md"
        path.write_text(path.read_text(encoding="utf-8") + "DRIFT\n", encoding="utf-8")
        errors, report = _build(repo, "out")
        assert errors
        assert report["success"] is False
        assert any("Knowledge hash/size drift" in error for error in errors), errors
        assert report["zip_path"] is None
    finally:
        td.cleanup()


def test_parity_failure_blocks_release() -> None:
    td, repo = stage_repo()
    try:
        parity_path = repo / "project_sources/validation/parity" / module.PARITY_JSON
        parity = json.loads(parity_path.read_text(encoding="utf-8"))
        parity["static_parity_status"] = "fail"
        parity["blocking_parity_gaps"] = [{"message": "seeded gap"}]
        parity_path.write_bytes(module._json_bytes(parity))
        errors, report = _build(repo, "out")
        assert errors
        assert report["success"] is False
        assert any("not statically clean" in error for error in errors), errors
        assert any("blocking gaps" in error for error in errors), errors
    finally:
        td.cleanup()


def test_source_commit_mismatch_blocks_release() -> None:
    td, repo = stage_repo()
    try:
        parity_path = repo / "project_sources/validation/parity" / module.PARITY_JSON
        parity = json.loads(parity_path.read_text(encoding="utf-8"))
        parity["source_commit"] = "b" * 40
        parity_path.write_bytes(module._json_bytes(parity))
        errors, report = _build(repo, "out")
        assert errors
        assert report["success"] is False
        assert any("source commit mismatch" in error for error in errors), errors
    finally:
        td.cleanup()


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
        resolved = module._resolve_repo_path(
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


def main() -> int:
    tests = [
        test_combined_delivery_and_determinism,
        test_cross_checkout_root_determinism,
        test_description_limit_fails_closed,
        test_instruction_limit_fails_closed,
        test_non_bmp_description_uses_webui_safe_counting,
        test_lone_surrogate_description_fails_closed_without_crash,
        test_human_markdown_tracks_json_and_instructions,
        test_knowledge_drift_fails_closed,
        test_parity_failure_blocks_release,
        test_source_commit_mismatch_blocks_release,
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
    ]
    for test in tests:
        test()
    print(json.dumps({"success": True, "tests": [test.__name__ for test in tests]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
