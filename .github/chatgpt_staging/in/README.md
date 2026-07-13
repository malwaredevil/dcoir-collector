# ChatGPT Apply-In Staging Contract

This staging area is intentionally narrow. The `chatgpt-apply-in` workflow accepts exactly one payload shape.

## Required shape

```text
.github/chatgpt_staging/in/<request_id>/payload.zip.b64
```

`<request_id>` must be safe for paths: letters, numbers, dots, underscores, and hyphens only.

## Decoded ZIP shape

The decoded ZIP must contain these archive-root entries:

```text
apply_manifest.json
files/<repo-relative-targets>
```

Do not add a wrapper root. Do not put target files beside `apply_manifest.json`; put target file content under `files/` and map each file through the manifest.

## Forbidden staging shapes

These are invalid for this workflow:

```text
payload.zip.b64.parts/
part-*.b64
*.part*
chunk_manifest.json
*chunk*
# dcoir-payload-b64-parts-v1
```

Do not split or chunk the base64.

## Required validation before staging

Before writing `payload.zip.b64`, validate:

1. request id is safe;
2. ZIP opens and CRC passes;
3. `apply_manifest.json` exists at archive root;
4. `files/` exists at archive root;
5. base64 length is divisible by 4;
6. base64 decode round-trip matches the ZIP SHA256;
7. no truncation marker such as `[... ELLIPSIZATION ...]` exists;
8. no non-base64 characters exist except whitespace;
9. no parts/chunk artifacts exist under the request folder.

## Expected verification after staging

After pushing `payload.zip.b64` to `main`, verify:

1. workflow report exists at `.github/chatgpt_staging/status_reports/chatgpt-apply-in/<request_id>/workflow_report.md`;
2. `progress_history.jsonl` exists at the same request path;
3. report result is `success`;
4. workflow job conclusion is `success`;
5. every target file is read back from GitHub `main` before claiming success.
