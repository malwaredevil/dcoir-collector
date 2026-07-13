# Generated evidence retention policy

## Purpose

This policy defines which generated validation and workflow evidence belongs in
Git, which belongs in GitHub Actions artifacts, and which may exist only as a
temporary connector-readable derivative.

GitHub remains source truth for repository source, committed report contracts,
workflows, and durable documentation. A generated file is not authoritative
merely because it is committed or easy for a connector to read.

## Evidence classes

### Canonical committed reports

Keep a generated report in Git only when a maintained validator, review gate,
manifest, fixture, or pull-request contract depends on its stable path. Its
generator and freshness or parity check must also remain available.

The collector PowerShell JSON/Markdown reports under
`project_sources/collector/` are the principal current example. They support
cross-report validation, review-assist ingestion, committed-report parity, and
pull-request checks. Their large size is an explicit generated-evidence
exemption from the 15,000-byte maintained-source policy.

Canonical reports must be regenerated in the same change when their governed
inputs change. A pull request must not update a report without either running
its generator or documenting the exact validation gap.

### GitHub Actions artifacts and job summaries

Use workflow artifacts for execution-specific output, packages, logs, full
validation results, and other evidence that does not need a stable repository
path. Artifact retention is owned by the producing workflow. Job summaries may
link to reports and artifacts, but they do not replace source or committed
report contracts.

An artifact proves only the run and head SHA from which it was produced. Do not
treat an expired artifact, a different-head run, or a copied local file as
current validation evidence.

### ChatGPT staging and status reports

`.github/chatgpt_staging/` contains operational requests, connector readback, progress,
and historical execution receipts. These paths are not canonical product or
validation source. The existing staging-cleanup and report-retention workflows
own their lifecycle.

Success reports, stale requests, and staged bundles should expire through those
lanes after the required GitHub or `ircore` readback exists. Failure evidence
may use a longer retention window. A bulk historical purge must use a bounded
cleanup plan and must not delete unread evidence.

Remaining Airtable strings in staging history are historical evidence, not an
active Airtable integration. Retired taxonomy entries and validation patterns
that detect stale Airtable authority wording are also retained safeguards, not
active capability. Do not remove these merely to obtain zero textual matches.

### Connector-readable chunks

Connector chunks are temporary derivatives, not a second canonical report.
Generate them only when a connector cannot read the authoritative report or
workflow artifact directly.

Connector chunks must:

- identify the canonical source path or workflow artifact and its SHA-256;
- record ordered reconstruction metadata and per-chunk hashes;
- remain at or below the task's chosen connector margin;
- prove byte-exact reconstruction before use;
- prove current canonical parity immediately before replacement claims; and
- have an explicit owner and deletion point.

Do not commit durable `project_sources/**/report_chunks/` trees. Prefer a
short-retention workflow artifact or cleanup-managed staging output. A scoped
issue may approve a temporary exception, but it must name the owner, source
hash, freshness check, and removal condition.

The former PR #350 report sidecars demonstrated why: their chunks remained
internally reconstructable while four canonical reports advanced, making the
sidecars stale and unsuitable as current replacement evidence.

### Fixtures and durable documentation

Sanitized fixtures may remain committed when a test requires exact stable input.
Long-form documentation and decision records may remain when they explain a
durable contract or historical decision. Neither class should be presented as
fresh workflow execution evidence.

## Decision table

| Evidence | Git | Artifact/staging | Required control |
| --- | --- | --- |
| Maintained source or manifest | Yes | No | Normal source validation |
| Canonical generated report required by validators | Yes | Optional copy | Generator plus freshness/parity check |
| Run-specific report, package, or logs | No by default | Yes | Run ID, head SHA, job result, retention |
| Connector-readable report chunks | No by default | Yes, temporary | Source hash, chunk hashes, reconstruction, cleanup |
| ChatGPT request/status receipt | Temporary only | Cleanup-managed Git path | Readback before retention cleanup |
| Sanitized regression fixture | Yes when test-owned | Optional | Provenance and fixture validation |
| Historical documentation | Yes when useful | No | Must be labeled historical |

## Reproducible audit

Run:

```text
python .github/dcoir_review/scripts/audit_generated_evidence.py --check
```

The command inventories tracked evidence classes and fails when an unapproved
durable `report_chunks` tree is committed. It reports counts and bytes for
canonical collector reports, ChatGPT staging, status reports, fixtures, and
Airtable references that still require contextual classification.

This audit is a policy check, not a substitute for each report generator,
workflow result, or committed-report parity validator.
