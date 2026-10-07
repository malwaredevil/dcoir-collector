# run-psscriptanalyzer

Reusable DCOIR GitHub Actions composite action for PSScriptAnalyzer static analysis of collector PowerShell source.

## Contract

- Callers keep triggers, permissions, artifact names, retention, and workflow claims visible in the entry or reusable workflow.
- This action owns the repeated mechanical step for running `Invoke-ScriptAnalyzer` against all collector PS1 source files under `project_sources/collector/source/`.
- The action writes a `dcoir_powershell_analyzer_report_v1` JSON report to the caller-provided repo-relative path.
- The action can fail the step on Error-severity findings (`fail-on-error-severity` input, default `true`), but the reusable validate-on-pr and validate-on-push workflows pass `'false'` and enforce the gate after all reports exist in `.github/scripts/Test-DcoirStaticAnalysisValidationGate.ps1`. Analyzer invocation errors still fail the step.
- The action must not upload artifacts, enable code scanning, generate SARIF, use `pull_request_target`, reference `secrets.*`, or mutate repository history.
- Compensating evidence is provided by caller-visible step names, explicit inputs, stdout severity breakdown, the generated JSON report, and uploaded artifacts from the caller workflow.

## Maintenance

Change this module when the PSScriptAnalyzer rule set or collector source discovery logic changes. Change the merge gate threshold in `.github/scripts/Test-DcoirStaticAnalysisValidationGate.ps1`. Then run local validation and applicable workflow readback.
