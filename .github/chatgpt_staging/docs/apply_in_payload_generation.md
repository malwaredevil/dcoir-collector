# Apply-in payload generation

Status: active build/verification rule for `chatgpt-apply-in` payloads.

Do not hand-construct or paste unverified `payload.zip.b64` content.

## Required process

1. Build a real ZIP with root entries:
   - `apply_manifest.json`
   - `files/<repo-relative-targets>`
2. Verify the ZIP opens and CRC checks pass.
3. Verify `apply_manifest.json` schema is `dcoir.chatgpt_staging.apply_manifest.v1`.
4. Verify every new file has `expected_new_sha256`.
5. Verify every existing file has `expected_blob_sha` or `expected_current_sha256`.
6. Base64-encode the exact ZIP bytes.
7. Verify base64 length is divisible by 4.
8. Decode the base64 back to a ZIP and verify its SHA256 equals the original ZIP SHA256.
9. Stage exactly one file:
   `.github/chatgpt_staging/in/<request_id>/payload.zip.b64`

If a payload fails with invalid base64 length, bad CRC, or missing central directory, treat that as a payload generation/verification failure unless post-stage readback proves the staged file differs from the verified local payload.
