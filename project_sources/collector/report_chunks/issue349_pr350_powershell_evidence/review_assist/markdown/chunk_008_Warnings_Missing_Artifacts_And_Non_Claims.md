## Warnings, Missing Artifacts, And Non-Claims

### Carried Forward Warnings

- #265 `project_sources/collector/powershell_assembly_parity_report.json`: no baseline parity report supplied; shrink checks used current inventory controls only
- #266 `project_sources/collector/powershell_finding_governance_report.json`: optional PowerShell finding report not present: project_sources/collector/powershell_analyzer_report.json
- #267 `project_sources/collector/powershell_engine_pester_boundary_report.json`: workflow readiness remains a later explicit gate; #267 only defines evidence ownership
- #267 `project_sources/collector/powershell_engine_pester_boundary_report.json`: Windows PowerShell 5.1 runtime evidence remains separate from local static report generation
- #267 `project_sources/collector/powershell_engine_pester_boundary_report.json`: engine matrix row powershell-7-psscriptanalyzer artifact is not committed or claimed by this #267 boundary: project_sources/collector/powershell_analyzer_report.json
- #262 `project_sources/collector/powershell_analyzer_report.json`: optional analyzer evidence is absent; #268 does not claim live PSScriptAnalyzer evidence
- #267 `project_sources/collector/powershell_engine_pester_boundary_report.json`: workflow or local Windows PowerShell 5.1 validation report: external_or_future is not claimed by #267/#268
- #267 `project_sources/collector/powershell_engine_pester_boundary_report.json`: project_sources/collector/powershell_analyzer_report.json: not_committed_in_267_boundary is not claimed by #267/#268
- #267 `project_sources/collector/powershell_engine_pester_boundary_report.json`: future Pester test result artifact when a later gate enables it: external_or_future is not claimed by #267/#268
- #263 `project_sources/collector/powershell_rule_risk_fixture_report.json`: This #263 harness uses a deterministic local fixture analyzer through the #262 wrapper. It intentionally does not execute PSScriptAnalyzer, so this fixture report does not claim whether pwsh or the PSScriptAnalyzer module is installed in the current environment.

### Missing Artifacts

- #262 `project_sources/collector/powershell_analyzer_report.json`: optional analyzer evidence is absent; #268 does not claim live PSScriptAnalyzer evidence

### Unclaimed Artifacts

- #267 `workflow or local Windows PowerShell 5.1 validation report`: Declared by #267 boundary but not committed, not claimed, external, or future evidence.
- #267 `project_sources/collector/powershell_analyzer_report.json`: Declared by #267 boundary but not committed, not claimed, external, or future evidence.
- #267 `future Pester test result artifact when a later gate enables it`: Declared by #267 boundary but not committed, not claimed, external, or future evidence.

### Non-Claims

- No workflow YAML was changed by #268.
- No SARIF file is generated or uploaded by #268.
- No GitHub code-scanning alert or required-check behavior is enabled by #268.
- No workflow artifact retention behavior is configured by #268.
- No Pester result is promoted to blocking static-validation evidence by #268.
- No changed-file execution, path-filter behavior, PR-diff coverage, or changed-file gating is claimed by #268.
- No live PSScriptAnalyzer evidence is claimed when the #262 analyzer report is absent.
- No Windows PowerShell 5.1 runtime validation is claimed by #268.
- No #269, #270, PR/workflow readiness, or parent #260 closeability claim is made by #268.
- No function deletion readiness or dead-code removal claim is made by #306 reachability reporting.

