"""Audited source witnesses for the fail-closed Git-discovery fallback proof."""

KIND = "git-discovery-fallback"
STATE = "source-backed-pending-independent-verification"
VERIFIER = "project_sources/collector/tools/verify_powershell_surface_inventory_ci.py"
ACTION = ".github/actions/run-psscriptanalyzer/action.yml"
OUTPUTS = "project_sources/collector/tools/powershell_surface_inventory_outputs.py"
DISCOVERY = "project_sources/collector/tools/powershell_surface_inventory_discovery.py"
ANALYZER = "project_sources/collector/tools/run_powershell_analyzer.py"
ANALYZER_CLI = "project_sources/collector/tools/powershell_analyzer_cli.py"
ANALYZER_INVENTORY = "project_sources/collector/tools/powershell_analyzer_inventory.py"
ANALYZER_CONTRACT = "project_sources/collector/tools/powershell_analyzer_contract.py"
ANALYZER_EXECUTION = "project_sources/collector/tools/powershell_analyzer_execution.py"
INVENTORY_COMMON = "project_sources/collector/tools/powershell_surface_inventory_common.py"
COLLECTOR_PATH_SAFETY = "project_sources/collector/tools/collector_tool_path_safety.py"
INVENTORY_VALIDATION = "project_sources/collector/tools/powershell_surface_inventory_validation.py"
INVENTORY_CLASSIFICATION = "project_sources/collector/tools/powershell_surface_inventory_classification.py"
INVENTORY_PROFILES = "project_sources/collector/tools/powershell_surface_inventory_profiles.py"
INVENTORY_CONTROLS = "project_sources/collector/tools/powershell_surface_inventory_controls.py"
INVENTORY_WORKFLOW_YAML = "project_sources/collector/tools/powershell_surface_inventory_workflow_yaml.py"
_REQUIRED_SURFACES_ACTION = ".github/actions/verify-required-surfaces/action.yml"
_REQUIRED_SURFACES_CHECK = ".github/github_actions/tools/check_required_surfaces.py"
ROUTES = (
    ".github/workflows/validate-on-pr.yml",
    ".github/workflows/validate-on-push.yml",
    ".github/workflows/reusable-validate-on-pr.yml",
    ".github/workflows/reusable-validate-on-push.yml",
    _REQUIRED_SURFACES_ACTION,
    _REQUIRED_SURFACES_CHECK,
)
# 22 mandatory audited source witnesses. Attachment fetches 21 additional
# sources (the changed verifier is already loaded); independent verification
# re-fetches all 22. The two passes must not share trusted read caches.
PATHS = tuple(sorted((
    VERIFIER, ACTION, OUTPUTS, DISCOVERY, ANALYZER, ANALYZER_CLI,
    ANALYZER_INVENTORY, ANALYZER_CONTRACT, ANALYZER_EXECUTION,
    INVENTORY_COMMON, COLLECTOR_PATH_SAFETY, INVENTORY_VALIDATION,
    INVENTORY_CLASSIFICATION, INVENTORY_PROFILES, INVENTORY_CONTROLS,
    INVENTORY_WORKFLOW_YAML, *ROUTES,
)))
# SHA256 of the audited historical verify_inventory source segment. This
# source fingerprint is independent of Python's AST serialization format.
_unused_UNGUARDED_VERIFIER_SOURCE_SHA256 = "33f1ad0f23d65810b6217cf68cfd03bf3d8f3d56e86a7c3d808aeed1da790426"
# Full source pin also covers decorators and module-level verifier bindings.
_unused_UNGUARDED_VERIFIER_FILE_SHA256 = "6133b38fd55f0b42271dec81f638e0acfc19ce76034b58472b5c3c184da65e66"
_FALLBACK_DISCOVERY_SHA = "9aad0c1d5b0c08fa4fd9c7fe206465cbabcfc569da87070ca0693dd7e61a5e91"
# Exact historical caller/analysis sources; unknown gates or helper steps abstain.
# Version 1 preserves the pre-Draft-gate source set used by historical replay.
_AUDITED_SOURCE_SHA256_V1 = {
    ACTION: "09a62842cb1a33bfdaedefc40360c1df9c4799ec4786e9b473d969440a84eed7",
    OUTPUTS: "1615467f2934487de2bc58e9ff2fe0b53221ad74b407c7e6e69a4a5807b311d8",
    DISCOVERY: _FALLBACK_DISCOVERY_SHA,
    ANALYZER: "3362ae4374d23c66615c9458145ca58b9b0b8031c7b9e980bc17ce5f686cb86b",
    ANALYZER_CLI: "37af5f839ad84e963f140ad338b56df7a72fe07cdf051f366ccad05385bae49e",
    ANALYZER_INVENTORY: "fb0d604a3a7631714437a53bb1425755d9387037f381ee27e8c0143d5f33a058",
    ANALYZER_CONTRACT: "1dca2587eee48fba0c0bc476254189004bf75cf7cdb4e5d2ac356504cdaff9cf",
    ANALYZER_EXECUTION: "88d5872d528ce363d90e2e34cba74061a03f65755c61a501c12d25c197681854",
    INVENTORY_COMMON: "d9fe1fdfbf87002d2a437f491eb8602a2f7889237da3213739a858f3e2778562",
    COLLECTOR_PATH_SAFETY: "5aebb6011407968c74ffe5ea0ebd40d38be7ee01772ae9a83c4fad452cb41b76",
    INVENTORY_VALIDATION: "7c70a7dc8cdb583717871db66adf61399a77a0c4b176f96a74821643924ad0d0",
    INVENTORY_CLASSIFICATION: "f41c097e63852bd7a6b5d11b0abd55a2c390d0df70bec73a12e46fd992ae8f3b",
    INVENTORY_PROFILES: "a92f77806aebf5f4209a77e5e40cfdb99d89991e5fff6d99b24f17f96fd57cbd",
    INVENTORY_CONTROLS: "1456d8a83b60e56d5e467384dd7dae63a52d89e6bf9c1be7bb4dab61698c0a68",
    INVENTORY_WORKFLOW_YAML: "af540a1b8d973bd73768fd347c17d53b4a388484f132614c8420740f74ccd5e3",
    _REQUIRED_SURFACES_ACTION: "57b4fb5fe5ee197b31c95d7dc0cff7425bb9a18f1739a21f2afb3871cb270db6",
    _REQUIRED_SURFACES_CHECK: "7bae51c61a42635a35e1b2c7119af2e3546f46d2486eec77b961d8c425ab08bc",
    ".github/workflows/validate-on-pr.yml": "2fe1df3acb85d218c754e8e771603cead9cad2664282b6f54a22e1c3ba277330",
    ".github/workflows/validate-on-push.yml": "212c059b4609ed73defc8f20c0a1806e3b5f72eac36cd75f2bb2a7147be2ddb1",
    ".github/workflows/reusable-validate-on-pr.yml": "c08ebc8fa2523a33707b305f39c11fac73dd544499b791c9df4fb1563d4e0833",
    ".github/workflows/reusable-validate-on-push.yml": "36d9562023641a65f5e0b28b8fd92ad4b63379b5e48c059b810bb45f92ef2448",
}
# Version 2 adds the current PR lifecycle gate while retaining the historical
# witnesses for sources that did not change.
_AUDITED_SOURCE_SHA256 = {
    **_AUDITED_SOURCE_SHA256_V1,
    ".github/workflows/validate-on-pr.yml": "faf2c87167b36244a0cc66d83ef47f121738a32902f3d812bc224de6d8afda6e",
    ".github/workflows/reusable-validate-on-pr.yml": "f984cf67b9e60522dcdf1d1e8d9493e2d39dbf2d38fb21e91951b316fd5fb457",
}
_AUDITED_SOURCE_HASH_VERSIONS = (
    _AUDITED_SOURCE_SHA256_V1,
    _AUDITED_SOURCE_SHA256,
)
