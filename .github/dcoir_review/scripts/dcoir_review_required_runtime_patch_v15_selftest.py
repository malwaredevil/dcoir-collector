#!/usr/bin/env python3
"""Regression self-test for the DCOIR Review v15 compatibility overlay."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from typing import Any

import dcoir_review_required_runtime_patch_v4 as v4
import dcoir_review_required_runtime_patch_v9 as v9
import dcoir_review_required_runtime_patch_v13 as v13
import dcoir_review_required_runtime_patch_v14 as v14


def _reload_v15_without_v13_family():
    if hasattr(v13, "_family"):
        delattr(v13, "_family")
    sys.modules.pop("dcoir_review_required_runtime_patch_v15", None)
    return importlib.import_module("dcoir_review_required_runtime_patch_v15")


def _finding(path: str, line: int, kind: str, text: str) -> dict[str, Any]:
    return {
        "path": path,
        "line": line,
        "title": "Synthetic high-risk finding",
        "body": "Synthetic body",
        "severity": "critical",
        "confidence": 1.0,
        "_anchored_line_text": text,
        "_risk_sentinel_key": [path, line, kind],
    }


def main() -> None:
    v15 = _reload_v15_without_v13_family()
    module = SimpleNamespace(base=None, hardened=SimpleNamespace())

    # Match the runtime entrypoint ordering: v14 applies first, then v15 patches
    # the family-compat helpers that v14 exposes.
    v14.apply_pareto_context_module(module)
    v15.apply_pareto_context_module(module)

    assert v14._family("yaml_broad_write") == "yaml"
    assert v14._family("ps_process_launch") == "powershell"
    assert v14._family("python_pickle_load") == "python"
    assert v14._family("k8s_host_network") == "kubernetes"
    assert v14._family("ts_inner_html") == "typescript"
    assert v14._family("") == "other"
    assert "kubernetes" not in v14.FAMILY_ORDER

    counts = v14._family_counts(
        [
            "a.yml:3 yaml_pull_request_target",
            "probe.ps1:14 ps_process_launch",
            "probe.py:12 python_pickle_load",
            "pod.yml:6 k8s_host_network",
            "probe.ts:2 ts_inner_html",
        ]
    )
    assert counts == {"yaml": 1, "powershell": 1, "python": 1, "kubernetes": 1, "typescript": 1}

    findings = [
        _finding(".github/workflows/probe.yml", 3, v4.YAML_PULL_REQUEST_TARGET, "  pull_request_target:"),
        _finding("probe.ps1", 14, v4.PS_PROCESS_LAUNCH, "Start-Process -FilePath $ToolPath"),
        _finding("probe.py", 12, v9.PYTHON_PICKLE_LOAD, "    return pickle.loads(raw)"),
        _finding("deploy/pod.yml", 6, v13.K8S_HOST_NETWORK, "  hostNetwork: true"),
        _finding("probe.ts", 2, v13.TS_INNER_HTML, "target.innerHTML = profile.bio"),
    ]
    ranked = module.rank_findings_for_required_budget(findings, SimpleNamespace(max_inline_comments=12))
    ranked_kinds = [v14._family(v13._postable_key(item)[2]) for item in ranked]

    assert len(ranked) == 5
    assert ranked_kinds[:3] == ["yaml", "powershell", "python"]

    print("dcoir_review_required_runtime_patch_v15_selftest passed")


if __name__ == "__main__":
    main()
