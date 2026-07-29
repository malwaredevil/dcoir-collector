# Knowledge - Gemini - AI Prompt and Agent Design

_Gemini runtime design principles for routing, grounding, handoff state, and output behavior_

**Summary:** Use this page to keep Gemini routing, grounding, action-state honesty, specialist handoffs, and output behavior clear during live operator use.

---

## Agent field responsibilities

| Field | Purpose |
| --- | --- |
| Description | Routing: when the agent should be used, when it should not be used, and what bounded result it returns |
| Instructions | Behavior: what the agent must do, avoid, preserve, and output |
| Attachments | Context: stable reference material that helps the agent interpret evidence and explain next steps |

A short slogan is not enough for routing. Excessive repetition is also not useful.

Use this exact description shape for Prime and each sub-agent:

- Use when: narrow positive trigger conditions.
- Do not use when: nearest overlapping lanes and explicit exclusions.
- Returns: the bounded output contract.

Keep descriptions concise. Put detailed edge cases, evidence rules, syntax rules, and output constraints in Instructions or maintained knowledge rather than repeating them across several router descriptions.

---

## Branch-specific routing

Do not force every request through a single universal agent order. Choose the route that matches the request family and respect specialist prerequisites. Examples:

- classify and ground alert evidence before query planning;
- normalize IOC-heavy material before hunting;
- interpret relevant existing collector artifacts before recommending more collection;
- keep explicit USB reporting in its dedicated terminal lane.

A stage may be skipped only when its required result is already present, current, and source-labeled.

---

## Common internal handoff

Internal specialists use `common_handoff_envelope_v1`. The envelope carries source references, grounded facts, inferences, confidence, operator constraints, tool/action state, unresolved gaps, blockers, next-owner advice, must-preserve facts, and a domain_payload.

The envelope is an internal orchestration transport, not an analyst-facing response schema. Prime decides the actual next owner, prevents loops, preserves must-survive facts, and sends one reconciled state to the appropriate terminal output owner.

---

## Grounding honesty

Gemini output must distinguish:

- public web search;
- uploaded or attached files;
- configured connector or enterprise retrieval;
- unsupported or unavailable retrieval.

Do not claim internal or enterprise lookup happened unless the runtime actually used an available retrieval surface and returned evidence.

---

## Action-state honesty

Keep these separate:

- requested action;
- planned action;
- executed action;
- returned result;
- unsupported action.

A specialist handoff marked complete means only that the bounded specialist task finished. It does not prove that a search, lookup, command, upload, workflow, or external action completed.

---

## Output contracts

Prefer enforceable output structures over large schemas that are hard to satisfy. When exact formatting matters, keep required fields clear and avoid large optional structures unless necessary. Do not duplicate an analyst-facing final schema inside every specialist prompt.

---

## Anti-patterns

- treating design docs as runtime agent files;
- thinning instruction bodies until behavior becomes vague;
- putting specialist playbooks back into Prime;
- repeating the same routing language across multiple descriptions;
- using one universal route despite conflicting specialist prerequisites;
- flattening specialist returns until source labels, operator corrections, or unresolved gaps are lost;
- allowing a specialist recommendation to create a route loop;
- claiming unavailable search or connector access;
- describing planned or requested actions as completed actions;
- letting routing language become so broad that the wrong specialist branch is chosen.

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.
