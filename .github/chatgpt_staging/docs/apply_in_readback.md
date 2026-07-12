# Apply-in readback

After staging `chatgpt-apply-in` / `chatgpt-in`, monitor the committed heartbeat files:

```text
.github/chatgpt_staging/status_reports/chatgpt-apply-in/<request_id>/workflow_report.md
.github/chatgpt_staging/status_reports/chatgpt-apply-in/<request_id>/progress_history.jsonl
```

Read the committed workflow report and native apply-in report before asking the operator for screenshots, logs, or uploads.

## Payload rule

Use exactly one payload:

```text
.github/chatgpt_staging/in/<request_id>/payload.zip.b64
```

Do not use chunks/parts. Do not hand-construct or paste unverified base64. Generate the ZIP/base64 bundle with a tool or script and verify it before staging.

Required verification before staging:

- ZIP opens and CRC check passes.
- Archive root contains `apply_manifest.json` and `files/`.
- Base64 length is divisible by 4.
- Base64 decode round-trip produces the same ZIP SHA256.
- Manifest target hashes match staged file content.
- No truncation marker or non-base64 characters are present.

If a future apply-in run produces additional artifact-only evidence, the workflow should also commit it under:

```text
.github/chatgpt_staging/status_reports/chatgpt-apply-in/<request_id>/artifact_readback/
```
