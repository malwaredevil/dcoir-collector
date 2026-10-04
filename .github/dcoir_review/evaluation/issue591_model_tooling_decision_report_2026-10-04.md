# Issue #591 — DCOIR Review 2026 Model and OpenRouter Tooling Decision Report

Date: 2026-10-04  
Issue: https://github.com/malwaredevil/dcoir-collector/issues/591  
Evaluation branch: `issue-591-current-candidate-refresh`  
Status: **benchmark decision package complete; recommended production refresh implemented on the evaluation branch and pending governed PR validation/review**

## Implementation status

The approved implementation preserves the benchmarked stage separation:

- Whole-PR premium and semantic adjudication now prefer `anthropic/claude-opus-5.5`.
- Routine per-file review now uses `anthropic/claude-sonnet-5.5` at high reasoning.
- The independent challenger remains `openai/gpt-5.6-sol-pro`.
- Repair authoring is independently governed as `openai/gpt-5.6-terra` -> `anthropic/claude-sonnet-5.5`, rather than inheriting the detector stack.
- Cross-family critic routing remains independent, with Anthropic critic roles upgraded to Opus 5.5 / Sonnet 5.5.
- Claude 5/5.5 adaptive-reasoning request shapes omit generic `temperature` while preserving `provider.require_parameters=true`.
- Auto, Advisor, Fusion, Subagent, Batch, Response Caching, Ori, and tool-use experiments remain outside the production authority path.

No production review invocation, external reviewer request, or additional paid benchmark is authorized by this implementation status.

## Executive decision

The evidence supports a targeted production refresh rather than a wholesale routing redesign.

Recommended production direction:

1. Upgrade the Anthropic premium path from **Claude Opus 5** to **Claude Opus 5.5**.
2. Upgrade the routine per-file path from **Claude Sonnet 5** to **Claude Sonnet 5.5**.
3. Keep **GPT-5.6 Sol Pro** as the independent adversarial challenger; GPT-6 Astra did not beat it on the mature multilingual corpus.
4. Keep **GPT-5.6 Terra** as the primary default repair critic.
5. Upgrade Anthropic repair-critic fallbacks from Opus 5 / Sonnet 5 to **Opus 5.5 / Sonnet 5.5**.
6. Decouple repair authoring from the global premium detector and prefer **GPT-5.6 Terra**, with **Claude Sonnet 5.5** as a bounded fallback, subject to post-change production telemetry confirming the expected cost advantage.
7. Fix the request-shape policy so Anthropic adaptive-reasoning requests do **not** carry the generic `temperature: 0.2` field when `provider.require_parameters=true`.
8. Keep **OpenRouter Auto, Advisor, Fusion, Subagent, Batch, Response Caching, Ori Eval, Shell/Bash, Apply Patch, Web tools, and Tool Search out of the governed production review path** unless explicitly noted below.

No benchmark threshold, verifier rule, scorer expectation, or safety invariant was weakened to produce these recommendations.

## Current production mapping read from `main`

Current main at the decision checkpoint: `acc49229a8722f83f5b7e594b221635a13d60260`.

| Stage | Current production |
| --- | --- |
| Whole-PR primary | `anthropic/claude-opus-5` -> `openai/gpt-5.6-sol-pro` |
| Routine per-file | `anthropic/claude-sonnet-5` |
| Independent challenger | `openai/gpt-5.6-sol-pro` |
| Semantic adjudication | `anthropic/claude-opus-5` -> `openai/gpt-5.6-sol-pro` |
| Default repair critic | `openai/gpt-5.6-terra` -> `anthropic/claude-sonnet-5` |
| Critic after OpenAI repair author | `anthropic/claude-opus-5` -> `anthropic/claude-sonnet-5` -> `google/gemini-3.1-pro-preview` |
| Critic after non-OpenAI repair author | `openai/gpt-5.6-sol-pro` -> `openai/gpt-5.6-terra` |
| Repair author | Uses the global review config/model stack rather than a separately governed author stack |

## Model evidence

### Claude Opus 5.5 should replace Opus 5 in premium Anthropic roles

Direct production-shaped PR-mutation comparison, run `37211220964`, 12 cases:

| Candidate | FN | FP | Cost | Serial time |
| --- | ---: | ---: | ---: | ---: |
| Opus 5, no temperature | 0 | 4 | $2.170956 | 478.794 s |
| Opus 5.5 | 0 | 1 | $1.497755 | 275.070 s |

The earlier complete 16-case screen, run `37144270826`, also had both models clear the complete quality floor, while Opus 5.5 was cheaper and faster than the compatible no-temperature Opus 5 control.

OpenRouter currently lists Opus 5.5 at $4/M input and $20/M output versus Opus 5 at $5/M input and $25/M output:
- https://openrouter.ai/anthropic/claude-opus-5.5
- https://openrouter.ai/anthropic/claude-opus-5

**Decision:** promote Opus 5.5 anywhere the existing governed role is specifically owned by Opus 5, while preserving cross-family fallbacks.

### Claude Sonnet 5.5 should replace Sonnet 5 for routine per-file review

Direct PR-mutation comparison, run `37195201575`, 12 cases:

| Candidate | FN | FP | Cost | Serial time |
| --- | ---: | ---: | ---: | ---: |
| Sonnet 5 | 0 | 4 | $0.892430 | 420.344 s |
| Sonnet 5.5 | 0 | 1 | $0.587300 | 93.123 s |

Direct precision-regression comparison, run `37193839204`, 10 cases:

| Candidate | FN | FP | Cost | Serial time |
| --- | ---: | ---: | ---: | ---: |
| Sonnet 5 | 0 | 4 | $1.428334 | 974.512 s |
| Sonnet 5.5 | 0 | 2 | $0.629375 | 161.149 s |

Mature multilingual run `37208600487`, 40 cases:
- Sonnet 5.5: **0 FN / 0 FP / 0 errors**, $0.451361, 164.761 s.
- Opus 5.5: 1 FN / 0 FP / 0 errors, $1.127669, 307.488 s.

OpenRouter lists Sonnet 5 and Sonnet 5.5 at the same standard $2/M input and $10/M output pricing:
- https://openrouter.ai/anthropic/claude-sonnet-5
- https://openrouter.ai/anthropic/claude-sonnet-5.5

**Decision:** promote Sonnet 5.5 for the routine per-file stage.

### Keep GPT-5.6 Sol Pro as the independent challenger

Mature multilingual comparison, run `37209650177`, 40 cases:

| Candidate | FN | FP | Cost | Serial time |
| --- | ---: | ---: | ---: | ---: |
| GPT-6 Astra | 2 | 0 | $1.675573 | 600.568 s |
| GPT-5.6 Sol Pro | 0 | 0 | $1.583336 | 403.233 s |

**Decision:** Astra does not displace Sol Pro in the independent challenger role.

### Repair-author evidence favors Terra / Sonnet 5.5 over premium Opus models for disposition clarity

Historical PR #581 false-positive regression:
- Run `37215046046`: Opus 5 correctly recognized the defect as absent at confidence 0.93; Opus 5.5 did so at 0.90. Both proposed no patch, but both stayed below the 0.95 suppression threshold and therefore fell back to `verified-no-safe-repair-set`.
- Run `37215333764`: Sonnet 5.5 suppressed the same false positive at confidence 0.96; Terra suppressed it at 0.99. Both produced `defect-absent-suppressed`.

Coordinated two-edit real repair:
- Run `37214677576`: Opus 5 and Opus 5.5 both authored the exact two required edits; Opus 5.5 was faster (~15.7 s vs ~20.2 s).
- Run `37216221978`: Sonnet 5.5 and Terra both authored the exact two required edits; Sonnet 5.5 was ~9.3 s and Terra ~13.0 s.

GPT-6 Astra:
- Run `37219111795`: after applying the known-compatible no-temperature request shape, Astra authored the exact coordinated repair and correctly suppressed the historical PR #581 false positive at confidence 0.99.
- Astra was materially slower than the Terra/Sonnet 5.5 repair-author probes.

Current standard OpenRouter price for Terra is $2/M input and $12/M output:
- https://openrouter.ai/openai/gpt-5.6-terra

**Decision:** the best repair-author evidence is Terra primary, Sonnet 5.5 fallback. This also directly addresses the historical non-answer behavior. The final promotion should be conditioned on post-change production telemetry confirming stage cost and token behavior because the repair-path benchmark intentionally did not fabricate exact cost measurements.

### Repair-critic evidence

Direct critic safety suite: accept a complete repair, reject a partial repair, reject an unnecessary extra edit.

Run `37217028035`:
- Sonnet 5.5: 3/3 correct, zero unsafe accepts, ~10.2 s total.
- Terra: 3/3 correct, zero unsafe accepts, ~7.5 s total, 0.99 confidence on all three.

Run `37217189564`:
- Sol Pro: 3/3 correct, zero unsafe accepts, ~17.3 s total, 0.99 confidence on all three.
- Opus 5: 3/3 correct, zero unsafe accepts, ~26.9 s total, lower rejection confidence margin.

Run `37220164778`:
- Opus 5.5: 3/3 correct, zero unsafe accepts, ~21.2 s total, 0.97 confidence on all three.
- Astra: 3/3 correct, zero unsafe accepts, ~19.1 s total, confidence 1.00 / 1.00 / 0.99.

**Decision:**
- keep Terra as default critic;
- keep Sol Pro as critic for non-OpenAI authors;
- upgrade the Anthropic critic path to Opus 5.5 / Sonnet 5.5;
- do not use Astra as critic for OpenAI repair authors because that would violate the cross-family independence requirement.

## Request-shape compatibility finding

Run `37185490646` proved that the generic production-shaped `temperature: 0.2` request is incompatible under `provider.require_parameters=true` for:
- Opus 5.5 with xhigh reasoning;
- Sonnet 5.5 with high reasoning;
- GPT-6 Astra with xhigh reasoning;
- GPT-6 Luna with high reasoning.

The same candidates route successfully when the unsupported sampling field is omitted. The repair benchmark initially reproduced the Astra failure until the evaluation harness honored the candidate's no-temperature request shape.

**Decision:** production payload policy must omit `temperature` for the promoted Anthropic adaptive-reasoning models. This is a request-compatibility fix, not a scoring relaxation.

## Auto Router

Complete-screen evidence:
- Run `37144270826`: Auto Max passed the 16-case quality floor but resolved to GPT-6 Astra on 15/16 requests and Kimi K3 on 1/16.

Exact repeat on three preserved historical defects:
- Run `37220629309`: 3/3 detected; all three resolved to GPT-6 Astra via Azure.
- Run `37220865485`: exact repeat, again 3/3 and all three resolved to GPT-6 Astra via Azure.

The short-term repeat was stable, but the earlier complete run proves that the resolved model identity is mutable. Current OpenRouter Auto routing is deliberately market-driven and can change as usage changes.

**Decision:** **evaluation/discovery only**. Do not use Auto Router as the governed production model authority for DCOIR Review.

## Advisor

Synthetic mechanics were previously proven to work, but the meaningful real-case experiment is run `37221116625`.

Case: production-shaped workflow-expression shell injection that MiMo Flash had previously missed in an earlier pass.

Plain MiMo Flash:
- caught the expected shell-injection defect on this run;
- also produced two extra findings, so it failed the precision gate;
- cost $0.001530;
- latency 11.589 s.

MiMo Flash + pinned Opus 5.5 Advisor:
- OpenRouter telemetry confirms `openrouter:advisor` was invoked;
- the request failed to produce a usable structured benchmark result (`ValueError`);
- cost $0.028938;
- latency 29.449 s.

That is approximately 19x the cost and 2.5x the latency without a usable quality result.

**Decision:** reject Advisor for the governed production path. Existing explicit candidate-scoped escalation is more transparent and reliable.

## OpenRouter capability dispositions

Current server-tool catalog:
https://openrouter.ai/tools/

### Fusion — do not implement

OpenRouter Fusion runs multiple models and a synthesis/judge step, and current product descriptions note that request cost is the sum of the underlying completions. It can also introduce web-search/fetch behavior depending on configuration.

DCOIR Review already has an explicit, auditable:
`primary -> independent challenger -> semantic adjudicator -> verifier`
pipeline with exact-head provenance and stage telemetry.

**Disposition:** not worth layering on top of the existing governed pipeline. Revisit only if a future hard-case corpus demonstrates a recall gap the current explicit stages cannot close.

### Subagent — do not implement

OpenRouter Subagent delegates focused work to another model inside a parent request.

DCOIR Review already owns per-file decomposition, exact file coverage, bounded concurrency, deterministic merge, recovery behavior, and telemetry.

**Disposition:** no current value. It would create a second opaque decomposition layer and weaken coverage accounting.

### Response Caching — keep disabled for governed review

OpenRouter response caching returns identical responses without reaching the model/provider. That is directly incompatible with stages whose purpose is a fresh independent judgment.

Current docs also state account-level ZDR disables response caching:
https://openrouter.ai/docs/guides/features/response-caching

**Disposition:** keep disabled for primary/challenger/adjudicator/verifier/critic and for model-comparison repeats. A future low-risk deterministic test-retry lane may use it only if workspace privacy policy permits and cache HIT/MISS is captured.

### Batch API — no live-review use; sanitized evaluation only if later justified

OpenRouter's Batch API generally discounts token pricing, but completion is asynchronous/variable and inputs/results are retained for up to 30 days:
https://openrouter.ai/blog/announcements/batch-api/

**Disposition:** do not use for live DCOIR Review. Do not send governed/sensitive historical review material through a 30-day-retention batch path. A future sanitized/public synthetic tournament could use Batch if the cost benefit becomes material.

### Ori Eval — explicitly not integrated in #591

Ori Eval can pin model/harness, generate `*.eval.ts` files, assert tool behavior, use an LLM judge, and run in CI:
https://openrouter.ai/blog/announcements/ori-eval/

The #591 work already produced a repository-native DCOIR harness with:
- deterministic known-defect and clean-control scoring;
- production-shaped mutation/precision/multilingual suites;
- provider/served-model telemetry;
- cost/token/latency accounting;
- router variance evidence;
- repair-author and repair-critic production-path probes;
- durable historical DCOIR specimens.

**Disposition:** do not add Ori/Bun as a second evaluation runtime now. Reconsider only if future maintainers want an external model-refresh framework; deterministic DCOIR assertions must remain authoritative.

### Shell / Bash — reject for production review

A model-controlled execution surface is unnecessary for ordinary repository-local review and creates an avoidable untrusted-PR execution boundary.

**Disposition:** keep disabled. Deterministic GitHub Actions/local validation remains authoritative.

### Apply Patch — reject for DCOIR Review

Apply Patch returns structured patch proposals, but DCOIR Review is review-only and already has a verified repair author/critic path that never mutates the PR branch.

**Disposition:** keep disabled in review. Autonomous remediation belongs to the separate remediation scope tracked elsewhere.

### Web Search / Web Fetch — not default

Repository-local review should be grounded in exact-head repository evidence.

**Disposition:** keep disabled by default. A future explicitly scoped external-contract verification stage may use them with provenance, but ordinary review must not depend on network-derived facts.

### Tool Search — no current need

DCOIR Review has a small, explicit tool surface.

**Disposition:** do not add complexity until tool-schema size becomes a demonstrated context problem.

## Models not promoted

- GPT-6 Astra: strong repair author/critic evidence, but lost to Sol Pro on the mature 40-case challenger corpus and was slower/more expensive there.
- GPT-6.1 Sol / Sol Pro: repeated upstream 429/provider-reliability failures prevented a safe promotion.
- MiMo V2.6 Flash: extremely cheap, but mature realistic runs showed unstable precision/recall and the Advisor experiment did not rescue it safely.
- MiMo V2.6 Pro: no compelling quality/latency advantage.
- DeepSeek V4 Pro / V4.1 Flash: no stage-specific win large enough to justify replacing the calibrated incumbents.
- Kimi candidates: no stage-specific advantage sufficient for promotion.
- GLM candidates: compatible and inexpensive in some runs, but no stage-specific evidence beat the recommended Anthropic/OpenAI mapping.
- Pareto/Auto: useful discovery/evaluation mechanisms, not fixed production authority.

## Recommended production mapping

| Stage | Recommended |
| --- | --- |
| Whole-PR primary | `anthropic/claude-opus-5.5` -> `openai/gpt-5.6-sol-pro` |
| Routine per-file | `anthropic/claude-sonnet-5.5` |
| Independent adversarial confirmation | keep `openai/gpt-5.6-sol-pro` |
| Semantic adjudication | `anthropic/claude-opus-5.5` -> `openai/gpt-5.6-sol-pro` |
| Repair author | `openai/gpt-5.6-terra` -> `anthropic/claude-sonnet-5.5` |
| Default repair critic | keep `openai/gpt-5.6-terra` -> `anthropic/claude-sonnet-5.5` fallback |
| Critic after OpenAI author | `anthropic/claude-opus-5.5` -> `anthropic/claude-sonnet-5.5` -> existing Gemini fallback |
| Critic after non-OpenAI author | keep `openai/gpt-5.6-sol-pro` -> `openai/gpt-5.6-terra` |
| Auto Router | evaluation only |
| Advisor/Fusion/Subagent | disabled |
| Shell/Bash/Apply Patch/Web tools | disabled by default |
| Batch/Response Cache | not used for governed live review |
| Ori Eval | not integrated |

## Remaining post-implementation validation and review scope

The production refresh is implemented on this evaluation branch. The remaining work is validation and governed review, not approval to implement:

1. Complete exact-head repository validation for the production model mapping, request shape, repair-author routing, critic routing, and rollback behavior.
2. Run a controlled post-change review/repair replay and capture real stage telemetry, including repair-author cost, only when separately authorized.
3. Complete the governed independent-review gates before readiness or merge.

## Rollback target

Rollback is the current `main` production mapping at `acc49229a8722f83f5b7e594b221635a13d60260`:
- Opus 5 premium;
- Sonnet 5 per-file;
- Sol Pro challenger;
- Terra/Sonnet 5 default critic;
- Opus 5/Sonnet 5/Gemini cross-family Anthropic critic stack;
- existing payload behavior.

Implementation should keep the rollback as a small model/config/policy revert rather than an architecture rollback.

## Decision checkpoint

**Paid benchmarking is complete.**

No further model tournament or implementation decision is needed. Complete validation and governed review; only after those gates pass can #591 be considered for closure and product work resume.
