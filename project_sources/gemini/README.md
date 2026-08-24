# DCOIR Gemini Lane

Gemini bundle adapters, docs, and tools for the current stored-source compile lane.
The canonical Prime-chunk and specialist text now lives under
`project_sources/agent_runtime/behavior_modules/`. The matching files under
`bundle_source/` are generated, checked-in adapters retained for the existing
Gemini topology, validation, and release workflow.

Edit the shared module, update its declared SHA-256, run
`materialize_agent_behavior_adapters.py --materialize`, and commit both the
canonical source and every affected generated adapter. The release builder runs
the same tool in `--check` mode and fails on drift before Prime reassembly.

Legacy prompt-pack surfaces were retired after the shift to the Gemini Agent
construct. The live bundle manifest points to the shared source contracts rather
than the retired `project_sources/PP-*` paths.
