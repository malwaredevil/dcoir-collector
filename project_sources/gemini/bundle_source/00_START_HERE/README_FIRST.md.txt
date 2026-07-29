# README FIRST

This source tree is the governed editable runtime source for the major-version Gemini bundle. It preserves the explicit topology contract, direct knowledge-generation path, attachment inventory, router-description contract, specialist handoff contract, and source-versus-build provenance boundary.

## Branch-built test boundary

Any bundle built from a non-main ref or an unpromoted topology is TEST-ONLY. Load it only into a separate Gemini draft/test agent until representative runtime evaluation is complete and an explicit promotion decision is recorded. A successful build or validation report does not promote the bundle to live/main.

## Writing rules

Router-facing Agent description fields must be concise and distinct. Use exactly this shape:

- Use when: the narrow trigger conditions owned by the agent.
- Do not use when: the nearest overlapping lanes and explicit exclusions.
- Returns: the bounded result the router can expect.

Detailed instruction bodies and shared knowledge pages should remain explicit enough to preserve operational edge cases, evidence boundaries, syntax rules, and output discipline. Do not move specialist playbooks back into Prime merely to make routing easier.

Do not aggressively summarize away operational constraints.
Do not duplicate the same routing claim across several agent descriptions.
Do not rely on shorthand when a more explicit instruction materially reduces ambiguity.

## Specialist handoff rule

Internal specialists 01 through 09 exchange `common_handoff_envelope_v1`. Agent-specific results remain under domain_payload. Prime preserves the envelope across routes, applies loop guards, and sends the reconciled state to one terminal output owner. The envelope is internal state and must never appear in analyst-facing output.

## Source and build identity

- `bundle_version` is the maintained source-bundle version.
- A workflow version override or timestamp is a build identifier, not a replacement source version.
- The authoritative identity of a test artifact is the tuple: source branch or ref, head SHA, workflow run ID, artifact name, and delivery ZIP SHA256.
- Do not infer any member of that tuple from filenames, prompt memory, or stale documentation.

## What to edit

- Edit `knowledge/*.md` when the shared knowledge layer changes.
- Edit `01_GEMINI_AGENT_BUILD/*.md.txt` when parent or sub-agent behavior changes.
- Edit `00_START_HERE/*.md.txt` when operator-facing build guidance or attachment inventory changes.
- Edit the manifest when topology, routing contracts, provenance contracts, or required-file contracts change.

## Topology rule

The manifest is the explicit source of truth for the active topology. A file dropped into the folder is not automatically an active sub-agent. It becomes active only when the manifest lists it.

## Knowledge generation rule

The build wrapper reads maintained `knowledge/*.md` files directly and packages them as `02_PRIME_AGENT_ATTACHMENTS/*.md.txt` inside the generated release ZIP. Maintained knowledge files are the only editable shared-knowledge source of truth.

## Attachment-inventory rule

The attachment map, maintained `knowledge/*.md` set, and manifest `knowledge_attachment_sources` inventory must stay aligned. If the shared attachment set changes, update those surfaces in the same bounded change set so manual build, validate-on-push, and compile agree about what the bundle must ship.
