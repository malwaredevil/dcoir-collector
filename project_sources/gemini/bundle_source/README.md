# DCOIR Gemini Bundle Source

Purpose
- This folder is the governed editable runtime source tree for the major-version Gemini bundle.
- Edit these files directly when accepted runtime wording changes.
- Compile the bundle only after maintained knowledge, topology, handoff, validation, and package-time attachment checks run.

Branch-built test boundary
- Any artifact built from a non-main ref or an unpromoted topology is TEST-ONLY.
- Load it only into a separate Gemini draft/test agent until representative runtime evaluation is complete and a promotion decision is recorded.
- A successful build, ZIP inspection, or static validation result does not promote the bundle to live/main.

Major-version topology rule
- `Gemini_Bundle_Source_Manifest.json` is the explicit source of topology truth.
- The manifest governs one Prime plus eleven specialist sub-agents.
- Prime routes and preserves state; specialists own bounded work.
- Validation must compare manifest topology against discovered source-tree files and fail on drift.

Router-description and handoff rules
- Router-facing descriptions must use concise Use when / Do not use when / Returns wording.
- Detailed edge cases remain in specialist instruction bodies and maintained knowledge.
- Internal specialists 01 through 09 return `common_handoff_envelope_v1` with agent-specific content under domain_payload.
- Prime applies branch-specific ordering and loop guards before sending one reconciled state to a terminal output owner.
- Internal envelope fields must never appear in analyst-facing output.

Knowledge-attachment rule
- The manifest governs the required shared knowledge attachment set.
- The maintained `knowledge/*.md` working set is the editable source of truth for those attachments.
- The attachment set includes twenty-eight knowledge pages that must stay aligned with the attachment map, maintained knowledge set, and validator surfaces.
- Ordinary shipment should fail if maintained knowledge, generated attachment inventory, and manifest inventory drift apart.

Source and build identity
- Manifest `bundle_version` is the maintained source-bundle version.
- A workflow override or timestamp is a build identifier.
- The authoritative identity of a test delivery is source branch/ref, head SHA, workflow run ID, artifact name, and delivery ZIP SHA256.
- Do not infer live status, source version, or provenance from an artifact filename alone.

Current major-version focus
- Router descriptions are concise and non-overlapping.
- Specialist instructions remain explicit about collector interpretation, collector pivoting, mixed-format IOC handling, targeted collection design, false-positive-aware security-product behavior, and output-contract consistency.
- If a behavioral instruction can be made clearer, prefer explicit specialist wording over duplication in Prime or router descriptions.

When changing the attachment set
1. Edit the maintained `knowledge/*.md` files.
2. Keep `knowledge/README.md` as the maintained-knowledge landing page.
3. Let the governed build path package those files directly into `02_PRIME_AGENT_ATTACHMENTS/*.md.txt` in the release ZIP.
4. Update `00_START_HERE/Agent_Attachment_Map.md.txt`.
5. Update `Gemini_Bundle_Source_Manifest.json` when the required attachment inventory changes.
6. Update workflow required-surface checks when the governed required-file contract changes.
7. Re-run validation and build.

What not to do
- Do not treat file drop alone as a topology or attachment-inventory change.
- Do not rely on ad hoc folder discovery as shipment authority.
- Do not skip manifest updates when adding or removing required shared knowledge files.
- Do not reintroduce separately maintained `02_PRIME_AGENT_ATTACHMENTS/*.md.txt` source files. They are generated at package time from `knowledge/*.md`.
- Do not treat source validation as a substitute for separate Gemini draft/test-agent evaluation.
