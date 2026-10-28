# Pull-request validation lifecycle (#557)

This page documents the first staged-validation increment and its remaining
work. It is not a claim that every repository workflow has been migrated.

## Stage mapping

| State | Expected behavior | Current scope |
| --- | --- | --- |
| Draft created or updated | Run cheap deterministic rejection checks before heavier work | Pull Request Validation runs the Linux draft_fail_fast job; its Windows validate job is skipped on Draft |
| Ready for review or updated non-Draft | Run the fast gate first and then the existing full validation on the current head | ready_for_review, opened, reopened, and synchronize trigger the original workflow; validate / validate keeps its historical check identity |
| Converted back to Draft | Cancel/supersede in-flight PR validation and return to cheap checks | converted_to_draft shares the existing per-PR concurrency group with cancel-in-progress=true |
| Merge decision | Verify the latest head, required checks, and operator-approved independent review | Manual governed gate; no reviewer is auto-requested |
| Post-merge | Read back merged main SHA and authoritative push checks | Existing push workflows are unchanged in this increment |

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

## Current boundaries

- The validate-on-push.yml workflow has broad push path filters but no main-only
  branch filter. Full push validation can therefore run on feature branches,
  including Draft development. The first increment does not deliver total
  Draft-cost savings. Constraining that trigger is deferred until the
  authoritative required-check/branch-protection set can be verified.
- Other PR workflows (Windows PowerShell 5.1, CodeQL, Gemini replay/harness,
  documentation, dependency review, audit) are not migrated to the
  staged design. Always-required security checks need explicit disposition.
- Classic GitHub branch-protection required-check configuration returned 403
  through the current integration. Do not remove or rename current contexts
  based only on ruleset metadata.
- The actual dependency scanner runs only when ENABLE_DEPENDENCY_REVIEW=true.
  A successful disabled-notice job is not dependency scanning.
- Issue #528's successful-harness/failed-report-push conflict remains to be
  reproduced and repaired separately. The first increment does not change
  Invoke-ChatGptReportPush.ps1, RequirePush, reporting, or cleanup behavior.
- Independent reviewer requests remain operator-controlled. DCOIR Review may
  not review itself. Review/merge decisions require current-head evidence.
- Local syntax, static contracts, and simulated event cases cannot prove
  actual GitHub event/cancellation or Windows runtime behavior.

## Regression and next increments

The source-level lifecycle regression is
.github/github_actions/tools/test_pr_validation_lifecycle.py, executed by
.github/github_actions/tools/run_pr_draft_fail_fast.py. It tests event
coverage, Draft/Ready job guards, prerequisite gating, manual dispatch,
cancellation, and negative controls that remove guards. It also tests
malformed Python, missing source files, and compiling without executing code.

Before changing broad push triggers or required check contexts, obtain
authoritative branch-protection evidence. Then stage remaining PR validation
and security workflows without weakening required checks, with current-SHA
artifact receipts and cancellation tests. Finally reproduce and fix the #528
same-request report conflict with a disposable remote, preserving progress
history, request cleanup, and RequirePush semantics.

See Issue #557 for all acceptance criteria. DCOIR Review source
consolidation remains a separate responsibility under #550.
