# DCOIR Review Model Benchmark

This is the reusable model-selection procedure for DCOIR Review.

## Configuration

Model IDs are **not secrets**. Keep benchmark candidates and named groups in:

`.github/dcoir_review/evaluation/first_pass_candidate_matrix_v1.json`

The only credential is `OPENROUTER_API_KEY`, which remains a GitHub Actions secret.

Do not create one GitHub Secret or repository variable per model. Version-controlled candidate configuration makes model changes reviewable, reproducible, and easy to roll back.

## Future model refresh

When a new model is worth testing:

1. Add one candidate entry to `first_pass_candidate_matrix_v1.json`.
2. Add its id to the appropriate named group such as `frontier`, `routine`, or `recommended`.
3. Run the deterministic evaluator self-test.
4. Run **08 Operator - DCOIR Review Model Benchmark** in plan mode first.
5. Review the planned paid-request count.
6. If a paid comparison is intended, rerun with `execute_live=true` and `confirm_paid_execution=true`.
7. Read the uploaded human-readable summary and JSON evidence.
8. Promote a production model only in a separate governed configuration change after the DCOIR-specific quality floor is met.

The workflow also accepts a comma-separated candidate selector, so a one-off comparison does not require changing the named groups.

## Decision rule

Quality is non-compensating.

A candidate that introduces a known-defect miss, false positive, ambiguous disposition, structured-output failure, or request error does not beat the incumbent merely because it is cheaper or faster. Cost and latency are tie-breakers among configurations that first satisfy the DCOIR quality floor.

Generic OpenRouter rankings and public benchmarks are discovery inputs only. DCOIR's own known-defect, clean-control, precision, and naturalistic corpus remains the promotion authority.

## Routers

`openrouter/auto` and `openrouter/pareto-code` are benchmark candidates, not production authority.

The matrix uses the current Auto Router `cost_tier` contract rather than the legacy numeric cost/quality compatibility setting. Router Metadata must identify the served model/provider so a mutable router result remains auditable.

## Data handling

Every benchmark request sets `provider.zdr=true` and `data_collection=deny`. If a model has no endpoint that satisfies those rules, it fails compatibility instead of silently weakening the data-handling policy.

Candidates that are known to require retention can be recorded under `excluded_candidates` so the research decision remains visible without sending the DCOIR corpus to them.

## Safety

- Plan mode makes zero paid inference calls.
- Paid-live mode has a second confirmation input and a maximum-request cap.
- Response caching remains disabled for model comparison.
- The benchmark has no GitHub review publication path.
- The benchmark never mutates production DCOIR Review model configuration.
- DCOIR Review does not review changes to itself; normal independent-review governance still applies to benchmark implementation changes.

## Diagnosing failed requests

A successful workflow means the comparison completed, not that every model passed.
Inspect each failed case in `benchmark_live.json`: `http_status` is the transport
status; `error_details.code` and `error_details.error_type` describe provider
failures, including errors returned inside HTTP 200 responses. The report also
retains allowlisted provider name/code, bounded sanitized messages and numeric
`retry_after_seconds` when available. Credential-bearing fields are omitted.
Raw provider bodies, arbitrary error metadata and exception text are not saved.
These diagnostics do not automatically retry or authorize more paid requests.

The first paid run (37138598449, merged source `6128da2da`) reported $1.836283887
across 160 requests. Six configurations passed the 16-case scorer; Opus 5 had
16 HTTP 404 failures, both GPT-6.1 configurations had six error-bearing HTTP 200
responses, and Luna had one scored miss. That older report discarded provider
error details, so it cannot establish the failure causes. It is preliminary
evidence, not a production promotion decision. A future run must use the fixed
diagnostic collector and separately approved paid scope.
