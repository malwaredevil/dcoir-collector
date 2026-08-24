# Shared Agent Runtime Source Contract

This directory defines how one governed source set is projected into the current Gemini agent and two OpenAI WebUI GPT packages without creating three independently maintained instruction trees.

## Authority

- `Shared_Agent_Source_Manifest.json` is the machine-readable ownership, target, capability, projection, and reverse-reconciliation contract.
- `Behavior_Module_Manifest.json` maps every canonical Prime chunk and specialist module to its generated Gemini adapter output and pins both sides by SHA-256.
- `docs/Behavior_Ownership_Matrix.md` is the human-readable projection of that contract and must cover the same stable ids.
- `behavior_modules/` is the canonical editable source for the 21 Prime chunks and 11 specialist prompts.
- The corresponding files under `project_sources/gemini/bundle_source/` are checked-in generated adapters. They remain present for the existing Gemini compiler and review workflow but are not canonical.
- `knowledge/*.md` remains the canonical atomic knowledge source set.
- Generated Gemini and OpenAI packages are never canonical source.

The extraction deliberately preserves the accepted Gemini prompt text byte-for-byte. Provider-neutral ownership does not imply that every current sentence is already suitable for OpenAI; later target compilers must apply the declared dispositions and capability boundaries.

## Targets

| Target id | Product shape | Current instruction and knowledge surface |
| --- | --- | --- |
| `gemini_dcoir_agent` | Gemini Prime orchestrator plus eleven specialists | Existing stored-source Gemini compile lane and direct canonical knowledge attachments |
| `openai_dcoir_analyst` | AFRICOM DCOIR Analyst custom GPT | Hosted GPT-5.4 with static Instructions and static Knowledge |
| `openai_usb_reporting` | AFRICOM USB Reporting custom GPT | Hosted GPT-5.4 with static Instructions and static Knowledge |

The OpenAI targets currently have no web search, Code Interpreter/Data Analysis, Canvas, image generation, Apps, Actions, live Elastic access, live collector execution, GitHub/Supabase connector access, or persistent cross-conversation memory. A later optional lookup capability may be enabled only after operator evidence changes the target contract. Generated instructions must not claim it exists today.

## Edit Rules

1. Edit a canonical file under `behavior_modules/` or `knowledge/`, not a generated target package.
2. Update the manifests and matrix when ownership, applicability, target capability, topology, or projection membership changes.
3. Refresh the module SHA-256 value after an intentional behavior edit.
4. Materialize every affected provider adapter. For Gemini:

   ```bash
   python project_sources/agent_runtime/tools/materialize_agent_behavior_adapters.py --materialize
   ```

5. Validate source-map coverage, byte identity, knowledge boundaries and hashes, output file budgets, and target capability truthfulness.
6. Compare generated output with the approved target state before release.

A direct WebUI or Gemini target edit is a temporary hotfix. Record the exact edit, map it back to canonical source, update canonical source, rebuild every affected target, compare the generated result, and remove drift. Target-to-target copying is not synchronization.

## Knowledge Projection

The 28 maintained Gemini knowledge attachments remain atomic canonical files. OpenAI packages will consolidate them into target-specific projection groups while preserving ordered source-boundary markers and a SHA-256 value for every included source. Consolidation must be lossless for normative content and must stay within the strict file-count ceiling declared in the manifest.

The four `Knowledge - Gemini -*` documents are not blindly copied into OpenAI packages. Three are classified as provider maintainer guidance; the output-contract document has a split disposition so shared response rules may project while Gemini-only topology and command-lane guidance remains provider-specific.

## IOC Enrichment

IOC enrichment is optional, additive, and capability-gated. It applies only to case-grounded indicators, and a source may be named as checked only when returned evidence exists. Failed or unavailable enrichment is silently omitted by default. No reputation result alone proves compromise or benignity. The current OpenAI targets may analyze operator-supplied returned source material but must not claim live lookup capability.

## Validation

From the repository root:

```bash
python project_sources/agent_runtime/tools/validate_shared_agent_source_contract.py
python project_sources/agent_runtime/tests/validate_shared_agent_source_contract_selftest.py
python project_sources/agent_runtime/tools/materialize_agent_behavior_adapters.py --check
python project_sources/agent_runtime/tests/materialize_agent_behavior_adapters_selftest.py
```

The validators compare the shared contract, behavior-module manifest, checked-in Gemini adapters, live Gemini bundle manifest, and Prime chunk manifest. They fail on unmapped or duplicate Prime, specialist, or knowledge ownership; source/adapter hash or byte drift; path escape; topology disagreement; missing source paths without an explicit stale disposition; conflicting authority; generated artifacts marked canonical; unavailable OpenAI capability claims; projection-budget overflow; missing source-map or reverse-reconciliation metadata; duplicate ids; or manifest/matrix drift.

## Deferred Work

Later issues will create the two OpenAI instruction bootstraps, consolidated knowledge projections, unified bundlers, target-specific validators, drift reports, and operator upload/reconciliation procedures. The seven retired `project_sources/PP-*` references remain documented as historical drift evidence, but the live Gemini manifest now points to the shared source and module contracts.
