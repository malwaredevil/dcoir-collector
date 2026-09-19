#!/usr/bin/env python3
"""Regression checks for connector-sized DCOIR Review runtime segments."""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import dcoir_review_architecture_inventory as architecture_inventory
from dcoir_review.entrypoint import DcoirReviewEntrypoint
from dcoir_review.module_loader import LAYER_SEGMENTS, RuntimeSegmentLoader

MAX_SEGMENT_SOURCE_BYTES = 15_000
NUMBERED_PRODUCTION_PATCH_VERSION_CEILING = 58
NUMBERED_PRODUCTION_PATCH_RE = re.compile(
    r"^dcoir_review_required_runtime_patch_v(?P<version>\d+)(?:$|_)"
)

# One pre-existing provider segment is already tracked as architecture debt in
# #550. Keep the exception explicit and size-frozen while the consolidated
# provider architecture replaces it; all other runtime segments stay subject
# to the normal connector-safe limit.
LEGACY_OVERSIZE_SEGMENT_MAX_BYTES = {
    "hardened/part_04a_provider.py": 19_159,
}

# Every maintained Python module under scripts/dcoir_review has one explicit
# ownership mode: concatenated runtime segment, ordinary direct-import module,
# or package marker (__init__.py). This keeps orphan detection fail-closed
# without forcing ordinary helper/selftest modules into LAYER_SEGMENTS.
DIRECT_IMPORT_MODULES = (
    "adversarial_prompt_policy.py",
    "entrypoint.py",
    "final_adjudication_policy.py",
    "finding_family.py",
    "finding_comment_policy.py",
    "finding_comment_render.py",
    "finding_verifier.py",
    "finding_verifier_contract.py",
    "incremental_review_frontier.py",
    "incremental_review_frontier_hooks.py",
    "incremental_review_scope.py",
    "incremental_review_state.py",
    "semantic_review_ledger.py",
    "semantic_review_ledger_builder.py",
    "semantic_review_ledger_contract.py",
    "semantic_review_ledger_fingerprints.py",
    "semantic_review_ledger_hooks.py",
    "semantic_result_reuse.py",
    "semantic_result_reuse_support.py",
    "module_loader.py",
    "normalized_finding_selection.py",
    "per_file_review.py",
    "per_file_routing.py",
    "prompt_review_scope_guard.py",
    "review_scope_guard.py",
    "review_config.py",
    "review_orchestration.py",
    "review_telemetry.py",
    "review_telemetry_events.py",
    "review_telemetry_state.py",
    "review_telemetry_summary.py",
    "review_scope_guard_hooks.py",
    "provider_review.py",
    "provider_transport_retry.py",
    "precision_guard.py",
    "progress_reporting.py",
    "publication_contract.py",
    "publication_disposition.py",
    "quality_gate.py",
    "repair.py",
    "repair_contract.py",
    "repair_pipeline.py",
    "repair_reliability.py",
    "repair_render.py",
    "repair_support.py",
    "semantic_adjudication_confidence.py",
    "semantic_candidate_identity.py",
    "semantic_candidate_identity_hooks.py",
    "semantic_evidence_hardening.py",
    "semantic_adjudication_normalization.py",
    "semantic_adjudication_recovery.py",
    "sentinel_selection.py",
    "status.py",
    "status_overview.py",
    "status_snapshot.py",
    "structured_result_disposition.py",
    "structured_result_provider.py",
    "structured_result_recovery.py",
    "structured_result_retry.py",
    "verified_finding_gate.py",
    "verified_finding_gate_prior.py",
    "verified_finding_gate_state.py",
    "verified_finding_render.py",
    "pareto_context/credit_aware_concurrency.py",
    "selftests/provider_transport/fixtures.py",
    "selftests/provider_transport/http_errors.py",
)

EXPECTED_ADJACENCY = {
    "base": (
        ("base/part_01_core_config_github.py", "base/part_01a_progress_diff.py"),
        ("base/part_03_redaction_shell.py", "base/part_03a_redaction_command_shell.py"),
        ("base/part_06_findings_comments.py", "base/part_06a_finding_validation.py"),
    ),
    "hardened": (
        ("hardened/part_01_rules.py", "hardened/part_01a_finding_rules.py"),
        ("hardened/part_03_sentinels_prompt.py", "hardened/part_03a_fallback_prompt.py"),
        ("hardened/part_04_quality_provider.py", "hardened/part_04a_provider.py"),
    ),
    "pareto_context": (
        ("pareto_context/part_04_sentinels_modes_context.py", "pareto_context/part_04a_ranking_context.py"),
        ("pareto_context/part_05_ranking_per_file_review.py", "pareto_context/part_05a_hybrid_review.py"),
    ),
}

PATCH_ADJACENCY = {
    "dcoir_review_runtime_patches": (("part_01.py", "part_01a.py"), ("part_02.py", "part_02a.py")),
    "dcoir_review_strict_runtime_patches": (("part_01.py", "part_01a.py"), ("part_02.py", "part_02a.py")),
    "dcoir_review_required_runtime_patches": (("part_01.py", "part_01a.py"), ("part_02.py", "part_02a.py")),
    "dcoir_review_required_runtime_patch_v2": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v3": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v4": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v5": (("part_01.py", "part_02.py"),),
    "dcoir_review_required_runtime_patch_v6": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v7": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v8": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v9_core": (("part_01.py", "part_02.py"),),
    "dcoir_review_required_runtime_patch_v9_selection": (("part_01.py", "part_02.py"),),
    "dcoir_review_required_runtime_patch_v10": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v11": (("part_01.py", "part_01a.py"), ("part_02.py", "part_02a.py")),
    "dcoir_review_required_runtime_patch_v13": (("part_02.py", "part_02a.py"),),
    "dcoir_review_required_runtime_patch_v14": (("part_01.py", "part_01a.py"),),
    "dcoir_review_required_runtime_patch_v16": (("part_01.py", "part_01a.py"),),
}

SELFTEST_ADJACENCY = {
    "base_selftest": (("part_01.py", "part_01a.py"),),
    "hardened_selftest": (("part_01.py", "part_01a.py"),),
    "pareto_context_selftest": (("part_01.py", "part_01a.py"), ("part_04.py", "part_04a.py")),
    "dcoir_review_required_runtime_patch_v14_selftest": (("part_01.py", "part_02.py"),),
    "dcoir_review_required_runtime_patch_v9_selftest": (("part_01.py", "part_02.py"),),
    "openrouter_pr_review_pareto_context_regression_selftest": (("part_02.py", "part_02a.py"),),
}

EXPECTED_EXPORTS = {
    "openrouter_pr_review": ("Config", "GitHubClient", "ProgressReporter", "sanitize_text"),
    "openrouter_pr_review_hardened": ("RISK_SENTINEL_RULES", "build_prompt", "openrouter_review"),
    "openrouter_pr_review_pareto_context": (
        "detect_risk_sentinels",
        "rank_findings_for_required_budget",
        "openrouter_review_with_hybrid_first_pass",
    ),
}

PRODUCTION_PATCH_GROUPS = (
    "patch_module_names",
    "terminal_patch_module_names",
    "post_terminal_patch_module_names",
    "candidate_integrity_patch_module_names",
    "stage_local_patch_module_names",
    "execution_policy_patch_module_names",
    "telemetry_patch_module_names",
    "post_telemetry_patch_module_names",
)


def normalized_source_size(path: Path) -> int:
    """Measure source bytes independent of Git checkout line-ending conversion."""
    return len(path.read_bytes().replace(b"\r\n", b"\n"))


def production_patch_module_names() -> tuple[str, ...]:
    """Return the complete currently registered production patch sequence."""
    entrypoint = DcoirReviewEntrypoint()
    names: list[str] = []
    for group_name in PRODUCTION_PATCH_GROUPS:
        names.extend(getattr(entrypoint, group_name))
    return tuple(names)


def assert_numbered_patch_freeze_before_cutover() -> None:
    """Enforce the #550 no-v59 production freeze while retirements continue."""
    numbered: dict[str, int] = {}
    for module_name in production_patch_module_names():
        match = NUMBERED_PRODUCTION_PATCH_RE.match(module_name)
        if match is not None:
            numbered[module_name] = int(match.group("version"))

    assert numbered, "expected historical numbered production patches before #550 cutover"
    violating = sorted(
        name
        for name, version in numbered.items()
        if version > NUMBERED_PRODUCTION_PATCH_VERSION_CEILING
    )
    assert not violating, {
        "numbered_patch_freeze_violation": violating,
        "ceiling": NUMBERED_PRODUCTION_PATCH_VERSION_CEILING,
    }
    assert "dcoir_review_required_runtime_patch_v58" not in numbered, (
        "retired v58 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v55" not in numbered, (
        "retired v55 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v37" not in numbered, (
        "retired v37 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v39" not in numbered, (
        "retired v39 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v38" not in numbered, (
        "retired v38 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v34" not in numbered, (
        "retired v34 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v48" not in numbered, (
        "retired v48 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v48_prompt_guard" not in numbered, (
        "retired v48 prompt-review companion production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v41" not in numbered, (
        "retired v41 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v42" not in numbered, (
        "retired v42 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v43" not in numbered, (
        "retired v43 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v45" not in numbered, (
        "retired v45 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v50" not in numbered, (
        "retired v50 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v51" not in numbered, (
        "retired v51 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v52" not in numbered, (
        "retired v52 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v54" not in numbered, (
        "retired v54 production owner reappeared"
    )
    assert "dcoir_review_required_runtime_patch_v57" not in numbered, (
        "retired v57 production owner reappeared"
    )
    assert max(numbered.values()) < NUMBERED_PRODUCTION_PATCH_VERSION_CEILING


def assert_patch_inventory_is_source_complete() -> None:
    """Require the #550 static inventory to cover every active patch root."""
    inventory = architecture_inventory.build_inventory()
    assert tuple(inventory["production_patch_sequence"]) == production_patch_module_names()
    assert inventory["production_patch_count"] == len(production_patch_module_names())
    assert inventory["inventory_module_count"] >= inventory["production_patch_count"]
    assert not inventory["missing_modules"], inventory["missing_modules"]
    numbered_versions = [
        int(match.group("version"))
        for name in production_patch_module_names()
        if (match := NUMBERED_PRODUCTION_PATCH_RE.match(name)) is not None
    ]
    expected_max = max(numbered_versions) if numbered_versions else None
    assert inventory["max_numbered_version"] == expected_max
    assert expected_max is None or expected_max < NUMBERED_PRODUCTION_PATCH_VERSION_CEILING


def assert_segment_source_sizes(paths: tuple[Path, ...], layer: str) -> None:
    """Enforce the normal size cap plus narrowly frozen legacy debt."""
    loader_root = SCRIPTS / "dcoir_review"
    for path in paths:
        relative_path = path.relative_to(loader_root).as_posix()
        source_bytes = normalized_source_size(path)
        legacy_cap = LEGACY_OVERSIZE_SEGMENT_MAX_BYTES.get(relative_path)
        if legacy_cap is None:
            assert source_bytes <= MAX_SEGMENT_SOURCE_BYTES, (
                layer,
                relative_path,
                source_bytes,
                MAX_SEGMENT_SOURCE_BYTES,
            )
            continue
        assert source_bytes > MAX_SEGMENT_SOURCE_BYTES, {
            "stale_legacy_oversize_waiver": relative_path,
            "source_bytes": source_bytes,
        }
        assert source_bytes <= legacy_cap, {
            "legacy_oversize_segment_grew": relative_path,
            "source_bytes": source_bytes,
            "legacy_cap": legacy_cap,
        }


def assert_segment_registry_is_complete() -> None:
    """Reject missing, duplicate, or unowned maintained Python modules."""
    loader_root = SCRIPTS / "dcoir_review"
    registered = [segment for segments in LAYER_SEGMENTS.values() for segment in segments]
    direct_imports = list(DIRECT_IMPORT_MODULES)
    actual = []
    for path in loader_root.rglob("*.py"):
        relative_path = path.relative_to(loader_root).as_posix()
        if path.name == "__init__.py":
            continue
        actual.append(relative_path)

    assert len(registered) == len(set(registered)), "duplicate module-loader segment registration"
    assert len(direct_imports) == len(set(direct_imports)), "duplicate direct-import module ownership"
    overlap = set(registered) & set(direct_imports)
    assert not overlap, {"ambiguous_ownership": sorted(overlap)}

    legacy_oversize = set(LEGACY_OVERSIZE_SEGMENT_MAX_BYTES)
    assert legacy_oversize <= set(registered), {
        "legacy_oversize_waiver_not_registered": sorted(legacy_oversize - set(registered)),
    }
    assert not (legacy_oversize & set(direct_imports)), {
        "legacy_oversize_waiver_direct_import_overlap": sorted(legacy_oversize & set(direct_imports)),
    }

    declared = set(registered) | set(direct_imports)
    assert declared == set(actual), {
        "missing": sorted(declared - set(actual)),
        "orphaned": sorted(set(actual) - declared),
    }



def assert_canonical_config_loader_ownership() -> None:
    base = (
        SCRIPTS / "dcoir_review" / "pareto_context" / "part_01_config_payload.py"
    ).read_text(encoding="utf-8")
    assert "review_config.apply_review_config(config, data, hardened)" in base

    former_config_owners = (
        "dcoir_review_required_runtime_patch_v32.py",
        "dcoir_review_required_runtime_patch_v35.py",
        "dcoir_review_required_runtime_patch_v44.py",
        "dcoir_review/publication_disposition.py",
        "dcoir_review_required_runtime_patch_v46.py",
        "dcoir_review/verified_finding_gate.py",
        "dcoir_review/semantic_candidate_identity.py",
        "dcoir_review/per_file_routing.py",
        "dcoir_review_required_runtime_patch_v56.py",
    )
    for relative in former_config_owners:
        source = (SCRIPTS / relative).read_text(encoding="utf-8")
        assert "def _patch_config_loader(" not in source, relative
        assert "def _install_config_loader(" not in source, relative

    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    canonical_loader = module.load_pareto_context_config
    assert canonical_loader.__module__ == entrypoint.review_module_name

    production_groups = (
        "patch_module_names",
        "terminal_patch_module_names",
        "post_terminal_patch_module_names",
        "candidate_integrity_patch_module_names",
        "stage_local_patch_module_names",
        "execution_policy_patch_module_names",
        "telemetry_patch_module_names",
        "post_telemetry_patch_module_names",
    )
    for group_name in production_groups:
        for patch_name in getattr(entrypoint, group_name):
            entrypoint._apply_patch_modules(module, (patch_name,))
            assert module.load_pareto_context_config is canonical_loader, (
                f"{patch_name} replaced canonical load_pareto_context_config"
            )

    stored_originals = [
        name
        for name, value in vars(module).items()
        if name.endswith("original_load_pareto_context_config") and callable(value)
    ]
    assert stored_originals == [], stored_originals


def assert_canonical_validation_text_ownership() -> None:
    canonical_path = SCRIPTS / "dcoir_review" / "base" / "part_06a_finding_validation.py"
    assert canonical_path.is_file(), "canonical finding-validation base segment is missing"

    former_owners = (
        "dcoir_review/patches/dcoir_review_required_runtime_patch_v8/part_01a.py",
        "dcoir_review_required_runtime_patch_v9_prompting.py",
    )
    for relative in former_owners:
        source = (SCRIPTS / relative).read_text(encoding="utf-8")
        assert "def _patch_validation_text(" not in source, relative
        assert "original_validation_text_for_finding" not in source, relative

    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    canonical = module.base.validation_text_for_finding
    assert canonical.__module__ == "openrouter_pr_review"

    ordinary = canonical({"path": "probe.py", "line": 3, "validation": "pytest -q tests/test_probe.py"})
    assert ordinary.splitlines() == [
        "pytest -q tests/test_probe.py",
        "python3 -m py_compile probe.py",
        "bandit -r probe.py",
    ]
    yaml_broad = canonical({"path": ".github/workflows/probe.yml", "line": 5, "_risk_sentinel_kind": "yaml_broad_write"})
    assert "write-all" in yaml_broad and "python3 - <<'PY'" in yaml_broad
    ps_env = canonical({"path": "tools/probe.ps1", "line": 15, "_risk_sentinel_kind": "ps_env_token_callback"})
    assert "$line = 15" in ps_env and "DCOIR_TOKEN" in ps_env and "callback" in ps_env
    py_shell = canonical({"path": "probe.py", "line": 18, "_risk_sentinel_kind": "python_shell_exec"})
    assert "shell=True" in py_shell
    pickle = canonical({"path": "probe.py", "line": 14, "_risk_sentinel_kind": "python_pickle_load"})
    assert "pickle.loads" in pickle and "pickle.load(" in pickle

    inferred_yaml = canonical({
        "path": ".github/workflows/probe.yml",
        "line": 5,
        "title": "GitHub Actions workflow grants write permissions",
        "body": "contents: write grants broad write token permissions",
    })
    assert inferred_yaml == yaml_broad
    inferred_shell = canonical({
        "path": "probe.py",
        "line": 18,
        "title": "Issue",
        "body": "Issue",
        "_anchored_line_text": "return subprocess.run(command, shell=True, check=False)",
    })
    assert inferred_shell == py_shell
    quote_safe = canonical({
        "path": ".github/chatgpt_staging/$bad/path.ps1",
        "line": 15,
        "_risk_sentinel_kind": "ps_env_token_callback",
    })
    assert "$bad" in quote_safe
    assert '$p = ".github/chatgpt_staging/$bad/path.ps1"' not in quote_safe

    for group_name in PRODUCTION_PATCH_GROUPS:
        for patch_name in getattr(entrypoint, group_name):
            entrypoint._apply_patch_modules(module, (patch_name,))
            assert module.base.validation_text_for_finding is canonical, (
                f"{patch_name} replaced canonical validation_text_for_finding"
            )

    stored = [
        name for name, value in vars(module.base).items()
        if "validation_text_for_finding" in name and name.startswith("_dcoir_") and callable(value)
    ]
    assert stored == [], stored


def assert_canonical_quality_retry_ownership() -> None:
    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    original = module.hardened.review_quality_retry_reason
    replacements = []
    for group_name in PRODUCTION_PATCH_GROUPS:
        for patch_name in getattr(entrypoint, group_name):
            before = module.hardened.review_quality_retry_reason
            entrypoint._apply_patch_modules(module, (patch_name,))
            after = module.hardened.review_quality_retry_reason
            if after is not before:
                replacements.append(patch_name)

    final = module.hardened.review_quality_retry_reason
    assert final is not original
    assert final.__module__ == "dcoir_review.quality_gate", final.__module__
    assert replacements == ["dcoir_review.quality_gate"], replacements
    forbidden = {
        "_dcoir_quality_gate_original_review_quality_retry_reason",
        "_dcoir_review_structured_result_disposition_prior_quality_retry_reason",
    }
    stored = {
        name for name, value in vars(module.hardened).items()
        if name in forbidden and callable(value)
    }
    assert stored == set(), stored



def assert_canonical_progress_reporter_ownership() -> None:
    owner_path = SCRIPTS / "dcoir_review" / "progress_reporting.py"
    assert owner_path.is_file(), "canonical progress-reporting owner is missing"

    gate_source = (SCRIPTS / "dcoir_review" / "verified_finding_gate.py").read_text(encoding="utf-8")
    assert "def _patch_progress_reporter(" not in gate_source
    assert "_dcoir_review_verified_finding_gate_original_progress_reporter" not in gate_source

    telemetry_source = (SCRIPTS / "dcoir_review" / "review_telemetry.py").read_text(encoding="utf-8")
    assert "def _patch_progress_reporter(" not in telemetry_source
    assert "_dcoir_review_v54_original_progress_reporter" not in telemetry_source

    entrypoint = DcoirReviewEntrypoint()
    wrapper = SCRIPTS / "openrouter_pr_review_pareto_context.py"
    spec = importlib.util.spec_from_file_location("_dcoir_progress_reporting_contract_probe", wrapper)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    initial = module.hardened.ProgressReporter
    replacements = []
    for group_name in PRODUCTION_PATCH_GROUPS:
        for patch_name in getattr(entrypoint, group_name):
            before = module.hardened.ProgressReporter
            entrypoint._apply_patch_modules(module, (patch_name,))
            after = module.hardened.ProgressReporter
            if after is not before:
                replacements.append(patch_name)

    final = module.hardened.ProgressReporter
    assert final is not initial
    assert final.__module__ == "dcoir_review.progress_reporting", final.__module__
    assert replacements == ["dcoir_review.progress_reporting"], replacements
    assert module.ProgressReporter is final
    assert module.base.ProgressReporter is final
    assert not callable(getattr(module, "_dcoir_review_verified_finding_gate_original_progress_reporter", None))
    assert not callable(getattr(module.hardened, "_dcoir_review_v54_original_progress_reporter", None))


def assert_canonical_per_file_prompt_ownership() -> None:
    policy_path = SCRIPTS / "dcoir_review" / "adversarial_prompt_policy.py"
    assert policy_path.is_file(), "current adversarial prompt policy owner is missing"

    v32_source = (SCRIPTS / "dcoir_review_required_runtime_patch_v32.py").read_text(encoding="utf-8")
    assert "def _patch_per_file_prompt(" not in v32_source
    assert "_dcoir_review_v32_original_build_per_file_review_prompt" not in v32_source

    evidence_source = (SCRIPTS / "dcoir_review" / "semantic_evidence_hardening.py").read_text(encoding="utf-8")
    assert "def _patch_v32_prompt_blocks(" not in evidence_source
    assert "v32.ADVERSARIAL_SEMANTIC_BLOCK =" not in evidence_source
    assert "v32.INDEPENDENT_CONFIRMATION_BLOCK =" not in evidence_source

    entrypoint = DcoirReviewEntrypoint()
    wrapper = SCRIPTS / "openrouter_pr_review_pareto_context.py"
    spec = importlib.util.spec_from_file_location("_dcoir_per_file_prompt_contract_probe", wrapper)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    canonical = module.build_per_file_review_prompt
    config = module.load_pareto_context_config(str(ROOT / "openrouter-pr-review-pareto.yml"))
    prompt = canonical(
        {"number": 553, "title": "prompt ownership"},
        {"filename": "probe.py", "patch": "@@ -0,0 +1 @@\n+value = 1"},
        "value = 1\n",
        "diff --git a/probe.py b/probe.py\n@@ -0,0 +1 @@\n+value = 1\n",
        config,
        [],
        "deep-forced",
    )
    assert "Adversarial semantic falsification requirements:" not in prompt
    assert "Predicate and call-site audit requirements:" not in prompt
    assert len(prompt) <= int(getattr(config, "max_prompt_chars", 120000))

    replacements = []
    for group_name in PRODUCTION_PATCH_GROUPS:
        for patch_name in getattr(entrypoint, group_name):
            before = module.build_per_file_review_prompt
            entrypoint._apply_patch_modules(module, (patch_name,))
            after = module.build_per_file_review_prompt
            if after is not before:
                replacements.append(patch_name)
    assert replacements == ["dcoir_review_required_runtime_patch_v46"], replacements
    assert not callable(getattr(module, "_dcoir_review_v32_original_build_per_file_review_prompt", None))


def assert_canonical_guidance_code_classifier_ownership() -> None:
    canonical_path = SCRIPTS / "dcoir_review" / "base" / "part_06b_guidance_code.py"
    assert canonical_path.is_file(), "canonical guidance-code base segment is missing"

    former_owners = (
        "dcoir_review/patches/dcoir_review_runtime_patches/part_02.py",
        "dcoir_review/patches/dcoir_review_strict_runtime_patches/part_02a.py",
    )
    for relative in former_owners:
        source = (SCRIPTS / relative).read_text(encoding="utf-8")
        assert "guidance_value_looks_like_code =" not in source, relative

    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    canonical = module.base.guidance_value_looks_like_code
    assert canonical.__module__ == "openrouter_pr_review"

    cases = (
        ("value = 1", "python", True),
        ("if ready:\n    run()", "python", True),
        ("if ready", "python", False),
        ("Use a safe parser instead.", "python", False),
        ("$x = Get-Content file.txt", "powershell", True),
        ("if ($x) {\nWrite-Host $x\n}", "powershell", True),
        ("permissions:\n  contents: read", "yaml", True),
        ("Use least privilege permissions.", "yaml", False),
        ("const x = value;", "javascript", True),
        ("return result;", "typescript", True),
        ("foo=bar", "text", True),
        ("Use foo=bar for this setting.", "text", False),
        ("```python\nvalue = 1\n```", "python", True),
        ("value = 1\nUse this value carefully.", "python", False),
    )
    for value, language, expected in cases:
        assert canonical(value, language) is expected, (value, language, expected)

    for group_name in PRODUCTION_PATCH_GROUPS:
        for patch_name in getattr(entrypoint, group_name):
            entrypoint._apply_patch_modules(module, (patch_name,))
            assert module.base.guidance_value_looks_like_code is canonical, (
                f"{patch_name} replaced canonical guidance_value_looks_like_code"
            )

    stored = [
        name for name, value in vars(module.base).items()
        if "guidance_value_looks_like_code" in name
        and name.startswith("_dcoir_")
        and callable(value)
    ]
    assert stored == [], stored


def assert_canonical_sanitize_text_ownership() -> None:
    former_owners = (
        "dcoir_review/patches/dcoir_review_required_runtime_patch_v6/part_01a.py",
        "dcoir_review/patches/dcoir_review_required_runtime_patch_v7/part_01a.py",
    )
    for relative in former_owners:
        source = (SCRIPTS / relative).read_text(encoding="utf-8")
        assert "def _patch_sanitize_text(" not in source, relative
        assert "original_sanitize_text" not in source, relative

    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    canonical = module.base.sanitize_text
    assert canonical.__module__ == "openrouter_pr_review"

    for group_name in PRODUCTION_PATCH_GROUPS:
        for patch_name in getattr(entrypoint, group_name):
            entrypoint._apply_patch_modules(module, (patch_name,))
            assert module.base.sanitize_text is canonical, (
                f"{patch_name} replaced canonical sanitize_text"
            )

    stored = [
        name for name, value in vars(module.base).items()
        if "sanitize_text" in name and name.startswith("_dcoir_") and callable(value)
    ]
    assert stored == [], stored


def assert_canonical_payload_builder_ownership() -> None:
    from dcoir_review import per_file_review

    v32_source = (SCRIPTS / "dcoir_review_required_runtime_patch_v32.py").read_text(
        encoding="utf-8"
    )
    assert "hardened.build_openrouter_payload =" not in v32_source
    assert "module.build_openrouter_payload =" not in v32_source
    assert "_dcoir_review_v32_original_build_openrouter_payload" not in v32_source
    assert "def apply_reasoning_payload_policy(" in v32_source

    routing_source = (SCRIPTS / "dcoir_review" / "per_file_routing.py").read_text(
        encoding="utf-8"
    )
    assert routing_source.count("hardened.build_openrouter_payload = build_openrouter_payload") == 1
    assert routing_source.count("module.build_openrouter_payload = build_openrouter_payload") == 1
    assert "_dcoir_per_file_routing_original_build_openrouter_payload" not in routing_source
    assert "reasoning_policy.apply_reasoning_payload_policy" in routing_source

    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    canonical = module.hardened.build_openrouter_payload
    assert canonical.__module__ == "dcoir_review.per_file_routing", canonical.__module__
    if hasattr(module, "build_openrouter_payload"):
        assert module.build_openrouter_payload is canonical

    stored = [
        name
        for owner in (module, module.hardened)
        for name, value in vars(owner).items()
        if "build_openrouter_payload" in name
        and name.startswith("_dcoir_")
        and callable(value)
    ]
    assert stored == [], stored

    before = module.hardened.build_openrouter_payload
    per_file_review.apply_pareto_context_module(module)
    assert module.hardened.build_openrouter_payload is before


def assert_canonical_per_file_review_ownership() -> None:
    from dcoir_review import per_file_review

    assert per_file_review.STAGE_ORDER == (
        "stage-local-routing",
        "semantic-result-reuse",
        "base-review",
    )

    semantic_source = (SCRIPTS / "dcoir_review" / "semantic_result_reuse.py").read_text(
        encoding="utf-8"
    )
    routing_source = (SCRIPTS / "dcoir_review" / "per_file_routing.py").read_text(
        encoding="utf-8"
    )
    canonical_source = (SCRIPTS / "dcoir_review" / "per_file_review.py").read_text(
        encoding="utf-8"
    )
    assert "module.review_single_file_context =" not in semantic_source
    assert "module.review_single_file_context =" not in routing_source
    assert "_dcoir_per_file_routing_original_review_single_file_context" not in routing_source
    assert "def build_per_file_semantic_result_reuse_stage(" in semantic_source
    assert "def build_per_file_routing_stage(" in routing_source
    assert canonical_source.count("module.review_single_file_context = review_single_file_context") == 1
    assert "semantic_result_reuse.build_per_file_semantic_result_reuse_stage" in canonical_source
    assert "per_file_routing.build_per_file_routing_stage" in canonical_source

    entrypoint = DcoirReviewEntrypoint()
    assert "dcoir_review.semantic_result_reuse" not in entrypoint.terminal_patch_module_names
    assert entrypoint.stage_local_patch_module_names == ("dcoir_review.per_file_review",)

    module = entrypoint.import_module(entrypoint.review_module_name)
    entrypoint.apply_runtime_patches(module)
    canonical = module.review_single_file_context
    assert canonical.__module__ == "dcoir_review.per_file_review", canonical.__module__
    assert tuple(module.DCOIR_PER_FILE_REVIEW_STAGE_ORDER) == per_file_review.STAGE_ORDER

    stored = [
        name
        for name, value in vars(module).items()
        if "review_single_file_context" in name
        and name.startswith("_dcoir_")
        and callable(value)
    ]
    assert stored == [], stored

    before = module.review_single_file_context
    per_file_review.apply_pareto_context_module(module)
    assert module.review_single_file_context is before


def assert_canonical_finding_comment_render_ownership() -> None:
    from dcoir_review import finding_comment_render

    former_renderer_owners = (
        "dcoir_review/patches/dcoir_review_runtime_patches/part_02.py",
        "dcoir_review/patches/dcoir_review_strict_runtime_patches/part_02a.py",
        "dcoir_review/patches/dcoir_review_required_runtime_patches/part_02a.py",
        "dcoir_review/patches/dcoir_review_required_runtime_patch_v2/part_02.py",
        "dcoir_review/patches/dcoir_review_required_runtime_patch_v3/part_02.py",
        "dcoir_review/patches/dcoir_review_required_runtime_patch_v4_apply/part_01.py",
        "dcoir_review/patches/dcoir_review_required_runtime_patch_v5_apply/part_01.py",
        "dcoir_review/patches/dcoir_review_required_runtime_patch_v8/part_01a.py",
        "dcoir_review_required_runtime_patch_v9_prompting.py",
        "dcoir_review/patches/dcoir_review_required_runtime_patch_v13/part_02a.py",
        "dcoir_review/patches/dcoir_review_required_runtime_patch_v16/part_02.py",
        "dcoir_review_required_runtime_patch_v20.py",
        "dcoir_review/verified_finding_render.py",
        "dcoir_review/repair_pipeline.py",
        "dcoir_review_required_runtime_patch_v30.py",
    )
    for relative in former_renderer_owners:
        source = (SCRIPTS / relative).read_text(encoding="utf-8")
        assert "build_inline_comment =" not in source, relative
        assert "original_build_inline_comment" not in source, relative

    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    starting = module.base.build_inline_comment
    canonical = starting if starting.__module__ == "dcoir_review.finding_comment_render" else None
    seen = canonical is not None
    for group_name in PRODUCTION_PATCH_GROUPS:
        for patch_name in getattr(entrypoint, group_name):
            before = module.base.build_inline_comment
            entrypoint._apply_patch_modules(module, (patch_name,))
            active = module.base.build_inline_comment
            if patch_name == "dcoir_review.finding_comment_render":
                if canonical is None:
                    assert active is not before
                    canonical = active
                else:
                    assert active is canonical
                seen = True
                assert canonical.__module__ == "dcoir_review.finding_comment_render"
                continue
            if canonical is None:
                assert active is before, f"{patch_name} replaced build_inline_comment before canonical renderer"
            else:
                assert active is canonical, f"{patch_name} replaced canonical finding-comment renderer"

    assert seen and callable(canonical)
    stored = [
        name for name, value in vars(module.base).items()
        if "build_inline_comment" in name and name.startswith("_dcoir_") and callable(value)
    ]
    assert stored == [], stored
    before = module.base.build_inline_comment
    finding_comment_render.apply_pareto_context_module(module)
    assert module.base.build_inline_comment is before


def assert_canonical_hybrid_review_ownership() -> None:
    from dcoir_review import review_orchestration

    assert review_orchestration.STAGE_ORDER == (
        "quality-gate",
        "adversarial-confirmation",
        "semantic-adjudication",
        "semantic-adjudication-confidence",
        "semantic-review-ledger",
        "semantic-result-reuse",
        "candidate-scoped-escalation",
        "canonical-semantic-context",
        "review-scope-terminal-translation",
        "structured-result-disposition",
    )

    former_hybrid_owners = (
        "dcoir_review/quality_gate.py",
        "dcoir_review_required_runtime_patch_v32.py",
        "dcoir_review_required_runtime_patch_v35.py",
        "dcoir_review/semantic_adjudication_confidence.py",
        "dcoir_review/semantic_review_ledger_hooks.py",
        "dcoir_review/semantic_result_reuse.py",
        "dcoir_review_required_runtime_patch_v44.py",
        "dcoir_review_required_runtime_patch_v46.py",
        "dcoir_review/review_scope_guard_hooks.py",
        "dcoir_review/structured_result_disposition.py",
    )
    for relative in former_hybrid_owners:
        source = (SCRIPTS / relative).read_text(encoding="utf-8")
        assert "module.openrouter_review_with_hybrid_first_pass =" not in source, relative
        assert "original_hybrid_first_pass" not in source, relative

    entrypoint = DcoirReviewEntrypoint()
    module = entrypoint.import_module(entrypoint.review_module_name)
    base_after_v16 = None
    final_hybrid = None
    orchestration_seen = False

    for group_name in PRODUCTION_PATCH_GROUPS:
        for patch_name in getattr(entrypoint, group_name):
            entrypoint._apply_patch_modules(module, (patch_name,))
            active = module.openrouter_review_with_hybrid_first_pass
            if patch_name == "dcoir_review_required_runtime_patch_v16":
                base_after_v16 = active
                continue
            if base_after_v16 is None:
                continue
            if patch_name == "dcoir_review.review_orchestration":
                orchestration_seen = True
                final_hybrid = active
                assert final_hybrid is not base_after_v16
                assert final_hybrid.__module__ == "dcoir_review.review_orchestration"
                assert tuple(module.DCOIR_REVIEW_ORCHESTRATION_STAGE_ORDER) == review_orchestration.STAGE_ORDER
                continue
            if not orchestration_seen:
                assert active is base_after_v16, f"{patch_name} replaced the pre-orchestration hybrid review callable"
            else:
                assert active is final_hybrid, f"{patch_name} replaced canonical hybrid review orchestration"

    assert orchestration_seen and callable(final_hybrid)
    former_storage_attrs = (
        "_dcoir_quality_gate_original_hybrid_first_pass",
        "_dcoir_review_v32_original_hybrid_first_pass",
        "_dcoir_review_v35_original_hybrid_first_pass",
        "_dcoir_semantic_adjudication_confidence_original_hybrid_first_pass",
        "_dcoir_review_semantic_ledger_original_hybrid_first_pass",
        "_dcoir_v44_original_hybrid_first_pass",
        "_dcoir_v46_original_hybrid_first_pass",
        "_dcoir_review_review_scope_guard_original_hybrid_first_pass",
        "_dcoir_review_structured_result_disposition_prior_hybrid_first_pass",
    )
    present = [name for name in former_storage_attrs if callable(getattr(module, name, None))]
    assert present == [], present

    before = module.openrouter_review_with_hybrid_first_pass
    review_orchestration.apply_pareto_context_module(module)
    assert module.openrouter_review_with_hybrid_first_pass is before


def main() -> None:
    assert_numbered_patch_freeze_before_cutover()
    assert_patch_inventory_is_source_complete()
    assert_canonical_hybrid_review_ownership()
    assert_canonical_payload_builder_ownership()
    assert_canonical_per_file_review_ownership()
    assert_canonical_finding_comment_render_ownership()
    assert_canonical_config_loader_ownership()
    assert_canonical_validation_text_ownership()
    assert_canonical_quality_retry_ownership()
    assert_canonical_progress_reporter_ownership()
    assert_canonical_per_file_prompt_ownership()
    assert_canonical_guidance_code_classifier_ownership()
    assert_canonical_sanitize_text_ownership()
    assert_segment_registry_is_complete()

    for layer in LAYER_SEGMENTS:
        paths = RuntimeSegmentLoader(layer).segment_paths()
        assert all(path.is_file() for path in paths), layer
        assert_segment_source_sizes(paths, layer)

    direct_paths = tuple((SCRIPTS / "dcoir_review" / relative) for relative in DIRECT_IMPORT_MODULES)
    assert all(path.is_file() for path in direct_paths)
    assert_segment_source_sizes(direct_paths, "direct-import")

    for layer, pairs in EXPECTED_ADJACENCY.items():
        segments = LAYER_SEGMENTS[layer]
        for first, second in pairs:
            index = segments.index(first)
            assert segments[index + 1] == second, (layer, first, second)

    for layer, pairs in PATCH_ADJACENCY.items():
        segments = LAYER_SEGMENTS[layer]
        directory = Path(segments[0]).parent.as_posix()
        for first_name, second_name in pairs:
            first = f"{directory}/{first_name}"
            second = f"{directory}/{second_name}"
            index = segments.index(first)
            assert segments[index + 1] == second, (layer, first, second)

    for layer, pairs in SELFTEST_ADJACENCY.items():
        segments = LAYER_SEGMENTS[layer]
        directory = Path(segments[0]).parent.as_posix()
        for first_name, second_name in pairs:
            first = f"{directory}/{first_name}"
            second = f"{directory}/{second_name}"
            index = segments.index(first)
            assert segments[index + 1] == second, (layer, first, second)

    for module_name, exports in EXPECTED_EXPORTS.items():
        module = importlib.import_module(module_name)
        missing = [name for name in exports if not hasattr(module, name)]
        assert not missing, (module_name, missing)

    print("DCOIR Review runtime module-loader selftest passed")


if __name__ == "__main__":
    main()
