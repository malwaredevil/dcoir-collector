# Issue #380 workflow regression evidence

## Purpose

This note records the dedicated repository evidence for issue #380, the post-consolidation workflow regression check. It summarizes the successful checkout-backed validation run that compared the post-relocation workflow surface with the #382/#383 pre-consolidation baseline and ran the current workflow audit suite.

This file is durable documentation of the evidence. The run-specific source of truth remains the referenced GitHub Actions run and artifact.

## Evidence source

- Issue: #380
- Baseline ref used by the audit harness: `44fc4a4dc5f8eef78536979decb60377a214e6c2`
- Staged exec request: `exec-20260713-issue380-regression-003`
- Request commit on `main`: `8121615e417b5e43662907f5c06aa8d531afdce3`
- Workflow run: `29235345417`
- Workflow job: `86768609431`
- Workflow result: success
- Command exit code: `0`
- Artifact: `8273179697` (`chatgpt-exec-exec-20260713-issue380-regression-003`)
- Artifact digest: `sha256:9ef4389730f85f4ee77af9c19e2be298b11ada55a4047e76357ee2ee52eb0c02`
- Artifact size: 122,558 bytes
- Artifact expiration: 2026-07-20

## Parity results

The audit harness generated baseline inventory from the baseline checkout rather than relying on an absent committed JSON inventory file. It then compared normalized baseline and current outputs.

- `baseline_inventory_generation_attempted`: `true`
- `normalized_inventory_json_generated_parity`: `true`
- `normalized_inventory_markdown_generated_parity`: `true`
- `normalized_contract_parity`: `true`
- Normalized inventory JSON diff: no normalized diff
- Normalized inventory Markdown diff: no normalized diff
- Normalized modularization contract diff: no normalized diff

## Audit command results

The following current-checkout audit commands completed with exit code `0`:

- `python .github/dcoir_review/scripts/check_workflow_action_versions.py`
  - Passed for 57 workflow files and 19 composite action files.
- `python .github/dcoir_review/scripts/check_workflow_consistency_drift.py`
  - Passed for 57 workflow files plus `.github/github_actions/README.md` and `.github/README.md`.
- `python .github/dcoir_review/scripts/build_workflow_inventory.py --check`
  - Passed for 29 workflow files.
- `python .github/dcoir_review/scripts/check_workflow_modularization_contracts.py`
  - Passed for 29 workflow files and 29 contracts.
- `python .github/dcoir_review/scripts/audit_reusable_contracts.py`
  - Passed for 29 primary workflows, 28 reusable workflow definitions, 29 local reusable workflow calls, 19 local action definitions, and 117 local action calls.

## Post-relocation workflow signals

The validation readback also checked the latest available post-relocation runs for the two workflows named in #380 scope item 4:

- `workflow-maintenance-audit`: latest read run `29232347703`, created 2026-07-13T07:31:26Z, head `db1e725a229ec4366495c9c49095b4f32640a8b0`, conclusion success.
- `scheduled-health-check`: latest read run `29231885941`, created 2026-07-13T07:22:53Z, head `20b91f9ee8a239d489f962b762804b0d2a83f921`, conclusion success.

## Scope note

The harness evaluated current ref `1f422b6adf844484cda68e36ce2a4665f593a4d3`; the changed files at that ref were request-scoped status report files only. The workflow source, reusable workflow, composite action, inventory, and contract checks above were still run against the checked-out repository workflow surfaces.

## Acceptance mapping

- Every primary workflow behavior after full relocation matches the prequel-established baseline: supported by normalized workflow inventory and modularization contract parity.
- Reusable workflow and composite action call sites verified post-relocation: supported by `audit_reusable_contracts.py` and `check_workflow_action_versions.py` passing on the current checkout.
- Any regression found fixed or escalated: no regression surfaced in the successful exec-003 evidence set.
- Dedicated branch and PR evidence: this file is intended to satisfy the durable evidence-record portion of that acceptance criterion once the PR carrying it is merged.

## Remaining closeout

Before #380 is closed, the PR containing this evidence must complete the normal PR gates, merge, and receive final live readback against the PR and issue state.
