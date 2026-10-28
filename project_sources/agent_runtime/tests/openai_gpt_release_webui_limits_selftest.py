#!/usr/bin/env python3
"""Independent WebUI limits and character counting checks for the governed OpenAI GPT deployment release."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from openai_gpt_release_test_fixture import (
    module,
    stage_repo,
    _build,
    _stage_target,
)

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


def test_package_manifest_integer_type_drift_fails_closed() -> None:
    td, repo = stage_repo()
    try:
        manifest_path = repo / "project_sources/agent_runtime/generated/packages/openai_dcoir_analyst/manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for field in (
            "instruction_character_count",
            "instruction_character_ceiling",
            "description_character_count",
            "description_character_ceiling",
        ):
            manifest[field] = float(manifest[field])
        manifest_path.write_bytes(module._json_bytes(manifest))
        errors, report = _build(repo, "out")
        assert errors
        assert report["success"] is False
        for message in (
            "package manifest instruction character count drift",
            "package manifest instruction ceiling drift",
            "package manifest description character count drift",
            "package manifest description ceiling drift",
        ):
            assert any(message in error for error in errors), errors
        assert report["zip_path"] is None
    finally:
        td.cleanup()


def test_stage_target_uses_webui_safe_counts_for_non_bmp() -> None:
    td = tempfile.TemporaryDirectory(prefix="openai-gpt-release-non-bmp-fixture-")
    repo = Path(td.name)
    try:
        instructions_text = "# Test\n\nInstruction-\U0001F600\n"
        description = "desc-\U0001F600"
        _stage_target(
            repo,
            target_id="openai_dcoir_analyst",
            webui_name="AFRICOM DCOIR Analyst",
            package_dir="project_sources/agent_runtime/generated/packages/openai_dcoir_analyst",
            knowledge_dir="project_sources/agent_runtime/generated/knowledge/openai_dcoir_analyst",
            knowledge_count=7,
            instructions_text=instructions_text,
            description=description,
        )
        manifest = json.loads(
            (
                repo
                / "project_sources/agent_runtime/generated/packages/openai_dcoir_analyst/manifest.json"
            ).read_text(encoding="utf-8")
        )
        assert manifest["instruction_character_count"] == module._webui_character_count(instructions_text)
        assert manifest["description_character_count"] == module._webui_character_count(description)
        assert manifest["instruction_character_count"] == len(instructions_text) + 1
        assert manifest["description_character_count"] == len(description) + 1
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

TESTS = (
    test_description_limit_fails_closed,
    test_instruction_limit_fails_closed,
    test_package_manifest_integer_type_drift_fails_closed,
    test_stage_target_uses_webui_safe_counts_for_non_bmp,
    test_non_bmp_description_uses_webui_safe_counting,
    test_lone_surrogate_description_fails_closed_without_crash,
)

def main() -> int:
    for test in TESTS:
        test()
    print(json.dumps({"success": True, "tests": [test.__name__ for test in TESTS]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
