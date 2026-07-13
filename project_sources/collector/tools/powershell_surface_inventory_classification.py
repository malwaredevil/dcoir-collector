#!/usr/bin/env python3
"""Classification rules for PowerShell and workflow surfaces."""
from pathlib import Path
from typing import Any

from powershell_surface_inventory_common import (
    HARNESS_GENERATED_OUTPUT, archive_temp_vendor_like, fixture_like, generated_like,
    has_prefix, is_powershell_file, is_workflow_yaml, make_surface, staging_like,
)
from powershell_surface_inventory_workflow_yaml import extract_workflow_snippets, workflow_yaml_shape_error

def classify_surface(repo_root: Path, rel: str, exists: bool = True) -> dict[str, Any] | None:
    if is_workflow_yaml(rel):
        if not exists:
            return make_surface(
                repo_root,
                rel,
                "missing_changed_workflow_surface",
                "missing",
                "fail",
                "Changed workflow/action YAML path is missing from the working tree.",
                exists,
            )
        workflow_error = workflow_yaml_shape_error(repo_root, rel)
        if workflow_error:
            return make_surface(
                repo_root,
                rel,
                "invalid_workflow_surface",
                "invalid",
                "fail",
                workflow_error,
                exists,
            )
        snippets = extract_workflow_snippets(repo_root, rel) if exists else []
        if not snippets:
            return None
        markers = sorted({snippet["line_start"] for snippet in snippets})
        return make_surface(
            repo_root,
            rel,
            "workflow_embedded_powershell",
            "workflow_embedded",
            "reference",
            "Workflow or composite-action YAML embeds PowerShell and needs later snippet-aware handling.",
            exists,
            markers,
            snippets,
        )

    if not is_powershell_file(rel):
        return None

    if not exists:
        return make_surface(
            repo_root,
            rel,
            "missing_changed_powershell_surface",
            "missing",
            "fail",
            "Changed PowerShell-relevant path is missing from the working tree.",
            exists,
        )

    if rel == "project_sources/collector/source/DCOIR_Collector.ps1":
        return make_surface(
            repo_root,
            rel,
            "collector_runtime_wrapper",
            "source",
            "include",
            "Collector runtime wrapper is a primary maintained PowerShell surface.",
            exists,
        )

    if rel == "project_sources/collector/source/parts/DCOIR_Collector.02_Baseline_Collection_And_Reports.ps1":
        return make_surface(
            repo_root,
            rel,
            "generated_or_assembled_output",
            "superseded_pointer",
            "reference",
            "Superseded monolithic Part 02 pointer is documentation, not manifest-loaded runtime source.",
            exists,
        )

    if has_prefix(rel, "project_sources/collector/source/parts"):
        return make_surface(
            repo_root,
            rel,
            "collector_runtime_source_part",
            "source",
            "include",
            "Collector runtime source part is primary maintained PowerShell source.",
            exists,
        )

    if has_prefix(rel, "project_sources/collector/harness/source/parts"):
        return make_surface(
            repo_root,
            rel,
            "collector_harness_source_part",
            "source_part",
            "include",
            "Collector harness source part is primary maintained PowerShell source.",
            exists,
        )

    if rel == HARNESS_GENERATED_OUTPUT.as_posix() or generated_like(rel):
        return make_surface(
            repo_root,
            rel,
            "generated_or_assembled_output",
            "generated",
            "reference",
            "Generated or assembled output is covered as parity/reference evidence, not source truth.",
            exists,
        )

    if has_prefix(rel, "project_sources/collector/harness"):
        return make_surface(
            repo_root,
            rel,
            "collector_harness_script",
            "source",
            "include",
            "Collector harness script is a primary maintained PowerShell surface.",
            exists,
        )

    if has_prefix(rel, "project_sources/collector/tools"):
        return make_surface(
            repo_root,
            rel,
            "collector_validation_tooling",
            "tooling",
            "include",
            "Collector validation/tooling script is maintained repo PowerShell.",
            exists,
        )

    if rel == "project_sources/collector/PSScriptAnalyzerSettings.psd1":
        return make_surface(
            repo_root,
            rel,
            "collector_validation_tooling",
            "tooling",
            "include",
            "Repository-owned PowerShell analyzer policy is maintained validation tooling.",
            exists,
        )

    if staging_like(rel):
        return make_surface(
            repo_root,
            rel,
            "staging_artifact",
            "staging",
            "exclude",
            "ChatGPT staging scripts are historical execution artifacts, not maintained source.",
            exists,
        )

    if archive_temp_vendor_like(rel):
        return make_surface(
            repo_root,
            rel,
            "archive_temp_vendor_artifact",
            "excluded_artifact",
            "exclude",
            "Archive, temp, or vendor path is not a maintained PowerShell validation target.",
            exists,
        )

    if fixture_like(rel):
        return make_surface(
            repo_root,
            rel,
            "fixture_or_example",
            "fixture",
            "reference",
            "Fixture/example PowerShell is inventoried separately from maintained source targets.",
            exists,
        )

    if (
        has_prefix(rel, ".github/actions")
        or has_prefix(rel, ".github/pester")
        or has_prefix(rel, ".github/scripts")
        or has_prefix(rel, ".github/dcoir_review/scripts")
    ):
        return make_surface(
            repo_root,
            rel,
            "github_workflow_support_script",
            "tooling",
            "include",
            "GitHub workflow support script is maintained repo PowerShell.",
            exists,
        )

    if has_prefix(rel, "operator_tools") or has_prefix(rel, ".github/operator_tools"):
        return make_surface(
            repo_root,
            rel,
            "operator_tooling",
            "tooling",
            "include",
            "Operator tooling PowerShell is maintained repo tooling.",
            exists,
        )

    if has_prefix(rel, "project_sources/validation") or has_prefix(rel, "scripts"):
        return make_surface(
            repo_root,
            rel,
            "validation_tooling",
            "tooling",
            "include",
            "Validation PowerShell is maintained repo tooling.",
            exists,
        )

    return make_surface(
        repo_root,
        rel,
        "unclassified_powershell_surface",
        "unknown",
        "fail",
        "PowerShell-relevant path has no inventory category.",
        exists,
    )
