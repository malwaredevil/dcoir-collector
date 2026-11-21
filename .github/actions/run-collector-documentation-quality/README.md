# run-collector-documentation-quality

Reusable DCOIR GitHub Actions composite action for issue #194 workflow modularization.

## Contract

- Callers keep triggers, permissions, secrets, artifact names, and report paths visible in the entry or reusable workflow.
- This action owns repeated mechanical documentation-quality step logic only.
- Callers must run `.github/actions/assemble-collector-harness` before this action. The assembler creates `project_sources/collector/harness/run_DCOIR_Tests.generated.ps1` from the checked-in harness parts in filename-sorted order; callers must preserve that canonical ordering.
- This action requires the generated harness at that path and fails if it is missing. It does not assemble or modify the harness, including for documentation-only runs.
- The action must not directly reference `secrets.*` or mutate repository content.
- Compensating evidence is provided by caller-visible step names, explicit inputs, assembler output, stdout markers, generated files, uploaded artifacts, or the caller workflow report section.

## Maintenance

Change this module when the shared mechanic changes, then run the workflow maintenance audit and applicable caller workflows.
