#!/usr/bin/env python3
"""Independent deterministic payload and parity checks for the governed OpenAI GPT deployment release."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from openai_gpt_release_test_fixture import (
    SOURCE_COMMIT,
    module,
    stage_repo,
    _build,
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
        assert sum(name.startswith(f"{module.DELIVERY_ROOT_NAME}/AFRICOM_USB_Reporting/Knowledge/") for name in names) == 1
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

TESTS = (
    test_combined_delivery_and_determinism,
    test_cross_checkout_root_determinism,
    test_human_markdown_tracks_json_and_instructions,
    test_knowledge_drift_fails_closed,
    test_parity_failure_blocks_release,
    test_source_commit_mismatch_blocks_release,
)

def main() -> int:
    for test in TESTS:
        test()
    print(json.dumps({"success": True, "tests": [test.__name__ for test in TESTS]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
