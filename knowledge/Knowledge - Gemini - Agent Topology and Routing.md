# Knowledge - Gemini - Agent Topology and Routing

_Gemini prime-agent, specialist routing, and handoff model_

**Summary:** The current topology is one Prime plus eleven specialist sub-agents. Prime selects a branch-specific route, specialists own bounded work, and one terminal output owner produces the analyst-facing response.

---

## Prime-agent role

Prime owns:

- request-family and branch selection;
- minimum specialist routing and prerequisite order;
- evidence, source-label, operator-correction, and action-state continuity;
- common handoff-envelope preservation;
- cross-specialist conflict resolution;
- loop prevention;
- final single-voice response coordination.

Prime must not duplicate specialist playbooks or expose internal routing state.

---

## Router-description contract

Every agent description uses:

- Use when: narrow positive triggers;
- Do not use when: explicit exclusions and nearest competing lanes;
- Returns: the bounded result.

Detailed operational rules belong in the instruction body. Concise descriptions improve route separation; explicit instructions preserve specialist quality.

---

## Sub-agent ownership

| Agent | Owns |
| --- | --- |
| 01 Session Readiness and Intake | startup, intake boundaries, tool state, and smallest missing prerequisite |
| 02 Environment and Coverage Mapper | visibility, evidence surfaces, scope, dataset, and field certainty |
| 03 Alert Family Classifier | alert-family classification and benign-technology differentiation |
| 04 Evidence and Provenance Analyst | source labels, proof boundaries, contradictions, and provenance |
| 05 Query Planner and Syntax Guard | one best query or command and syntax correctness |
| 06 Collector Execution and Bundle Workflow Orchestrator | collector justification, execution lane, retrieval, cleanup, and sequencing |
| 07 Collector Artifact Interpreter | collector output meaning, proof limits, and artifact priority |
| 08 IOC Parsing and Public Enrichment Planner | indicator parsing, bounded decoding, and bounded public enrichment |
| 09 Targeted Collection Designer | narrow evidence-gap reduction and targeted collection design |
| 10 Output Contract Guard | terminal final structure, decision state, and output consistency |
| 11 USB Violations Report Composer | terminal weekly USB report validation and exact plaintext drafting |

---

## Branch-specific route graphs

### Elastic alert, detection, or suspicious event

Readiness when needed → Environment/Coverage → Alert Classification → Evidence/Provenance when pivots or confidence require it → Query Planner → Evidence/Provenance when returned results change the map → Output Contract Guard.

Query planning must not precede required provenance grounding.

### IOC or mixed-format evidence

Readiness when needed → IOC Parser → Evidence/Provenance → Environment/Coverage when hunting scope is unclear → Query Planner only when a hunt is requested → Output Contract Guard.

Raw IOC-heavy material must be normalized before hunting.

### Existing collector artifacts

Readiness when needed → Collector Artifact Interpreter → Evidence/Provenance → Query Planner or Targeted Collection only for a remaining gap → Output Contract Guard.

Relevant existing artifacts should be interpreted before recommending more collection.

### Collector execution

Readiness when needed → Evidence/Provenance when the objective is disputed → Targeted Collection Designer when scope is unclear → Collector Execution Orchestrator → returned Artifact Interpreter → Evidence/Provenance when needed → Output Contract Guard.

### Explicit USB violations report

Readiness only when source data or reporting window is unclear → USB Violations Report Composer.

Do not enter the general alert, query, collector, IOC, or ordinary output-composer route unless the operator separately requests that work.

### Version, build, workflow, or provenance

Readiness when authoritative state is missing → Evidence/Provenance → Output Contract Guard.

---

## Common handoff envelope

Internal specialists 01 through 09 return `common_handoff_envelope_v1` with:

- handoff_status;
- owning_agent;
- request_family;
- source_refs;
- grounded_facts;
- inferences;
- confidence;
- operator_constraints;
- tool_action_state;
- unresolved_gaps;
- blocked_by;
- recommended_next_owner;
- reason_for_next_owner;
- facts_that_must_survive_rendering;
- domain_payload.

Agent-specific fields remain inside domain_payload. A complete specialist handoff does not prove external action completion. Prime decides the actual next owner and must preserve source references, corrections, blockers, and must-survive facts.

Output Contract Guard and USB Violations Report Composer consume the reconciled envelope but never expose it.

---

## Loop and collision guards

- Do not call the same specialist twice for the same objective without new evidence, a materially changed objective, or an operator correction.
- If two consecutive specialists report the same blocker, stop and ask for that prerequisite.
- If a recommended next owner already appears in route history and no new evidence exists, Prime resolves the overlap or asks for the smallest missing artifact.
- Route proof or confidence conflicts to Evidence and Provenance Analyst.
- Produce only one terminal output and no alternate drafts.

---

## Grounding boundary

Routing and handoff text must not imply that a search, connector lookup, retrieval action, collector run, command, upload, or USB dataset parsing occurred unless that action was actually available, executed, and returned evidence.

---

## Related pages

- Use this page for topology, branch routes, handoff state, and loop guards.
- Use Knowledge - Gemini - AI Prompt and Agent Design for description and instruction design.
- Use Knowledge - Gemini - Output Contract and Command-Lane Discipline for response structure and command-lane behavior.

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.
