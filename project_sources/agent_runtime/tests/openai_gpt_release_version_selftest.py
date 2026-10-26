#!/usr/bin/env python3
"""Independent WebUI paste-safe handoff and version-override tests (Issue 428)."""
from __future__ import annotations

import json
from pathlib import Path
from openai_gpt_release_test_fixture import module, SOURCE_COMMIT, stage_repo

def _build(repo: Path, output_name: str, *, version: str | None = None):
    return module.build_release(
        repo,
        repo / "project_sources/validation" / output_name,
        repo / "project_sources/validation/parity",
        source_commit=SOURCE_COMMIT,
        version=version,
    )


def test_crlf_expansion_count() -> None:
    value = "A\nB\n"
    assert module._webui_character_count(value) == 4
    assert module._webui_paste_safe_character_count(value) == 6
    already_crlf = "A\r\nB\r\n"
    assert module._webui_paste_safe_character_count(already_crlf) == 6


def test_crlf_expansion_can_fail_when_lf_count_is_at_limit() -> None:
    td, repo = stage_repo()
    try:
        package_root = repo / "project_sources/agent_runtime/generated/packages/openai_dcoir_analyst"
        instructions = "x\n" * (module.INSTRUCTION_CHARACTER_CEILING // 2)
        assert module._webui_character_count(instructions) == module.INSTRUCTION_CHARACTER_CEILING
        assert module._webui_paste_safe_character_count(instructions) > module.INSTRUCTION_CHARACTER_CEILING
        (package_root / "Instructions.md").write_text(instructions, encoding="utf-8", newline="")
        manifest_path = package_root / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["instruction_character_count"] = module._webui_character_count(instructions)
        manifest_path.write_bytes(module._json_bytes(manifest))
        errors, report = _build(repo, "out")
        assert report["success"] is False
        assert any("paste-safe characters after CRLF expansion" in error for error in errors), errors
        assert report["zip_path"] is None
    finally:
        td.cleanup()


def test_version_override_controls_zip_and_manifest_identity() -> None:
    td, repo = stage_repo()
    try:
        errors, report = _build(repo, "out", version="3_0_1")
        assert not errors, errors
        assert report["bundle_version"] == "3_0_1"
        zip_path = repo / report["zip_path"]
        assert zip_path.name == "DCOIR_OpenAI_GPT_Deployment_Packages_3_0_1.zip"
        manifest = json.loads(
            (repo / "project_sources/validation/out" / module.DELIVERY_ROOT_NAME / "delivery_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        assert manifest["bundle_version"] == "3_0_1"
    finally:
        td.cleanup()


def test_default_zip_identity_remains_source_commit() -> None:
    td, repo = stage_repo()
    try:
        errors, report = _build(repo, "out")
        assert not errors, errors
        assert report["bundle_version"] is None
        assert Path(report["zip_path"]).name == (
            f"DCOIR_OpenAI_GPT_Deployment_Packages_{SOURCE_COMMIT[:12]}.zip"
        )
    finally:
        td.cleanup()


def test_invalid_version_override_fails_closed() -> None:
    td, repo = stage_repo()
    try:
        errors, report = _build(repo, "out", version="../unsafe")
        assert errors
        assert report["success"] is False
        assert report["zip_path"] is None
        assert any("bundle version override must match" in error for error in errors), errors
    finally:
        td.cleanup()


def test_operator_handoff_reports_paste_safe_count() -> None:
    td, repo = stage_repo()
    try:
        errors, report = _build(repo, "out")
        assert not errors, errors
        handoff = (
            repo
            / "project_sources/validation/out"
            / module.DELIVERY_ROOT_NAME
            / "AFRICOM_DCOIR_Analyst"
            / module.HUMAN_WEBUI_FILENAME
        ).read_text(encoding="utf-8")
        instructions = (
            repo
            / "project_sources/agent_runtime/generated/packages/openai_dcoir_analyst/Instructions.md"
        ).read_text(encoding="utf-8")
        paste_safe = module._webui_paste_safe_character_count(instructions)
        source_count = module._webui_character_count(instructions)
        assert f"Paste-safe character count (Windows CRLF): **{paste_safe} / 8000**" in handoff
        assert f"Source character count (LF): **{source_count}**" in handoff
        assert "Copy only the text inside the fenced block" in handoff
    finally:
        td.cleanup()

TESTS = (
    test_crlf_expansion_count,
    test_crlf_expansion_can_fail_when_lf_count_is_at_limit,
    test_version_override_controls_zip_and_manifest_identity,
    test_default_zip_identity_remains_source_commit,
    test_invalid_version_override_fails_closed,
    test_operator_handoff_reports_paste_safe_count,
)

def main() -> int:
    for test in TESTS:
        test()
    print(json.dumps({"success": True, "tests": [test.__name__ for test in TESTS]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
