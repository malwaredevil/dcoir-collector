# PowerShell Assembly Parity Report

- Schema: `dcoir_powershell_assembly_parity_report_v1`
- Issue: `#265`
- Success: `True`
- Source parts: `60`
- Collector source parts: `43`
- Harness source parts: `17`
- Generated outputs mapped: `2`
- Parse status: `pass`
- Parity status: `pass`

## Generated Outputs

| Output | Inputs | Parse | Parity | Line Mapping |
| --- | ---: | --- | --- | --- |
| `compiled_runtime/DCOIR_Collector.ps1` | `43` | `pass` | `pass` | `available` |
| `project_sources/collector/harness/run_DCOIR_Tests.generated.ps1` | `17` | `pass` | `pass` | `available` |

## Coverage Statement

| Surface | Analyzer wrapper reporting | Custom check reporting | Assembly parity reporting |
| --- | --- | --- | --- |
| `collector runtime source parts` | source-part paths when #262 analyzer targets #261 inventory entries | source-part paths when #264 checks target source-part risk classes | source input map, source hash, generated runtime hash, parse status, and line mapping |
| `collector compiled runtime generated output` | not invoked by this #265 runner; future workflow integration can pass generated output explicitly | not invoked by this #265 runner; parity and parse proof are reported here | generated output hash, parse status, deterministic regeneration status, and source line map |
| `harness source parts and generated harness` | source-part paths when #262 analyzer targets .ps1.txt surfaces; generated output when materialized and explicitly targeted | source-part drift risks through #264 fixtures plus #265 parity proof | ordered source input map, generated harness hash, optional checked-in comparison, parse status, and line map |

## Controlled Cases

- `stale_checked_in_generated_output`: fails when a committed generated harness differs from deterministic assembly (`test_stale_checked_in_generated_output_fails`)
- `missing_source_part`: fails when the collector manifest references a missing source part (`test_missing_source_part_fails`)
- `missing_source_output_mapping`: fails when collector part mapping is absent and generated output cannot be mapped (`test_missing_source_output_mapping_fails`)
- `generated_output_parse_failure`: fails when regenerated runnable output has an unbalanced PowerShell structure (`test_generated_output_parse_failure_fails`)
- `unexpected_inventory_shrink`: fails when source/generated counts shrink below baseline without an exception record (`test_baseline_shrink_without_exception_fails`)
- `clean_control`: passes when source parts, generated outputs, parse status, parity status, and mappings are fresh (`test_clean_control_passes_and_maps_counts and test_real_repo_contract_passes`)

## Warnings

- no baseline parity report supplied; shrink checks used current inventory controls only
