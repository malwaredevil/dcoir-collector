# verify-required-surfaces

Reusable DCOIR GitHub Actions composite action for issue #194 workflow modularization.

## Contract

- Callers keep triggers, permissions, secrets, artifact names, and report paths visible in the entry or reusable workflow.
- This action owns repeated mechanical step logic only.
- With `include-gemini-manifest: true` (the default), the action runs `.github/github_actions/tools/test_check_gemini_manifest_surfaces.py` and then `check_gemini_manifest_surfaces.py`. The helper runs the canonical bundle path-safety, identity, inventory, topology, and runtime-surface checks, so it rejects governance leaks and other invalid bundle surfaces even when a caller skips full bundle validation.
- Compensating evidence is provided by caller-visible step names, explicit inputs, stdout markers, generated files, uploaded artifacts, or the caller workflow report section.

## Maintenance

Change this module when the shared mechanic changes, then run the workflow maintenance audit and applicable caller workflows.
