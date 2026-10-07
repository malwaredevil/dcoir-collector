# run-gemini-path-safety-selftests

Reusable DCOIR GitHub Actions composite action for the Gemini bundle path-safety self-tests.

## Contract

- This action is the single owner of the Gemini bundle path-safety self-test list:
  - `project_sources/gemini/tools/lib/gemini_bundle_path_safety_selftest.py`
  - `project_sources/gemini/tools/gemini_bundle_path_safety_integration_selftest.py`
  - `project_sources/gemini/tools/reassemble_dcoir_gemini_prime_agent_selftest.py`
  - `project_sources/agent_runtime/tests/reassemble_dcoir_gemini_prime_agent_selftest.py`
- It fails before running anything if a listed self-test is missing, then stops at the first failing self-test.
- Callers (`reusable-validate-on-push.yml`, `reusable-validate-on-pr.yml`, `reusable-gemini-bundle-build.yml`) keep triggers, permissions, and report paths visible and run this action before their Gemini build step.
- Compensating evidence is provided by the caller-visible step name and the per-self-test stdout markers.

## Maintenance

Add, rename, or remove a Gemini path-safety self-test here only, then run the workflow maintenance audit and the caller workflows.
