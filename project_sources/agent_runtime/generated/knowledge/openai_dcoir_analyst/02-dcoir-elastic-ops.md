# Generated DCOIR Knowledge Projection

> Generated, non-canonical output. Edit the atomic files under knowledge/, then rebuild all affected targets.

- Target: openai_dcoir_analyst
- Projection group: dcoir_elastic_ops
- Purpose: Elastic quick-start operations.
- Source count: 1

<!-- DCOIR_SOURCE_BEGIN {"bytes":3923,"git_blob_sha":"c79e681fc694dfa3cbf19a2d7a0d9d3be765d0c5","id":"knowledge.core.elastic_quick_start","path":"knowledge/Knowledge - Core - Elastic Quick Start.md","sha256":"b6c452839862b1a029318d4e87daa3d88e64938d785913f3b51708abebc6b856"} -->
# Knowledge - Core - Elastic Quick Start

_Endpoint response-console execution versus local workstation execution_

**Summary:** Use this page when running DCOIR through Elastic response actions. It separates endpoint syntax from local PowerShell syntax and keeps collection, enrichment, retrieval, and cleanup actions bounded.

---

## Command-lane rule

| Lane | Use for | Syntax |
| --- | --- | --- |
| Elastic response console | Endpoint-side collector execution | `execute --command "powershell.exe ..." --comment "..."` |
| Local workstation | Repo testing, harness runs, packaging checks | Direct PowerShell command |
| GitHub Actions | Build, validation, and release workflows | Workflow inputs |

Do not paste local commands into the response console without the response-action wrapper. Do not add the response-action wrapper to local workstation commands.

---

## Endpoint command pattern

Use this shape:

```text
execute --command "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "".\DCOIR_Collector.ps1"" <collector args>" --comment "<operator intent>"
```

Keep prose in `--comment`, not inside the PowerShell command body.

---

## Common endpoint actions

| Intent | Example |
| --- | --- |
| Version preflight | `execute --command "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "".\DCOIR_Collector.ps1"" -ShowVersion" --comment "Get DCOIR collector version"` |
| Help | `execute --command "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "".\DCOIR_Collector.ps1"" -ShowHelp" --comment "Show DCOIR collector help"` |
| Tier 1 collect | `execute --command "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "".\DCOIR_Collector.ps1"" -Mode Collect -Tier T1 -Hours 24" --comment "Run DCOIR Tier 1 collect"` |
| TCP enrichment | `execute --command "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "".\DCOIR_Collector.ps1"" -Quick enrich-start-tcp" --comment "Run DCOIR TCP enrichment"` |
| Cleanup | `execute --command "powershell.exe -NoProfile -ExecutionPolicy Bypass -File "".\DCOIR_Collector.ps1"" -Quick cleanup" --comment "Run DCOIR cleanup"` |

---

## Before running on an endpoint

Confirm:

- the collector package is staged on the endpoint;
- the runtime filename matches the command (`DCOIR_Collector.ps1` unless an EXE lane is explicitly being used);
- the action answers a defined investigative question;
- artifacts from a previous run have been retrieved or intentionally left in place;
- cleanup will not remove evidence still needed for review.

---

## EXE note

The optional EXE lane is documented in Knowledge - Collector - EXE Usage and Runtime Behavior. Do not substitute EXE commands into endpoint guidance unless the EXE artifact is the intended staged runtime and the operator has selected that execution form.

---

## Targeted collection boundary

Targeted mode narrows intent and output emphasis. It should not be described as exact filtering unless the specific lane being used has validated exact filtering behavior.

Use targeted collection when:

- the investigative question is narrow;
- a time window or indicator is known;
- the operator needs focused follow-up rather than another broad baseline.

---

## After execution

1. Capture emitted `STATUS`, `RUN_ID`, and artifact paths.
2. Retrieve or review the highest-signal artifact first.
3. Prefer retrieval/review over rerunning collection when the needed artifact already exists.
4. Use one enrichment action at a time.
5. Cleanup only after evidence is safe.

---

## Common mistakes

- mixing endpoint and local command syntax;
- rerunning collection because output was not reviewed;
- treating cleanup as harmless before retrieval;
- interpreting staging or quoting errors as collector logic failures;
- using broad collection when telemetry or a targeted action would answer the question.

---

> Supporting human-readable Knowledge doc. Not part of the DCOIR control plane.

<!-- DCOIR_SOURCE_END {"id":"knowledge.core.elastic_quick_start","sha256":"b6c452839862b1a029318d4e87daa3d88e64938d785913f3b51708abebc6b856"} -->

