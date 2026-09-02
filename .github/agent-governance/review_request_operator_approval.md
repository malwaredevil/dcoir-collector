# Review Request Operator Approval

Status: active governance rule.
Tracking issue: #460.

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

## Sequencing

When another governance rule says that `/dcoir-review`, `/or-review`, or `/openrouter-review` is the next review gate after Prog/Adva/Codi or after a finding is fixed, interpret that as **the next gate that may be proposed to the operator**. It is not permission to post the command automatically.

After an operator-approved DCOIR Review request is posted, use the normal readback discipline for the command comment, workflow/run, reviewed head, model/context metadata, review output, and findings. If a rerun is needed, stop and obtain fresh approval for the exact rerun request before posting it.

## Static snapshot precedence

This rule also controls interpretation of `.github/agent-governance/chatgpt_agent_core_reference.md`. That file is a repo-side reference snapshot, not the live ChatGPT WebUI authority surface. Any older sentence in that snapshot that says to run or rerun an internal review command automatically is superseded by this rule and must be read as sequencing only: propose the exact request to the operator, obtain fresh current-session approval, and post only after approval. The same snapshot must not be used to infer permission to request GitHub Copilot review automatically.

The existing exact-text operator-approval requirement for literal `@codex` review/action requests remains unchanged.

## Evidence references

Merely citing an already-completed Codex, Copilot, or DCOIR Review in issue text, PR text, readback receipts, or status reports is not a new review request and does not itself require approval. Avoid trigger-capable literal handles or slash commands when a non-triggering reference is sufficient.

This rule is mirrored in repository adapter/skill/checklist surfaces and in Supabase `ircore` operator-preference, lesson, scenario, and validation records. If a lower-priority or older instruction conflicts by saying to run or rerun DCOIR Review automatically, this explicit operator-approval rule controls.
