## Evidence Channels

| Channel | State | Key Evidence |
| --- | --- | --- |
| analyzer | optional_missing | live PSScriptAnalyzer evidence is not claimed unless this report is present and valid |
| deterministic_fixture_analyzer | success | 14 findings; This #263 harness uses a deterministic local fixture analyzer through the #262 wrapper. It intentionally does not execute PSScriptAnalyzer, so this fixture report does not claim whether pwsh or the PSScriptAnalyzer module is installed in the current environment. |
| custom_checks | success | 8 findings |
| assembly_parity | success | 2 generated outputs; pass |
| finding_governance | success | 0 baseline records; 0 suppressions |
| engine_boundary | success | 2 unclaimed blocking artifacts |
| function_reachability | success | 167 functions; 163 literal referenced; 4 dynamic uncertain; coverage not_collected |
| pester_boundary | supporting_non_blocking | Pester may support later runtime or wrapper evidence but is not blocking static-validation evidence in #268. |

