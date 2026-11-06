# Pull-request validation lifecycle (#557)

This page documents the first staged-validation increment and its remaining
work. It is not a claim that every repository workflow has been migrated.

## Stage mapping

| State | Expected behavior | Current scope |
| --- | --- | --- |
| Draft created or updated | Run cheap deterministic rejection checks before heavier work | Pull Request Validation runs the Linux draft_fail_fast job; its Windows validate job is skipped on Draft |
| Draft review and fix loop | Complete code review and fixes while the PR remains Draft, before Ready-stage heavy validation | Internal adversarial review plus operator-approved/manually triggered independent reviews; only fast scoped tests are the default after Draft fixes |
| Ready for review or updated non-Draft | Run the fast gate first and then the existing full validation on the current head | ready_for_review, opened, reopened, and synchronize trigger the original workflow; validate / validate keeps its historical check identity |
| Converted back to Draft | Cancel/supersede in-flight PR validation and return to cheap checks | converted_to_draft shares the existing per-PR concurrency group with cancel-in-progress=true |
| Merge decision | Verify the latest head, required checks, and operator-approved independent review | Manual governed gate; no reviewer is auto-requested |
| Post-merge | Read back merged main SHA and authoritative push checks | Main-only automatic push validation still runs on relevant merged main commits; manual feature-branch dispatch remains available |

The draft_fail_fast job checks all tracked Python syntax without executing
source, verifies workflow modularization contracts, and runs a lifecycle
event/guard regression suite. Permissions are contents:read on Ubuntu. The
existing validate reusable workflow depends on that job. On non-Draft PRs or
trusted default-branch manual dispatch, a failed fast gate forces
validate / validate to fail, not silently skip. This prevents a failed cheap
check from being accepted via a permissive skipped-check merge rule.

A trusted default-branch workflow_dispatch remains a review-context baseline,
not exact evidence for a feature-branch or PR head. Heavy Windows/PowerShell
coverage and collector harness checks remain in the existing validation job.

## Review and fix before Ready (operator directive 2026-11-06)

The default sequence is **Draft implementation -> cheap fail-fast checks -> internal
adversarial review -> operator-approved or manually triggered independent review
and fix loop on Draft -> current-head review/readback -> separately approved Ready
transition -> full Ready validation -> separately approved merge**.

During Draft, the implementation/fix owner handles findings, runs targeted
inexpensive tests, resolves actionable review threads, verifies the actual file
scope against the PR description, and records the reviewed head SHA. Request
Copilot review during Draft only when the operator explicitly approves or
manually triggers it. Other independent reviewers and paid review commands
remain subject to their existing per-invocation approvals or opt-outs. The
objective is to avoid waiting until expensive Ready checks have started to
discover straightforward review defects. A reviewer request is **not** an
automatic side effect of opening a PR or moving it to Ready.

Mark Ready only after relevant Draft checks are green on the current head,
review findings are dispositioned (or an operator-approved exception is
recorded), no actionable review threads remain unresolved, and the operator
explicitly approves the state change. Ready triggers required full PR/Windows
checks and security checks on that exact head. Do **not** request another
code review just because Ready validation finished if the reviewed head and
scope have not changed. If the Ready checks reveal a defect or the head
changes materially, requalify the affected code and checks, preferably using
an operator-approved transition back to Draft for substantive fixes.
Merging and closing the issue remain separate approval gates.

## Current boundaries

- The follow-on #649 cost staging restricts automatic `validate-on-push.yml`
  pushes to `main` without changing its path filters, workflow_dispatch,
  reusable call, job identity, or post-merge validation. Branches under
  development rely on Draft PR fail-fast and Ready exact-head full PR checks;
  operator-selected feature-branch smoke testing remains available manually.
  A missing Main Push check on a feature SHA must not be presented as a pass.
- To keep pre-merge coverage equal, the Ready `validate` job in
  `reusable-validate-on-pr.yml` now also runs the collector runtime package
  smoke build (`smoke-build-collector-package`), which previously ran only in
  push validation.
- Main Push concurrency gives every `main` push its own per-SHA group with
  `cancel-in-progress` false, so a later merge neither cancels nor replaces
  (while pending) an earlier merge's run, and every merged SHA keeps its own
  post-merge result. Manual feature-ref dispatches still supersede each other. Treat a cancelled or missing post-merge Main Push run
  as missing evidence: re-dispatch it on that SHA, never present it as a pass.
- Reporting impact: `chatgpt-workflow-run-reporter.yml` writes repo-workflows
  reports when `21 Validation - Main Push` completes, so automatic Main Push
  reports now exist only for `main`. Feature, staging, and exec branches get a
  Main Push report only after a manual `workflow_dispatch` on that branch; a
  branch with an open PR can use the validate-on-pr report instead.
- Pre-change protection evidence: Issue #642 records an authenticated empty
  classic required-check list (2026-11-05). As of 2026-11-06 the two active
  default-branch rulesets (14712753, 23701760) have no required-status-check
  rule, and the GitHub branch summary reports required checks off. The detailed
  classic-protection API still returns 403 through the connector. Recheck
  required checks before merging this workflow change if protections drift.
- Other PR workflows (Windows PowerShell 5.1, CodeQL, Gemini replay/harness,
  documentation, dependency review, audit) are not migrated to the
  staged design. Always-required security checks need explicit disposition.
- Classic GitHub branch-protection required-check configuration returned 403
  through the current integration. Do not remove or rename current contexts
  based only on ruleset metadata.
- The actual dependency scanner runs only when ENABLE_DEPENDENCY_REVIEW=true.
  A successful disabled-notice job is not dependency scanning.
- The Issue #528 same-request report-push conflict repair is included in this
  increment. Invoke-ChatGptReportPush.ps1 publishes from the latest main tree,
  preserves caller-staged Apply-In files, checks report-history continuity, and
  fails closed when a concurrently updated report or marker would be replaced
  by older content. A local bare-remote regression suite covers both successful
  sequential phases and a newer concurrent report/marker update.
- The publisher regression is local evidence only; default-branch live
  ChatGPT Exec execution remains outside this increment and is not claimed.
- Independent reviewer requests remain operator-controlled. DCOIR Review may
  not review itself. Review/merge decisions require current-head evidence.
- Local syntax, static contracts, and simulated event cases cannot prove
  actual GitHub event/cancellation or Windows runtime behavior.

## Regression and next increments

The source-level lifecycle regression is
.github/github_actions/tools/test_pr_validation_lifecycle.py, executed by
.github/github_actions/tools/run_pr_draft_fail_fast.py. It includes the Ready
collector package smoke-build guard and tests event
coverage, Draft/Ready job guards, prerequisite gating, manual dispatch,
cancellation, and negative controls that remove guards. It also tests
malformed Python, missing source files, and compiling without executing code.
The #649 main-only push guard is
.github/github_actions/tools/test_main_only_push_trigger.py, also executed by
the Draft fail-fast runner. Its named hostile variants cover unrestricted,
non-main, extra, wildcard, tags, and branches-ignore filters, missing paths or
dispatch, cancelled main runs, and a shared (replaceable) main group.
The Issue #528 publisher regression is
project_sources/collector/tools/test_chatgpt_report_push_rebase.py; it uses a
local bare Git remote and requires PowerShell 7.

Before changing further push triggers or required-check contexts, obtain
authoritative branch-protection evidence. Then stage remaining PR validation
and security workflows without weakening required checks, with current-SHA
artifact receipts and cancellation tests. Validate the publisher repair on the
default branch before claiming live ChatGPT Exec behavior.

See Issue #557 for all acceptance criteria. DCOIR Review source
consolidation remains a separate responsibility under #550.
