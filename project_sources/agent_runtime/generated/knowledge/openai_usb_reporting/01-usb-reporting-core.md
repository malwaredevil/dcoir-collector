# Generated DCOIR Knowledge Projection

> Generated, non-canonical output. Edit the atomic files under knowledge/, then rebuild all affected targets.

- Target: openai_usb_reporting
- Projection group: usb_reporting_core
- Purpose: USB reporting role and output contract.
- Source count: 2

<!-- DCOIR_SOURCE_BEGIN {"bytes":6013,"git_blob_sha":"88a95d467a8a5272389eddeb8d2c065c9efc2c1b","id":"knowledge.core.overview","path":"knowledge/Knowledge - Core - Overview and About.md","sha256":"711089230e2e65f3712aea9392ba5ee68e0759b8ce872115ae7a640c1dbff07c"} -->
# Knowledge - Core - Overview and About

_AFRICOM_SOC_IR / DCOIR project context and maintained knowledge-doc charter_

**Summary:** Defines the DCOIR authority model, source classes, and operational lanes so operators and Gemini can interpret collector, harness, and Gemini surfaces correctly.

---

## Current authority model

DCOIR uses GitHub as governed source/readback for repository files and Supabase `ircore` as the operational routing, validation, and receipt surface.

| Surface | Role |
| --- | --- |
| Project Instructions | First bootstrap anchor |
| GitHub repo | Source/readback for collector, harness, Gemini bundle, workflows, and promoted history |
| Supabase `ircore` | Operational routing, retrieval profiles, validation rules, receipts, preferences, and active session state |
| `knowledge/*.md` | Maintained human-readable knowledge source |
| Gemini `.md.txt` attachments | Runtime attachment files generated in the release ZIP from `knowledge/Knowledge - *.md` |

Knowledge docs explain the system. They do not override Project Instructions, governed GitHub source, implemented source behavior, or Supabase `ircore` operational records.

---

## Current knowledge set

The maintained set currently contains 28 pages grouped by role:

- Core pages for shared DCOIR workflow and operating guidance
- Gemini pages for runtime bundle, routing, and output behavior
- Collector pages for validation, EXE behavior, and output-contract reference
- Reference pages for exact Elastic and OSQuery lookup material

---

## Knowledge ownership map

Use one owner per topic to avoid duplicate guidance.

| Topic | Owner | Supporting references |
| --- | --- | --- |
| Authority model and source classes | Knowledge - Core - Overview and About | README and `knowledge/README.md` |
| Endpoint command lane | Knowledge - Core - Elastic Quick Start | Knowledge - Gemini - Output Contract and Command-Lane Discipline |
| Local and CI validation | Knowledge - Collector - Local Test and Regression | `validate-on-push.yml`, `manual-full-validation.yml`, Knowledge - Collector - EXE Usage and Runtime Behavior, and Knowledge - Collector - Feature and Output Contract Reference |
| Tier 1 procedure | Knowledge - Core - Tier 1 Collect Runbook | Knowledge - Collector - Feature and Output Contract Reference for feature/output facts |
| Tier 2 procedure | Knowledge - Core - Tier 2 Collect Runbook | Knowledge - Collector - Feature and Output Contract Reference for feature/output facts |
| Enrichment and retrieval workflow | Knowledge - Core - Enrichment Actions | Knowledge - Core - Artifact Review Guide and Knowledge - Collector - Feature and Output Contract Reference |
| Artifact review and upload priority | Knowledge - Core - Artifact Review Guide | Knowledge - Gemini - Output Contract and Command-Lane Discipline and Knowledge - Gemini - Runtime Bundle and Source Tree for Gemini upload behavior |
| Troubleshooting | Knowledge - Core - Troubleshooting | Knowledge - Collector - Local Test and Regression, Knowledge - Collector - EXE Usage and Runtime Behavior, and Knowledge - Collector - Feature and Output Contract Reference |
| FAQ | Knowledge - Core - FAQ | All owner docs; FAQ must stay shallow |
| Gemini design, routing, output, and attachments | Knowledge - Gemini - AI Prompt and Agent Design, Knowledge - Gemini - Runtime Bundle and Source Tree, Knowledge - Gemini - Agent Topology and Routing, and Knowledge - Gemini - Output Contract and Command-Lane Discipline | Gemini stored-source agent files |
| Public IOC enrichment | Knowledge - Core - IOC Enrichment and Public Sources | Case evidence and source-tier rules |
| Optional EXE behavior | Knowledge - Collector - EXE Usage and Runtime Behavior | Knowledge - Collector - Local Test and Regression and Knowledge - Core - Troubleshooting |
| Collector features, parameters, and output contract | Knowledge - Collector - Feature and Output Contract Reference | Knowledge - Core - Tier 1 Collect Runbook, Knowledge - Core - Tier 2 Collect Runbook, Knowledge - Core - Enrichment Actions, Knowledge - Core - Artifact Review Guide, and Knowledge - Collector - EXE Usage and Runtime Behavior |

---

## Source classes

| Class | Examples | How to use it |
| --- | --- | --- |
| Operational state and validation records | Supabase `ircore` routing, retrieval profiles, validation rules, receipts, preferences, and active session state | Supports current routing, readback, validation, and receipt evidence |
| Governed source | Collector source, harness, workflows, Gemini bundle source | Determines implemented behavior |
| Supporting assets | Runtime ZIPs, delivery bundles, retained generated artifacts | Delivery or execution aids, not source of truth |
| Knowledge docs | `knowledge/Knowledge - <Group> - *.md` | Human/Gemini guidance only |

---

## Main system lanes

### Collector lane
The collector produces bounded host-side evidence through collect, enrich, and cleanup-oriented actions.

### Harness lane
The harness validates collector behavior from a repo-style layout and supports PS1 and optional EXE validation.

### Gemini lane
The Gemini bundle uses stored-source agent instructions and maintained knowledge attachments to support analyst workflow, routing, output interpretation, and command-lane discipline.

---

## Common mistakes to avoid

- Treating knowledge docs as control-plane authority
- Treating generated attachments as the editable source
- Treating an EXE wrapper limitation as a collector regression
- Treating package build success as runtime proof
- Mixing endpoint-response syntax with local PowerShell syntax
- Running broad collection before defining the investigative question

---

## Maintenance trigger points

Update dependent surfaces when any of these change:

- collector behavior
- harness behavior
- EXE behavior
- Gemini attachment inventory
- manifest-required files
- GitHub Actions validation coverage

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.
<!-- DCOIR_SOURCE_END {"id":"knowledge.core.overview","sha256":"711089230e2e65f3712aea9392ba5ee68e0759b8ce872115ae7a640c1dbff07c"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":2592,"git_blob_sha":"68f340ff477f7be9d1cccd6f7ac79e1dd1192336","id":"knowledge.shared.output_contract","path":"project_sources/agent_runtime/knowledge_modules/shared/knowledge.shared.output_contract.md","sha256":"b3395b2ccaa82383622131555761c8a5fe77092b4f7dcd7ccf9f10b2f40ba2e4","split_from_id":"knowledge.gemini.output_contract","split_from_path":"knowledge/Knowledge - Gemini - Output Contract and Command-Lane Discipline.md"} -->
# Shared Response and Action-State Discipline

_Provider-neutral rules for evidence-bounded analyst-facing output_

**Summary:** Use these shared rules to keep final answers evidence-bounded, internally consistent, and free of hidden workflow scaffolding. Target-specific Instructions remain the authority for exact section names, decision vocabularies, and command syntax.

---

## Authority boundary

This file is stable reference material. It does not create tools, grant retrieval capability, or override the target's Instructions.

When target-specific Instructions define an exact response structure, decision vocabulary, or command syntax, follow those Instructions. Use this reference only for the shared principles below.

---

## Evidence-bounded conclusions

- Support a final decision only with reviewed evidence.
- Treat missing evidence as a bounded gap, not proof of a benign or malicious condition.
- Separate observed facts, returned source material, and analysis.
- State uncertainty when the available material cannot support a final conclusion.

---

## Grounding honesty

Keep these evidence lanes distinct:

- operator-provided content;
- uploaded or attached files;
- returned public-source material;
- connector-backed retrieval, when actually available;
- unsupported or unavailable lookup.

Describe a search, lookup, retrieval, validation, or handoff as completed only when that action ran and returned usable support.

---

## Action-state honesty

Keep these states separate:

- requested action;
- planned action;
- executed action;
- returned result;
- bounded inability.

Do not present a requested or planned action as completed work.

---

## Singular answer and command discipline

- Produce one coherent analyst-facing answer.
- Do not repeat major sections or provide competing final drafts.
- When the target-specific Instructions call for a single command or query, provide one copy-paste-ready command unless a multi-step exception is necessary and explicitly justified.
- Keep command syntax within the execution lane named by the target-specific Instructions and the operator's request.

---

## Internal scaffold suppression

Do not expose internal planner payloads, routing state, readiness objects, hidden diagnostics, control scaffolding, or handoff narration as analyst-facing content.

The final answer should contain the requested operational result, not an internal work trace.

---

> Canonical provider-neutral projection source. Target package compilers include this file losslessly; provider-specific source remains in its native target.

<!-- DCOIR_SOURCE_END {"id":"knowledge.shared.output_contract","sha256":"b3395b2ccaa82383622131555761c8a5fe77092b4f7dcd7ccf9f10b2f40ba2e4"} -->

