#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CORE_PATH = Path(__file__).with_name("build_openai_gpt_deployment_release_core.py")
SPEC = importlib.util.spec_from_file_location("build_openai_gpt_deployment_release_core", CORE_PATH)
if SPEC is None or SPEC.loader is None:
    raise SystemExit("Unable to load build_openai_gpt_deployment_release_core.py")
_core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(_core)

# Preserve the original builder API for existing tests and callers.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

WEBUI_SETUP_FILE = "GPT_WebUI_Setup.md"
DESCRIPTION_CHARACTER_CEILING = 300
INSTRUCTIONS_CHARACTER_CEILING = 8000


def _webui_character_count(value: str) -> int:
    """Count UTF-16 code units, conservatively matching browser-style string limits."""
    return len(value.encode("utf-16-le")) // 2


def _max_backtick_run(text: str) -> int:
    longest = 0
    current = 0
    for character in text:
        if character == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _fenced_value(value: str, language: str = "text") -> str:
    fence = "`" * max(3, _max_backtick_run(value) + 1)
    normalized = value if value.endswith("\n") else value + "\n"
    return f"{fence}{language}\n{normalized}{fence}"


def _webui_setup_markdown(
    config: dict[str, Any],
    instructions: str,
    knowledge_names: list[str],
) -> str:
    description = config["description"]
    starters = config["conversation_starters"]
    capabilities = config["capabilities"]
    description_count = _webui_character_count(description)
    instructions_count = _webui_character_count(instructions)
    lines = [
        f"# {config['name']} - GPT WebUI Setup",
        "",
        "This is the single human-facing setup file for this GPT. It is generated from the validated JSON configuration, exact Instructions, and ordered Knowledge list. Do not hand-edit it.",
        "",
        "Use this file from top to bottom in the ChatGPT GPT editor. `GPT_Configuration.json` and `manifest.json` remain machine-readable validation evidence and are not the normal copy/paste surface.",
        "",
        "## Field-limit readback",
        "",
        f"- Description: **{description_count} / {DESCRIPTION_CHARACTER_CEILING} characters** (governed package ceiling)",
        f"- Instructions: **{instructions_count} / {INSTRUCTIONS_CHARACTER_CEILING} characters** (hard package ceiling)",
        "",
        "## 1. Name / Title",
        "",
        _fenced_value(config["name"]),
        "",
        "## 2. Description",
        "",
        _fenced_value(description),
        "",
        "## 3. Instructions",
        "",
        "Copy the complete contents of the block below into the GPT Instructions field. The character count above applies only to the block contents, not this setup file.",
        "",
        _fenced_value(instructions, "markdown"),
        "",
        "## 4. Conversation starters",
        "",
    ]
    for index, starter in enumerate(starters, start=1):
        lines.extend([f"### Starter {index}", "", _fenced_value(starter), ""])
    lines.extend(
        [
            "## 5. Recommended model / runtime",
            "",
            _fenced_value(config["runtime_model"]),
            "",
            "## 6. Capabilities",
            "",
            "Apply these settings exactly unless a separately governed capability change supersedes this package.",
            "",
            "| Capability | State |",
            "| --- | --- |",
        ]
    )
    for capability in sorted(capabilities):
        lines.append(f"| `{capability}` | {'ON' if capabilities[capability] else 'OFF'} |")
    lines.extend(
        [
            "",
            "## 7. Knowledge attachments",
            "",
            f"Upload exactly these **{len(knowledge_names)}** files from this target's `Knowledge/` folder, in this order:",
            "",
        ]
    )
    for index, name in enumerate(knowledge_names, start=1):
        lines.append(f"{index}. `{name}`")
    lines.extend(
        [
            "",
            "## 8. Save and read back",
            "",
            "Save/update the existing GPT, then verify the target name, model/runtime, Description, conversation starters, capability states, complete Instructions, and Knowledge filenames/count against this file before claiming live deployment complete.",
            "",
        ]
    )
    return "\n".join(lines)


def _prevalidate_webui_inputs(repo_root: Path) -> tuple[list[str], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    inputs: dict[str, dict[str, Any]] = {}
    for target in TARGETS:
        target_id = target["target_id"]
        package_root = _resolve_repo_path(repo_root, target["package_root"], errors, f"{target_id} package root")
        if package_root is None:
            continue
        config_path = package_root / "GPT_Configuration.json"
        instructions_path = package_root / "Instructions.md"
        config = _load_json(config_path, errors, f"{target_id} configuration")
        description = config.get("description")
        if not isinstance(description, str) or not description.strip():
            errors.append(f"{target_id} Description must be a non-empty string")
        else:
            description_count = _webui_character_count(description)
            if description_count > DESCRIPTION_CHARACTER_CEILING:
                errors.append(
                    f"{target_id} Description exceeds character ceiling: "
                    f"{description_count} > {DESCRIPTION_CHARACTER_CEILING}"
                )
        starters = config.get("conversation_starters")
        if not isinstance(starters, list) or not starters or not all(
            isinstance(value, str) and value for value in starters
        ):
            errors.append(f"{target_id} conversation_starters must be a non-empty array of strings")
        capabilities = config.get("capabilities")
        if not isinstance(capabilities, dict) or not all(
            isinstance(key, str) and type(value) is bool for key, value in capabilities.items()
        ):
            errors.append(f"{target_id} capabilities must be a boolean-valued object")
        instructions = ""
        if instructions_path.is_symlink() or not instructions_path.is_file():
            errors.append(f"Missing or unsafe {target_id} Instructions: {instructions_path.as_posix()}")
        else:
            try:
                instructions = instructions_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                errors.append(f"{target_id} Instructions must be UTF-8")
            else:
                instructions_count = _webui_character_count(instructions)
                if instructions_count > INSTRUCTIONS_CHARACTER_CEILING:
                    errors.append(
                        f"{target_id} Instructions exceed character ceiling: "
                        f"{instructions_count} > {INSTRUCTIONS_CHARACTER_CEILING}"
                    )
        inputs[target_id] = {
            "config_path": config_path,
            "instructions_path": instructions_path,
            "config": config,
            "instructions": instructions,
        }
    return errors, inputs


def _failure_report(repo_root: Path, source_commit: str | None, errors: list[str]) -> dict[str, Any]:
    return {
        "schema": REPORT_SCHEMA,
        "success": False,
        "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": _source_commit(repo_root, source_commit),
        "delivery_root": None,
        "zip_path": None,
        "zip_sha256": None,
        "target_count": 0,
        "targets": [],
        "static_parity_status": None,
        "live_parity_status": None,
        "errors": errors,
    }


def _delivery_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# OpenAI GPT deployment package manifest",
        "",
        f"- source_commit: `{manifest['source_commit']}`",
        f"- static_parity_status: **{manifest['static_parity_status']}**",
        f"- live_parity_status: **{manifest['live_parity_status']}**",
        "- live_model_parity_claimed: `false`",
        "- manual_webui_deployment_required: `true`",
        "",
        "## Targets",
        "",
    ]
    for target in manifest["targets"]:
        setup = target.get("webui_setup_file") or {}
        lines.extend(
            [
                f"### {target['webui_name']}",
                "",
                f"- target_id: `{target['target_id']}`",
                f"- runtime_model: `{target['runtime_model']}`",
                f"- WebUI setup: `{setup.get('delivery_path', 'unavailable')}`",
                f"- Description characters: {target.get('description_character_count')} / {DESCRIPTION_CHARACTER_CEILING}",
                f"- Instructions characters: {target.get('instructions_character_count')} / {INSTRUCTIONS_CHARACTER_CEILING}",
                f"- Knowledge files: {target['knowledge_file_count']}",
                f"- delivery_directory: `{target['delivery_directory']}`",
                "",
            ]
        )
    lines.extend(
        [
            "Each target folder exposes one human-facing `GPT_WebUI_Setup.md`; JSON and manifests remain machine-readable evidence.",
            "Generated deployment files are not canonical editable source.",
            "OpenAI WebUI deployment and live behavior remain manual evidence steps.",
            "",
        ]
    )
    return "\n".join(lines)


def build_release(
    repo_root: Path,
    output_dir: Path,
    parity_root: Path,
    *,
    source_commit: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    repo_root = repo_root.resolve()
    pre_errors, inputs = _prevalidate_webui_inputs(repo_root)
    if pre_errors:
        return pre_errors, _failure_report(repo_root, source_commit, pre_errors)

    errors, report = _core.build_release(
        repo_root,
        output_dir,
        parity_root,
        source_commit=source_commit,
    )
    if errors:
        return errors, report

    delivery_root = repo_root / report["delivery_root"]
    zip_path = repo_root / report["zip_path"]
    targets_by_id = {target["target_id"]: target for target in TARGETS}

    for target_report in report["targets"]:
        target_id = target_report["target_id"]
        target = targets_by_id[target_id]
        target_input = inputs[target_id]
        destination_root = delivery_root / target["delivery_dir"]
        old_instructions = destination_root / "Instructions.md"
        if old_instructions.is_symlink() or not old_instructions.is_file():
            errors.append(f"Expected direct-delivery Instructions file is missing or unsafe for {target_id}")
            continue
        old_instructions.unlink()
        target_report["package_files"] = [
            record
            for record in target_report["package_files"]
            if record.get("delivery_path") != f"{target['delivery_dir']}/Instructions.md"
        ]

        knowledge_records = sorted(target_report["knowledge_files"], key=lambda item: item.get("order", -1))
        knowledge_names = [Path(record["delivery_path"]).name for record in knowledge_records]
        setup_text = _webui_setup_markdown(
            target_input["config"],
            target_input["instructions"],
            knowledge_names,
        )
        setup_path = destination_root / WEBUI_SETUP_FILE
        if not _write_output_bytes(
            delivery_root,
            setup_path,
            setup_text.encode("utf-8"),
            errors,
            f"{target_id} WebUI setup Markdown",
        ):
            continue

        # Re-read every source after writing and require exact regeneration.
        sync_errors: list[str] = []
        sync_config = _load_json(target_input["config_path"], sync_errors, f"{target_id} sync configuration")
        try:
            sync_instructions = target_input["instructions_path"].read_text(encoding="utf-8")
        except (FileNotFoundError, UnicodeDecodeError):
            sync_errors.append(f"{target_id} sync Instructions are unavailable or invalid")
            sync_instructions = ""
        sync_knowledge = sync_config.get("knowledge_files")
        if not isinstance(sync_knowledge, list):
            sync_errors.append(f"{target_id} sync knowledge_files must be an array")
            sync_names: list[str] = []
        else:
            sync_names = [Path(item.get("path", "")).name for item in sync_knowledge if isinstance(item, dict)]
        if sync_names != knowledge_names:
            sync_errors.append(f"{target_id} Knowledge filenames changed during setup generation")
        expected_setup = _webui_setup_markdown(sync_config, sync_instructions, sync_names) if not sync_errors else ""
        if sync_errors or setup_path.read_text(encoding="utf-8") != expected_setup:
            errors.extend(sync_errors)
            errors.append(f"{target_id} WebUI setup Markdown is not synchronized with JSON/Instructions/Knowledge inputs")
            continue

        setup_bytes = setup_path.read_bytes()
        setup_record = {
            "delivery_path": setup_path.relative_to(delivery_root).as_posix(),
            "source_path": target_input["config_path"].relative_to(repo_root).as_posix(),
            "derived_from": [
                target_input["config_path"].relative_to(repo_root).as_posix(),
                target_input["instructions_path"].relative_to(repo_root).as_posix(),
                *[record["source_path"] for record in knowledge_records],
            ],
            "sha256": _sha256_bytes(setup_bytes),
            "bytes": len(setup_bytes),
        }
        target_report["package_files"].append(setup_record)
        target_report["webui_setup_file"] = setup_record
        target_report["description_character_count"] = _webui_character_count(sync_config["description"])
        target_report["description_character_ceiling"] = DESCRIPTION_CHARACTER_CEILING
        target_report["instructions_character_count"] = _webui_character_count(sync_instructions)
        target_report["instructions_character_ceiling"] = INSTRUCTIONS_CHARACTER_CEILING

        root_markdowns = sorted(path.name for path in destination_root.glob("*.md") if path.is_file())
        if root_markdowns != [WEBUI_SETUP_FILE]:
            errors.append(
                f"{target_id} must expose exactly one human-facing Markdown at target root: "
                f"{root_markdowns}"
            )

    manifest_path = delivery_root / "delivery_manifest.json"
    manifest = _load_json(manifest_path, errors, "delivery manifest")
    manifest["targets"] = report["targets"]
    _write_output_bytes(
        delivery_root,
        manifest_path,
        _json_bytes(manifest),
        errors,
        "delivery manifest JSON",
    )
    _write_output_bytes(
        delivery_root,
        delivery_root / "delivery_manifest.md",
        _delivery_markdown(manifest).encode("utf-8"),
        errors,
        "delivery manifest Markdown",
    )

    if zip_path.exists():
        zip_path.unlink()
    if not errors:
        _write_deterministic_zip(delivery_root, zip_path, errors)

    report["success"] = not errors
    report["zip_path"] = zip_path.relative_to(repo_root).as_posix() if zip_path.exists() else None
    report["zip_sha256"] = _sha256_file(zip_path) if zip_path.exists() else None
    report["errors"] = errors
    report_path = Path(output_dir).resolve() / "build_openai_gpt_deployment_release_report.json"
    _write_output_bytes(
        Path(output_dir).resolve(),
        report_path,
        _json_bytes(report),
        errors,
        "build report",
    )
    if errors and zip_path.exists():
        zip_path.unlink()
        report["success"] = False
        report["zip_path"] = None
        report["zip_sha256"] = None
        report["errors"] = errors
        _write_output_bytes(
            Path(output_dir).resolve(),
            report_path,
            _json_bytes(report),
            errors,
            "build report",
        )
    return errors, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build one deterministic human-first manual-deployment ZIP containing both governed OpenAI GPT packages."
    )
    default_repo = Path(__file__).resolve().parents[3]
    parser.add_argument("--repo-root", type=Path, default=default_repo)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("project_sources/validation/out_openai_gpt_deployment"),
    )
    parser.add_argument(
        "--parity-root",
        type=Path,
        default=Path("project_sources/validation/out_openai_gpt_deployment/parity"),
    )
    parser.add_argument("--source-commit")
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir if args.output_dir.is_absolute() else repo_root / args.output_dir
    parity_root = args.parity_root if args.parity_root.is_absolute() else repo_root / args.parity_root
    errors, report = build_release(
        repo_root,
        output_dir,
        parity_root,
        source_commit=args.source_commit,
    )
    print(json.dumps(report, indent=2), file=sys.stderr if errors else sys.stdout)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
