# Post-modularization audit

Issue #355 audits the repository state after PR #350 and the follow-up
modularization PRs #361 through #368. The audit is deliberately bounded: it
removes proven migration residue and strengthens structural validation without
reopening working modules for aesthetic refactoring.

## Decision summary

| Classification | Surface | Decision and evidence |
| --- | --- | --- |
| Delete | PR #350 connector report sidecars and their dedicated reassembler | Completed by PR #368. The sidecars were temporary derivatives, had drifted from their canonical reports, and had no runtime consumer. |
| Delete | Retired Airtable tooling, dependencies, secrets, and active routing guidance | Completed by PR #361. No active Airtable integration remains. |
| Consolidate | DCOIR Review loader coverage | Keep the single `LAYER_SEGMENTS` registry and strengthen its selftest to require an exact match between registered and on-disk segments. This rejects missing, duplicate, and orphaned segments without adding another registry. |
| Retain | DCOIR Review top-level wrappers | Stable script entrypoints and import surfaces. Runtime and selftest callers load their implementations through the shared module loader. |
| Retain | Collector tool facades | Stable CLI/import contracts used by tests, manifests, generated reports, workflow validation, or sibling modules. |
| Retain | Manual-test runner and check facades | Required by the PowerShell launcher, bundle builder, download installer, and documented operator entrypoint. |
| Retain | Workflow inventory generator alias | Deliberate compatibility command enforced by the workflow consistency contract and documented alongside the canonical builder. |
| Retain | Canonical generated validation reports | Stable validator and reviewer contracts governed by the generated-evidence retention policy. Their size does not make them maintained source modules. |
| Retain | Remaining Airtable text | Retired-label and stale-guidance detectors, explicit historical-only workflow notes, generated inventories, fixtures, operator history, and staging evidence. These do not provide an active Airtable integration. |

## Loader integrity

The DCOIR Review module loader owns 111 Python segment paths. The audit found:

- no missing registered segment;
- no duplicate registration;
- no unregistered segment file;
- no segment above the 15 KB maintained-source policy;
- stable wrapper exports covered by the existing loader selftest.

The selftest now compares the complete on-disk segment set with the registry so
future migration residue cannot silently become an orphan module.

## Follow-up disposition

No new follow-up issue is warranted from this audit. Removing the retained
facades would break documented or executable compatibility contracts, and
removing historical Airtable strings would weaken stale-authority detection or
rewrite governed evidence. Any future behavior-changing consolidation should be
proposed independently with its own dependency and parity evidence.

## Validation commands

```bash
python .github/dcoir_review/scripts/dcoir_review_runtime_module_loader_selftest.py
python .github/github_actions/tools/check_workflow_modularization_contracts.py
python .github/github_actions/tools/check_workflow_consistency_drift.py
python scripts/audit_generated_evidence.py --check
```
