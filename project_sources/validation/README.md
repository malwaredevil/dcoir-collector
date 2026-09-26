# DCOIR Validation Lane

Shared validation helpers, fixtures, manual test framework, and specs.

## Shared test-artifact registry

The canonical cross-provider test-artifact entry point is:

- `project_sources/validation/fixtures/index.json`
- human guidance: `project_sources/validation/fixtures/README.md`

Use this registry for sanitized, reusable inputs that may be exercised manually or automatically across governed runtimes such as the Gemini Agent and OpenAI GPT targets.

Subsystem-specific fixture families may remain with their owning harness when that harness already has a stable location, for example `project_sources/gemini/fixtures/behavioral_replay/`. Do not duplicate or move those fixtures merely to centralize them. The shared registry should point to cross-provider families and may reference specialized families when useful.

Run-specific model output, screenshots, transcripts, logs, and workflow evidence are not committed here by default. Keep execution-specific evidence in GitHub Actions artifacts or other governed evidence lanes unless a sanitized capture is intentionally promoted into a durable regression fixture.
