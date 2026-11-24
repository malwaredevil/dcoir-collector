# run-duplicate-function-check

Reusable DCOIR GitHub Actions composite action for cross-file duplicate PowerShell function definition detection in collector source.

## Contract

- Callers keep triggers, permissions, artifact names, retention, and workflow claims visible in the entry or reusable workflow.
- This action owns the repeated mechanical step for parsing all collector PS1 source files with the PowerShell AST and detecting function names defined in more than one file.
- The action prints each duplicate name with every file and line that defines it and emits complete JSON/Markdown reports. The shared static-analysis gate in `.github/scripts/Test-DcoirStaticAnalysisValidationGate.ps1` blocks any reported duplicate. Parse failures still fail the action.
- The action must not upload artifacts, enable code scanning, generate SARIF, use `pull_request_target`, reference `secrets.*`, or mutate repository history.
- Compensating evidence is provided by caller-visible step names, explicit inputs, stdout duplicate report listing file paths and line numbers, and the caller workflow conclusion.

## Report path safety and tests

- The supported execution platform is Windows with PowerShell 7 (`pwsh`). `DuplicateFunctionCheck.Paths.ps1` is the single owner of the report path resolver and Markdown cell escaping; the action dot-sources it before resolving either report path.
- Both outputs must be distinct, repo-relative paths under `project_sources/collector/`, with the appropriate `.json` or `.md` suffix. The guard rejects ambiguous Windows path components, reserved device names, streams, control characters, reparse points and existing hard-linked output files. Metadata inspection fails closed when the path cannot be verified. Missing descendant directories are allowed; directory creation and output writes use literal paths and are revalidated at their boundaries.
- These checks reject unsafe paths observed during validation. They do not guarantee protection against concurrent filesystem changes between validation and use, or cover every possible filesystem alias. Run only in a trusted, isolated checkout.
- Run the direct native regression suite on Windows: `pwsh -NoProfile -NonInteractive -File .github/scripts/Test-DuplicateFunctionCheckPaths.ps1`. The contract suite `python .github/github_actions/tools/test_duplicate_function_action_contract.py -v` exercises the same shipped helper on Windows and requires its exact native pass record. On non-Windows platforms the native behavior test is explicitly skipped; structural and mocked driver tests still run.

## Maintenance

Change this module when the collector source discovery logic or duplicate detection AST traversal changes, then run local validation and applicable workflow readback.
