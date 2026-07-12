#!/usr/bin/env python3
"""Add workflow artifact metadata to the PowerShell review-assist report."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


def load_report_renderer():
    module_path = Path("project_sources/collector/tools/run_powershell_review_assist_report.py").resolve()
    spec = importlib.util.spec_from_file_location(
        "run_powershell_review_assist_report",
        module_path,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    sys.path.insert(0, str(module_path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def main() -> int:
    generated_json = Path(os.environ["REVIEW_ASSIST_GENERATED_JSON"])
    target_json = Path(os.environ["REVIEW_ASSIST_TARGET_JSON"])
    target_markdown = Path(os.environ["REVIEW_ASSIST_TARGET_MARKDOWN"])
    retention_scope = (
        "workflow-generated report artifacts uploaded by the caller workflow; "
        "retention is configured by the caller upload-artifact step, not by #268"
    )
    workflow_behavior = "caller_uploaded_artifact"

    report = json.loads(generated_json.read_text(encoding="utf-8"))
    artifact_contract = report.setdefault("artifact_contract", {})
    local_artifacts = artifact_contract.setdefault("local_artifacts", {})
    local_artifacts["json"] = target_json.as_posix()
    local_artifacts["markdown"] = target_markdown.as_posix()
    artifact_contract["retention_scope"] = retention_scope
    artifact_contract["workflow_behavior"] = workflow_behavior

    target_json.parent.mkdir(parents=True, exist_ok=True)
    target_markdown.parent.mkdir(parents=True, exist_ok=True)
    target_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    module = load_report_renderer()
    markdown = module.render_markdown(report)
    if "Workflow behavior:" not in markdown:
        retention_line = f"- Retention scope: {retention_scope}"
        workflow_line = f"- Workflow behavior: `{workflow_behavior}`"
        markdown = markdown.replace(retention_line, f"{workflow_line}\n{retention_line}")
    target_markdown.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
