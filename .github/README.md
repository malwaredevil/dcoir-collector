# GitHub operating surfaces

This folder contains repository-native GitHub support surfaces for the DCOIR collector repository.

- `ISSUE_TEMPLATE/` keeps issue intake structured with YAML forms that each apply exactly one approved `area:*` label and one approved `type:*` label.
- `PULL_REQUEST_TEMPLATE.md` preserves label discipline, issue scope review, readback, and governed review gates.
- `workflows/` contains validation, packaging, reporting, and maintenance automation.
- `dependabot.yml` and related metadata support repository maintenance.
- `../.github/github_actions/workflow_modularization_contracts.json` and generated workflow inventory files record the issue #194 workflow restructuring contract.

## Issue intake model

Use the closest issue form instead of a generic issue whenever possible. Each form owns a single label pair so the issue starts inside the approved taxonomy.

- Collector issue: `area:collector`, `type:bug`
- Workflow issue: `area:workflows`, `type:bug`
- Gemini agent issue: `area:gemini-agent`, `type:bug`
- Validation finding: `area:validation`, `type:bug`
- Documentation or workflow correction: `area:docs`, `type:maintenance`
- Knowledge docs correction: `area:knowledge-docs`, `type:maintenance`
- Operator tooling request: `area:operator-tooling`, `type:maintenance`
- Supabase ircore request: `area:supabase-ircore`, `type:maintenance`
- Project tracking request: `area:project-tracking`, `type:planning`
- Repository governance request: `area:repo-governance`, `type:planning`
- Feature request: `area:repo-governance`, `type:enhancement`
- Bug report: `area:repo-governance`, `type:bug`

API-created, connector-created, or otherwise programmatically created issues must mirror the closest issue form. Apply only that form's approved label pair. If no issue form fits, stop and ask the operator before creating, relabeling, or silently broadening the issue.

## Operating rules

- Keep GitHub as the canonical source for repo content and workflow behavior.
- Do not describe retired mirror or parity-refresh paths as active maintenance surfaces.
- Preserve clear separation between collector/runtime guidance and repo/governance guidance.
- For workflow restructuring work, keep entry workflow contract surfaces visible and use the repo-local workflow inventory and modularization audits before claiming readiness.
- Keep `.github/github_actions/github_intake_taxonomy.json` aligned with issue forms, PR-template requirements, label policy, and the intake validator.
