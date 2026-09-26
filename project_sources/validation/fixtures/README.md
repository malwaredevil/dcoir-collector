# Shared Test Artifacts

This directory is the canonical repository entry point for reusable **testing artifacts** used by manual and automated validation.

## Discovery contract

Future coding sessions should start with `index.json` when they need stable test data for Gemini, OpenAI, or another governed runtime. The repository `AGENTS.md` and root `README.md` both point here so this location does not depend on chat memory.

## Layout

Cross-provider fixture families are grouped by capability:

```text
project_sources/validation/fixtures/
  index.json
  agent_runtime/
    usb_reporting/
      README.md
      manifest.json
      inputs/
        violations_sanitized_nipr.csv
        violations_sanitized_mixed.csv
```

Existing subsystem-owned fixtures remain in their established locations when a dedicated harness already owns them.

## Artifact rules

- Commit only sanitized inputs that are safe and useful as durable regression fixtures.
- Every cross-provider family must have a machine-readable manifest describing purpose, intended targets, provenance, privacy handling, and artifact hashes.
- Prefer capability-oriented families over provider-specific duplication when Gemini and OpenAI are expected to implement the same operator-visible behavior.
- Inputs are test data, not fresh execution evidence.
- Run-specific outputs, screenshots, transcripts, logs, and model captures belong in GitHub Actions artifacts or another governed evidence lane by default.
- A runtime capture may be committed only when it has been sanitized and deliberately promoted into a stable regression fixture.
- Do not weaken a test contract merely to make current model output pass.

## Adding a family

1. Add a capability directory under the appropriate shared surface.
2. Add a `README.md` for human use and a `manifest.json` for automation.
3. Put stable inputs below an `inputs/` directory.
4. Record SHA-256 hashes and privacy/provenance metadata in the family manifest.
5. Register the family in `index.json`.
6. Validate JSON/CSV structure and read the committed files back from GitHub after mutation.
