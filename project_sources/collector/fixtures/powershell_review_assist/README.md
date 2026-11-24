# PowerShell Review-Assist Fixtures

This directory holds seeded examples for the #268 review-assist report contract.

- `good_report.json` is a compact good-path fixture derived from the generated #268 report. Its `summary` and channel counts describe the included sample arrays, and full-report counts are preserved under `fixture_contract`; the complete reviewer artifact is `project_sources/collector/powershell_review_assist_report.json`.
- The optional #262 analyzer report is intentionally represented as `optional_missing` in the seeded example unless a validated analyzer artifact is explicitly supplied.
- `issue608_slice6_legacy_wrapper.py` and `issue608_slice6_legacy_c8c76c59/` are the frozen, non-production Issue #608 Slice 6 legacy oracle: the removed workflow metadata wrapper and the complete report implementation archived byte-for-byte from main SHA `c8c76c59`. `issue608_slice6_legacy_artifact_manifest.json` pins each file to its Git blob SHA-1. `project_sources/collector/tools/test_run_powershell_review_assist_workflow_mode.py` runs them in an isolated interpreter and compares complete native workflow-mode bytes against their output. Do not edit or regenerate these files to make tests pass.
- Failure examples are covered by `project_sources/collector/tools/test_run_powershell_review_assist_report.py` so negative cases do not overwrite the committed good-path report artifacts.

The #268 fixtures do not claim workflow readiness, SARIF output, code scanning, required-check behavior, artifact retention, Pester promotion, changed-file gating, #269/#270 completion, or parent #260 closeability.
