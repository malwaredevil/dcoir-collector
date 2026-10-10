# run-psscriptanalyzer: single canonical analyzer owner (issue #606)

This composite action installs PSScriptAnalyzer **1.25.0** and runs
`project_sources/collector/tools/run_powershell_analyzer.py` against the
`powershell_surface_inventory.json` target set. The retired action-local
PowerShell producer is no longer used. Exactly one producer writes schema
`dcoir_powershell_analyzer_report_v1` and produces JSON and Markdown evidence.

The Python owner runs both built-in rules (preserving legacy findings and every
Error) and the six rules from `PSScriptAnalyzerSettings.psd1`. New unbaselined
Warnings from the six declared policy rules and **every Error finding** block
`.github/scripts/Test-DcoirStaticAnalysisValidationGate.ps1`. Other built-in
Warnings remain visible but do not silently enlarge the blocking ruleset.

`project_sources/collector/powershell_analyzer_baseline.json` records each
reviewed pre-existing Warning exception with a file/rule/fingerprint and reason.
The baseline is fail-closed: stale entries and attempts to suppress Errors fail.
Never create wildcard suppression or disable the policy to make CI green.

The legacy `fail-on-error-severity` action input remains for existing callers
until issue #608 retires dead action inputs. PR/push callers set it to `false`,
so their shared static-analysis gate enforces counts after review-assist has
consumed the produced report. Analyzer execution, missing settings or baseline,
missing target hashes, malformed data, and report errors still fail the action.

The action does not upload artifacts, add triggers, use privileged events,
mutate Git history, or request independent reviews. Callers retain those
boundaries. Validate with Python analyzer unit tests, workflow/action contract
checks, and the exact-head Windows CI jobs after publication.
