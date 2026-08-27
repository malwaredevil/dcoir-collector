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
        "capabilities": {},
        "description": "test",
        "conversation_starters": [],
    }
    _write(package_root / "GPT_Configuration.json", module._json_bytes(config))
    _write(package_root / "manifest.json", module._json_bytes({"target_id": target_id}))


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
        test_knowledge_drift_fails_closed,
        test_parity_failure_blocks_release,
        test_source_commit_mismatch_blocks_release,
        test_output_escape_is_rejected,
    ]
    for test in tests:
        test()
    print(json.dumps({"success": True, "tests": [test.__name__ for test in tests]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
