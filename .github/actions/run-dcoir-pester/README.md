# run-dcoir-pester

Reusable DCOIR composite action for supporting Pester evidence under Windows
PowerShell 5.1.

## Contract

- The caller owns triggers, permissions, artifact upload, retention, and the
  bounded workflow claim.
- This action installs one exact Pester version, runs pass/fail/empty-discovery
  controls, and executes `.github/pester` through the repository wrapper.
- The action exposes the PowerShell and Pester versions plus discovered,
  passed, failed, and skipped counts.
- The caller-provided result path must be uploaded as NUnit XML even when a
  later workflow step fails.
- Pester remains supporting evidence. This action does not replace the
  collector harness, Windows PowerShell parser validation, PSScriptAnalyzer,
  DCOIR custom checks, fixtures, or assembly parity.
- The action must not use secrets, mutate repository history, or perform live
  collector operations.
- Compensating evidence for composite-action log grouping is provided by named
  control and suite steps, explicit stdout summaries and outputs, and the
  caller-uploaded NUnit artifact.

## Maintenance

Change this action when the approved Pester version, runner controls, result
contract, or Windows PowerShell 5.1 execution behavior changes. Run the local
runner controls, full Pester suite, workflow inventory, and reusable-contract
audits after edits.
