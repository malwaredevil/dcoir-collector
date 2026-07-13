# DCOIR Operator Tool Engineering Contracts

These contracts apply when creating or suggesting reusable DCOIR operator tools under `.github/operator_tools/github_desktop_lane/`.

## Global contract

1. Prefer reusable tools over one-off chat scripts when a pattern is likely to recur.
2. Put shared behavior in modules, not wrappers.
3. Wrappers may collect parameters, create reviewed config, tee logs, and call a module-owned engine.
4. Use Machine/System environment variables for local paths, tokens, base IDs, repo roots, and downloads folders.
5. Never hardcode or print secrets. Store only canonical environment-variable names and safe references in repo-governed documentation when needed.
6. Produce ChatGPT-friendly ZIP outputs with manifest, index, logs, transcript or tee-equivalent terminal capture, and machine-readable result JSON.
7. Make every tool discoverable in `tool_catalog.json` and linked repo docs.
8. Add a sample manifest or first-run launcher for every recurring-use tool.
9. Include stop conditions and safe first-run mode.
11. Create a timestamped run folder and uploadable diagnostic ZIP even when early configuration validation fails, unless no writable output folder can be found.
12. Log environment variable presence/absence, command context, tool version, PowerShell version, output paths, and error details, but never log secret values.
10. Cleanup or removal recommendations must use DCOIR Delete Queue and dependency order.

## PowerShell contract

- Use PowerShell 5.1-compatible syntax unless a tool explicitly requires PowerShell 7+.
- Use `Set-StrictMode -Version 2.0` and `$ErrorActionPreference = 'Stop'` in modules.
- Put shared logic in `modules/Dcoir.<Domain>/Dcoir.<Domain>.psm1`.
- Keep public wrappers in `scripts/`.
- Use existing `Dcoir.Common` helpers when possible.
- Use UTF-8 no-BOM output for JSON, markdown, and logs.
- Start logging before required secret/config validation so missing environment variables still produce uploadable diagnostics.
- Prefer `Start-Transcript` plus a line-oriented run log; launch examples may also use `2>&1 | Tee-Object` for operator visibility.
- Use approved PowerShell verbs for exported module functions to avoid import warnings.
- Read required local configuration from Machine/System scope.
- Reject obvious placeholders.

## Python contract

- Place reusable Python tools under a dedicated package folder or tool folder with a clear CLI entrypoint.
- Use `argparse` or a small config JSON; avoid hidden interactive prompts for recurring tools.
- Read configuration from environment variables unless an explicit manifest is safer.
- Write deterministic JSON/Markdown outputs and ZIP bundles.
- Include `requirements.txt` only when non-stdlib packages are required.
- Add a smoke-test command that can run without destructive side effects.

## Docker/container contract

- Use Docker only when isolation or dependency reproducibility is materially valuable.
- Provide a Dockerfile or Compose file plus a no-Docker fallback when practical.
- Mount input/output folders explicitly; never bake secrets into images.
- Read tokens and IDs from environment variables or Docker secrets.
- Document cleanup of containers/images/volumes if generated.

## Rust/compiled-tool contract

- Use Rust or compiled languages only when performance, static distribution, or strong typing materially helps.
- Provide source, build instructions, and expected binary output path.
- Keep config through environment variables or explicit config files.
- Emit JSON/Markdown outputs compatible with ChatGPT upload workflows.
- Include a no-network smoke test and a version command.

## JavaScript/TypeScript contract

- Prefer TypeScript for maintained tools.
- Keep dependencies minimal and pinned in `package-lock.json` when used.
- Read configuration from environment variables.
- Emit machine-readable JSON and ChatGPT-friendly ZIP-ready folders.
- Do not require a browser unless the tool is explicitly browser automation.

## Browser automation/userscript contract

- Treat browser snippets as experimental unless packaged as a maintained userscript or extension.
- Avoid auto-hiding or auto-clicking behavior that can select whole chat messages or permission prompts.
- Prefer explicit operator actions and visible restore controls.
- Do not treat browser UI manipulation as durable operational state.

## Discoverability checklist

For every new recurring tool, update:

- `.github/operator_tools/github_desktop_lane/tool_catalog.json`
- `.github/operator_tools/github_desktop_lane/README.md` or a linked doc
- documented canonical environment-variable names for required local configuration
- Active Work Item / Plan status or related issue/PR traceability

If a new language or architecture is introduced, extend this contract document in the same bundle.