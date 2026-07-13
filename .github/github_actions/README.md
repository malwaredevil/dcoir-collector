# GitHub workflow authority pointer

This folder holds repo-native GitHub workflow support surfaces.

Current authority model:

- The workflow YAML body is the executable source of truth.
- The top comment block in each `.github/workflows/*.yml` file owns workflow-specific execution guidance.
- GitHub is canonical for workflow and source truth.
- Supabase `ircore` is the operational routing, validation, lessons, and active-state surface.
- Historical migration evidence may remain under governed staging paths, but active workflow routing comes from GitHub source and Supabase `ircore`.

## Workflow modularization contract

Issue #194 governs the repo-wide GitHub Actions restructuring into deliberate entry workflows, reusable workflows, composite actions, repo-local scripts, and audited contracts.

The foundation surfaces are:

- `workflow_modularization_contracts.json`: the issue #194 contract registry for all existing workflow files, required contract families, migration status, rollback notes, and acceptance evidence.
- `workflow_inventory.json`: generated machine-readable inventory for the current workflow surface.
- `workflow_inventory.md`: generated readable contract matrix for operators and reviewers.
- `tools/build_workflow_inventory.py`: regenerates the JSON and Markdown inventory; use `--check` in CI to fail on stale generated outputs.
- `tools/check_workflow_modularization_contracts.py`: validates that every workflow has a contract entry, required contract families are mapped, reusable workflows avoid generic catch-all posture, composite actions expose compensating evidence, and inventory fields match the registry.

Regenerate the inventory after any workflow, reusable workflow, composite action, report, artifact, or workflow-tooling change:

```bash
python .github/github_actions/tools/build_workflow_inventory.py
python .github/github_actions/tools/build_workflow_inventory.py --check
python .github/github_actions/tools/check_workflow_modularization_contracts.py
```

Entry workflows must keep operator-visible contract surfaces visible: workflow name, triggers, path filters, schedules, dispatch inputs, permissions, concurrency, secret names, artifact names, report path shapes, and central-reporter compatibility. Reusable workflows should be family-specific contract surfaces, composite actions should be mechanical step bundles only, and complex safety/reporting logic should remain script-backed and testable.

Phase 1 established the inventory, contract registry, and audit foundation.
The bundled Phase 2+ implementation now makes the architecture executable:

- primary entry workflows call repo-local `reusable-*` workflows;
- reusable workflows own moved job bodies while entry workflows retain triggers,
  path filters, schedules, dispatch inputs, permissions, concurrency, and
  operator-facing headers;
- repeated mechanical step bundles use repo-local composite actions for shared
  runtime setup, artifact upload, validation, packaging, and report mechanics;
- reusable workflow and composite action contracts are audited for local target
  existence, caller input/secret compatibility, checkout-before-local-action
  posture, compensating evidence notes, and stale inventory/readback drift.

Future workflow changes should prefer updating the reusable workflow or
composite action module that owns the shared mechanic before editing many
entry workflows. Keep entry workflow contracts visible, and regenerate the
inventory after module, caller, artifact, report, or audit changes.

`tools/generate_workflow_inventory.py` is a compatibility wrapper for
`tools/build_workflow_inventory.py`; both names use the same canonical inventory
format.

Recommended local validation after workflow-tooling changes:

```bash
python3 .github/github_actions/tools/build_workflow_inventory.py --check
python3 .github/github_actions/tools/check_workflow_modularization_contracts.py
python3 .github/github_actions/tools/audit_reusable_contracts.py
python3 .github/github_actions/tools/check_workflow_consistency_drift.py
python3 .github/github_actions/tools/check_workflow_action_versions.py
```
