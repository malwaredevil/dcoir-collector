---
name: ircore-config-lookup
description: lookup helper for ircore names and structured references. use for config-name lookup, tool catalog lookup, workflow catalog lookup, source-ref lookup, and governed Supabase reference lookup when required.
---

# ircore-config-lookup

## Purpose

Use this skill when `ircore` work depends on finding the right named thing before acting.

Its job is to:
- resolve canonical config names
- resolve source references
- resolve workflow catalog entries
- resolve tool catalog entries
- resolve validation rule names
- resolve scenario or lane names
- resolve GitHub work-item gateway names
- identify exact Core Agent Instructions or repository `AGENTS.md` section targets
- report ambiguity before mutation

This is a lookup helper. It does not decide source truth by itself and does not override Core Agent Instructions, live GitHub, repository `AGENTS.md`, or Supabase `ircore`.

## When To Use

Use this skill when you need to find:
- canonical config names
- Supabase `ircore` source refs
- workflow catalog entries
- tool catalog entries
- validation rule names
- scenario or lane names
- GitHub work-item gateway names
- Core Agent Instructions or `AGENTS.md` section targets
- governed Supabase reference records when required

Do not use this skill for broad research or memory-history exploration.

## Lookup Order

Prefer this order:

1. live GitHub source, issue, PR, branch, workflow, or file metadata when GitHub owns the fact
2. Supabase `ircore` routing, validation, workflow/tool catalog, source-ref, preference, lesson, and receipt records when Supabase owns the operational fact
3. active continuity only for current-session resumption

When a GitHub issue or PR governs the task, read live GitHub first, then use `ircore.get_github_work_item_context` if available.

## Canonical Supabase Redirect Names

Use unversioned canonical function names only:

- startup pack: `ircore.get_agent_startup_pack`
- fallback bootstrap: `ircore.get_agent_bootstrap`
- preferences: `ircore.get_agent_preferences`
- lane matrix: `ircore.get_agent_lane_matrix`
- authority contract: `ircore.get_agent_authority_contract`
- Gemini research consultation: `ircore.get_gemini_research_consultation`
- Gemini research receipt: `ircore.get_gemini_research_receipt`
- GitHub work-item context: `ircore.get_github_work_item_context`
- GitHub work-item upsert gateway: `ircore.upsert_github_work_item`
- GitHub work-item readback gateway: `ircore.record_github_work_item_readback`
- GitHub work-item archive gateway: `ircore.archive_github_work_item`

If a needed name is missing, look it up in live Supabase schema or routing records instead of inventing it.

## Core Responsibilities

### Config Name Lookup

When a task depends on a config name:
- search the relevant Supabase `ircore` record or GitHub source
- identify the canonical slug or key
- report whether the lookup was exact, nearest-safe, or missing
- do not proceed as if a guessed name is canonical

### Tool Lookup

When work might reuse an existing tool:
- check whether an existing tool already covers the task
- identify the governed usage path
- note any required config names or workflow companions
- prefer reuse over creating a new tool

### Workflow Lookup

When execution might use GitHub Actions or another governed workflow:
- identify the intended workflow
- confirm its purpose before recommending it
- distinguish workflow selection from workflow readback
- surface any known routing or safety notes
- do not recommend workflow mutation unless the operator has explicitly approved workflow changes for the current session

### Source-Ref Lookup

When the task needs the governing document, source file, or procedure:
- identify the canonical source reference
- prefer GitHub docs and source over memory summaries
- use `ircore` records as pointers, not replacements for canonical source
- for Core Agent Instructions or repository `AGENTS.md` updates, identify the exact target section and whether the operator has approved a direct update lane or requires a branch/PR lane

### GitHub Work-Item Lookup

When governed issue or PR work is in scope:
- read live GitHub issue or PR state first
- use `ircore.get_github_work_item_context` when available
- identify whether `ircore.upsert_github_work_item`, `ircore.record_github_work_item_readback`, or `ircore.archive_github_work_item` is required
- do not manually write `ircore.github_work_items` or `ircore.github_work_item_readbacks` unless the operator explicitly approves emergency repair or test cleanup in the current session

### Codi Review-Gate Lookup

When Codi is mentioned or a PR review gate is in scope:
- treat Codi as required before external `@codex` for PR-related code, workflow, or governed-source review unless the operator explicitly waives Codi for the current task
- keep Codi evidence distinct from external `@codex`, GitHub Actions, and Supabase receipts
- preserve the required Codi review-comment prefix: the raw comment body first non-blank line must start with `CODI FINDS`
- identify whether the OpenRouter internal review command gate (`/or-review` or `/dcoir-review`) applies between Codi clearance and the external `@codex` request, including whether the workflow/script are available on the default branch or an explicitly approved equivalent live-test lane
- if `/dcoir-review` is the next applicable gate, report it only as a gate that may be proposed to the operator; do not treat sequencing as permission to post the command
- before posting or confirming any `/dcoir-review` command, including standard, `deep`, `diff`, `debug`, or any other current/future variant, require the exact proposed command text to be shown to the operator and explicitly approved in the current session
- treat DCOIR Review approval as per-invocation: every rerun or later `/dcoir-review` request requires fresh explicit approval; no approval means no DCOIR Review request
- identify whether any proposed PR comment would invoke the literal `@codex` handle; if so, the agent must draft the exact comment text, show it to the operator, and receive explicit operator approval in the current session before posting or confirming it
- identify whether GitHub Copilot review is being requested; if so, the request is operator-controlled and requires explicit operator approval unless the operator manually triggers it
- when locating prior Codex, Copilot, or DCOIR Review evidence for issue, PR, closure, or parent-tracker text, prefer non-triggering wording when a trigger-capable literal handle or slash command is unnecessary

## Output Contract

When used, return a compact lookup result with:

1. lookup type
2. authority surface consulted
3. resolved canonical name, tool, workflow, source ref, gateway, or section target
4. any ambiguity or evidence gap
5. whether reuse is available
6. whether GitHub work-item receipts are required
7. whether Codi review, DCOIR Review exact-request operator approval, GitHub Copilot operator approval/manual trigger, and external `@codex` exact-text operator approval are required for this task
8. one best next move

## Hard Rules

- do not invent config names when a governed one should exist
- do not create a new tool before checking for an existing one
- do not treat memory notes as canonical
- do not skip GitHub source truth for repo source, issue, PR, branch, or workflow facts
- do not skip Supabase gateway lookups when governed issue/PR receipts are required
- do not make Codi optional by default
- do not skip OpenRouter internal review gate lookup when PR review-gate sequencing is in scope, and do not treat branch-only existence of an OpenRouter `issue_comment` workflow/script as live-test availability
- do not post or confirm any `/dcoir-review` command unless the operator approved the exact proposed command in the current session; this applies to every variant and each rerun independently
- do not request GitHub Copilot review unless the operator explicitly approves or manually triggers it
- do not treat an external `@codex` PR comment as postable until the operator approves the exact proposed comment text in the current session
- do not treat skill wording as higher authority than Core Agent Instructions, repository `AGENTS.md`, or Supabase `ircore`
- do not widen narrow lookup into full-task ceremony
