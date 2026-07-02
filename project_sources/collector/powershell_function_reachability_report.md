# PowerShell Function Reachability Report

- Schema: `dcoir_powershell_function_reachability_report_v1`
- Issue: #306
- Parent issue: #260
- Parser mode: `python_lexical_fallback`
- Validation: `pass`
- Functions: `170`

## Classification Summary

| Classification | Count |
| --- | ---: |
| `entrypoint` | 0 |
| `literal_referenced` | 166 |
| `dynamic_invocation_uncertain` | 4 |
| `static_unreferenced` | 0 |

## Scope

- Manifest: `project_sources/collector/manifests/Collector_Runtime_Package_Manifest.json`
- Runtime-lane coverage: `not_collected`
- Covered source files:
  - `project_sources/collector/source/DCOIR_Collector.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.01A1_Core_Logging_And_Process_Capture.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.01A2_Core_Logging_And_Process_Capture.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.01B1_Json_State_And_Array_Utilities.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.01B2_Json_State_And_Array_Utilities.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.01C_Runtime_Paths_Artifacts_And_Reports.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.01D1_Process_Event_And_Baseline_Utilities.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.01D2_Process_Event_And_Baseline_Utilities.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.01E_Tool_Staging_And_Availability.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.02A_Baseline_Collection_And_Reports.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.02B_Baseline_Collection_And_Reports.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.02C_Baseline_Collection_And_Reports.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.02D1A_Baseline_Collection_And_Reports.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.02D1B_Baseline_Collection_And_Reports.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.02D2_Baseline_Collection_And_Reports.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.03A_Enrich_Session_State.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.03B_Enrich_Actions_Review.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.03C_Enrich_Actions_Retrieval.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04A1_Quick_Interface_And_Output.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04A2_Quick_Interface_And_Output.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04A3_Quick_Interface_And_Output.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04B1_Feature_Wave_Targeted_Collection.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04B2_Feature_Wave_Targeted_Collection.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04C_Explicit_Event_Window_Overrides.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04D1_Bounded_Parallel_Runtime.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04D2_Bounded_Parallel_Runtime.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04D3_Bounded_Parallel_Runtime.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04E1_Diagnostic_Context_Overrides.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04E2_Diagnostic_Context_Overrides.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04F1_PR186_Review_Fixes.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04F2_PR186_Review_Fixes.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04G1_PR186_External_Review_Fixes.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04G2_PR186_External_Review_Fixes.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04H1_PR212_Metadata_Finalization_Fixes.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04H2_PR212_Metadata_Finalization_Fixes.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.04H3_PR212_Metadata_Finalization_Fixes.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.05A1_Main_Entry.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.05A2_Main_Entry.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.05A3_Main_Entry.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.05B_Main_Entry.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.05C_Main_Entry.ps1`
  - `project_sources/collector/source/parts/DCOIR_Collector.05_Main_Entry.ps1`

## Potential Follow-Up Functions

| Function | Classification | Source | Line | References |
| --- | --- | --- | ---: | ---: |
| `Convert-ToArrayList` | `dynamic_invocation_uncertain` | `project_sources/collector/source/parts/DCOIR_Collector.01B2_Json_State_And_Array_Utilities.ps1` | 410 | 0 |
| `New-CollectUploadArtifacts` | `dynamic_invocation_uncertain` | `project_sources/collector/source/parts/DCOIR_Collector.02B_Baseline_Collection_And_Reports.ps1` | 173 | 0 |
| `New-AnalystOverviewArtifact` | `dynamic_invocation_uncertain` | `project_sources/collector/source/parts/DCOIR_Collector.04B1_Feature_Wave_Targeted_Collection.ps1` | 213 | 0 |
| `Get-CollectorEventFilterHashtable` | `dynamic_invocation_uncertain` | `project_sources/collector/source/parts/DCOIR_Collector.04C_Explicit_Event_Window_Overrides.ps1` | 40 | 0 |

## Dynamic Invocation Sites

| Kind | Source | Line | Context |
| --- | --- | ---: | --- |
| `dot_source_variable` | `project_sources/collector/source/DCOIR_Collector.ps1` | 217 | `. $partPath` |

## Non-Claims

- This report is not whole-program dead-code proof.
- This report does not claim any function is safe to delete.
- This report only covers manifest-declared collector runtime source.
- Runtime-lane coverage is not collected unless explicit suite evidence is supplied by a later lane.
- Static absence is reported as bounded evidence, not as proof of operator or dynamic invocation absence.
