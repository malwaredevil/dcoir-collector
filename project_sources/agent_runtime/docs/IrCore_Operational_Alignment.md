# Supabase `ircore` Operational Alignment

Issue: #418  
Parent EPIC: #399  
Baseline source commit: `b1a4771e693639d5670b2c5378ccac758aeb09cd`

## Purpose

This document records the Stage 8 operational alignment between the governed cross-provider agent-runtime source in GitHub and the routing, discovery, validation, workflow/tool catalog, and receipt metadata stored in Supabase schema `ircore`.

GitHub remains canonical for all agent behavior, Knowledge, target definitions, source mappings, hashes, generated package contracts, validation tooling, and release/deployment procedures. Supabase `ircore` is an operational index and routing/readback backend. It must point to canonical GitHub authority rather than reproduce it.

## Governed Target Set

The aligned operational family covers the three targets already defined by `Shared_Agent_Source_Manifest.json`:

1. `gemini_dcoir_agent`
2. `openai_dcoir_analyst`
3. `openai_usb_reporting`

Gemini-only live behavioral replay remains separately governed under `gemini_instruction_work` and issue #184. The cross-provider family does not weaken, replace, or close that live-behavior evidence track.

## Operational Task Family And Routes

Stage 8 adds the `agent_runtime_work` task family for work that spans the shared source contract, provider adapters, Knowledge projections, generated OpenAI packages, unified release/parity reporting, or Gemini Knowledge-consolidation evaluation.

The family has three primary scenarios:

- `make_github_update` — governed cross-provider source/package changes. It requires live GitHub readback, the canonical source contract and directly affected manifests, target-impact mapping, reuse of maintained tools, exact-head validation, review gates, and work-item receipts.
- `read_release_parity` — read-only release/parity and drift evidence. It requires the exact source commit, the agent-runtime validation receipt, unified release/parity reports, relevant manifests, and an explicit separation between static repository success and manual/live evidence.
- `prepare_openai_webui_deployment` — planning and readback for the manual OpenAI WebUI deployment lane. The operator performs and explicitly confirms WebUI changes; repository state alone is not deployment evidence.

Aliases include the canonical family name plus common phrases for shared agent runtime, release parity, and the two OpenAI package targets. These aliases route cross-provider package work away from the Gemini-only instruction family.

## Canonical Source References

`ircore.source_refs` now points to the maintained GitHub authority surfaces needed for bounded retrieval:

- `project_sources/agent_runtime/Shared_Agent_Source_Manifest.json`
- `project_sources/agent_runtime/Behavior_Module_Manifest.json`
- `project_sources/agent_runtime/Knowledge_Projection_Manifest.json`
- `project_sources/agent_runtime/README.md`
- `project_sources/agent_runtime/docs/Release_Parity_Deployment_Readback.md`
- `project_sources/agent_runtime/docs/Gemini_Knowledge_Consolidation_Decision.md`
- `project_sources/agent_runtime/generated/` as a supplemental, explicitly noncanonical output root

The existing `knowledge/` reference remains canonical atomic Knowledge authority. Generated OpenAI/Gemini packages and reports never become canonical source through their presence in Supabase.

## Bounded Retrieval Profiles

Three retrieval profiles prevent broad-history lookup from becoming the default:

- `agent_runtime_write_default`
- `agent_runtime_readback_default`
- `agent_runtime_planning_default`

The profiles prioritize the shared source contract and operating guide, then only the behavior, Knowledge-projection, deployment/readback, consolidation-decision, generated-output, or atomic-Knowledge surfaces relevant to the requested task class.

## Tool Catalog

The maintained agent-runtime tools are registered as active operational tools with their GitHub paths and use/avoid boundaries:

- `project_sources/agent_runtime/tools/validate_shared_agent_source_contract.py`
- `project_sources/agent_runtime/tools/materialize_agent_behavior_adapters.py`
- `project_sources/agent_runtime/tools/project_agent_knowledge.py`
- `project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py`
- `project_sources/agent_runtime/tools/build_openai_usb_reporting.py`
- `project_sources/agent_runtime/tools/report_agent_release_parity.py`
- `project_sources/agent_runtime/tools/evaluate_gemini_knowledge_consolidation.py`

The catalog describes what each tool is for; it does not duplicate implementation logic, source hashes, projection maps, or target semantics from GitHub.

## Workflow Readback Alignment

The existing `validate-on-pr` and `validate-on-push` workflow catalog records now identify the agent-runtime evidence produced by the current workflows when relevant paths are in scope:

- `agent_runtime_validation.json`
- `agent_release_parity_report.json`
- `agent_release_parity_report.md`

The operational record requires these artifacts to be tied to the exact PR head or merged `main` commit being claimed. No workflow YAML was changed by Stage 8.

## Validation Rules

Stage 8 adds three family-specific validation rules:

1. `agent_runtime_write_requires_exact_head_validation`
   - requires the exact reviewed head;
   - requires the applicable ten-command agent-runtime contract and generated drift checks;
   - requires unified release/parity readback;
   - requires GitHub and Supabase work-item receipts before readiness claims.
2. `agent_runtime_static_live_evidence_boundary`
   - a static source/package/parity pass is repository evidence only;
   - OpenAI WebUI deployment and Gemini live behavior must be recorded separately;
   - pending manual/live evidence is an acceptable explicit gap and must not be converted into an inferred success claim.
3. `agent_runtime_manual_openai_deployment_requires_operator_confirmation`
   - requires the validated package/source identity plus explicit operator confirmation and observed WebUI readback before deployment is described as complete;
   - direct WebUI hotfixes must be reverse-reconciled into canonical GitHub source before parity is reclaimed.

Issue #184 remains the authoritative live Gemini replay tracker. Static Stage 8 routing/readback cannot satisfy its live behavior evidence requirement.

## Startup Queries

Use the unversioned startup function with the exact family/scenario pair:

```sql
select ircore.get_agent_startup_pack(
  'agent_runtime_work',
  'write',
  'make_github_update'
);
```

```sql
select ircore.get_agent_startup_pack(
  'agent_runtime_work',
  'readback',
  'read_release_parity'
);
```

```sql
select ircore.get_agent_startup_pack(
  'agent_runtime_work',
  'planning',
  'prepare_openai_webui_deployment'
);
```

Each route was read back after the Stage 8 mutation and resolved the intended task family, scenario steps, bounded retrieval profile, and applicable evidence rule.

## Idempotency And Readback

The Stage 8 rows use stable unique slugs or family/scenario keys and conflict-safe updates. A repeat no-delete upsert of all scenario-step and retrieval-profile-source mappings preserved the existing 19 scenario-step row identities and 17 retrieval-profile-source row identities with unchanged counts. This demonstrates duplicate-safe reapplication for the two ordered child surfaces most vulnerable to accidental duplication.

The aligned live inventory contains:

- 1 `agent_runtime_work` task family;
- 7 active family aliases;
- 3 active scenarios;
- 19 blocking scenario steps;
- 7 agent-runtime source references;
- 3 bounded retrieval profiles with 17 source bindings;
- 7 active agent-runtime tool records;
- 2 updated workflow-catalog records (`validate-on-pr`, `validate-on-push`);
- 3 family-specific validation rules.

These counts are operational readback evidence, not a replacement for the canonical GitHub manifests.

## Explicit Non-Changes

Stage 8 does not:

- change `.github/workflows/**`;
- change DCOIR Collector PowerShell runtime behavior;
- change Gemini Prime or specialist behavior;
- change OpenAI DCOIR Analyst or USB Reporting instruction/package semantics;
- mutate the live Gemini Agent;
- mutate either live OpenAI WebUI GPT;
- promote the deferred Gemini 8-file Knowledge candidate;
- close or weaken #184;
- claim live-model or WebUI parity from static repository or Supabase evidence.

## Future Maintenance

When the canonical agent-runtime architecture changes, update GitHub first. Then update only the `ircore` routing, source pointer, catalog, validation, or receipt metadata needed to discover and govern that new state. Do not copy canonical target mappings, hashes, Instructions, Knowledge payloads, or generated package contents into Supabase as a second source of truth.
