---
name: ircore-validation
description: validation and readback helper for ircore work. use for validation-rule lookup, readiness gating, post-change readback discipline, workflow completion evidence, and bounded claim language.
---

# ircore-validation

## Purpose

Use this skill when `ircore` work is about to make, assess, or report a consequential change.

Its job is to:
- identify the relevant validation rule
- enforce readiness and evidence discipline
- require post-change readback before success claims
- distinguish checked facts from unchecked assumptions
- enforce GitHub work-item receipt discipline for governed issue/PR work
- enforce Prog/Adva internal review evidence for non-trivial governed work before readiness, closeability, completion, or external-review claims
- enforce Codi review evidence before external `@codex` requests when PR-related code review is in scope
- enforce operator approval of the exact proposed external `@codex` PR comment text before any such comment is posted or confirmed
- enforce operator approval of the exact proposed `/dcoir-review` command before every invocation or rerun
- keep completion language bounded to the evidence actually available

This skill is not a universal startup helper. Invoke it when validation, readiness, mutation, or completion claims matter.

## When To Use

Use this skill when the task involves:
- mutation of a governed surface
- readiness claims
- closeability claims
- workflow completion claims
- package-validity claims
- install or parity claims
- post-change verification
- direct agent-instruction updates
- governed GitHub issue or PR evidence recording
- Prog/Adva internal review claims, waivers, or evidence gaps
- PR review-gate claims involving Prog, Adva, Codi, `/dcoir-review`, external `@codex`, GitHub Copilot, GitHub Actions, or Supabase receipts
- report-back language such as verified, complete, ready, fixed, successful, or installed

Do not invoke this skill for casual discussion or early brainstorming with no evidence claim attached.

## Validation Order

Before a consequential claim:

1. identify the authority surface
2. identify the task family and mutation class if applicable
3. locate the relevant validation rule or evidence standard
4. determine whether Prog/Adva discipline applies
5. perform the change if one is required and approved
6. perform or read back the Prog implementation/fix pass and Adva adversarial review pass when applicable
7. read back from the governing surface
8. record GitHub work-item receipts when governed issue/PR work is in scope
9. only then make a bounded claim

If evidence is partial:
- say what was checked
- say what was not checked
- state the exact remaining gap

## Authority Model

Use this authority order:

1. Core Agent Instructions for always-on non-negotiable behavior
2. GitHub for canonical source, workflows, procedures, tools, validation playbooks, issues, PRs, branches, workflow runs, and artifacts
3. Supabase schema `ircore` for operational validation rules, routing rules, preferences, live state, workflow/tool catalogs, lessons, and GitHub work-item receipts
4. repository `AGENTS.md` for workspace-local bootstrapping mechanics when it does not contradict core instructions
5. memory folder only for continuity support

Do not let continuity notes or skill wording replace validation evidence from the governing surface.

## Readback Discipline

Readback must come from the authority surface that governs the claim.

Examples:
- source change claim -> read back the changed source or canonical repo surface
- GitHub issue/PR claim -> read back live GitHub issue or PR state and relevant Supabase work-item context
- workflow completion claim -> read back workflow status, run ID, head SHA, job/step status, artifact path, or governed output
- config or routing mutation claim -> read back the governing operational record
- install claim -> confirm the installed artifact is actually present and recognized
- direct agent-instruction update claim -> read back the changed instruction file from GitHub or configured instruction surface and state whether a session restart or reload is still required
- Prog/Adva gate claim -> summarize the implementation/fix scope, adversarial review result, valid findings disposition, and any waiver or unavailable-worker gap
- Codi gate claim -> summarize Codi's latest review result and keep it separate from external `@codex` evidence
- DCOIR Review gate claim -> summarize the exact `/dcoir-review` request text, current-session operator approval for that exact invocation, posted command comment id, reviewed head/run evidence, findings, and any later rerun approval/readback separately
- External `@codex` gate claim -> summarize the exact-text operator approval status, posted comment id if approved and posted, formal response readback, valid finding disposition, and any remaining approval or readback gap
- GitHub Copilot review gate claim -> summarize whether the operator explicitly approved the request or manually triggered it, plus the reviewed head and finding disposition

Do not treat intention, draft text, or an unverified action as proof of completion.

## GitHub Work-Item Receipt Discipline

For governed GitHub issue or PR work in `malwaredevil/dcoir-collector`:
- read live GitHub first
- use `ircore.get_github_work_item_context` when available
- use `ircore.upsert_github_work_item` when creating or refreshing context
- use `ircore.record_github_work_item_readback` when recording evidence
- use `ircore.archive_github_work_item` when retiring a work item
- read back work-item context when evidence affects status, readiness, closure, blocker state, or next action

Do not manually insert, update, or delete rows in `ircore.github_work_items` or `ircore.github_work_item_readbacks` unless the operator explicitly approves emergency repair or test cleanup in the current session.

## PR Review Gate Validation

Resolve the active runtime adapter in `AGENTS.md` before applying PR review gates. When the Codex local-session operator adapter applies, named Prog/Adva/Codi passes, `/dcoir-review`, and external self-invocation are not required. Validate Codex self-review, relevant tests, GitHub/source readback, review-thread disposition, and the retained operator/safety approvals instead. Do not extend this exception to ChatGPT WebUI, connector-only sessions, Replit, Gemini, or other runtimes.

For governed PR readiness:
- Prog and Adva are internal professional review passes.
- Codi must review PR-related code changes before the external `@codex` comment is posted unless the operator explicitly waives Codi for the current task.
- Valid Codi findings must be fixed and re-reviewed until Codi approves, the operator explicitly waives Codi for the current task, or a future durable instruction change removes or changes the Codi requirement.
- Codi review comments related to code review in PRs or issues must have a raw comment body whose first non-blank line starts with `CODI FINDS`, then follow the closest practical `@codex` review/finding format used in this repository.
- Codi approval is internal evidence only and does not replace external `@codex`.
- After Prog/Adva and Codi are clear for a governed PR, the OpenRouter internal review command (`/or-review` or `/dcoir-review`) may be the next review gate when the gate applies and the workflow/script are available on the default branch or an explicitly approved equivalent live-test lane. This sequencing does not authorize the command. Before posting or confirming any `/dcoir-review` command, including standard, `deep`, `diff`, `debug`, or any other current/future variant, draft the exact proposed command text, show it to the operator, and receive explicit operator approval in the current session. No approval means no DCOIR Review request. Approval is per invocation; every rerun or later `/dcoir-review` request requires fresh explicit approval. For PRs that add or change the OpenRouter `issue_comment` workflow/script, branch-only existence is not enough; record the bootstrap gap until default-branch landing or an approved equivalent live-test lane can exercise the changed code. Required readback includes the operator approval evidence, command comment id, eyes reaction lifecycle, workflow/run state, progress/status comment, PR review output, and valid finding disposition.
- If a DCOIR Review finding requires a later rerun, stop after the fix and obtain fresh current-session approval for the exact rerun command before posting it.
- Before posting or confirming any PR comment that invokes the literal `@codex` handle and asks Codex to review, act, fix, patch, implement, update, or otherwise perform PR-related work, draft the exact comment text, show it to the operator, and receive explicit operator approval in the current session. No approval means no post.
- External `@codex` requires a literal `@codex` top-level PR comment, comment-id capture, reaction polling, formal response readback, and finding disposition.
- GitHub Copilot review requests are operator-controlled. Do not request Copilot review unless the operator explicitly approves or manually triggers the review.
- When citing prior Codex evidence in issue, PR, closure, or parent-tracker text, use non-triggering wording such as `External Codex review` unless the operator explicitly approves a live invocation.
- Applicable GitHub Actions validation must be read back by run ID, head SHA, job/step status, and artifacts/reports when available.
- Final readiness evidence should be recorded through `ircore.record_github_work_item_readback` when a governed issue work item exists.

## Bounded Claim Language

Use careful claim language:

- say `updated` only when the change was actually performed
- say `read back` only when the governing surface was checked after the change
- say `verified` only when the relevant validation condition was satisfied
- say `partial` when some evidence exists but an important gap remains
- say `not verified` when readback did not happen

Avoid stronger language than the evidence supports.

## Common Failure Patterns

Check these first:

1. success claimed before readback
2. wrong authority surface used for verification
3. workflow assumed successful without artifact or status readback
4. package assumed valid without install or structure check
5. mutation reported complete even though only draft content exists
6. GitHub work-item gateway functions skipped for governed issue/PR work
7. Prog/Adva skipped when applicable without waiver, unavailable-worker explanation, or not-applicable reason
8. Codi skipped before external `@codex` for PR-related code review when not explicitly waived
9. `/dcoir-review` posted, confirmed, or rerun without operator approval of that exact proposed command in the current session
10. external `@codex` PR comment posted or confirmed without operator approval of the exact proposed comment text in the current session
11. GitHub Copilot review requested without explicit operator approval when the operator did not manually trigger it
12. direct agent-instruction update performed without exact operator approval and post-update GitHub readback

## Output Contract

When used, return:

1. claim or mutation being validated
2. authority surface
3. validation rule or evidence standard applied
4. what was checked
5. what was not checked
6. GitHub work-item receipt status, if applicable
7. Prog/Adva applicability and evidence, or reason not applicable
8. Codi/internal review status, DCOIR Review exact-request approval/readback status, GitHub Copilot approval/manual-trigger status, and external `@codex` exact-text approval status, if applicable
9. pass, partial, gap, failed, stale, or not verified as supported by the governing surface
10. one best next move

## Hard Rules

- do not claim verified, complete, ready, fixed, or successful without evidence
- do not skip readback after mutation
- do not skip GitHub work-item receipt gateways for governed issue/PR work
- do not claim Prog/Adva discipline is complete unless the implementation/fix scope, adversarial review result, and valid finding disposition are stated, or the pass is explicitly waived, unavailable, or not applicable
- do not claim the Codi gate is clear unless Codi was actually asked and approved, the operator explicitly waived Codi for the task, or the Codex local-session operator adapter makes the gate not applicable
- do not post or confirm any `/dcoir-review` command unless the operator approved the exact proposed command in the current session; this applies to every variant and every rerun independently
- do not claim the OpenRouter internal review gate is clear unless the applicable exact-request operator approval, command comment, eyes lifecycle, workflow/run state, PR review output, and finding disposition were read back, or the gate was explicitly waived/not applicable through the active runtime adapter; for OpenRouter `issue_comment` workflow/script changes, default-branch or equivalent live-test availability is required before live slash evidence can clear the gate
- do not request GitHub Copilot review unless the operator explicitly approves or manually triggers it
- do not post or confirm any external `@codex` PR review or action comment unless the operator approved the exact proposed comment text in the current session
- do not claim the external `@codex` gate is clear until the formal response is read live and valid findings are fixed or dispositioned
- do not treat skill wording as higher authority than Core Agent Instructions, repository `AGENTS.md`, or Supabase `ircore`
- do not confuse draft creation with applied change
- do not overstate certainty
- do not turn small validation into broad ceremony
