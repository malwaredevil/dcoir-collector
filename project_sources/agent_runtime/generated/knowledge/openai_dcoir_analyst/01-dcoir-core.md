# Generated DCOIR Knowledge Projection

> Generated, non-canonical output. Edit the atomic files under knowledge/, then rebuild all affected targets.

- Target: openai_dcoir_analyst
- Projection group: dcoir_core
- Purpose: Core role, FAQ, and shared output behavior.
- Source count: 3

<!-- DCOIR_SOURCE_BEGIN {"bytes":3911,"git_blob_sha":"1772e022d8e9009ae77c7c9f76fb2aeb90829cf6","id":"knowledge.core.faq","path":"knowledge/Knowledge - Core - FAQ.md","sha256":"6c594f2e74ad2f2e311e8a5f19e30cee24997844994376f118fdd4e81f9d82b4"} -->
# Knowledge - Core - FAQ

_Short answers to recurring DCOIR operator questions_

**Summary:** Fast answers for authority, command lanes, collector use, EXE behavior, Gemini attachments, and validation.

---

## Authority and source

| Question | Answer |
| --- | --- |
| Are knowledge docs authoritative? | No. They support operators and Gemini but do not override Project Instructions, governed GitHub source, implemented source behavior, or Supabase `ircore` operational records. |
| Which files should be edited? | Edit `knowledge/*.md` as the maintained source. Gemini `.md.txt` attachment files are generated runtime surfaces inside the release ZIP. |
| Why do old references mention `.ps1.txt` or `.cmd.txt`? | Older bundle/readable-text surfaces used suffixes more heavily. Current governed runtime files use native repo paths. |
| Is `DCOIR_Collector.zip` source of truth? | No. It is a retained supporting asset for delivery/execution support. |

---

## Execution lanes

| Question | Answer |
| --- | --- |
| When do I use Elastic endpoint shell execution? | Use it only for endpoint response-console execution. |
| When do I use local PowerShell? | Use it for workstation testing, harness runs, and repo-local validation. |
| What is the biggest command mistake? | Mixing endpoint response syntax with local PowerShell syntax. |
| Is there a default CMD harness wrapper? | No current default CMD wrapper is part of the governed guidance. Use `run_DCOIR_Tests.ps1`. |

---

## Collection and enrichment

| Question | Answer |
| --- | --- |
| When should I use Tier 1? | Use Tier 1 for a first-pass host evidence package when current evidence is insufficient. |
| When should I use Tier 2? | Use Tier 2 only when a specific unresolved question needs deeper persistence/configuration context. |
| When is retrieval better than more collection? | When current output already points to a specific artifact likely to answer the next question. |
| Why one enrichment action at a time? | It keeps each action tied to one follow-up question. |

---

## EXE behavior

| Question | Answer |
| --- | --- |
| Is the optional EXE a separate product line? | No. It is a packaged execution form of the same collector source. |
| Can EXE FailureGates differ from PS1? | Yes. EXE wrapping can hide native PowerShell bind-reject diagnostics. Use EXE-aware interpretation. |
| Does EXE build success prove runtime correctness? | No. Runtime behavior is proven by harness suites and output/artifact checks. |

---

## Gemini and attachments

| Question | Answer |
| --- | --- |
| Why does Gemini need knowledge attachments? | They provide stable operational context for routing, output interpretation, and command-lane discipline. |
| What happens when attachment files change? | Update maintained source, attachment map, manifest, and workflow checks together; release packaging regenerates attachment files from `knowledge/*.md`. |
| Where does validation and receipt state belong? | Supabase `ircore` stores operational validation rules, consultation receipts, and readback state. GitHub remains source and packaging authority. |

---

## Review and evidence

| Question | Answer |
| --- | --- |
| What should I read first after Tier 1? | Merged baseline report, metadata, final artifacts, then high-signal referenced artifacts. |
| Are metadata reports evidence? | They are workflow context. They can support interpretation but are not automatically proof of suspicious activity. |
| What does public IOC enrichment provide? | Context and corroboration only; it does not replace case evidence. |

---

## FAQ boundary

FAQ answers are intentionally short. When the answer requires procedure, feature detail, EXE nuance, or output-contract interpretation, follow the owner page instead of expanding this FAQ into duplicate guidance.

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.
<!-- DCOIR_SOURCE_END {"id":"knowledge.core.faq","sha256":"6c594f2e74ad2f2e311e8a5f19e30cee24997844994376f118fdd4e81f9d82b4"} -->

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

<!-- DCOIR_SOURCE_BEGIN {"bytes":2592,"git_blob_sha":"0069bc1f7093d9d816f262c5ba2b25fd936ef622","id":"knowledge.shared.output_contract","path":"project_sources/agent_runtime/knowledge_modules/shared/knowledge.shared.output_contract.md","sha256":"55ce676290c0236209a3c02edf6b72d0e858d2e86d09b7052d68446200f24536","split_from_id":"knowledge.gemini.output_contract","split_from_path":"knowledge/Knowledge - Gemini - Output Contract and Command-Lane Discipline.md"} -->
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

> Canonical provider-neutral projection source. OpenAI package compilers include this file losslessly; provider-specific source remains in its native target.

<!-- DCOIR_SOURCE_END {"id":"knowledge.shared.output_contract","sha256":"55ce676290c0236209a3c02edf6b72d0e858d2e86d09b7052d68446200f24536"} -->

