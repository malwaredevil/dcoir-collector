# Behavior Ownership Matrix

This matrix is the human-readable projection of `Shared_Agent_Source_Manifest.json`.
The manifest is machine-readable contract authority; this file must cover the same stable ids.

## Target Capability Boundary

| Target | Output owner | Instruction mode | Knowledge mode | Current live lookup | Current external actions |
| --- | --- | --- | --- | --- | --- |
| `gemini_dcoir_agent` | project_sources/gemini bundle compiler | prime_plus_sub_agents | direct_canonical_attachments | Runtime-dependent; never assumed | Unavailable unless returned execution evidence exists |
| `openai_dcoir_analyst` | future OpenAI DCOIR package compiler | static_instructions | static_knowledge | Unavailable | Unavailable unless returned execution evidence exists |
| `openai_usb_reporting` | future OpenAI USB package compiler | static_instructions | static_knowledge | Unavailable | Unavailable unless returned execution evidence exists |

## Behavior Ownership

| Stable id | Source / section | Class | Gemini | OpenAI DCOIR | OpenAI USB | Responsibility |
| --- | --- | --- | --- | --- | --- | --- |
<!-- contract-behavior-id:prime.chunk.00 -->
| `prime.chunk.00` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.00.md` / `00` | shared_behavior_source | materialize_then_compile | adapt | adapt | Defines the agent identity and description metadata. |
<!-- contract-behavior-id:prime.chunk.01 -->
| `prime.chunk.01` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.01.md` / `01` | shared_behavior_source | materialize_then_compile | adapt | adapt | Defines identity, capability boundaries, and truthful action language. |
<!-- contract-behavior-id:prime.chunk.02 -->
| `prime.chunk.02` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.02.md` / `02` | shared_behavior_source | materialize_then_compile | adapt | exclude | Controls intake readiness and workflow branch selection. |
<!-- contract-behavior-id:prime.chunk.03 -->
| `prime.chunk.03` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.03.md` / `03` | shared_behavior_source | materialize_then_compile | adapt | adapt | Requires complete responses and paced operator commands. |
<!-- contract-behavior-id:prime.chunk.04 -->
| `prime.chunk.04` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.04.md` / `04` | shared_behavior_source | materialize_then_compile | adapt | adapt | Separates source facts, returned results, and analysis. |
<!-- contract-behavior-id:prime.chunk.05 -->
| `prime.chunk.05` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.05.md` / `05` | shared_behavior_source | materialize_then_compile | adapt | exclude | Governs evidence objectives, field discovery, and query syntax. |
<!-- contract-behavior-id:prime.chunk.06 -->
| `prime.chunk.06` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.06.md` / `06` | shared_behavior_source | materialize_then_compile | adapt | exclude | Bounds negative results and optional public-source enrichment. |
<!-- contract-behavior-id:prime.chunk.07 -->
| `prime.chunk.07` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.07.md` / `07` | shared_behavior_source | materialize_then_compile | adapt | exclude | Governs conclusions, containment, and benign-technology tuning. |
<!-- contract-behavior-id:prime.chunk.08 -->
| `prime.chunk.08` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.08.md` / `08` | shared_behavior_source | materialize_then_compile | adapt | adapt | Defines required analyst-facing response structures. |
<!-- contract-behavior-id:prime.chunk.09 -->
| `prime.chunk.09` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.09.md` / `09` | shared_behavior_source | materialize_then_compile | adapt | exclude | Defines the evidence-first investigation sequence. |
<!-- contract-behavior-id:prime.chunk.10 -->
| `prime.chunk.10` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.10.md` / `10` | shared_behavior_source | materialize_then_compile | adapt | exclude | Constrains tool claims and operator-facing tool guidance. |
<!-- contract-behavior-id:prime.chunk.11 -->
| `prime.chunk.11` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.11.md` / `11` | shared_behavior_source | materialize_then_compile | adapt | adapt | Defines uncertainty, evidence, and conclusion guardrails. |
<!-- contract-behavior-id:prime.chunk.12 -->
| `prime.chunk.12` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.12.md` / `12` | shared_behavior_source | materialize_then_compile | adapt | exclude | Separates known schema and access from assumptions. |
<!-- contract-behavior-id:prime.chunk.13 -->
| `prime.chunk.13` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.13.md` / `13` | shared_behavior_source | materialize_then_compile | adapt | exclude | Routes field and schema guidance to maintained references. |
<!-- contract-behavior-id:prime.chunk.14 -->
| `prime.chunk.14` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.14.md` / `14` | shared_behavior_source | materialize_then_compile | adapt | exclude | Bounds environment-specific facts to maintained evidence. |
<!-- contract-behavior-id:prime.chunk.15 -->
| `prime.chunk.15` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.15.md` / `15` | shared_behavior_source | materialize_then_compile | adapt | adapt | Defines response composition and output consistency. |
<!-- contract-behavior-id:prime.chunk.16 -->
| `prime.chunk.16` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.16.md` / `16` | shared_behavior_source | materialize_then_compile | exclude | exclude | Defines Gemini Prime-to-sub-agent orchestration semantics. |
<!-- contract-behavior-id:prime.chunk.17 -->
| `prime.chunk.17` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.17.md` / `17` | shared_behavior_source | materialize_then_compile | adapt | adapt | Separates collector, analyst, and USB reporting ownership. |
<!-- contract-behavior-id:prime.chunk.18 -->
| `prime.chunk.18` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.18.md` / `18` | shared_behavior_source | materialize_then_compile | adapt | exclude | Parses indicators and gates additive public enrichment. |
<!-- contract-behavior-id:prime.chunk.19 -->
| `prime.chunk.19` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.19.md` / `19` | shared_behavior_source | materialize_then_compile | adapt | exclude | Applies evidence-first host and network forensics discipline. |
<!-- contract-behavior-id:prime.chunk.20 -->
| `prime.chunk.20` | `project_sources/agent_runtime/behavior_modules/prime/prime.chunk.20.md` / `20` | shared_behavior_source | materialize_then_compile | adapt | adapt | Governs request coverage, routing, tool access, and memory limits. |
<!-- contract-behavior-id:sub_agent.01 -->
| `sub_agent.01` | `project_sources/agent_runtime/behavior_modules/specialists/sub_agent.01.md` / `01` | shared_behavior_source | materialize | flatten | exclude | Owns intake validation, readiness, and first-turn gating. |
<!-- contract-behavior-id:sub_agent.02 -->
| `sub_agent.02` | `project_sources/agent_runtime/behavior_modules/specialists/sub_agent.02.md` / `02` | shared_behavior_source | materialize | flatten | exclude | Maps data coverage, environment facts, and blind spots. |
<!-- contract-behavior-id:sub_agent.03 -->
| `sub_agent.03` | `project_sources/agent_runtime/behavior_modules/specialists/sub_agent.03.md` / `03` | shared_behavior_source | materialize | flatten | exclude | Classifies alert families and differentiates known benign technology. |
<!-- contract-behavior-id:sub_agent.04 -->
| `sub_agent.04` | `project_sources/agent_runtime/behavior_modules/specialists/sub_agent.04.md` / `04` | shared_behavior_source | materialize | flatten | exclude | Separates evidence, provenance, inference, and unknowns. |
<!-- contract-behavior-id:sub_agent.05 -->
| `sub_agent.05` | `project_sources/agent_runtime/behavior_modules/specialists/sub_agent.05.md` / `05` | shared_behavior_source | materialize | flatten | exclude | Designs bounded Elastic and OSQuery pivots with syntax safeguards. |
<!-- contract-behavior-id:sub_agent.06 -->
| `sub_agent.06` | `project_sources/agent_runtime/behavior_modules/specialists/sub_agent.06.md` / `06` | shared_behavior_source | materialize | flatten | exclude | Guides collector execution and bundle workflow state. |
<!-- contract-behavior-id:sub_agent.07 -->
| `sub_agent.07` | `project_sources/agent_runtime/behavior_modules/specialists/sub_agent.07.md` / `07` | shared_behavior_source | materialize | flatten | exclude | Interprets collector artifacts and extracts report evidence. |
<!-- contract-behavior-id:sub_agent.08 -->
| `sub_agent.08` | `project_sources/agent_runtime/behavior_modules/specialists/sub_agent.08.md` / `08` | shared_behavior_source | materialize | flatten | exclude | Parses indicators and plans optional returned-evidence enrichment. |
<!-- contract-behavior-id:sub_agent.09 -->
| `sub_agent.09` | `project_sources/agent_runtime/behavior_modules/specialists/sub_agent.09.md` / `09` | shared_behavior_source | materialize | flatten | exclude | Designs targeted follow-up collection to reduce material gaps. |
<!-- contract-behavior-id:sub_agent.10 -->
| `sub_agent.10` | `project_sources/agent_runtime/behavior_modules/specialists/sub_agent.10.md` / `10` | shared_behavior_source | materialize | flatten | flatten | Composes consistent analyst-facing conclusions and reports. |
<!-- contract-behavior-id:sub_agent.11 -->
| `sub_agent.11` | `project_sources/agent_runtime/behavior_modules/specialists/sub_agent.11.md` / `11` | workflow_specific_behavior | materialize | exclude | flatten | Owns the separately gated weekly USB violations reporting workflow. |
<!-- contract-behavior-id:gemini.topology.bundle_manifest -->
| `gemini.topology.bundle_manifest` | `project_sources/gemini/bundle_source/Gemini_Bundle_Source_Manifest.json` / `whole-file` | topology_manifest | metadata | reference_only | reference_only | Canonical Gemini bundle topology and attachment inventory. |
<!-- contract-behavior-id:gemini.topology.prime_chunk_manifest -->
| `gemini.topology.prime_chunk_manifest` | `project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/prime_agent_chunks/Prime_Agent_Chunks_Manifest.json` / `whole-file` | topology_manifest | metadata | reference_only | reference_only | Canonical Prime chunk order and reassembly contract. |
<!-- contract-behavior-id:gemini.topology.generated_index -->
| `gemini.topology.generated_index` | `project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/Generated_DCOIR_Gemini_Agent_Index.md.txt` / `whole-file` | generated_metadata | generated | reference_only | reference_only | Generated Gemini agent index. |
<!-- contract-behavior-id:gemini.topology.attachment_map -->
| `gemini.topology.attachment_map` | `project_sources/gemini/bundle_source/00_START_HERE/Agent_Attachment_Map.md.txt` / `whole-file` | maintainer_guidance | metadata | reference_only | reference_only | Gemini attachment placement map. |
<!-- contract-behavior-id:gemini.topology.quick_start -->
| `gemini.topology.quick_start` | `project_sources/gemini/bundle_source/00_START_HERE/Gemini_Build_Quick_Start.md.txt` / `whole-file` | maintainer_guidance | metadata | reference_only | reference_only | Gemini build quick start. |
<!-- contract-behavior-id:gemini.topology.readme_first -->
| `gemini.topology.readme_first` | `project_sources/gemini/bundle_source/00_START_HERE/README_FIRST.md.txt` / `whole-file` | maintainer_guidance | metadata | reference_only | reference_only | Bundle entry-point guidance. |
<!-- contract-behavior-id:gemini.topology.bundle_readme -->
| `gemini.topology.bundle_readme` | `project_sources/gemini/bundle_source/README.md` / `whole-file` | maintainer_guidance | metadata | reference_only | reference_only | Gemini source and generated-artifact boundary. |
<!-- contract-behavior-id:gemini.topology.lane_readme -->
| `gemini.topology.lane_readme` | `project_sources/gemini/README.md` / `whole-file` | maintainer_guidance | metadata | reference_only | reference_only | Gemini lane and retired prompt-pack statement. |
<!-- contract-behavior-id:gemini.topology.compile_strategy -->
| `gemini.topology.compile_strategy` | `project_sources/gemini/docs/DOC-10_DCOIR_Gemini_Stored_Source_And_Compile_Strategy_v1_0_0.txt` / `whole-file` | maintainer_guidance | metadata | reference_only | reference_only | Stored-source compile strategy. |
<!-- contract-behavior-id:gemini.topology.creation_pipeline -->
| `gemini.topology.creation_pipeline` | `project_sources/gemini/docs/DOC-11_DCOIR_Gemini_Creation_Pipeline_v1_0_0.txt` / `whole-file` | maintainer_guidance | metadata | reference_only | reference_only | Gemini creation pipeline. |
<!-- contract-behavior-id:gemini.runtime.generated_prime -->
| `gemini.runtime.generated_prime` | `project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/Prime_Agent_DCOIR_Gemini_Orchestrator.md.txt` / `whole-file` | generated_runtime_artifact | generated | reference_only | reference_only | Generated Prime runtime output assembled from chunks. |

All behavior rows require a source map and a reverse-reconciliation path. Generated outputs are not canonical.

## Behavior Control Details

| Stable id | Applies to | Provider differences | Dependencies | Validation | Reverse sync | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| `prime.chunk.00` | gemini_dcoir_agent, openai_dcoir_analyst, openai_usb_reporting | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.01` | gemini_dcoir_agent, openai_dcoir_analyst, openai_usb_reporting | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.02` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.03` | gemini_dcoir_agent, openai_dcoir_analyst, openai_usb_reporting | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.04` | gemini_dcoir_agent, openai_dcoir_analyst, openai_usb_reporting | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.05` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.06` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.07` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.08` | gemini_dcoir_agent, openai_dcoir_analyst, openai_usb_reporting | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.09` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.10` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.11` | gemini_dcoir_agent, openai_dcoir_analyst, openai_usb_reporting | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.12` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.13` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.14` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.15` | gemini_dcoir_agent, openai_dcoir_analyst, openai_usb_reporting | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.16` | gemini_dcoir_agent | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.17` | gemini_dcoir_agent, openai_dcoir_analyst, openai_usb_reporting | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.18` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.19` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `prime.chunk.20` | gemini_dcoir_agent, openai_dcoir_analyst, openai_usb_reporting | Gemini retains Prime orchestration; OpenAI targets receive flattened, capability-gated adaptations. | Gemini behavior adapter; gemini prime reassembly; provider-specific instruction compilers; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_capability | Required | None |
| `sub_agent.01` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini keeps physical specialists; OpenAI targets compile applicable responsibilities into a single static instruction surface. | Gemini behavior adapter; gemini topology manifest; provider behavior compiler; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_routing | Required | None |
| `sub_agent.02` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini keeps physical specialists; OpenAI targets compile applicable responsibilities into a single static instruction surface. | Gemini behavior adapter; gemini topology manifest; provider behavior compiler; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_routing | Required | None |
| `sub_agent.03` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini keeps physical specialists; OpenAI targets compile applicable responsibilities into a single static instruction surface. | Gemini behavior adapter; gemini topology manifest; provider behavior compiler; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_routing | Required | None |
| `sub_agent.04` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini keeps physical specialists; OpenAI targets compile applicable responsibilities into a single static instruction surface. | Gemini behavior adapter; gemini topology manifest; provider behavior compiler; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_routing | Required | None |
| `sub_agent.05` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini keeps physical specialists; OpenAI targets compile applicable responsibilities into a single static instruction surface. | Gemini behavior adapter; gemini topology manifest; provider behavior compiler; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_routing | Required | None |
| `sub_agent.06` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini keeps physical specialists; OpenAI targets compile applicable responsibilities into a single static instruction surface. | Gemini behavior adapter; gemini topology manifest; provider behavior compiler; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_routing | Required | None |
| `sub_agent.07` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini keeps physical specialists; OpenAI targets compile applicable responsibilities into a single static instruction surface. | Gemini behavior adapter; gemini topology manifest; provider behavior compiler; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_routing | Required | None |
| `sub_agent.08` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini keeps physical specialists; OpenAI targets compile applicable responsibilities into a single static instruction surface. | Gemini behavior adapter; gemini topology manifest; provider behavior compiler; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_routing | Required | None |
| `sub_agent.09` | gemini_dcoir_agent, openai_dcoir_analyst | Gemini keeps physical specialists; OpenAI targets compile applicable responsibilities into a single static instruction surface. | Gemini behavior adapter; gemini topology manifest; provider behavior compiler; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_routing | Required | None |
| `sub_agent.10` | gemini_dcoir_agent, openai_dcoir_analyst, openai_usb_reporting | Gemini keeps physical specialists; OpenAI targets compile applicable responsibilities into a single static instruction surface. | Gemini behavior adapter; gemini topology manifest; provider behavior compiler; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_routing | Required | None |
| `sub_agent.11` | gemini_dcoir_agent, openai_usb_reporting | Gemini keeps physical specialists; OpenAI targets compile applicable responsibilities into a single static instruction surface. | Gemini behavior adapter; gemini topology manifest; provider behavior compiler; shared behavior module manifest | behavior_coverage; byte_identity_adapter; source_contract; target_routing | Required | None |
| `gemini.topology.bundle_manifest` | gemini_dcoir_agent | Gemini topology files remain provider-specific and do not become OpenAI knowledge attachments. | gemini bundle compiler; source contract validator | topology_accounting; generated_artifact_boundary | Required | None |
| `gemini.topology.prime_chunk_manifest` | gemini_dcoir_agent | Gemini topology files remain provider-specific and do not become OpenAI knowledge attachments. | gemini bundle compiler; source contract validator | topology_accounting; generated_artifact_boundary | Required | None |
| `gemini.topology.generated_index` | gemini_dcoir_agent | Gemini topology files remain provider-specific and do not become OpenAI knowledge attachments. | gemini bundle compiler; source contract validator | topology_accounting; generated_artifact_boundary | Required | None |
| `gemini.topology.attachment_map` | gemini_dcoir_agent | Gemini topology files remain provider-specific and do not become OpenAI knowledge attachments. | gemini bundle compiler; source contract validator | topology_accounting; generated_artifact_boundary | Required | None |
| `gemini.topology.quick_start` | gemini_dcoir_agent | Gemini topology files remain provider-specific and do not become OpenAI knowledge attachments. | gemini bundle compiler; source contract validator | topology_accounting; generated_artifact_boundary | Required | None |
| `gemini.topology.readme_first` | gemini_dcoir_agent | Gemini topology files remain provider-specific and do not become OpenAI knowledge attachments. | gemini bundle compiler; source contract validator | topology_accounting; generated_artifact_boundary | Required | None |
| `gemini.topology.bundle_readme` | gemini_dcoir_agent | Gemini topology files remain provider-specific and do not become OpenAI knowledge attachments. | gemini bundle compiler; source contract validator | topology_accounting; generated_artifact_boundary | Required | None |
| `gemini.topology.lane_readme` | gemini_dcoir_agent | Gemini topology files remain provider-specific and do not become OpenAI knowledge attachments. | gemini bundle compiler; source contract validator | topology_accounting; generated_artifact_boundary | Required | None |
| `gemini.topology.compile_strategy` | gemini_dcoir_agent | Gemini topology files remain provider-specific and do not become OpenAI knowledge attachments. | gemini bundle compiler; source contract validator | topology_accounting; generated_artifact_boundary | Required | None |
| `gemini.topology.creation_pipeline` | gemini_dcoir_agent | Gemini topology files remain provider-specific and do not become OpenAI knowledge attachments. | gemini bundle compiler; source contract validator | topology_accounting; generated_artifact_boundary | Required | None |
| `gemini.runtime.generated_prime` | gemini_dcoir_agent | Gemini topology files remain provider-specific and do not become OpenAI knowledge attachments. | gemini bundle compiler; source contract validator | topology_accounting; generated_artifact_boundary | Required | None |

## Knowledge Disposition

| Stable id | Canonical source | Class | Gemini attachment | DCOIR projection | USB projection | Boundary/hash and overlap rule |
| --- | --- | --- | --- | --- | --- | --- |
<!-- contract-knowledge-id:knowledge.collector.exe_runtime -->
| `knowledge.collector.exe_runtime` | `knowledge/Knowledge - Collector - EXE Usage and Runtime Behavior.md` | runtime_reference | include | `dcoir_collection` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.collector.feature_contract -->
| `knowledge.collector.feature_contract` | `knowledge/Knowledge - Collector - Feature and Output Contract Reference.md` | runtime_reference | include | `dcoir_collection` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.collector.local_test -->
| `knowledge.collector.local_test` | `knowledge/Knowledge - Collector - Local Test and Regression.md` | runtime_reference | include | `dcoir_collection` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.core.artifact_review -->
| `knowledge.core.artifact_review` | `knowledge/Knowledge - Core - Artifact Review Guide.md` | runtime_reference | include | `dcoir_artifacts` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.core.elastic_quick_start -->
| `knowledge.core.elastic_quick_start` | `knowledge/Knowledge - Core - Elastic Quick Start.md` | runtime_reference | include | `dcoir_elastic_ops` | `usb_query_reference` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.core.enrichment_actions -->
| `knowledge.core.enrichment_actions` | `knowledge/Knowledge - Core - Enrichment Actions.md` | runtime_reference | include | `dcoir_collection` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.core.faq -->
| `knowledge.core.faq` | `knowledge/Knowledge - Core - FAQ.md` | runtime_reference | include | `dcoir_core` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.core.ioc_public_sources -->
| `knowledge.core.ioc_public_sources` | `knowledge/Knowledge - Core - IOC Enrichment and Public Sources.md` | runtime_reference | include | `dcoir_ioc_enrichment` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.core.overview -->
| `knowledge.core.overview` | `knowledge/Knowledge - Core - Overview and About.md` | runtime_reference | include | `dcoir_core` | `usb_reporting_core` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.core.tier1_runbook -->
| `knowledge.core.tier1_runbook` | `knowledge/Knowledge - Core - Tier 1 Collect Runbook.md` | runtime_reference | include | `dcoir_collection` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.core.tier2_runbook -->
| `knowledge.core.tier2_runbook` | `knowledge/Knowledge - Core - Tier 2 Collect Runbook.md` | runtime_reference | include | `dcoir_collection` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.core.troubleshooting -->
| `knowledge.core.troubleshooting` | `knowledge/Knowledge - Core - Troubleshooting.md` | runtime_reference | include | `dcoir_collection` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.gemini.ai_design -->
| `knowledge.gemini.ai_design` | `knowledge/Knowledge - Gemini - AI Prompt and Agent Design.md` | maintainer_only | include | `excluded` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.gemini.topology_routing -->
| `knowledge.gemini.topology_routing` | `knowledge/Knowledge - Gemini - Agent Topology and Routing.md` | maintainer_only | include | `excluded` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.gemini.output_contract -->
| `knowledge.gemini.output_contract` | `knowledge/Knowledge - Gemini - Output Contract and Command-Lane Discipline.md` | split | include | `dcoir_core` | `usb_reporting_core` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.gemini.runtime_bundle -->
| `knowledge.gemini.runtime_bundle` | `knowledge/Knowledge - Gemini - Runtime Bundle and Source Tree.md` | maintainer_only | include | `excluded` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.reference.elastic_fields -->
| `knowledge.reference.elastic_fields` | `knowledge/Knowledge - Reference - Elastic Field Name Reference.md` | runtime_reference | include | `dcoir_elastic_reference` | `usb_query_reference` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.reference.elastic_actions -->
| `knowledge.reference.elastic_actions` | `knowledge/Knowledge - Reference - Elastic Response Actions Reference.md` | runtime_reference | include | `dcoir_elastic_reference` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.reference.osquery_applications -->
| `knowledge.reference.osquery_applications` | `knowledge/Knowledge - Reference - OSQuery Application, Package, and Extension Tables.md` | runtime_reference | include | `dcoir_osquery_reference` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.reference.osquery_files -->
| `knowledge.reference.osquery_files` | `knowledge/Knowledge - Reference - OSQuery File and Filesystem Tables.md` | runtime_reference | include | `dcoir_osquery_reference` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.reference.osquery_network -->
| `knowledge.reference.osquery_network` | `knowledge/Knowledge - Reference - OSQuery Network and Connection Tables.md` | runtime_reference | include | `dcoir_osquery_reference` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.reference.osquery_persistence -->
| `knowledge.reference.osquery_persistence` | `knowledge/Knowledge - Reference - OSQuery Persistence and Startup Tables.md` | runtime_reference | include | `dcoir_osquery_reference` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.reference.osquery_process -->
| `knowledge.reference.osquery_process` | `knowledge/Knowledge - Reference - OSQuery Process and Execution Tables.md` | runtime_reference | include | `dcoir_osquery_reference` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.reference.osquery_index -->
| `knowledge.reference.osquery_index` | `knowledge/Knowledge - Reference - OSQuery Reference Index.md` | runtime_reference | include | `dcoir_osquery_reference` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.reference.osquery_security -->
| `knowledge.reference.osquery_security` | `knowledge/Knowledge - Reference - OSQuery Security, Detection, and Event Tables.md` | runtime_reference | include | `dcoir_osquery_reference` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.reference.osquery_system -->
| `knowledge.reference.osquery_system` | `knowledge/Knowledge - Reference - OSQuery System, Hardware, and Platform Tables.md` | runtime_reference | include | `dcoir_osquery_reference` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.reference.osquery_users -->
| `knowledge.reference.osquery_users` | `knowledge/Knowledge - Reference - OSQuery User, Auth, and Account Tables.md` | runtime_reference | include | `dcoir_osquery_reference` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |
<!-- contract-knowledge-id:knowledge.reference.osquery_virtualization -->
| `knowledge.reference.osquery_virtualization` | `knowledge/Knowledge - Reference - OSQuery Virtualization, Cloud, and Container Tables.md` | runtime_reference | include | `dcoir_osquery_reference` | `excluded` | Preserve ordered source boundary and SHA-256; Validate headings and source-boundary markers during projection; do not silently deduplicate normative text. |

The four Gemini-specific knowledge documents are deliberately classified: three are maintainer-only and one has a split disposition. They remain Gemini attachments until a later validated packaging change says otherwise.

## Stale Behavioral Authority References

| Stable id | Missing path | Status | Replacement authority | Runtime action |
| --- | --- | --- | --- | --- |
<!-- contract-stale-id:stale.pp_01 -->
| `stale.pp_01` | `project_sources/PP-01_System_Prompt_v1_0_1.txt` | retired | Shared behavior modules and the shared source contract introduced by issue #404. | Removed from the live Gemini bundle manifest by issue #404; retained here only as historical drift evidence. |
<!-- contract-stale-id:stale.pp_02 -->
| `stale.pp_02` | `project_sources/PP-02_Output_Schema_v1_0_0.txt` | retired | Shared behavior modules and the shared source contract introduced by issue #404. | Removed from the live Gemini bundle manifest by issue #404; retained here only as historical drift evidence. |
<!-- contract-stale-id:stale.pp_03 -->
| `stale.pp_03` | `project_sources/PP-03_Baseline_Triage_Prompt_v1_0_0.txt` | retired | Shared behavior modules and the shared source contract introduced by issue #404. | Removed from the live Gemini bundle manifest by issue #404; retained here only as historical drift evidence. |
<!-- contract-stale-id:stale.pp_04 -->
| `stale.pp_04` | `project_sources/PP-04_Enrichment_Review_Prompt_v0_1_1.txt` | retired | Shared behavior modules and the shared source contract introduced by issue #404. | Removed from the live Gemini bundle manifest by issue #404; retained here only as historical drift evidence. |
<!-- contract-stale-id:stale.pp_05 -->
| `stale.pp_05` | `project_sources/PP-05_Retrieved_Artifact_Review_Prompt_v0_1_1.txt` | retired | Shared behavior modules and the shared source contract introduced by issue #404. | Removed from the live Gemini bundle manifest by issue #404; retained here only as historical drift evidence. |
<!-- contract-stale-id:stale.pp_06 -->
| `stale.pp_06` | `project_sources/PP-06_Final_Case_Synthesis_Prompt_v0_1_1.txt` | retired | Shared behavior modules and the shared source contract introduced by issue #404. | Removed from the live Gemini bundle manifest by issue #404; retained here only as historical drift evidence. |
<!-- contract-stale-id:stale.pp_07 -->
| `stale.pp_07` | `project_sources/PP-07_Agent_Guardrails_v1_0_0.txt` | retired | Shared behavior modules and the shared source contract introduced by issue #404. | Removed from the live Gemini bundle manifest by issue #404; retained here only as historical drift evidence. |

## IOC Enrichment

IOC enrichment is optional and additive. Only case-grounded indicators may be enriched; source claims require returned evidence. Unavailable or failed enrichment is silently omitted by default, and no reputation result alone establishes compromise or benignity. The current OpenAI targets may analyze operator-supplied returned material but must not claim live lookup capability.

## Remaining Decisions

No operator decision blocks this source contract. Exact OpenAI instruction wording, projection file names, and runtime upload steps belong to later implementation issues and must stay inside the declared target capability profiles.
