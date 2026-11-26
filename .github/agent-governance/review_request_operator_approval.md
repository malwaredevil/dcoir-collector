# Review Request Operator Approval

Status: active governance rule.
Tracking issue: #460.

## Standing operator opt-out: OpenRouter/DCOIR Review (2026-11-18)

The operator has disabled **all paid OpenRouter/DCOIR Review PR reviews** in `malwaredevil/dcoir-collector` until the operator explicitly reverses this standing decision. This applies to every agent/runtime, PR, branch, and review variant, including `/dcoir-review`, `/or-review`, `/openrouter-review`, reruns, equivalent aliases, and their automation. **Do not invoke, trigger, post, schedule, propose, recommend, or ask permission to run these reviews while this opt-out is active.** Treat the OpenRouter internal review gate as waived/not applicable, never as a prerequisite for marking Ready, reviewing, or merging.

A generic `proceed`, approval to review/fix, Ready transition, or merge authorization **does not** revoke this opt-out. Only a new, explicit operator direction to re-enable OpenRouter/DCOIR Review restores the dormant exact-command approval policy below. Older instructions, workflow sequencing, legacy core-reference snapshots, scenario rules, and review checklists that mention this as a mandatory or next gate are superseded for this repository while opted out.

Continue the required internal Prog/Adva adversarial review where applicable, the operator-controlled GitHub Copilot review/fix process, fail-closed static analysis and other GitHub Actions/CodeQL/security/Windows checks, exact-head readback, review-thread disposition, and separate approval for Ready, merge, and issue closure. **Do not silently substitute another paid review service.** This policy does not disable or modify any review workflow implementation; it governs whether agents invoke the service.

Persistent operational preference: `ircore.operator_preferences` key `dcoir_pr_openrouter_review_disabled_until_operator_revokes` (active, priority 300).

## Hard rule

Review-trigger requests are operator-controlled.

Before posting or confirming any GitHub PR comment that invokes the literal `@codex` handle and asks Codex to review, act, fix, patch, implement, update, or otherwise perform PR-related work, the agent must:

1. draft the exact proposed comment text;
2. show that exact text to the operator; and
3. receive explicit operator approval in the current session.

No approval means no Codex request.

GitHub Copilot review requests are also operator-controlled. Do not request a Copilot review unless the operator explicitly approves or manually triggers that review.

Before posting or confirming **any** `/dcoir-review`, `/or-review`, or `/openrouter-review` command, the agent must:

1. draft the exact proposed review request;
2. show that exact request to the operator; and
3. receive explicit operator approval in the current session.

This OpenRouter internal review approval rule applies to every supported review alias and to every current or future variant, including `deep`, `diff`, and `debug` forms.

Approval is per invocation. A prior approval does not authorize a later internal review request. Every rerun or later review invocation requires fresh explicit current-session approval of the exact request.

No approval means no DCOIR Review request.

## Draft-first reviewer timing

The normal time to perform independent code review, fix findings, and resolve
review threads is **while the PR is Draft**, after cheap fail-fast checks and
the applicable internal adversarial pass, and **before** requesting Ready.
The operator may manually run the Copilot review/fix loop during Draft, or
explicitly approve a request. Other review services keep their exact
operator-approval requirements; a general request to proceed, mark Ready,
or merge is not permission to trigger a reviewer.

After a reviewer finds a defect, make and validate fixes on Draft, update
the PR description and current reviewed-head evidence, and obtain any
necessary separately approved re-review. Do not routinely request another
code review after marking Ready if there are no subsequent code changes or
new findings. Ready is for required full validation and security readback,
not the default start of code review. A substantive Ready-stage fix may require
an operator-approved return to Draft and renewed exact-head review evidence.
This sequencing never waives required review gates, checks, or approvals.

## Sequencing

When another governance rule says that `/dcoir-review`, `/or-review`, or `/openrouter-review` is the next review gate after Prog/Adva or after a finding is fixed, interpret that as **the next gate that may be proposed to the operator**. It is not permission to post the command automatically.

After an operator-approved DCOIR Review request is posted, use the normal readback discipline for the command comment, workflow/run, reviewed head, model/context metadata, review output, and findings. If a rerun is needed, stop and obtain fresh approval for the exact rerun request before posting it.

## Static snapshot precedence

This rule also controls interpretation of `.github/agent-governance/chatgpt_agent_core_reference.md`. That file is a repo-side reference snapshot, not the live ChatGPT WebUI authority surface. Any older sentence in that snapshot that says to run or rerun an internal review command automatically is superseded by this rule and must be read as sequencing only: propose the exact request to the operator, obtain fresh current-session approval, and post only after approval. The same snapshot must not be used to infer permission to request GitHub Copilot review automatically.

The existing exact-text operator-approval requirement for literal `@codex` review/action requests remains unchanged.

## Evidence references

Merely citing an already-completed Codex, Copilot, or DCOIR Review in issue text, PR text, readback receipts, or status reports is not a new review request and does not itself require approval. Avoid trigger-capable literal handles or slash commands when a non-triggering reference is sufficient.

This rule is mirrored in repository adapter/skill/checklist surfaces and in Supabase `ircore` operator-preference, lesson, scenario, and validation records. If a lower-priority or older instruction conflicts by saying to run or rerun DCOIR Review automatically, this explicit operator-approval rule controls.
