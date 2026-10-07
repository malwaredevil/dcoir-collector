# run-path-safety-selftests

Reusable DCOIR GitHub Actions composite action for the path-safety self-tests that guard manifest-controlled file access in the OpenAI GPT package builders and the Gemini bundle build.

## Contract

- This action is the single owner of the path-safety self-test list:
  - `project_sources/agent_runtime/tests/agent_runtime_path_safety_selftest.py` (shared containment owner)
  - `project_sources/gemini/tools/lib/gemini_bundle_path_safety_selftest.py` (Gemini manifest preflight and bundle identity)
  - `project_sources/gemini/tools/gemini_bundle_path_safety_integration_selftest.py` (compiler and validator)
  - `project_sources/gemini/tools/reassemble_dcoir_gemini_prime_agent_selftest.py` (prime-agent reassembly)
- It fails before running anything if a listed self-test is missing, then stops at the first failing self-test.
- Callers (`reusable-validate-on-push.yml`, `reusable-validate-on-pr.yml`, `reusable-gemini-bundle-build.yml`) keep triggers, permissions, and report paths visible and run this action before their Gemini build step.
- Compensating evidence is provided by the caller-visible step name and the per-self-test stdout markers.

## Maintenance

Add, rename, or remove a path-safety self-test here only, then run the workflow maintenance audit and the caller workflows.
