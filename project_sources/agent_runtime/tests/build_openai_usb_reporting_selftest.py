#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE_SELFTEST = ROOT / "project_sources/agent_runtime/tests/build_openai_usb_reporting_core_selftest.py"
DEPLOYMENT_SELFTEST = ROOT / "project_sources/agent_runtime/tests/build_openai_gpt_deployment_release_selftest.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    core = _load(CORE_SELFTEST, "build_openai_usb_reporting_core_selftest")
    deployment = _load(DEPLOYMENT_SELFTEST, "build_openai_gpt_deployment_release_selftest")
    if core.main() != 0:
        return 1
    if deployment.main() != 0:
        return 1
    print(json.dumps({"success": True, "composed_selftests": [CORE_SELFTEST.name, DEPLOYMENT_SELFTEST.name]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
