# Generated DCOIR Knowledge Projection

> Generated, non-canonical output. Edit the atomic files under knowledge/, then rebuild all affected targets.

- Target: openai_dcoir_analyst
- Projection group: dcoir_collection
- Purpose: Collector runbooks, execution, features, and troubleshooting.
- Source count: 7

<!-- DCOIR_SOURCE_BEGIN {"bytes":2257,"git_blob_sha":"4923d9ec8b9cb6ddb9d772bc9f5a83041fb99be3","id":"knowledge.collector.exe_runtime","path":"knowledge/Knowledge - Collector - EXE Usage and Runtime Behavior.md","sha256":"e4083554d2b348eb9f2a65f997006d0223f54e3beef44f421756ec3d8cbf745c"} -->
# Knowledge - Collector - EXE Usage and Runtime Behavior

_Optional EXE execution and PS1 behavior differences_

**Summary:** Use this page when running or interpreting the optional DCOIR Collector EXE.

---

## What the EXE is

The optional EXE is a packaged execution form of the same collector behavior. It is useful when the operator intends to run the collector as an executable rather than as a PowerShell script.

---

## Local EXE examples

Tier 1 collect:

```powershell
.\DCOIR_Collector.exe -Mode Collect -Tier T1 -Hours 24 -OutRoot C:\Temp
```

Targeted collection:

```powershell
.\DCOIR_Collector.exe -Mode Collect -Targeted -TargetProfile PopupWindow -WindowStart "2026-04-30T08:00:00" -WindowEnd "2026-04-30T09:00:00" -OutRoot C:\Temp
```

Help and version:

```powershell
.\DCOIR_Collector.exe -ShowHelp
.\DCOIR_Collector.exe -ShowVersion
```

---

## PS1 versus EXE behavior

| Area | PS1 | EXE |
| --- | --- | --- |
| Runtime path | Script metadata | May resolve through executable process path |
| Parameter binding diagnostics | Native PowerShell behavior visible | Wrapper may hide or reshape diagnostics |
| FailureGates bind-reject behavior | Strict native checks | EXE-aware interpretation required |
| Output contract on successful runs | Must remain stable | Must remain stable |

Do not treat EXE wrapper differences as collector defects unless functional behavior, artifacts, or the output contract are wrong.

---

## FailureGates rule

FailureGates and FullRegression must be interpreted with runtime mode in mind:

- PS1 mode: strict native bind-reject expectations;
- EXE mode: wrapper-limited bind-reject probes may be expected.

---

## Gemini interpretation

When an EXE run fails, Gemini should classify the failure before recommending a fix:

1. workflow/build failure;
2. packaging failure;
3. harness execution failure;
4. EXE wrapper limitation;
5. real collector runtime behavior regression.

---

## Related pages

- Use this page for optional EXE behavior and EXE-specific interpretation.
- Use Knowledge - Collector - Feature and Output Contract Reference for collector features, parameters, and output-contract expectations.

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.

<!-- DCOIR_SOURCE_END {"id":"knowledge.collector.exe_runtime","sha256":"e4083554d2b348eb9f2a65f997006d0223f54e3beef44f421756ec3d8cbf745c"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":22860,"git_blob_sha":"5908fba9335c787bd35e38c8df08ced6a15ae452","id":"knowledge.collector.feature_contract","path":"knowledge/Knowledge - Collector - Feature and Output Contract Reference.md","sha256":"a9ae1a40988d32cafec014c1a4122aada41b6c261ad41763579718b0857c490a"} -->
# Knowledge - Collector - Feature and Output Contract Reference

_Source-grounded collector anchor page for modes, quick aliases, targeted collection, enrichment, output surfaces, and runtime contract_

**Summary:** Use this page as the main operator reference when you only have `DCOIR_Collector.ps1` and `DCOIR_Collector.zip` and need to understand what the collector can do, which entry path to choose, what outputs to expect, and what the current implementation does not guarantee.

---

## Operator starting point

This page is written for the operator who did not build the collector.

Start here when you need to answer questions like:

- What are the real top-level modes?
- When should I use Tier 1 versus Tier 2?
- Which quick alias already matches what I want to do?
- When should I use targeted collection instead of baseline collection?
- What does enrichment really do in practice?
- Which outputs should I look at first?
- What does the collector guarantee, and what does it not guarantee?

This page is the collector anchor page.
Dependent runbooks should align to this page rather than restating partial copies of the source contract.

---

## Collector mental model

The collector is not one generic "collect more" button.
It has three different top-level operating modes:

| Mode | Purpose | Typical operator question |
| --- | --- | --- |
| `Collect` | Create a baseline or targeted host evidence package | What broad or scoped host evidence should I collect now? |
| `Enrich` | Run one bounded follow-up action tied to an evidence question | What specific process, path, service, task, log, or file needs deeper follow-up? |
| `Cleanup` | Remove runtime/output material after evidence is safe | Have I already retrieved or preserved what I need? |

The safest general pattern is:

1. collect only what matches the current question;
2. review summary surfaces before raw volume;
3. enrich only when one bounded follow-up question exists;
4. retrieve specific evidence carriers when a known artifact matters more than another broad run;
5. clean up only after evidence is safe.

---

## Top-level modes

| Mode | What it does | Important boundary |
| --- | --- | --- |
| `Collect` | Builds the run structure, stages the runtime ZIP, expands tools, collects baseline artifacts, writes reports/manifests, and bundles the result | Collection breadth does not prove maliciousness by itself |
| `Enrich` | Reuses the existing run state and appends one bounded follow-up action into an enrichment session | Enrichment is for narrower follow-up, not a second baseline pass |
| `Cleanup` | Removes the run root and consumed package state | Cleanup is not the same as retrieval and should happen only after evidence is safe |

---

## Tier model

| Tier | Purpose | Normal use |
| --- | --- | --- |
| `T1` | First-pass baseline collection | Start here when you need a broad but still triage-oriented evidence package |
| `T2` | Deeper persistence and configuration context | Use only when Tier 1 or current evidence leaves a specific unresolved deeper question |

Tier selection is a depth decision, not a confidence decision.
Use T2 because a named question needs deeper persistence/configuration context, not because T1 feels incomplete in the abstract.

---

## Entry styles actually supported

| Entry style | Use when | Example |
| --- | --- | --- |
| Explicit parameters | You want the clearest source-aligned invocation | `-Mode Collect -Tier T1 -Hours 24` |
| `-Quick` shortcut | The collector already exposes a matching common path | `-Quick collect-t1` |
| `-ShowHelp` | You need the collector’s built-in operator help | `-ShowHelp` |
| `-ShowVersion` | You need to prove runtime/build identity before a stateful step | `-ShowVersion` |

---

## Common parameters

| Parameter | Purpose | Notes |
| --- | --- | --- |
| `-Mode` | Select `Collect`, `Enrich`, or `Cleanup` | Top-level execution selector |
| `-Tier` | Select `T1` or `T2` | Used for collect depth |
| `-Hours` | Set the lookback window | Still relevant even when targeted mode is used |
| `-OutRoot` | Select the output root | Used to locate run state, reports, artifacts, bundles, and cleanup target |
| `-PackageName` | Select the runtime ZIP name | Defaults to `DCOIR_Collector.zip` |
| `-RunId` | Reuse or target a specific run state | Usually auto-created for collect |
| `-Quick` | Use a supported shortcut | See the source-grounded quick alias list below |
| `-ShowHelp` | Print help | Can also route through help quick aliases |
| `-ShowVersion` | Print version/build identity | Use before stateful validation or package-movement questions |

---

## Quick aliases accepted by source

These are the quick aliases currently accepted by the collector quick resolver. Some are
also highlighted in the help surface as common operator shortcuts, but this table is the
source-backed complete quick set. Operators and Gemini should not invent commands outside
this supported set.

### Collect quick aliases

| Quick alias | Purpose |
| --- | --- |
| `collect-t1` | Run Tier 1 collect |
| `collect-t2` | Run Tier 2 collect |
| `collect-targeted-popup` | Start a targeted popup-oriented collection path |
| `collect-targeted-script` | Start a targeted script-execution-oriented collection path |

### Enrich quick aliases

Each `enrich-start-*` alias starts a new enrich session for that action. The matching
`enrich-add-*` alias adds the same action to the currently open session or to the explicit
non-finalized session supplied with `-EnrichSessionId`.

| Quick alias family | Action | Required target |
| --- | --- | --- |
| `enrich-start-tcp`, `enrich-add-tcp` | Refresh TCP connection evidence | None |
| `enrich-start-logtext`, `enrich-add-logtext` | Export event log text | Optional `-Target <log name>`; defaults to Security |
| `enrich-start-lograw`, `enrich-add-lograw` | Export raw EVTX log data | Optional `-Target <log name>`; defaults to Security |
| `enrich-start-sigcheck`, `enrich-add-sigcheck` | Run signature/hash review for a path | `-Target <path>` |
| `enrich-start-listdlls`, `enrich-add-listdlls` | Review loaded modules for a PID | `-Target <pid>` |
| `enrich-start-access-file`, `enrich-add-access-file` | Run access-check review for a file path | `-Target <path>` |
| `enrich-start-access-service`, `enrich-add-access-service` | Run access-check review for a service | `-Target <service name>` |
| `enrich-start-access-reg`, `enrich-add-access-reg` | Run access-check review for a registry path | `-Target <registry path>` |
| `enrich-start-strings`, `enrich-add-strings` | Extract strings from a path | `-Target <path>` |
| `enrich-start-streams`, `enrich-add-streams` | Check alternate data streams for a path | `-Target <path>` |
| `enrich-start-pull-file`, `enrich-add-pull-file` | Retrieve a suspicious file | `-Target <path>` |
| `enrich-start-pull-script`, `enrich-add-pull-script` | Retrieve a suspicious script or config file | `-Target <path>` |
| `enrich-start-pull-task`, `enrich-add-pull-task` | Retrieve scheduled task XML | `-Target <task path>` |
| `enrich-start-pull-service`, `enrich-add-pull-service` | Retrieve a service binary | `-Target <service name>` |
| `enrich-start-pull-wmi-file`, `enrich-add-pull-wmi-file` | Retrieve a file referenced by WMI persistence evidence | `-Target <path>` |
| `enrich-finalize` | Finalize and bundle the current open enrich session, or the explicit non-finalized session supplied with `-EnrichSessionId` | None unless finalizing an explicit session |

### Cleanup and help quick aliases

| Quick alias | Purpose |
| --- | --- |
| `cleanup` | Run cleanup |
| `help` | Print general help |
| `help-collect` | Print collect-specific contextual help |
| `help-enrich` | Print enrich-specific contextual help |
| `help-cleanup` | Print cleanup-specific contextual help |
| `help-targeted` | Print targeted-collection-specific contextual help |
| `help-version` | Print version/build guidance |

---

## Targeted collection contract

Use targeted collection when the question is narrower than a generic baseline and you have specific context such as a time window, user report, focal process, focal path, or focal indicator.

### Targeted parameters

| Parameter | Purpose |
| --- | --- |
| `-Targeted` | Enable targeted collection posture |
| `-TargetProfile` | Choose the targeted profile |
| `-WindowStart` | Set explicit requested start time |
| `-WindowEnd` | Set explicit requested end time |
| `-IncludeArtifactCategory` | Prefer specific artifact families |
| `-FocusProcess` | Name a focal process |
| `-FocusPath` | Name a focal path |
| `-FocusIndicator` | Name a focal indicator |
| `-FocusIndicatorType` | Clarify indicator type |
| `-UserReport` | Preserve the user/analyst problem statement |

Exact event-window filtering is source-backed for event-log text and raw EVTX lanes that route through the explicit event-window helpers. Targeted mode still does not mean every artifact family is exact-window filtered; use the scope and plan surfaces to identify the requested boundary and event-log artifacts to verify the filtered evidence carrier.

### Targeted profiles actually exposed by source

| Profile | Intended use |
| --- | --- |
| `Generic` | Narrow the request without a more specific profile fit |
| `PopupWindow` | Follow a user-reported popup or likely GUI-launching event |
| `ScriptExecution` | Follow suspicious script or command execution |
| `PersistenceFollowUp` | Follow a persistence-oriented lead |
| `NetworkOnly` | Follow a primarily network-oriented lead |
| `ProcessAndPowerShell` | Follow a process-plus-PowerShell execution lead |

### Current implementation boundary

The current source is explicit about a boundary that operators must understand:

- targeted mode narrows analyst guidance, collection scope intent, artifact prioritization, and recommended next actions;
- it does **not** yet rewrite every baseline collection helper into exact start/end timestamp filtering across all artifact families.

That means targeted mode is still valuable and real, but it should not be described as universal exact filtering unless a narrower claim is backed by source and validation for that specific path.

---

## Enrichment session contract

Enrichment is session-based, not just action-based.
The collector keeps bounded follow-up work grouped into one session until the operator finalizes it.

### Session behavior actually visible in source

| Behavior | Meaning |
| --- | --- |
| Create new session | `enrich-start` style paths create a fresh session |
| Reuse current open session | `enrich-add` style paths append to the current open session when appropriate |
| Reuse by explicit id | Operators can target an existing session with `-EnrichSessionId` |
| Finalize session | Creates a bundle and closes the active non-finalized session |
| Reject finalized requested session | Explicit `-EnrichSessionId` cannot append to a session already finalized |
| Reject finalize without open session | `enrich-finalize` without `-EnrichSessionId` requires an existing open session |

### Session controls

| Parameter | Purpose |
| --- | --- |
| `-EnrichSessionId` | Continue or target a specific session |
| `-NewEnrichSession` | Force a new session |
| `-FinalizeEnrichSession` | Finalize the current or targeted session |
| `-Action` | Select the enrich action |

### Important session rule

The source-backed behavioral contract is:

- `enrich-start` creates a new session;
- `enrich-add` reuses the current open session unless explicitly overridden;
- `enrich-finalize` finalizes the current open session;
- `enrich-finalize -EnrichSessionId <id>` finalizes that specific non-finalized session;
- a finalized session cannot be appended to;
- a finalize-only call with no open session is rejected instead of creating an empty bundle.

Use one session for closely related follow-up.
Do not mix unrelated questions into one enrich session just because the session is open.

---

## Enrichment actions actually exposed by source

### Review-style enrich actions

These answer analyst-review questions without primarily staging a new retrieval artifact.

| Action | Typical use |
| --- | --- |
| `SigcheckPath` | Review signer, hashes, and version data for a suspicious path |
| `ListDllsPid` | Review loaded modules for a suspicious process |
| `AccessChkFile` | Review effective access for a file or directory |
| `AccessChkService` | Review effective access for a service |
| `AccessChkReg` | Review effective access for a registry location |
| `StringsPath` | Extract readable strings from a suspicious file |
| `StreamsPath` | Review alternate data streams |
| `TcpvconRefresh` | Refresh TCP view for network review |
| `LogText` | Export text-form event review data |

### Retrieval-style enrich actions

These stage or export a concrete evidence carrier for analyst pickup.

| Action | Typical use |
| --- | --- |
| `LogRaw` | Export raw EVTX for workstation review |
| `PullSuspiciousFile` | Stage a suspicious file for retrieval |
| `PullScriptOrConfig` | Stage a script or config file for retrieval |
| `PullTaskXml` | Export a scheduled task XML definition |
| `PullServiceBinary` | Stage the binary referenced by a service |
| `PullWmiReferencedFile` | Stage a file referenced by suspicious WMI persistence |

### Action-specific parameter families visible in source

| Parameter family | Common actions |
| --- | --- |
| `-Path` | file, script, config, task-name-as-path, WMI-referenced file |
| `-TargetPid` | process-centric review |
| `-ServiceName` | service review or service-binary retrieval |
| `-RegistryPath` | registry access review |
| `-LogName` | text or raw log export |
| `-EventId` | narrower log selection |
| `-MaxEvents` | bounded event count |

The exact best action should be chosen from the question you are trying to answer, not from the broadest available action.

---

## Runtime/package contract visible to operators

### PS1-first delivery contract

The current governed runtime contract is PS1-first.
Operators should treat the PowerShell runtime as the primary supported delivery path unless an explicit future promotion decision changes that contract.

### Retained runtime ZIP

The governed retained runtime ZIP is `DCOIR_Collector.zip`.
It is part of the current packaging/runtime model and should not be mentally replaced with an imagined newer source of truth.

### Transport-safe delivery rule

The packaging manifest and packaging pipeline docs make clear that the delivery artifact uses transport-safe `.txt` suffixes for script entries inside the delivery package.
That matters when handling packaged contents and when reasoning about how the runtime is delivered.

### Optional EXE lane

The optional EXE exists, but it is additive.
It does not replace the PS1-first collector delivery contract.
Use the EXE page for wrapper-specific interpretation, not as a reason to blur the primary runtime contract.

---

## Collect output contract

A successful collect run emits more than one useful surface.
Operators should not reduce it to “one big bundle” or “one report.”

### Core collect status surfaces visible in source

| Surface | Why it matters |
| --- | --- |
| `STATUS` | Tells you whether the run succeeded, partially succeeded, or failed |
| `RUN_ID` | Anchors later enrich, retrieval, and cleanup work |
| `COLLECTOR_VERSION` | Confirms runtime version |
| `COLLECTOR_BUILD_IDENTITY` | Confirms runtime/build identity |

### Core collect report and context surfaces visible in source

| Surface | Why it matters |
| --- | --- |
| `METADATA_REPORT_PATH` | High-level run metadata and state |
| `EXECUTION_CONTEXT_PATH` | Elevation, identity, host, and runtime context |
| `SECURITY_AUDIT_POLICY_PATH` | Audit-policy visibility context |
| `AUDIT_POLICY_ACCESS_STATUS` | Signals whether the audit-policy surface was accessible as expected |
| `SECURITY_FILTERED_PATH` | Security-focused filtered output surface |
| `SECURITY_HIGH_SIGNAL_SUMMARY_PATH` | High-signal triage surface |
| `IS_ELEVATED` | Matters for visibility and interpretation |
| `NETSTAT_OWNER_AWARE_STATUS` | Explains whether owner-aware netstat succeeded |
| optional `NETSTAT_PID_ONLY_PATH` | Supplemental path when owner-aware capture cannot be used |

### Analyst-first collect guidance surfaces visible in source

| Surface | Why it matters |
| --- | --- |
| `ANALYST_OVERVIEW_PATH` | Source-backed analyst-first entry surface |
| `UPLOAD_SUMMARY_PATH` | Tells you what is recommended for upload/review first |
| `ATTACHMENT_BUDGET_MANIFEST_PATH` | Records the recommended upload set against environment budget |
| optional `UPLOAD_SAFE_CHUNK_MANIFEST_PATH` | Lists upload-safe chunk companions for oversized real text artifacts |
| `COLLECTION_SCOPE_PATH` | Documents the current collect scope |
| `PARALLELISM_ASSESSMENT_PATH` | Explains bounded runtime parallelism posture |
| optional `TARGETED_COLLECTION_PLAN_PATH` | Gives targeted analyst guidance when targeted mode is used |
| optional `PARALLEL_EXECUTION_PROOF_PATH` | Supports validation of bounded runtime overlap/proof surfaces |

### Bundle and handoff surfaces visible in source

| Surface | Why it matters |
| --- | --- |
| `COLLECT_BUNDLE_PATH` | Points to the collect bundle |
| `NEXT_GET_FILE` | Retrieval handoff |
| `CLEANUP_COMMAND` | Cleanup handoff |
| `DELETE_SCRIPT_COMMAND` | Response-action-safe script removal handoff |
| `GEMINI_UPLOAD_GUIDANCE` | Upload-priority guidance from the collector itself |

### Optional collect surfaces visible in source

| Surface | Why it matters |
| --- | --- |
| `DEFAULT_GEMINI_UPLOAD_SET_STATUS` | Shows whether the default upload set fits the expected budget |
| optional `UPLOAD_SAFE_CHUNK_MANIFEST_PATH` | Production chunk manifest for oversized real human-readable artifacts such as full-fidelity event text |
| optional `SYNTHETIC_OVERSIZE_SOURCE_PATH` | Validation-specific oversized-artifact surface |
| optional `CHUNK_MANIFEST_PATH` | Validation-specific chunking surface |
| `MaxEvents` in collection metadata | Confirms the bounded event-count setting used by collect-mode event surfaces |
| repeated `COLLECTOR_ERROR=` lines | Preserve bounded degraded-run facts without hiding them |

### Practical operator review order

For current source behavior, the safest first-pass review order is:

1. `ANALYST_OVERVIEW_PATH`
2. `UPLOAD_SUMMARY_PATH`
3. `METADATA_REPORT_PATH`
4. `ATTACHMENT_BUDGET_MANIFEST_PATH`
5. optional `UPLOAD_SAFE_CHUNK_MANIFEST_PATH` when the upload summary reports oversized full-fidelity text chunks
6. `COLLECTION_SCOPE_PATH`
7. `SECURITY_HIGH_SIGNAL_SUMMARY_PATH`
8. representative high-signal artifacts referenced by those surfaces
9. upload-safe full-fidelity chunks only when the high-signal summary is not enough
10. bundle retrieval or deeper local review after the first-pass question is clearer

Do not assume a merged baseline report is the primary review surface in the current build.

---

## Enrich output contract

A successful enrich run also emits more than one meaningful surface.

| Surface | Why it matters |
| --- | --- |
| `STATUS` | Success / partial / error |
| `RUN_ID` | Anchors back to the collect run |
| `COLLECTOR_VERSION` | Runtime identity |
| `COLLECTOR_BUILD_IDENTITY` | Build identity |
| `ENRICH_SESSION_ID` | Session anchor |
| `SESSION_RESOLUTION_MODE` | Tells you whether the session was created, reused, or explicitly targeted |
| `ENRICH_REPORT_PATH` | Session summary/report surface |
| optional `ACTION_ARTIFACT_PATH` | Per-action artifact surface when an action ran |
| optional `STAGED_PATH` | Retrieval-ready staged artifact |
| `SESSION_STATUS` | Whether the session remains open or has been finalized |
| optional `ENRICH_BUNDLE_PATH` | Finalized enrich bundle |
| `NEXT_GET_FILE` | Retrieval handoff when finalized |
| `DELETE_SCRIPT_COMMAND` | Script-removal handoff |

A finalize-only enrich path is a normal success path only when there is an open session or a valid non-finalized `-EnrichSessionId`.
When the operator runs `enrich-finalize` without a new action, current source emits the session report and finalization surfaces without `ACTION_ARTIFACT_PATH`; if there is no open or requested non-finalized session, the collector rejects the command instead of producing an empty bundle.

Review-style enrich actions often answer the next question directly.
Retrieval-style enrich actions often exist to hand you the next evidence carrier to inspect offline.

---

## Cleanup contract

Cleanup exists to remove run/output material after evidence is safe.
It is not a retrieval step, and it should not be used as a substitute for deciding what matters first.

Source-backed cleanup guidance also makes clear that cleanup does not remove the uploaded collector script unless the explicit delete-script command is used.
If collect fails before `state.json` is saved, cleanup has a bounded missing-state fallback: plain latest cleanup removes only timestamp-style latest `DCOIR_*` orphans under the selected `OutRoot` plus the configured package file, while custom `-RunId` no-state roots require cleanup with that explicit `-RunId`. The collector reports `MISSING_STATE_ORPHAN_CLEANED` or `NO_TARGET_FOUND` instead of requiring broad manual temp-folder cleanup.

Practical operator rule:

- retrieve first when retrieval is still needed;
- review first when review is still needed;
- clean up only after the evidence you care about is preserved.

---

## Current limitations and uncertainty boundaries

The current source and governed docs support these bounded statements:

- targeted mode is real and source-backed, but not a universal exact-time filtering guarantee across all artifact families;
- enrichment is a bounded follow-up mechanism, not a replacement for baseline collection;
- collect outputs include multiple analyst-first guidance surfaces, not just one report or one bundle;
- the optional EXE lane exists, but the supported delivery contract remains PS1-first;
- passing code/help coverage checks does not by itself prove operator-usable documentation depth.

Avoid stronger claims than the source currently supports.

---

## Cross-reference boundaries

- Use this page as the collector anchor page.
- Use `knowledge/Knowledge - Core - Tier 1 Collect Runbook.md` for T1 procedure and decision framing.
- Use `knowledge/Knowledge - Core - Tier 2 Collect Runbook.md` for T2 procedure and decision framing.
- Use `knowledge/Knowledge - Core - Enrichment Actions.md` for enrichment workflow guidance.
- Use `knowledge/Knowledge - Core - Artifact Review Guide.md` for evidence-review order and upload priority.
- Use `knowledge/Knowledge - Collector - EXE Usage and Runtime Behavior.md` for EXE-specific interpretation only.

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.
<!-- DCOIR_SOURCE_END {"id":"knowledge.collector.feature_contract","sha256":"a9ae1a40988d32cafec014c1a4122aada41b6c261ad41763579718b0857c490a"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":4625,"git_blob_sha":"5d8ea9049bf70c14e0fc6a888b42ff5c4450de25","id":"knowledge.collector.local_test","path":"knowledge/Knowledge - Collector - Local Test and Regression.md","sha256":"b9429d3382d91ffd2916a70b7f76e08e4b67b85398b7107ea24e1bae63f3daf3"} -->
# Knowledge - Collector - Local Test and Regression

_How to run and interpret collector validation locally across PS1 and EXE modes_

**Summary:** Defines the local validation model, harness usage, suite intent, and how to interpret results without duplication or drift. Aligns with Knowledge - Collector - EXE Usage and Runtime Behavior (EXE behavior) and Knowledge - Collector - Feature and Output Contract Reference (feature/output contract).

---

## Core principle

The harness exists to test the **collector**, not to introduce alternative behavior.

- One collector line
- One harness
- Repeatable execution

All validation must map back to:
- a defined test objective
- an observable output contract

---

## Runtime modes

### PS1 (authoritative behavior)
- Direct PowerShell execution
- Full parameter-binding visibility
- Strict FailureGates expectations

### EXE (packaged behavior)
- Wrapper-limited diagnostics
- May not surface native PowerShell bind-reject errors
- Requires EXE-aware interpretation (see Knowledge - Collector - EXE Usage and Runtime Behavior)

**Rule:**
- Do not treat EXE diagnostic differences as regressions unless output contract or runtime behavior is actually broken

---

## Harness entry

Primary file:
```
project_sources/collector/harness/run_DCOIR_Tests.ps1
```

Key parameters:

| Parameter | Purpose |
|----------|--------|
| `-Suite` | Select validation surface |
| `-CollectorPath` | Runtime under test (PS1 or EXE) |
| `-MasterZipPath` | Restaging source |
| `-OutputRoot` | Evidence location |
| `-SkipCleanup` | Preserve artifacts |

---

## GitHub Actions validation lanes

| Workflow | Role | Trigger model |
| --- | --- | --- |
| `.github/workflows/validate-on-push.yml` | Targeted automatic Core gate for maintained collector, Gemini, validation, knowledge, and workflow surfaces | `push` path filters plus manual dispatch |
| `.github/workflows/manual-full-validation.yml` | Deeper operator-selected regression lane | Manual dispatch |
| `.github/workflows/manual-gemini-bundle-build.yml` | Gemini bundle build and attachment validation | Manual dispatch |
| `.github/workflows/manual-collector-optional-exe-build.yml` | Optional EXE build and selected validation lane | Manual dispatch |

Automatic validation proves the watched surfaces still satisfy the targeted Core gate. It does not replace a deliberate manual full-regression run when the change affects deeper runtime behavior.

---

## Suite intent (non-duplicated)

| Suite | What it proves |
|------|---------------|
| Core | Baseline functionality |
| Retrieval | Artifact movement |
| QuickAliases | Shortcut correctness |
| SessionBehavior | Enrich lifecycle |
| TargetedCollection | Targeted output correctness |
| Chunking* | Large artifact handling |
| FailureGates | Negative-path behavior |
| FullRegression | Combined confidence |

---

## EXE-specific validation rule

For FailureGates and FullRegression:

- PS1 mode → strict failure expectations
- EXE mode → allow wrapper-limited behavior

Valid EXE outcomes may include:
- missing native bind-reject text
- exit code differences

Invalid EXE outcomes:
- incorrect output contract
- missing required artifacts
- incorrect functional behavior

---

## Restaging rule

Each run must:
- start from a clean runtime state
- avoid artifact contamination

If results differ across runs:
- verify restaging before investigating logic

---

## Manual validation pattern (condensed)

1. Define objective from the governed issue, validation rule, or Supabase `ircore` test/readback record
2. Run one bounded command
3. Verify output contract
4. Verify artifacts exist
5. Apply validator if needed
6. Record result honestly

---

## Output contract focus

Always verify:

- `STATUS`
- `RUN_ID`
- artifact paths
- next-step guidance

Console output alone is not sufficient.

---

## Common failure misinterpretations

| Symptom | Likely cause |
|--------|-------------|
| Missing bind error (EXE) | Wrapper limitation |
| Inconsistent results | No restaging |
| Pass without artifacts | Misread output |
| Packaging success | Not runtime proof |

---

## Operator discipline

After every run ask:

1. What did this prove?
2. What did it not prove?
3. What artifact matters next?
4. What is the next bounded step?

---

## Relationship to other docs

- EXE behavior → Knowledge - Collector - EXE Usage and Runtime Behavior
- Features/contract → Knowledge - Collector - Feature and Output Contract Reference
- Troubleshooting → Knowledge - Core - Troubleshooting

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.
<!-- DCOIR_SOURCE_END {"id":"knowledge.collector.local_test","sha256":"b9429d3382d91ffd2916a70b7f76e08e4b67b85398b7107ea24e1bae63f3daf3"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":13007,"git_blob_sha":"1619a2ec86e347ed668f8258794a8ebef1c36212","id":"knowledge.core.enrichment_actions","path":"knowledge/Knowledge - Core - Enrichment Actions.md","sha256":"e9d0e2f3744c4d21806d875f9ac9ef7cfa28116bd136547d2fab854990edeb01"} -->
# Knowledge - Core - Enrichment Actions

_One-bounded-question-at-a-time enrichment and retrieval-oriented follow-up_

**Summary:** Use enrichment after baseline or artifact review identifies one bounded follow-up question. Enrichment is session-based and intentionally narrow so the reason for each action remains clear.

---

## What enrichment is for

Enrichment exists for the moment when broad collection has already identified the next question.

Examples:

- Which DLLs were loaded by this suspicious process?
- Is this file signed and what hash does it have?
- Which strings does this script or binary expose?
- Should I export the raw EVTX instead of relying on text-form event output?
- Should I stage this task XML, service binary, or referenced script for offline review?

Enrichment should answer one bounded follow-up question at a time.
It is not a second baseline collection path.

---

## Enrichment rule

Run one enrichment action at a time.

Each action should answer a specific question such as:

- What process, connection, service, task, registry path, log, or file needs more evidence?
- Is the next step review, retrieval, another related enrichment, or stop?

Do not stack unrelated actions into one session.
A session is for one investigative thread, not for every open question on the host.

---

## Session lifecycle

The collector's enrich behavior is session-based.
That matters for operator use because one session can remain open across closely related actions.

| Phase | Purpose |
| --- | --- |
| Start | Begin a new bounded enrichment session |
| Add | Add one closely related action to the same session |
| Finalize | Close and package the session |
| Cleanup | Remove runtime/output material only after evidence is safe |

Finalize and cleanup are not interchangeable.

### Source-backed session behavior

The current source supports these bounded statements:

- `enrich-start` style paths create a new session;
- `enrich-add` style paths reuse the current open session unless explicitly overridden;
- explicit session targeting can be done with `-EnrichSessionId`;
- a finalized requested session cannot be appended to;
- `enrich-finalize` finalizes the current open session or a valid non-finalized requested session and produces a bundle;
- `enrich-finalize` without an open or requested non-finalized session is rejected instead of creating an empty bundle.

---

## Session controls

| Parameter | Purpose |
| --- | --- |
| `-EnrichSessionId` | Continue or target a specific existing session |
| `-NewEnrichSession` | Force a new session |
| `-FinalizeEnrichSession` | Finalize the current or targeted session |
| `-Action` | Choose the enrich action |

Use one session for one closely related investigative thread.
Do not create a new session when the current open one already owns the question, and do not keep extending a session when it is time to finalize and review.

---

## Review-style versus retrieval-style enrichment

This distinction matters for interpretation.

| Action type | Purpose |
| --- | --- |
| Review-style action | Produce an action artifact that helps answer the next question directly |
| Retrieval-style action | Stage or export a concrete evidence carrier for offline review |

Do not flatten these into one review model.
Some enrich actions primarily answer the question in place.
Others primarily hand you the next file or EVTX to retrieve.

---

## Review-style enrich actions actually exposed by source

| Action | Typical use |
| --- | --- |
| `SigcheckPath` | Review signer, hashes, and version data for a suspicious path |
| `ListDllsPid` | Review loaded modules for a suspicious process |
| `AccessChkFile` | Review effective access for a file or directory |
| `AccessChkService` | Review effective access for a service |
| `AccessChkReg` | Review effective access for a registry path |
| `StringsPath` | Extract readable strings from a suspicious file |
| `StreamsPath` | Review alternate data streams |
| `TcpvconRefresh` | Refresh command-line TCP view for network review |
| `LogText` | Export text-form event evidence |

### Typical parameter families for review-style actions

| Parameter family | Common actions |
| --- | --- |
| `-Path` | signature, strings, streams, file review |
| `-TargetPid` | loaded-module review |
| `-ServiceName` | service access review |
| `-RegistryPath` | registry access review |
| `-LogName` | log text export |
| `-EventId` | narrower event selection |
| `-MaxEvents` | bounded event count |

---

## Retrieval-style enrich actions actually exposed by source

| Action | Typical use |
| --- | --- |
| `LogRaw` | Export raw EVTX for workstation review |
| `PullSuspiciousFile` | Stage a suspicious file for retrieval |
| `PullScriptOrConfig` | Stage a script or config file for retrieval |
| `PullTaskXml` | Export scheduled task XML |
| `PullServiceBinary` | Stage the binary referenced by a service |
| `PullWmiReferencedFile` | Stage a file referenced by suspicious WMI persistence |

### Typical parameter families for retrieval-style actions

| Parameter family | Common actions |
| --- | --- |
| `-Path` | suspicious file, script/config, task-name-as-path, WMI-referenced file |
| `-ServiceName` | service-binary retrieval |
| `-LogName` | raw EVTX export |
| `-EventId` | narrower event selection |
| `-Hours` | time window for event export |

Prefer retrieval when the decisive next evidence carrier is already known.
If you already know the suspicious file, script, service binary, or task definition you need, retrieval is often better than another broader collection step.

---

## Quick aliases accepted by source

Quick aliases are the safest way to avoid unsupported command shapes when one of the source-backed paths matches the question. Each `enrich-start-*` alias starts a new enrich session for that action. The matching `enrich-add-*` alias adds the same action to the currently open session or to the explicit non-finalized session supplied with `-EnrichSessionId`.

For quick aliases that need a value, pass the value with `-Target`. The collector maps that target into the action-specific parameter family. Use explicit `-Mode Enrich -Action ...` parameters when you need to set more specific fields such as `-EventId`, `-MaxEvents`, `-WindowStart`, or `-WindowEnd`.

| Quick alias family | Action | Required target |
| --- | --- | --- |
| `enrich-start-tcp`, `enrich-add-tcp` | Refresh TCP connection evidence | None |
| `enrich-start-logtext`, `enrich-add-logtext` | Export event log text | Optional `-Target <log name>`; defaults to Security |
| `enrich-start-lograw`, `enrich-add-lograw` | Export raw EVTX log data | Optional `-Target <log name>`; defaults to Security |
| `enrich-start-sigcheck`, `enrich-add-sigcheck` | Run signature/hash review for a path | `-Target <path>` |
| `enrich-start-listdlls`, `enrich-add-listdlls` | Review loaded modules for a PID | `-Target <pid>` |
| `enrich-start-access-file`, `enrich-add-access-file` | Run access-check review for a file path | `-Target <path>` |
| `enrich-start-access-service`, `enrich-add-access-service` | Run access-check review for a service | `-Target <service name>` |
| `enrich-start-access-reg`, `enrich-add-access-reg` | Run access-check review for a registry path | `-Target <registry path>` |
| `enrich-start-strings`, `enrich-add-strings` | Extract strings from a path | `-Target <path>` |
| `enrich-start-streams`, `enrich-add-streams` | Check alternate data streams for a path | `-Target <path>` |
| `enrich-start-pull-file`, `enrich-add-pull-file` | Retrieve a suspicious file | `-Target <path>` |
| `enrich-start-pull-script`, `enrich-add-pull-script` | Retrieve a suspicious script or config file | `-Target <path>` |
| `enrich-start-pull-task`, `enrich-add-pull-task` | Retrieve scheduled task XML | `-Target <task path>` |
| `enrich-start-pull-service`, `enrich-add-pull-service` | Retrieve a service binary | `-Target <service name>` |
| `enrich-start-pull-wmi-file`, `enrich-add-pull-wmi-file` | Retrieve a file referenced by WMI persistence evidence | `-Target <path>` |
| `enrich-finalize` | Finalize and bundle the current open enrich session, or the explicit non-finalized session supplied with `-EnrichSessionId` | None unless finalizing an explicit session |

### Common quick-alias examples

| Question | Example command shape |
| --- | --- |
| Start a TCP follow-up session | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\DCOIR_Collector.ps1 -Quick enrich-start-tcp` |
| Add log-text review to the open session | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\DCOIR_Collector.ps1 -Quick enrich-add-logtext -Target Security` |
| Start file signature review | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\DCOIR_Collector.ps1 -Quick enrich-start-sigcheck -Target C:\Path\To\File.exe` |
| Stage a service binary for retrieval | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\DCOIR_Collector.ps1 -Quick enrich-start-pull-service -Target SuspiciousService` |
| Finalize the current open session | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\DCOIR_Collector.ps1 -Quick enrich-finalize` |

These matter because operators and Gemini should prefer supported quick paths instead of inventing unsupported command shapes.

---

## Before enrichment

Confirm:

- the prior finding that justifies enrichment;
- the narrow question the enrich action is supposed to answer;
- whether the best next step is review-style or retrieval-style;
- whether an existing artifact should be retrieved first;
- whether the current session should be extended or finalized;
- whether cleanup would remove still-needed evidence.

A good enrich action begins from a specific question, not a desire to "look deeper" in general.

---

## What enrich output actually gives the operator

Important enrich output surfaces visible in current source include:

- `STATUS`
- `RUN_ID`
- `COLLECTOR_VERSION`
- `COLLECTOR_BUILD_IDENTITY`
- `ENRICH_SESSION_ID`
- `SESSION_RESOLUTION_MODE`
- `ENRICH_REPORT_PATH`
- optional `ACTION_ARTIFACT_PATH` when an enrich action ran
- optional `STAGED_PATH`
- `SESSION_STATUS`
- optional `ENRICH_BUNDLE_PATH`
- `NEXT_GET_FILE` when finalized
- `DELETE_SCRIPT_COMMAND`

A finalize-only path is still a normal enrich outcome when it closes an existing open session or a valid non-finalized requested session.
When the operator runs `enrich-finalize` without a new action, the current source emits the session report and finalization surfaces without `ACTION_ARTIFACT_PATH`; if no open or requested non-finalized session exists, the collector rejects the command so operators do not receive an empty finalized bundle.

### Practical enrich review order

1. `ENRICH_REPORT_PATH`
2. optional `ACTION_ARTIFACT_PATH` when an action ran
3. `SESSION_RESOLUTION_MODE`
4. `SESSION_STATUS`
5. optional `STAGED_PATH` when retrieval occurred
6. optional `ENRICH_BUNDLE_PATH` after finalization

Review-style actions often answer the next question in the action artifact.
Retrieval-style actions often exist to give you the next evidence carrier to inspect offline.

---

## Output interpretation

An enrichment result may provide:

- direct evidence;
- session/workflow state;
- a candidate path for retrieval;
- a reason to stop;
- a reason to run one more closely related bounded action in the same session.

It is not automatically a final verdict.

---

## Retrieval preference

Prefer retrieval when the collector or prior review already identified a specific evidence carrier.

Retrieval is usually better than another broad collection when the question is about:

- one known file;
- one known script or config;
- one task definition;
- one service binary;
- one raw event-log export for workstation review.

---

## Common mistakes

- running multiple unrelated enrichments in one session;
- starting a new session when the current one should be extended;
- extending a session that should be finalized;
- trying to append to a session that has already been finalized;
- treating a rejected finalize-without-open command as a collector failure instead of a guardrail;
- using enrichment when retrieval is already the narrower answer;
- cleaning up before outputs are reviewed or retrieved;
- inventing action flags not exposed by the collector;
- treating retrieval-style and review-style actions as if they behave the same way.

---

## Cross-reference boundaries

- Use this page for enrichment workflow, session behavior, action families, and enrich-output interpretation.
- Use `Knowledge - Collector - Feature and Output Contract Reference` for the source-backed collector anchor contract.
- Use `Knowledge - Core - Artifact Review Guide` for review order after enrichment surfaces or staged evidence are produced.
- Use `Knowledge - Collector - EXE Usage and Runtime Behavior` only when EXE-specific wrapper interpretation matters.

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.

<!-- DCOIR_SOURCE_END {"id":"knowledge.core.enrichment_actions","sha256":"e9d0e2f3744c4d21806d875f9ac9ef7cfa28116bd136547d2fab854990edeb01"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":8367,"git_blob_sha":"d9b4b7b5f2983d753795856a324ed923615b8d86","id":"knowledge.core.tier1_runbook","path":"knowledge/Knowledge - Core - Tier 1 Collect Runbook.md","sha256":"4826b5f7ecbcc6615d8ad35522391e91752123be800ace550d259bba6decec74"} -->
# Knowledge - Core - Tier 1 Collect Runbook

_First-pass collection workflow for broad but triage-oriented host evidence_

**Summary:** Use Tier 1 when you need the first broad evidence package for a host, but still want the collector to orient you toward the most useful review surfaces instead of forcing you into raw output immediately.

---

## What Tier 1 is for

Tier 1 is the normal first collect path when:

- current alert or telemetry evidence is not enough by itself;
- you need a baseline host evidence package;
- no narrower enrich or retrieval action is already the clearly better next step;
- the goal is to triage efficiently, not to collect everything possible by default.

Tier 1 is broad, but it is still meant to support decision-making.
It is not proof of maliciousness by itself.

---

## When to use Tier 1

Use Tier 1 when:

- the host needs a first-pass evidence package;
- you need host, process, service, task, registry, network, and event context before choosing a narrower next move;
- the likely next decision is still one of: stop, retrieve, enrich, targeted follow-up, or Tier 2;
- outputs can be preserved long enough for review or retrieval.

Do not run Tier 1 only because the collector is available.
If a known artifact already needs retrieval, retrieval may be the narrower and better next move.

---

## Entry points

| Lane | Command |
| --- | --- |
| Local quick alias | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\DCOIR_Collector.ps1 -Quick collect-t1` |
| Local explicit form | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\DCOIR_Collector.ps1 -Mode Collect -Tier T1 -Hours 24` |
| Elastic endpoint form | `execute --command "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "".\DCOIR_Collector.ps1"" -Quick collect-t1" --comment "Run DCOIR Tier 1 collect"` |

For optional EXE usage, use `Knowledge - Collector - EXE Usage and Runtime Behavior`.
For the source-backed collector contract, use `Knowledge - Collector - Feature and Output Contract Reference`.

---

## Before running

Confirm:

- the investigative question;
- whether the correct lane is endpoint or local;
- whether the staged runtime state is understood;
- whether there are already outputs or retrieved artifacts that should be reviewed first;
- whether output preservation/retrieval needs are understood before any cleanup later.

A good Tier 1 run starts from a named question, not from vague curiosity.

---

## What Tier 1 is intended to collect

Tier 1 is the first-pass baseline evidence layer around:

- host and identity context;
- process and service state;
- scheduled tasks;
- registry and persistence clues;
- network context;
- event-log and Defender-relevant surfaces;
- package metadata and retrieval guidance.

Tier 1 is designed to support triage.
It gives you enough breadth to choose a narrower next step, not to eliminate all uncertainty in one pass.

---

## What Tier 1 actually gives the operator

A successful Tier 1 run emits more than a bundle.
For current source behavior, the important operator-visible surfaces include:

- `STATUS`
- `RUN_ID`
- `METADATA_REPORT_PATH`
- `ANALYST_OVERVIEW_PATH`
- `UPLOAD_SUMMARY_PATH`
- `ATTACHMENT_BUDGET_MANIFEST_PATH`
- optional `UPLOAD_SAFE_CHUNK_MANIFEST_PATH` when oversized full-fidelity text artifacts were chunked
- `COLLECTION_SCOPE_PATH`
- `SECURITY_HIGH_SIGNAL_SUMMARY_PATH`
- `EXECUTION_CONTEXT_PATH`
- `PARALLELISM_ASSESSMENT_PATH`
- optional `TARGETED_COLLECTION_PLAN_PATH` when targeted mode was used
- `COLLECT_BUNDLE_PATH`
- `NEXT_GET_FILE`
- `CLEANUP_COMMAND`
- `DELETE_SCRIPT_COMMAND`

Treat these as distinct surfaces with different jobs, not as duplicate noise.

---

## First review order for Tier 1

For the current build, use this review order:

1. `ANALYST_OVERVIEW_PATH`
2. `UPLOAD_SUMMARY_PATH`
3. `METADATA_REPORT_PATH`
4. `ATTACHMENT_BUDGET_MANIFEST_PATH`
5. optional `UPLOAD_SAFE_CHUNK_MANIFEST_PATH` when full-fidelity text chunks are present
6. `COLLECTION_SCOPE_PATH`
7. `SECURITY_HIGH_SIGNAL_SUMMARY_PATH`
8. `EXECUTION_CONTEXT_PATH` when elevation/visibility affects interpretation
9. representative high-signal artifacts referenced by the above surfaces
10. upload-safe full-fidelity chunks only when the summary is insufficient
11. broader flat output or the bundle only after the first-pass question is clearer

Avoid jumping directly into raw files before reading the orientation surfaces.

---

## What to decide after Tier 1

Tier 1 should help you choose one of these next moves:

- stop because the current question is answered;
- retrieve a specific evidence carrier;
- run one bounded enrich action;
- run a targeted follow-up collection path;
- escalate to Tier 2 because a specific deeper question remains.

A good Tier 1 outcome is not "more files."
A good Tier 1 outcome is a clearer next move.

---

## Repeated Tier 1 runs

Before rerunning Tier 1:

- identify what the prior run did not answer;
- check whether the needed artifact already exists;
- review whether targeted follow-up or enrichment would now be narrower;
- verify staged runtime state;
- re-stage when runtime state is uncertain;
- avoid cleanup until evidence is safe.

Do not rerun Tier 1 as a reflex when a narrower step would answer the question faster.

---

## Targeted follow-through from Tier 1

Tier 1 can justify targeted follow-up, retrieval, enrichment, or Tier 2.

Important boundary:

- targeted mode is real and useful;
- it narrows guidance, scope intent, artifact prioritization, and recommended next actions;
- it should not be described as universal exact filtering across all artifact families unless that narrower claim is specifically validated.

Use targeted follow-through when the incident is now narrow enough that a profile, time window, user report, process, path, or indicator can focus the next step.

---

## Large-output boundary

The current collector can create upload-safe chunk companions for oversized real human-readable artifacts such as full-fidelity event text, and it reports those companions through `UPLOAD_SAFE_CHUNK_MANIFEST_PATH` when they exist.

Use the chunk manifest when the summary points to a large source artifact that still needs full-fidelity review:

1. read `UPLOAD_SUMMARY_PATH` to see whether chunk companions were recommended;
2. read `UPLOAD_SAFE_CHUNK_MANIFEST_PATH` to identify the original artifact, ordered chunk files, byte counts, and reconstruction metadata;
3. upload or review the ordered chunk companions only when the high-signal summary is not enough;
4. keep the manifest with the chunks so the reviewer can reconstruct or reason about the original artifact.

This production chunking support is not a promise that every possible large artifact family is chunked. A very large monolithic output outside the supported upload-safe chunk paths should still be treated as a retrieval/review planning or implementation-boundary issue, not automatically as a collector failure.

---

## Common mistakes

- running Tier 1 when retrieval would already answer the question;
- treating baseline breadth as proof of compromise;
- ignoring `ANALYST_OVERVIEW_PATH` and `UPLOAD_SUMMARY_PATH`;
- assuming a merged baseline report is still the primary review surface in the current build;
- cleaning up before retrieval or review;
- jumping to Tier 2 without naming the unresolved question;
- ignoring `UPLOAD_SAFE_CHUNK_MANIFEST_PATH` when the collector reports upload-safe chunks for oversized full-fidelity text;
- assuming every possible large artifact family is chunked.

---

## Completion checklist

- Correct lane used?
- Tier 1 run completed with expected status and run id?
- Analyst overview and upload summary reviewed first?
- Key high-signal artifacts identified?
- Narrowest next move selected: stop, review, retrieval, enrich, targeted follow-up, or Tier 2?

---

## Cross-reference boundaries

- Use this page for Tier 1 procedure and decision framing.
- Use `Knowledge - Collector - Feature and Output Contract Reference` for the source-backed collector contract.
- Use `Knowledge - Core - Artifact Review Guide` for evidence-review order and upload priority.
- Use `Knowledge - Collector - EXE Usage and Runtime Behavior` only when EXE-specific wrapper interpretation matters.

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.

<!-- DCOIR_SOURCE_END {"id":"knowledge.core.tier1_runbook","sha256":"4826b5f7ecbcc6615d8ad35522391e91752123be800ace550d259bba6decec74"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":7710,"git_blob_sha":"283d47ff789c0fa3bb1678e2e6350b32f01a3876","id":"knowledge.core.tier2_runbook","path":"knowledge/Knowledge - Core - Tier 2 Collect Runbook.md","sha256":"b4de59f8ca569a00021666e6722a078a2d4da9afb1069901d499d2da3ac810d2"} -->
# Knowledge - Core - Tier 2 Collect Runbook

_Deeper collection workflow for persistence, configuration, and follow-on context after Tier 1_

**Summary:** Use Tier 2 only when Tier 1 or current evidence leaves a specific unresolved question that needs deeper host context. Tier 2 is not a generic “do more” button.

---

## What Tier 2 is for

Tier 2 exists for the moment when Tier 1 has already done its job and the next question is now more specific.

Examples:

- Is this persistence-looking surface merely present, or does it need deeper host context?
- Which registry or WMI persistence details matter enough to justify artifact retrieval?
- Do deeper configuration surfaces support or weaken the leading theory?

Use Tier 2 to answer a deeper question that has already been named.
Do not use it as a substitute for reviewing Tier 1 properly.

---

## When to use Tier 2

Use Tier 2 when:

- Tier 1 exposed persistence, service, task, registry, WMI, identity, firewall, share, or session questions;
- the next question needs deeper host configuration context;
- retrieval or a single enrichment action is not already the narrower answer;
- broader context is still required before choosing the next retrieval or enrichment move.

Do not use Tier 2 as a generic escalation path just because Tier 1 produced a lot of output.

---

## Entry points

| Lane | Command |
| --- | --- |
| Local quick alias | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\DCOIR_Collector.ps1 -Quick collect-t2` |
| Local explicit form | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\DCOIR_Collector.ps1 -Mode Collect -Tier T2 -Hours 72` |
| Bounded validation form | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\DCOIR_Collector.ps1 -Mode Collect -Tier T2 -Hours 1 -MaxEvents 100` |
| Elastic endpoint form | `execute --command "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "".\DCOIR_Collector.ps1"" -Quick collect-t2" --comment "Run DCOIR Tier 2 collect"` |

For optional EXE usage, use `Knowledge - Collector - EXE Usage and Runtime Behavior`.
For the broader source-backed contract, use `Knowledge - Collector - Feature and Output Contract Reference`.

---

## Bounded Tier 2 validation shape

The maintained regression harness uses a runner-safe Tier 2 shape: `-Tier T2 -Hours 1 -MaxEvents 100`.

That validation shape proves three operator-relevant facts when FullRegression passes:

- the collector accepts the Tier 2 path without relying on an unbounded time window;
- collection metadata records `Tier=T2`, `Hours=1`, and `MaxEvents=100`;
- the bundle contains the Tier 2 deep-check artifacts under `TIER2_DEEP_CHECKS`, including IFEO, Winlogon, LSA, WMI persistence, network share/session, and firewall profile outputs.

For live operations, choose a wider `-Hours` value only when the case needs it. Keep `-MaxEvents` bounded when event volume or upload budget matters.

---

## What Tier 2 adds

Tier 2 adds deeper context around:

- registry persistence, including IFEO, Winlogon, and LSA-related paths;
- WMI subscription and persistence surfaces;
- network share and session context;
- firewall profile context;
- a longer time horizon than Tier 1.

Think of Tier 2 as the deeper context layer that helps explain suspicious host state after the first broad pass.

---

## Before running

Confirm:

- the exact Tier 1 or alert finding that justifies deeper collection;
- which deeper evidence class is expected to answer the question;
- whether retrieval or enrichment would answer it faster;
- whether targeted follow-up would now be narrower than another broad collect run;
- the correct execution lane;
- output preservation needs.

If you cannot name the unresolved question, Tier 2 is probably not the right next move yet.

---

## What Tier 2 actually gives the operator

Tier 2 is still a collect-mode run, so many of the same operator-visible surfaces still matter:

- `STATUS`
- `RUN_ID`
- `METADATA_REPORT_PATH` including `Tier`, `Hours`, and `MaxEvents` values
- `ANALYST_OVERVIEW_PATH`
- `UPLOAD_SUMMARY_PATH`
- `ATTACHMENT_BUDGET_MANIFEST_PATH`
- optional `UPLOAD_SAFE_CHUNK_MANIFEST_PATH` when oversized full-fidelity text artifacts were chunked
- `COLLECTION_SCOPE_PATH`
- `SECURITY_HIGH_SIGNAL_SUMMARY_PATH`
- `EXECUTION_CONTEXT_PATH`
- `PARALLELISM_ASSESSMENT_PATH`
- `COLLECT_BUNDLE_PATH`
- `NEXT_GET_FILE`
- `CLEANUP_COMMAND`
- `DELETE_SCRIPT_COMMAND`

Even in Tier 2, do not skip the orientation surfaces just because the run is “deeper.”

---

## How to read Tier 2 output

Read Tier 2 as deeper context, not as automatic escalation or proof.

Ask:

- Which deeper surface produced a meaningful signal?
- Did it support or weaken the leading explanation?
- Does it justify retrieval, enrichment, targeted follow-up, broader artifact review, or stopping?
- Is the finding evidence of use, or only evidence that a mechanism exists?

Tier 2 becomes useful when it narrows the next move, not when it simply adds volume.

---

## Practical first review order for Tier 2

Use this order for the current build:

1. `ANALYST_OVERVIEW_PATH`
2. `UPLOAD_SUMMARY_PATH`
3. `METADATA_REPORT_PATH`
4. `ATTACHMENT_BUDGET_MANIFEST_PATH`
5. optional `UPLOAD_SAFE_CHUNK_MANIFEST_PATH` when full-fidelity text chunks are present
6. `COLLECTION_SCOPE_PATH`
7. `SECURITY_HIGH_SIGNAL_SUMMARY_PATH`
8. Tier 2 deep-check artifacts under `TIER2_DEEP_CHECKS` when present: IFEO, Winlogon, LSA, WMI persistence, network share/session, and firewall profile outputs
9. upload-safe full-fidelity chunks only when the summary is insufficient
10. broader local output only after the deeper question is more clearly framed

If the run was launched to answer a narrow persistence or WMI question, prioritize the artifacts that most directly support that question instead of reading all deeper output uniformly.

---

## When Tier 2 should lead to retrieval or enrichment

Tier 2 should often end by identifying one narrower next move.

Common patterns:

- suspicious service path found -> retrieve service binary
- suspicious scheduled task action found -> retrieve task XML or referenced script/binary
- suspicious WMI persistence reference found -> retrieve the referenced file
- suspicious registry/config surface found -> choose the narrow enrich or retrieval action that best answers the next question

Tier 2 is often the bridge between broad baseline context and a specific evidence carrier.

---

## Common Tier 2 mistakes

- running Tier 2 before reading Tier 1 properly;
- treating persistence-capable configuration as proof of malicious use;
- using Tier 2 when one specific artifact should simply be retrieved;
- using Tier 2 as a substitute for naming the unresolved question;
- cleaning up before reviewing deeper outputs and preserving needed evidence;
- widening the review before the highest-value deeper surface is read.

---

## Completion checklist

- Driving finding named?
- Deeper evidence class identified?
- Analyst overview and orientation surfaces reviewed first?
- Tier 2 output reviewed against the specific question?
- Next move selected: retrieval, enrich, targeted follow-up, broader review, stop, or additional collection?

---

## Cross-reference boundaries

- Use this page for Tier 2 procedure and deeper-question framing.
- Use `Knowledge - Collector - Feature and Output Contract Reference` for the source-backed collector contract.
- Use `Knowledge - Core - Artifact Review Guide` for review order and evidence-carrier priority.
- Use `Knowledge - Collector - EXE Usage and Runtime Behavior` only when EXE-specific wrapper interpretation matters.

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.

<!-- DCOIR_SOURCE_END {"id":"knowledge.core.tier2_runbook","sha256":"b4de59f8ca569a00021666e6722a078a2d4da9afb1069901d499d2da3ac810d2"} -->

<!-- DCOIR_SOURCE_BEGIN {"bytes":3812,"git_blob_sha":"8b4883b49a38edb484d0d81e5bbb4d5b2db9d0ae","id":"knowledge.core.troubleshooting","path":"knowledge/Knowledge - Core - Troubleshooting.md","sha256":"3c71d9e59650e987f478fd757c67e5e7332c19dc9f2c7be0477eb2ce8a2e6921"} -->
# Knowledge - Core - Troubleshooting

_Common DCOIR execution, packaging, validation, and interpretation failures_

**Summary:** Use this page to separate lane mistakes, staging problems, packaging issues, wrapper limitations, and real collector defects.

---

## First checks

Before editing source or rerunning broad validation, confirm:

- execution lane: Elastic endpoint, local workstation, GitHub Actions, PS1, or EXE;
- runtime path and filename;
- staged package or asset state;
- current branch/ref used by GitHub Actions;
- whether output already exists and should be reviewed or retrieved;
- whether the symptom is build, packaging, runtime, harness, or interpretation.

---

## Lane mixing

| Symptom | Check |
| --- | --- |
| Local command fails in Elastic | Missing `execute --command` wrapper or quoting issue |
| Endpoint command pasted locally | Response-action syntax used in wrong lane |
| Valid command gives unexpected context | Wrong runtime path or working directory |

Use Knowledge - Core - Elastic Quick Start for endpoint command syntax.

---

## Local regression path failures

Check:

- `run_DCOIR_Tests.ps1` is the harness being used;
- `DCOIR_Collector.ps1` or EXE path exists at `-CollectorPath`;
- master ZIP exists at `-MasterZipPath`;
- current directory matches the command examples;
- PowerShell 5.1 compatibility is preserved.

---

## EXE-specific failures

The optional EXE can differ from PS1 in native PowerShell diagnostic behavior.

Expected EXE differences may include:

- missing native bind-reject text;
- different exit-code behavior;
- wrapper-limited failure output.

Do not treat those as collector defects unless the output contract, artifact creation, or functional behavior is wrong. Use Knowledge - Collector - EXE Usage and Runtime Behavior for EXE-specific interpretation.

---

## Repeated collect runs

Before rerunning collection:

- review or retrieve existing output first;
- verify staging state;
- re-stage when uncertain;
- name the new question the rerun must answer.

---

## Targeted collection expectations

Targeted mode narrows intent and output emphasis. Do not claim exact filtering unless that specific path has validated exact filtering behavior.

If targeted output is broader than expected, decide whether this is:

- documentation/expectation drift;
- a validated limitation;
- or a new implementation requirement.

---

## Large output and chunking

Synthetic chunking reconstruction is validated for the regression fixture. That does not prove every real large output chunks automatically.

Treat large monolithic live output as a retrieval/review or implementation-boundary issue unless exact live chunking has been validated.

---

## Packaging and bundle issues

Common causes:

- wrong source treated as authoritative;
- manifest/map not updated with new files;
- generated attachment edited instead of maintained source;
- retained ZIP read as current source;
- workflow required-surface checks not updated.

---

## Troubleshooting pattern

1. State the symptom.
2. Identify the lane.
3. Identify failure stage: build, packaging, execution, validation, or interpretation.
4. Check source and staging assumptions.
5. Apply the narrowest fix.
6. Validate the specific behavior before broad regression.

---

## Cross-reference boundaries

- Use this page for failure classification and recovery patterns.
- Use Knowledge - Collector - Local Test and Regression for validation-lane selection and harness interpretation.
- Use Knowledge - Collector - EXE Usage and Runtime Behavior for EXE-specific wrapper limitations.
- Use Knowledge - Collector - Feature and Output Contract Reference for collector feature and output-contract expectations.

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.

<!-- DCOIR_SOURCE_END {"id":"knowledge.core.troubleshooting","sha256":"3c71d9e59650e987f478fd757c67e5e7332c19dc9f2c7be0477eb2ce8a2e6921"} -->

