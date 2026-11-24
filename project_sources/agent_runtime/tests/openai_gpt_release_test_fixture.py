#!/usr/bin/env python3
"""Isolated governed fixture and release builder for all OpenAI release tests."""
from __future__ import annotations

import hashlib
import json
import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "project_sources/agent_runtime/tools/build_openai_gpt_deployment_release.py"
sys.path.insert(0, str(SCRIPT.parent))
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
    instructions_text: str | None = None,
    description: str = "test",
) -> None:
    package_root = repo / package_dir
    knowledge_root = repo / knowledge_dir
    if instructions_text is None:
        instructions_text = f"# {webui_name}\n\nGoverned instructions.\n"
    instructions = instructions_text.encode("utf-8")
    _write(package_root / "Instructions.md", instructions)
    governed_projection = json.loads(
        (ROOT / 'project_sources/agent_runtime/Knowledge_Projection_Manifest.json').read_text()
    )['targets'][target_id]['projection_groups']
    knowledge_files = []
    for order in range(knowledge_count):
        name = f"{order + 1:02d}-knowledge-{order + 1}.md"
        data = f"# Knowledge {order + 1}\n\ncontent-{target_id}-{order}\n".encode()
        path = knowledge_root / name
        _write(path, data)
        knowledge_files.append(
            {
                "id": governed_projection[order]["id"],
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
        "runtime_model": "GPT-5.6 Terra",
        "instructions_file": (Path(package_dir) / "Instructions.md").as_posix(),
        "knowledge_files": knowledge_files,
        "capabilities": {capability: False for capability in module.CAPABILITY_KEYS},
        "description": description,
        "conversation_starters": ["Starter one", "Starter two", "Starter three", "Starter four"],
    }
    _write(package_root / "GPT_Configuration.json", module._json_bytes(config))
    package_manifest = {
        "target_id": target_id,
        "manual_deployment_required": True,
        "instruction_character_count": module._webui_character_count(instructions.decode("utf-8")),
        "instruction_character_ceiling": module.INSTRUCTION_CHARACTER_CEILING,
        "description_character_count": module._webui_character_count(config["description"]),
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
        knowledge_count=1,
    )
    # Synthetic release fixtures use actual governed source/Knowledge manifest
    # values so package output changes cannot be masked by a copied test spec.
    for basename in ("Shared_Agent_Source_Manifest.json", "Knowledge_Projection_Manifest.json"):
        relative = Path("project_sources/agent_runtime") / basename
        _write(repo / relative, (ROOT / relative).read_bytes())
    # Projected test bytes use synthetic filenames, but must be governed by
    # exactly the same source IDs, target manifest, order and hash contracts.
    projection_path = repo / "project_sources/agent_runtime/Knowledge_Projection_Manifest.json"
    projection_doc = json.loads(projection_path.read_text(encoding="utf-8"))
    for target_id in ("openai_dcoir_analyst", "openai_usb_reporting"):
        package_root = repo / "project_sources/agent_runtime/generated/packages" / target_id
        config = json.loads((package_root / "GPT_Configuration.json").read_text(encoding="utf-8"))
        entries = config["knowledge_files"]
        projection_target = projection_doc["targets"][target_id]
        for group, entry in zip(projection_target["projection_groups"], entries):
            assert group["id"] == entry["id"] and group["order"] == entry["order"]
            group["output_path"] = entry["path"]
        manifest_relative = Path(projection_target["target_manifest_path"])
        target_manifest = json.loads((ROOT / manifest_relative).read_text(encoding="utf-8"))
        target_manifest["projection_file_count"] = len(entries)
        target_manifest["projections"] = [
            {
                "id": entry["id"], "order": entry["order"],
                "output_path": entry["path"],
                "sha256": entry["sha256"], "bytes": entry["bytes"],
            }
            for entry in entries
        ]
        _write(repo / manifest_relative, module._json_bytes(target_manifest))
    _write(projection_path, module._json_bytes(projection_doc))
    source_path = repo / "project_sources/agent_runtime/Shared_Agent_Source_Manifest.json"
    source_sha256 = _sha(source_path.read_bytes())
    for target_id in ("openai_dcoir_analyst", "openai_usb_reporting"):
        package_manifest_path = (
            repo / "project_sources/agent_runtime/generated/packages" / target_id / "manifest.json"
        )
        package_manifest = module._load_json(
            package_manifest_path, [], f"{target_id} package manifest"
        )
        package_manifest["source_contract_sha256"] = source_sha256
        if target_id == "openai_dcoir_analyst":
            package_manifest["source_contracts"] = {
                "source_contract": {
                    "path": "project_sources/agent_runtime/Shared_Agent_Source_Manifest.json",
                    "sha256": source_sha256,
                }
            }
        _write(package_manifest_path, module._json_bytes(package_manifest))
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
