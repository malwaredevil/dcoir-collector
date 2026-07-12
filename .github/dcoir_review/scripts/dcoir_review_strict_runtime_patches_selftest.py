#!/usr/bin/env python3
"""Offline checks for strict DCOIR Review runtime patch behavior."""

from __future__ import annotations

import copy
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARDENED_SCRIPT = ROOT / "scripts" / "openrouter_pr_review_hardened.py"
PARETO_SCRIPT = ROOT / "scripts" / "openrouter_pr_review_pareto_context.py"
STRICT_SCRIPT = ROOT / "scripts" / "dcoir_review_strict_runtime_patches.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


hardened = load_module("openrouter_pr_review_hardened", HARDENED_SCRIPT)
pareto = load_module("openrouter_pr_review_pareto_context", PARETO_SCRIPT)
strict = load_module("dcoir_review_strict_runtime_patches", STRICT_SCRIPT)
strict.apply_pareto_context_module(pareto)

os.environ["GITHUB_REPOSITORY"] = "DCOIR-Collector/dcoir-collector"
os.environ["PR_NUMBER"] = "323"

config = hardened.load_hardened_config(str(ROOT / "openrouter-pr-review-governed.yml"))
config.max_inline_comments = 1

sentinel = hardened.RiskSentinel(
    path="project_sources/collector/test_fixtures/dcoir_review_cycle/actions_review_probe.yml",
    line=14,
    label="GitHub Actions untrusted checkout ref",
    detail=(
        "checkout uses untrusted pull request head refs or SHAs; privileged workflows must not execute "
        "PR-controlled code with write tokens"
    ),
    text="ref: ${{ github.event.pull_request.head.ref }}",
)

optional_finding = {
    "title": "Optional Kubernetes pressure finding",
    "severity": "critical",
    "confidence": 0.99,
    "path": "project_sources/collector/test_fixtures/dcoir_review_cycle/kubernetes_pressure_probe.yml",
    "line": 6,
    "body": "Optional Kubernetes privilege pressure finding.",
    "suggested_replacement": "",
    "validation": "python3 .github/dcoir_review/scripts/dcoir_review_strict_runtime_patches_selftest.py",
}

augmented = hardened.add_risk_sentinel_fallback_findings([optional_finding], [sentinel], config)
assert len(augmented) == 1
assert augmented[0]["path"] == sentinel.path
assert augmented[0]["line"] == sentinel.line
assert "untrusted" in (augmented[0]["title"] + augmented[0]["body"]).lower()
hardened.enforce_risk_sentinel_findings(augmented, [sentinel], config)

empty_findings: list[dict[str, object]] = []
hardened.enforce_risk_sentinel_findings(empty_findings, [sentinel], config)
assert len(empty_findings) == 1
assert empty_findings[0]["path"] == sentinel.path
assert empty_findings[0]["line"] == sentinel.line

body_finding = copy.deepcopy(optional_finding)
body_finding.update(
    {
        "title": "Privileged workflow checks out untrusted PR code",
        "path": sentinel.path,
        "line": 12,
        "body": "The workflow checks out untrusted PR code, but this is not anchored to the exact ref line.",
    }
)
inline_required = hardened.add_risk_sentinel_fallback_findings([], [sentinel], config, [body_finding])
assert len(inline_required) == 1
assert inline_required[0]["line"] == sentinel.line
hardened.enforce_risk_sentinel_findings(inline_required, [sentinel], config, [body_finding])

print("strict DCOIR Review runtime patch selftest passed")
