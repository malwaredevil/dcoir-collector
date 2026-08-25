# Generated DCOIR Knowledge Projection

> Generated, non-canonical output. Edit the atomic files under knowledge/, then rebuild all affected targets.

- Target: openai_dcoir_analyst
- Projection group: dcoir_artifacts
- Purpose: Artifact review and report interpretation.
- Source count: 1

<!-- DCOIR_SOURCE_BEGIN {"bytes":8935,"git_blob_sha":"62597c9825e018ceae39693c93544a3052d012c1","id":"knowledge.core.artifact_review","path":"knowledge/Knowledge - Core - Artifact Review Guide.md","sha256":"04df85293cb955a0570e7a5cf66c8308541e4dac06776dff9518f85a62cbb824"} -->
# Knowledge - Core - Artifact Review Guide

_Evidence-first review order for current collector output surfaces, enrichment results, and retrieved artifacts_

**Summary:** Use this page to decide what to read first after a collect or enrich run, to separate workflow wrappers from evidence carriers, and to avoid treating older review assumptions as current source truth.

---

## Current review posture

The current collector build is not best understood as “run once, open one merged report, and read top to bottom.”

Current source behavior is analyst-overview-first and guidance-surface-first.
That means the safest operator posture is:

1. read the collector’s own orientation surfaces first;
2. identify the highest-signal evidence carriers they point to;
3. review those evidence carriers before widening the review;
4. treat bundles, large flat output, and broader local review as later steps unless the question already requires them.

This matters because the current source explicitly emits analyst-facing orientation surfaces and explicitly records that a merged baseline report is not the primary review assumption for this build.

---

## Review order for current collect runs

Use this order unless a narrower evidence question clearly justifies deviating from it.

1. `ANALYST_OVERVIEW_PATH`
2. `UPLOAD_SUMMARY_PATH`
3. `METADATA_REPORT_PATH`
4. `ATTACHMENT_BUDGET_MANIFEST_PATH`
5. optional `UPLOAD_SAFE_CHUNK_MANIFEST_PATH` when full-fidelity event text was chunked for upload
6. `COLLECTION_SCOPE_PATH`
7. `SECURITY_HIGH_SIGNAL_SUMMARY_PATH`
8. `EXECUTION_CONTEXT_PATH` when visibility/elevation context matters
9. `PARALLELISM_ASSESSMENT_PATH` when runtime interpretation matters
10. `TARGETED_COLLECTION_PLAN_PATH` when targeted mode was used
11. representative high-signal artifacts referenced by the above surfaces
12. upload-safe full-fidelity chunks only when the high-signal summary is not enough
13. the collect bundle or broader flat output only after the first-pass question is clearer

Do not default to searching the entire output tree before reading the orientation surfaces.

---

## What each early review surface is for

| Surface | Use it to answer |
| --- | --- |
| `ANALYST_OVERVIEW_PATH` | What should I review first, and what posture should I take? |
| `UPLOAD_SUMMARY_PATH` | Which files are most likely to be useful first when upload/review budget matters? |
| `METADATA_REPORT_PATH` | What run state, timing, and structural context do I need before interpreting artifacts? |
| `ATTACHMENT_BUDGET_MANIFEST_PATH` | Which recommended files fit the intended environment budget, and which do not? |
| `UPLOAD_SAFE_CHUNK_MANIFEST_PATH` | Which oversized real text artifacts have ordered full-fidelity chunk companions? |
| `COLLECTION_SCOPE_PATH` | What collection scope was actually requested or emphasized? |
| `SECURITY_HIGH_SIGNAL_SUMMARY_PATH` | What security-relevant signals deserve first-pass attention? |
| `EXECUTION_CONTEXT_PATH` | Was the run elevated, and were visibility limits likely to affect interpretation? |
| `PARALLELISM_ASSESSMENT_PATH` | What bounded runtime parallelism behavior should I understand before making claims about execution? |
| `TARGETED_COLLECTION_PLAN_PATH` | What targeted evidence families were meant to be prioritized for a narrow incident? |

These are not all evidence carriers themselves.
They are orientation and prioritization surfaces that tell you where the decisive evidence is most likely to be.

---

## Wrapper versus evidence carrier

This distinction is critical.
A collector output can be useful without being the thing that proves the case.

| Artifact type | Role |
| --- | --- |
| Orientation / summary / metadata surface | Explains scope, context, priority, and next review targets |
| Upload or retrieval guidance surface | Helps decide what to inspect or move next |
| Retrieved file, script, task XML, EVTX, binary, config, registry export, or focused log extract | Evidence carrier |

Do not treat a wrapper or orientation file as proof when it is pointing you to the actual evidence carrier.

---

## Review order for current enrich runs

For enrich output, start with the session and action surfaces before jumping into staged content.

1. `ENRICH_REPORT_PATH`
2. optional `ACTION_ARTIFACT_PATH` when an action ran
3. `SESSION_RESOLUTION_MODE`
4. `SESSION_STATUS`
5. optional `STAGED_PATH` when a retrieval-style action staged evidence
6. optional `ENRICH_BUNDLE_PATH` after finalization

A finalize-only enrich path is a normal outcome only when it finalizes an existing open session or a valid non-finalized requested session.
When the operator runs `enrich-finalize` without a new action, the current source emits the session report and finalization surfaces without `ACTION_ARTIFACT_PATH`; if there is no open or requested non-finalized session, the collector rejects the command so operators do not review an empty enrichment bundle as evidence.

### Practical enrich interpretation rule

- Review-style enrich actions often answer the next question directly in the action artifact.
- Retrieval-style enrich actions often exist to hand you the next evidence carrier for offline review.

Do not assume every enrich action should be interpreted the same way.

---

## Evidence-first review posture

When you read a collector artifact, keep these categories separate:

- observed evidence;
- inference;
- uncertainty;
- recommended next action.

A good review note should make clear:

- what the artifact directly shows;
- what it merely suggests;
- what it still does not prove;
- what narrower next step would most efficiently reduce uncertainty.

---

## Artifact-specific focus

| Artifact | Focus |
| --- | --- |
| Script or command file | behavior, referenced paths, parameters, intent clues, execution context |
| Config or XML | triggers, accounts, timing, paths, command arguments, referenced payloads |
| Registry export | exact path, value meaning, startup/security relevance, whether it shows existence or use |
| EVTX or log excerpt | event timing, actor, process, host context, and correlation limits |
| Binary or service artifact | signer, hash, path, service context, relationship to observed behavior |
| Process or network artifact | what launched, what connected, under which account, and what still needs corroboration |

---

## Upload priority when limits matter

When you cannot upload or review everything at once, prefer what is most likely to answer the current question.

1. orientation surface that identifies the lead finding
2. highest-signal evidence carrier referenced by that surface
3. supporting context required to interpret that carrier
4. only then lower-signal supporting volume

In practical current-source terms, that often means:

1. `ANALYST_OVERVIEW_PATH`
2. `UPLOAD_SUMMARY_PATH`
3. `SECURITY_HIGH_SIGNAL_SUMMARY_PATH`
4. one representative evidence carrier
5. upload-safe chunks for a full-fidelity source artifact only when the summary is insufficient
6. only then broader supporting files

Do not upload broad low-value output before the artifact most likely to answer the live question.

---

## Common mistakes

- treating an orientation surface as proof instead of as guidance
- starting with broad flat output before reading analyst overview and upload summary
- assuming a merged baseline report is still the default first review surface in the current build
- jumping to final synthesis before the decisive evidence carrier is reviewed
- reading many low-value artifacts before the one high-signal artifact the collector already pointed to
- treating artifact volume as severity or confidence

---

## Source-backed boundary notes

The current governed source supports these careful statements:

- analyst-overview-first review is real and source-backed in the current build;
- targeted collection may emit a targeted collection plan that should influence first review for narrow incidents;
- enrich actions split into review-style and retrieval-style outcomes and should not be flattened into one review model;
- workflow/bundle surfaces help with handling and prioritization, but they do not replace evidence review.

Avoid stronger claims than the output surfaces support.

---

## Cross-reference boundaries

- Use this page for evidence review order and upload priority.
- Use `knowledge/Knowledge - Collector - Feature and Output Contract Reference.md` for the collector anchor contract.
- Use `knowledge/Knowledge - Core - Tier 1 Collect Runbook.md` and `knowledge/Knowledge - Core - Tier 2 Collect Runbook.md` for collect decision framing.
- Use `knowledge/Knowledge - Core - Enrichment Actions.md` for enrichment workflow and action selection.
- Use `knowledge/Knowledge - Collector - EXE Usage and Runtime Behavior.md` only when EXE-specific wrapper interpretation matters.

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.

<!-- DCOIR_SOURCE_END {"id":"knowledge.core.artifact_review","sha256":"04df85293cb955a0570e7a5cf66c8308541e4dac06776dff9518f85a62cbb824"} -->

