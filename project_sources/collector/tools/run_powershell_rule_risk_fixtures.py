#!/usr/bin/env python3
"""Validate #263 PowerShell rule-to-risk fixture evidence.

CLI entry point (also run as the fixture analyzer subprocess) and stable import
surface. Behavior is owned by the powershell_rule_risk_fixtures_* modules; this
module only re-exports their public names. Tests that intercept a dependency
patch its owner, for example powershell_rule_risk_fixtures_common.sha256_file.
"""
from __future__ import annotations

from powershell_rule_risk_fixtures_cli import main, parse_args
from powershell_rule_risk_fixtures_common import (
    DEFAULT_JSON_OUTPUT,
    DEFAULT_MANIFEST,
    DEFAULT_MARKDOWN_OUTPUT,
    DEFAULT_MATRIX,
    DEFAULT_MATRIX_MARKDOWN_OUTPUT,
    FIXTURE_ROOT,
    ISSUE_NUMBER,
    MANIFEST_SCHEMA_VERSION,
    MATRIX_SCHEMA_VERSION,
    RuleRiskFixtureError,
    analyzer,
)
from powershell_rule_risk_fixtures_findings import fixture_findings
from powershell_rule_risk_fixtures_reporting import write_outputs
from powershell_rule_risk_fixtures_runner import build_fixture_report

__all__ = [
    "DEFAULT_JSON_OUTPUT",
    "DEFAULT_MANIFEST",
    "DEFAULT_MARKDOWN_OUTPUT",
    "DEFAULT_MATRIX",
    "DEFAULT_MATRIX_MARKDOWN_OUTPUT",
    "FIXTURE_ROOT",
    "ISSUE_NUMBER",
    "MANIFEST_SCHEMA_VERSION",
    "MATRIX_SCHEMA_VERSION",
    "RuleRiskFixtureError",
    "analyzer",
    "build_fixture_report",
    "fixture_findings",
    "main",
    "parse_args",
    "write_outputs",
]


if __name__ == "__main__":
    raise SystemExit(main())
