#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "dcoir.agent_runtime.openai_gpt_deployment_release.v1"
REPORT_SCHEMA = "dcoir.agent_runtime.openai_gpt_deployment_release_report.v1"
DELIVERY_ROOT_NAME = "OpenAI_GPT_Deployment_Packages"
PARITY_JSON = "agent_release_parity_report.json"
PARITY_MD = "agent_release_parity_report.md"
GUIDE = Path("project_sources/agent_runtime/docs/Release_Parity_Deployment_Readback.md")
HUMAN_WEBUI_FILENAME = "GPT_WebUI_Configuration.md"
INSTRUCTION_CHARACTER_CEILING = 8000
DESCRIPTION_CHARACTER_CEILING = 300
CAPABILITY_LABELS = {
    "web_search": "Web search",
    "code_interpreter_data_analysis": "Code Interpreter / Data Analysis",
    "canvas": "Canvas",
    "image_generation": "Image generation",
    "apps": "Apps",
    "actions": "Actions",
    "live_elastic_access": "Live Elastic access",
    "live_collector_execution": "Live collector execution",
    "github_supabase_connectors": "GitHub / Supabase connectors",
    "persistent_cross_conversation_memory": "Persistent cross-conversation memory",
}
TARGETS = (
    {
        "target_id": "openai_dcoir_analyst",
        "webui_name": "AFRICOM DCOIR Analyst",
        "delivery_dir": "AFRICOM_DCOIR_Analyst",
        "package_root": Path("project_sources/agent_runtime/generated/packages/openai_dcoir_analyst"),
        "knowledge_root": Path("project_sources/agent_runtime/generated/knowledge/openai_dcoir_analyst"),
        "knowledge_count": 7,
    },
    {
        "target_id": "openai_usb_reporting",
        "webui_name": "AFRICOM USB Reporting",
        "delivery_dir": "AFRICOM_USB_Reporting",
        "package_root": Path("project_sources/agent_runtime/generated/packages/openai_usb_reporting"),
        "knowledge_root": Path("project_sources/agent_runtime/generated/knowledge/openai_usb_reporting"),
        "knowledge_count": 2,
    },
)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _webui_character_count(value: str) -> int:
    """Count UTF-16 code units conservatively for browser-style WebUI limits."""
    return len(value.encode("utf-16-le", errors="surrogatepass")) // 2


def _load_json(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"Missing {label}: {path.as_posix()}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON in {label} {path.as_posix()}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} must be a JSON object: {path.as_posix()}")
        return {}
    return value


def _resolve_inside(root: Path, relative: str | Path, errors: list[str], label: str) -> Path | None:
    value = Path(relative)
    if value.is_absolute() or ".." in value.parts:
        errors.append(f"{label} must be repository-relative without traversal: {relative}")
        return None
    try:
        resolved_root = root.resolve()
        lexical_candidate = resolved_root
        for part in value.parts:
            lexical_candidate = lexical_candidate / part
            if lexical_candidate.is_symlink():
                errors.append(f"{label} must not traverse a symlink: {relative}")
                return None
        candidate = lexical_candidate.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        errors.append(f"{label} could not be resolved: {type(exc).__name__}: {exc}")
        return None
    if not candidate.is_relative_to(resolved_root):
        errors.append(f"{label} escapes its allowed root: {relative}")
        return None
    return candidate


def _resolve_repo_path(repo_root: Path, relative: str | Path, errors: list[str], label: str) -> Path | None:
    return _resolve_inside(repo_root, relative, errors, label)


def _validate_output_path(
    root: Path,
    destination: Path,
    errors: list[str],
    label: str,
) -> Path | None:
    try:
        resolved_root = root.resolve()
        resolved_parent = destination.parent.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        errors.append(f"{label} could not be resolved safely: {type(exc).__name__}: {exc}")
        return None
    if not resolved_parent.is_relative_to(resolved_root):
        errors.append(f"{label} escapes its allowed output root: {destination.as_posix()}")
        return None
    if destination.is_symlink():
        errors.append(f"{label} must not be a symlink: {destination.as_posix()}")
        return None
    if destination.exists() and not destination.is_file():
        errors.append(f"{label} must be a regular file or absent: {destination.as_posix()}")
        return None
    return destination


def _write_output_bytes(
    root: Path,
    destination: Path,
    data: bytes,
    errors: list[str],
    label: str,
) -> bool:
    safe_destination = _validate_output_path(root, destination, errors, label)
    if safe_destination is None:
        return False
    safe_destination.parent.mkdir(parents=True, exist_ok=True)
    safe_destination.write_bytes(data)
    return True


def _source_commit(repo_root: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    github_sha = os.environ.get("GITHUB_SHA")
    if github_sha:
        return github_sha
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        completed = None
    if completed and completed.returncode == 0 and completed.stdout.strip():
        return completed.stdout.strip()
    return "unknown"


def _copy_record(
    source: Path,
    destination: Path,
    delivery_root: Path,
    repo_root: Path,
    errors: list[str],
) -> dict[str, Any] | None:
    if source.is_symlink() or not source.is_file():
        errors.append(f"Missing or unsafe source file: {source.as_posix()}")
        return None
    data = source.read_bytes()
    if not _write_output_bytes(
        delivery_root,
        destination,
        data,
        errors,
        "delivery file",
    ):
        return None
    return {
        "delivery_path": destination.relative_to(delivery_root).as_posix(),
        "source_path": source.relative_to(repo_root).as_posix(),
        "sha256": _sha256_bytes(data),
        "bytes": len(data),
    }


def _markdown_fence(value: str) -> str:
    longest = 0
    current = 0
    for char in value:
        if char == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return "`" * max(4, longest + 1)


def _fenced_text(value: str) -> str:
    fence = _markdown_fence(value)
    suffix = "" if value.endswith("\n") else "\n"
    return f"{fence}text\n{value}{suffix}{fence}"


def _validate_webui_limits(
    config: dict[str, Any],
    instructions: bytes,
    package_manifest: dict[str, Any],
    target_id: str,
    errors: list[str],
) -> str:
    try:
        instructions_text = instructions.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(f"{target_id} Instructions must be UTF-8")
        instructions_text = ""

    description = config.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append(f"{target_id} Description must be a non-empty string")
        description = ""

    instruction_character_count = _webui_character_count(instructions_text)
    description_character_count = _webui_character_count(description)
    if instruction_character_count > INSTRUCTION_CHARACTER_CEILING:
        errors.append(
            f"{target_id} Instructions exceed {INSTRUCTION_CHARACTER_CEILING} characters: "
            f"{instruction_character_count}"
        )
    if description_character_count > DESCRIPTION_CHARACTER_CEILING:
        errors.append(
            f"{target_id} Description exceeds {DESCRIPTION_CHARACTER_CEILING} characters: "
            f"{description_character_count}"
        )

    if package_manifest.get("instruction_character_count") != instruction_character_count:
        errors.append(f"{target_id} package manifest instruction character count drift")
    if package_manifest.get("instruction_character_ceiling") != INSTRUCTION_CHARACTER_CEILING:
        errors.append(f"{target_id} package manifest instruction ceiling drift")
    if package_manifest.get("description_character_count") != description_character_count:
        errors.append(f"{target_id} package manifest description character count drift")
    if package_manifest.get("description_character_ceiling") != DESCRIPTION_CHARACTER_CEILING:
        errors.append(f"{target_id} package manifest description ceiling drift")

    starters = config.get("conversation_starters")
    if not isinstance(starters, list) or len(starters) != 4 or not all(
        isinstance(value, str) and value.strip() for value in starters
    ):
        errors.append(f"{target_id} must define exactly four non-empty conversation starters")

    return instructions_text


def _webui_configuration_markdown(
    config: dict[str, Any],
    instructions_text: str,
    knowledge_names: list[str],
) -> bytes:
    name = config.get("name") if isinstance(config.get("name"), str) else ""
    description = config.get("description") if isinstance(config.get("description"), str) else ""
    starters = config.get("conversation_starters")
    if not isinstance(starters, list):
        starters = []
    capabilities = config.get("capabilities")
    if not isinstance(capabilities, dict):
        capabilities = {}

    lines = [
        f"# {name} - GPT WebUI Configuration",
        "",
        "> Generated operator handoff. Copy these values into the existing GPT editor.",
        "> Do not upload this setup sheet as Knowledge and do not edit it as canonical source.",
        "",
        "## Name",
        "",
        _fenced_text(name),
        "",
        "## Description",
        "",
        f"Character count: **{_webui_character_count(description)} / {DESCRIPTION_CHARACTER_CEILING}**",
        "",
        _fenced_text(description),
        "",
        "## Conversation starters",
        "",
    ]
    for index, starter in enumerate(starters, start=1):
        lines.append(f"{index}. {starter}")
    lines.extend(
        [
            "",
            "## Model / runtime",
            "",
            f"`{config.get('runtime_model', '')}`",
            "",
            "## Capabilities",
            "",
        ]
    )
    for key, value in capabilities.items():
        label = CAPABILITY_LABELS.get(key, key.replace("_", " ").title())
        state = "ON" if value is True else "OFF" if value is False else "UNSPECIFIED"
        lines.append(f"- {label}: **{state}**")
    lines.extend(
        [
            "",
            "## Instructions",
            "",
            f"Character count: **{_webui_character_count(instructions_text)} / {INSTRUCTION_CHARACTER_CEILING}**",
            "",
            "Copy the complete contents of the block below into the GPT Instructions field.",
            "",
            _fenced_text(instructions_text),
            "",
            "## Knowledge files",
            "",
            f"Upload exactly **{len(knowledge_names)}** files from the adjacent `Knowledge/` folder, in this order:",
            "",
        ]
    )
    for index, name_value in enumerate(knowledge_names, start=1):
        lines.append(f"{index}. `{name_value}`")
    lines.extend(
        [
            "",
            "## Final WebUI checklist",
            "",
            "- [ ] Name and Description match this sheet.",
            "- [ ] All four conversation starters match this sheet.",
            "- [ ] Model/runtime and capability toggles match this sheet.",
            "- [ ] Instructions were copied in full without hand edits.",
            f"- [ ] Exactly {len(knowledge_names)} Knowledge files were uploaded with the listed filenames.",
            "- [ ] Save/update the GPT, then perform the governed live readback/smoke checks.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def _validate_and_copy_target(
    repo_root: Path,
    delivery_root: Path,
    target: dict[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    package_root = _resolve_repo_path(repo_root, target["package_root"], errors, "package root")
    knowledge_root = _resolve_repo_path(repo_root, target["knowledge_root"], errors, "knowledge root")
    if package_root is None or knowledge_root is None:
        return {"target_id": target["target_id"], "success": False}

    config_path = package_root / "GPT_Configuration.json"
    instructions_path = package_root / "Instructions.md"
    manifest_path = package_root / "manifest.json"
    config = _load_json(config_path, errors, f"{target['target_id']} configuration")
    package_manifest = _load_json(manifest_path, errors, f"{target['target_id']} package manifest")
    if instructions_path.is_symlink() or not instructions_path.is_file():
        errors.append(f"Missing or unsafe {target['target_id']} Instructions: {instructions_path.as_posix()}")
        instructions = b""
    else:
        instructions = instructions_path.read_bytes()
    instructions_text = _validate_webui_limits(
        config, instructions, package_manifest, target["target_id"], errors
    )

    if config.get("target_id") != target["target_id"]:
        errors.append(f"{target['target_id']} configuration target_id drift")
    if package_manifest.get("target_id") != target["target_id"]:
        errors.append(f"{target['target_id']} package manifest target_id drift")
    if config.get("name") != target["webui_name"]:
        errors.append(f"{target['target_id']} WebUI name drift")
    if config.get("runtime_model") != "GPT-5.4":
        errors.append(f"{target['target_id']} runtime model drift")

    expected_instructions = (target["package_root"] / "Instructions.md").as_posix()
    if config.get("instructions_file") != expected_instructions:
        errors.append(f"{target['target_id']} instructions_file drift")

    knowledge = config.get("knowledge_files")
    if not isinstance(knowledge, list):
        errors.append(f"{target['target_id']} knowledge_files must be an array")
        knowledge = []
    if len(knowledge) != target["knowledge_count"]:
        errors.append(
            f"{target['target_id']} expected {target['knowledge_count']} Knowledge files, got {len(knowledge)}"
        )
    orders = [item.get("order") for item in knowledge if isinstance(item, dict)]
    if orders != list(range(len(knowledge))):
        errors.append(f"{target['target_id']} Knowledge order must be contiguous from zero")

    destination_root = delivery_root / target["delivery_dir"]
    file_records: list[dict[str, Any]] = []
    for source, name in (
        (config_path, "GPT_Configuration.json"),
        (manifest_path, "manifest.json"),
    ):
        if not source.is_file() or source.is_symlink():
            errors.append(f"Missing or unsafe {target['target_id']} package file: {source.as_posix()}")
            continue
        record = _copy_record(
            source,
            destination_root / name,
            delivery_root,
            repo_root,
            errors,
        )
        if record is not None:
            file_records.append(record)

    knowledge_names = [
        Path(item.get("path")).name
        for item in knowledge
        if isinstance(item, dict) and isinstance(item.get("path"), str) and item.get("path")
    ]
    handoff_bytes = _webui_configuration_markdown(config, instructions_text, knowledge_names)
    handoff_path = destination_root / HUMAN_WEBUI_FILENAME
    handoff_record: dict[str, Any] | None = None
    if _write_output_bytes(
        delivery_root, handoff_path, handoff_bytes, errors, "human WebUI configuration"
    ):
        handoff_record = {
            "delivery_path": handoff_path.relative_to(delivery_root).as_posix(),
            "sha256": _sha256_bytes(handoff_bytes),
            "bytes": len(handoff_bytes),
            "derived_from": [
                config_path.relative_to(repo_root).as_posix(),
                instructions_path.relative_to(repo_root).as_posix(),
            ],
        }

    knowledge_records: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for item in knowledge:
        if not isinstance(item, dict):
            errors.append(f"{target['target_id']} contains a non-object Knowledge entry")
            continue
        declared_path = item.get("path")
        if not isinstance(declared_path, str) or not declared_path:
            errors.append(f"{target['target_id']} Knowledge entry lacks path")
            continue
        source = _resolve_repo_path(repo_root, declared_path, errors, "Knowledge file")
        if source is None:
            continue
        try:
            source.relative_to(knowledge_root)
        except ValueError:
            errors.append(f"{target['target_id']} Knowledge file escapes target root: {declared_path}")
            continue
        if not source.is_file() or source.is_symlink():
            errors.append(f"Missing or unsafe Knowledge file: {declared_path}")
            continue
        if source.name in seen_names:
            errors.append(f"Duplicate Knowledge filename for {target['target_id']}: {source.name}")
            continue
        seen_names.add(source.name)
        data = source.read_bytes()
        actual_sha = _sha256_bytes(data)
        if item.get("sha256") != actual_sha or item.get("bytes") != len(data):
            errors.append(f"Knowledge hash/size drift for {declared_path}")
        record = _copy_record(
            source,
            destination_root / "Knowledge" / source.name,
            delivery_root,
            repo_root,
            errors,
        )
        if record is not None:
            record.update({"id": item.get("id"), "order": item.get("order")})
            knowledge_records.append(record)

    return {
        "target_id": target["target_id"],
        "webui_name": target["webui_name"],
        "runtime_model": config.get("runtime_model"),
        "delivery_directory": target["delivery_dir"],
        "package_files": file_records,
        "operator_handoff_file": handoff_record,
        "knowledge_file_count": len(knowledge_records),
        "knowledge_files": knowledge_records,
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
        lines.extend(
            [
                f"### {target['webui_name']}",
                "",
                f"- target_id: `{target['target_id']}`",
                f"- runtime_model: `{target['runtime_model']}`",
                f"- Knowledge files: {target['knowledge_file_count']}",
                f"- delivery_directory: `{target['delivery_directory']}`",
                "",
            ]
        )
    lines.extend(
        [
            "The files in this package are generated deployment surfaces, not canonical editable source.",
            "OpenAI WebUI deployment and live behavior remain manual evidence steps.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_deterministic_zip(
    delivery_root: Path,
    zip_path: Path,
    errors: list[str],
) -> bool:
    files: list[Path] = []
    for path in sorted(delivery_root.rglob("*")):
        if path.is_symlink():
            errors.append(
                f"Unsafe symlink in delivery tree: {path.relative_to(delivery_root).as_posix()}"
            )
            return False
        if path.is_file():
            files.append(path)

    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for path in files:
                if path.is_symlink() or not path.is_file():
                    raise OSError(f"unsafe delivery file changed during ZIP assembly: {path.as_posix()}")
                archive_name = (Path(delivery_root.name) / path.relative_to(delivery_root)).as_posix()
                info = zipfile.ZipInfo(archive_name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                zf.writestr(info, path.read_bytes())
    except OSError as exc:
        if zip_path.exists():
            zip_path.unlink()
        errors.append(f"Delivery ZIP assembly failed: {exc}")
        return False
    return True


def build_release(
    repo_root: Path,
    output_dir: Path,
    parity_root: Path,
    *,
    source_commit: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    repo_root = repo_root.resolve()
    output_dir = output_dir.resolve()
    parity_root = parity_root.resolve()
    if not output_dir.is_relative_to(repo_root) or output_dir == repo_root:
        errors.append("output_dir must be a non-root path inside the repository")
    if not parity_root.is_relative_to(repo_root):
        errors.append("parity_root must be inside the repository")
    commit = _source_commit(repo_root, source_commit)
    if errors:
        return errors, {
            "schema": REPORT_SCHEMA,
            "success": False,
            "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "source_commit": commit,
            "delivery_root": None,
            "zip_path": None,
            "zip_sha256": None,
            "target_count": 0,
            "targets": [],
            "static_parity_status": None,
            "live_parity_status": None,
            "errors": errors,
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "build_openai_gpt_deployment_release_report.json"
    zip_name = f"DCOIR_OpenAI_GPT_Deployment_Packages_{commit[:12] if commit != 'unknown' else 'unknown'}.zip"
    zip_path = output_dir / zip_name
    _validate_output_path(output_dir, report_path, errors, "build report")
    _validate_output_path(output_dir, zip_path, errors, "delivery ZIP")
    if errors:
        return errors, {
            "schema": REPORT_SCHEMA,
            "success": False,
            "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "source_commit": commit,
            "delivery_root": None,
            "zip_path": None,
            "zip_sha256": None,
            "target_count": 0,
            "targets": [],
            "static_parity_status": None,
            "live_parity_status": None,
            "errors": errors,
        }

    parity_json_path = parity_root / PARITY_JSON
    parity_md_path = parity_root / PARITY_MD
    parity = _load_json(parity_json_path, errors, "release parity report")
    if parity.get("static_parity_status") != "pass":
        errors.append("Unified release parity report is not statically clean")
    if parity.get("blocking_parity_gaps") not in ([], None):
        errors.append("Unified release parity report contains blocking gaps")
    if commit != "unknown" and parity.get("source_commit") != commit:
        errors.append(
            f"Release parity report source commit mismatch: {parity.get('source_commit')!r} != {commit!r}"
        )
    if not parity_md_path.is_file():
        errors.append(f"Missing release parity Markdown: {parity_md_path.as_posix()}")

    guide_path = _resolve_repo_path(repo_root, GUIDE, errors, "deployment/readback guide")
    if guide_path is None or not guide_path.is_file():
        errors.append("Deployment/readback guide is unavailable")

    delivery_root = output_dir / DELIVERY_ROOT_NAME
    if delivery_root.exists() or delivery_root.is_symlink():
        if delivery_root.is_symlink() or not delivery_root.is_dir():
            errors.append(f"Unsafe existing delivery root: {delivery_root.as_posix()}")
            return errors, {
                "schema": REPORT_SCHEMA,
                "success": False,
                "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "source_commit": commit,
                "delivery_root": delivery_root.relative_to(repo_root).as_posix(),
                "zip_path": None,
                "zip_sha256": None,
                "target_count": 0,
                "targets": [],
                "static_parity_status": parity.get("static_parity_status"),
                "live_parity_status": parity.get("live_parity_status"),
                "errors": errors,
            }
        shutil.rmtree(delivery_root)
    delivery_root.mkdir(parents=True, exist_ok=True)

    target_reports = [
        _validate_and_copy_target(repo_root, delivery_root, target, errors)
        for target in TARGETS
    ]
    if guide_path is not None and guide_path.is_file():
        _copy_record(guide_path, delivery_root / GUIDE.name, delivery_root, repo_root, errors)
    if parity_json_path.is_file():
        _copy_record(parity_json_path, delivery_root / PARITY_JSON, delivery_root, repo_root, errors)
    if parity_md_path.is_file():
        _copy_record(parity_md_path, delivery_root / PARITY_MD, delivery_root, repo_root, errors)

    manifest = {
        "schema": SCHEMA,
        "source_commit": commit,
        "static_parity_status": parity.get("static_parity_status"),
        "live_parity_status": parity.get("live_parity_status"),
        "live_model_parity_claimed": False,
        "manual_webui_deployment_required": True,
        "generated_outputs_are_canonical": False,
        "targets": target_reports,
    }
    _write_output_bytes(
        delivery_root,
        delivery_root / "delivery_manifest.json",
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

    report = {
        "schema": REPORT_SCHEMA,
        "success": not errors,
        "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": commit,
        "delivery_root": delivery_root.relative_to(repo_root).as_posix(),
        "zip_path": zip_path.relative_to(repo_root).as_posix() if zip_path.exists() else None,
        "zip_sha256": _sha256_file(zip_path) if zip_path.exists() else None,
        "target_count": len(target_reports),
        "targets": target_reports,
        "static_parity_status": parity.get("static_parity_status"),
        "live_parity_status": parity.get("live_parity_status"),
        "errors": errors,
    }
    if not _write_output_bytes(
        output_dir,
        report_path,
        _json_bytes(report),
        errors,
        "build report",
    ):
        report["success"] = False
        report["errors"] = errors
    return errors, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build one deterministic manual-deployment ZIP containing both governed OpenAI GPT packages."
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
