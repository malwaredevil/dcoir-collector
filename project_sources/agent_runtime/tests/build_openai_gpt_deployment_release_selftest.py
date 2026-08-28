#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEGACY = ROOT / "project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_core_selftest.py"
SCRIPT = ROOT / "project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py"

LEGACY_SPEC = importlib.util.spec_from_file_location("build_openai_gpt_deployment_release_core_selftest", LEGACY)
if LEGACY_SPEC is None or LEGACY_SPEC.loader is None:
    raise SystemExit("Unable to load core release-builder self-tests")
legacy = importlib.util.module_from_spec(LEGACY_SPEC)
LEGACY_SPEC.loader.exec_module(legacy)

SCRIPT_SPEC = importlib.util.spec_from_file_location("build_openai_gpt_deployment_release", SCRIPT)
if SCRIPT_SPEC is None or SCRIPT_SPEC.loader is None:
    raise SystemExit("Unable to load human-first release builder")
module = importlib.util.module_from_spec(SCRIPT_SPEC)
SCRIPT_SPEC.loader.exec_module(module)


def _config_path(repo: Path, target: str) -> Path:
    return repo / f"project_sources/agent_runtime/generated/packages/{target}/GPT_Configuration.json"


def _instructions_path(repo: Path, target: str) -> Path:
    return repo / f"project_sources/agent_runtime/generated/packages/{target}/Instructions.md"


def _write_config(repo: Path, target: str, mutate) -> None:
    path = _config_path(repo, target)
    value = json.loads(path.read_text(encoding="utf-8"))
    mutate(value)
    path.write_bytes(module._json_bytes(value))


def test_human_first_direct_delivery_shape_and_sync() -> None:
    td, repo = legacy.stage_repo()
    try:
        errors, report = legacy._build(repo, "human")
        assert not errors, errors
        assert report["success"] is True
        zip_path = repo / report["zip_path"]
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
        for delivery_dir, target, knowledge_count in (
            ("AFRICOM_DCOIR_Analyst", "openai_dcoir_analyst", 7),
            ("AFRICOM_USB_Reporting", "openai_usb_reporting", 2),
        ):
            prefix = f"{module.DELIVERY_ROOT_NAME}/{delivery_dir}/"
            assert prefix + module.WEBUI_SETUP_FILE in names
            assert prefix + "GPT_Configuration.json" in names
            assert prefix + "manifest.json" in names
            assert prefix + "Instructions.md" not in names
            root_markdowns = [
                name for name in names
                if name.startswith(prefix)
                and name.endswith(".md")
                and "/Knowledge/" not in name
                and name.count("/") == prefix.count("/")
            ]
            assert root_markdowns == [prefix + module.WEBUI_SETUP_FILE], root_markdowns
            assert sum(name.startswith(prefix + "Knowledge/") for name in names) == knowledge_count

            config = json.loads(_config_path(repo, target).read_text(encoding="utf-8"))
            instructions = _instructions_path(repo, target).read_text(encoding="utf-8")
            setup = (
                repo
                / "project_sources/validation/human"
                / module.DELIVERY_ROOT_NAME
                / delivery_dir
                / module.WEBUI_SETUP_FILE
            )
            knowledge_names = [
                Path(item["path"]).name
                for item in sorted(config["knowledge_files"], key=lambda item: item["order"])
            ]
            assert setup.read_text(encoding="utf-8") == module._webui_setup_markdown(
                config, instructions, knowledge_names
            )
    finally:
        td.cleanup()


def test_description_character_ceiling_fails_closed() -> None:
    td, repo = legacy.stage_repo()
    try:
        _write_config(repo, "openai_dcoir_analyst", lambda value: value.__setitem__("description", "d" * 301))
        errors, report = legacy._build(repo, "description-over")
        assert errors
        assert report["success"] is False
        assert report["zip_path"] is None
        assert any("Description exceeds character ceiling" in error for error in errors), errors
    finally:
        td.cleanup()


def test_instructions_character_ceiling_fails_closed() -> None:
    td, repo = legacy.stage_repo()
    try:
        _instructions_path(repo, "openai_usb_reporting").write_text("i" * 8001, encoding="utf-8")
        errors, report = legacy._build(repo, "instructions-over")
        assert errors
        assert report["success"] is False
        assert report["zip_path"] is None
        assert any("Instructions exceed character ceiling" in error for error in errors), errors
    finally:
        td.cleanup()


def test_exact_character_ceilings_and_nested_fences() -> None:
    td, repo = legacy.stage_repo()
    try:
        _write_config(repo, "openai_dcoir_analyst", lambda value: value.__setitem__("description", "d" * 300))
        instructions = "before\n```\ninside\n```\nafter\n"
        instructions += "i" * (8000 - len(instructions))
        _instructions_path(repo, "openai_dcoir_analyst").write_text(instructions, encoding="utf-8")
        errors, report = legacy._build(repo, "at-boundary")
        assert not errors, errors
        assert report["success"] is True
        target = next(item for item in report["targets"] if item["target_id"] == "openai_dcoir_analyst")
        assert target["description_character_count"] == 300
        assert target["instructions_character_count"] == 8000
        setup_path = (
            repo
            / "project_sources/validation/at-boundary"
            / module.DELIVERY_ROOT_NAME
            / "AFRICOM_DCOIR_Analyst"
            / module.WEBUI_SETUP_FILE
        )
        setup = setup_path.read_text(encoding="utf-8")
        assert "````markdown\n" in setup
        assert "before\n```\ninside\n```\nafter\n" in setup
    finally:
        td.cleanup()


def main() -> int:
    legacy_result = legacy.main()
    if legacy_result != 0:
        return legacy_result
    tests = [
        test_human_first_direct_delivery_shape_and_sync,
        test_description_character_ceiling_fails_closed,
        test_instructions_character_ceiling_fails_closed,
        test_exact_character_ceilings_and_nested_fences,
    ]
    for test in tests:
        test()
    print(json.dumps({"success": True, "human_first_tests": [test.__name__ for test in tests]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
