# Agent Release, Parity, Deployment, and Readback

This procedure is the human-operated release and readback lane for EPIC #399. GitHub remains canonical for shared behavior, knowledge, provider adapters, build tooling, validation tooling, and generated package manifests. The Gemini and OpenAI target surfaces are deployment/readback destinations, not independent source authorities.

## Static release/parity gate

From the approved repository commit, run the existing target checks and then the unified report:

```bash
python project_sources/agent_runtime/tools/validate_shared_agent_source_contract.py
python project_sources/agent_runtime/tools/materialize_agent_behavior_adapters.py --check
python project_sources/agent_runtime/tools/project_agent_knowledge.py --check
python project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py --check
python project_sources/agent_runtime/tools/build_openai_usb_reporting.py --check
python project_sources/agent_runtime/tests/report_agent_release_parity_selftest.py
python project_sources/agent_runtime/tools/report_agent_release_parity.py
```

The unified report is a static-repository release gate. It records the source/review commit, hashes the three source-contract manifests, inventories the three governed targets, reuses the existing target checkers for drift truth, classifies provider-specific differences separately from blocking gaps, and records any live/manual evidence that is still pending. A static pass does **not** prove that either OpenAI GPT was updated successfully or that live GPT-5.4 behavior matches the package.

Before deployment, archive the JSON and Markdown report from the applicable validation output directory with the GitHub run/readback evidence for the reviewed commit. Do not continue to manual deployment while the report contains a blocking static parity gap.

## AFRICOM DCOIR Analyst manual deployment

Use only the generated package under `project_sources/agent_runtime/generated/packages/openai_dcoir_analyst/` and the seven Knowledge files enumerated by that package manifest.

1. Confirm the approved commit and a passing static release/parity report.
2. Run `python project_sources/agent_runtime/tools/build_openai_dcoir_analyst.py --check` immediately before deployment.
3. Open the company OpenAI/ChatGPT WebUI and edit the existing `AFRICOM DCOIR Analyst` GPT. Do not create a replacement target unless the operator explicitly intends a new GPT.
4. Apply the name, description, conversation starters, model/runtime selection, and capability settings from `GPT_Configuration.json`.
5. Replace the WebUI Instructions with the complete generated `Instructions.md` contents. Do not hand-edit generated wording during the normal release lane.
6. Remove stale Knowledge attachments and upload exactly the seven ordered Knowledge paths and filenames listed by the package manifest. Do not upload maintainer-only Gemini material.
7. Verify that unsupported capabilities remain disabled: web search, Code Interpreter/Data Analysis, Canvas, image generation, Apps, Actions, live Elastic access, live collector execution, GitHub/Supabase connectors, and persistent cross-conversation memory unless a separately approved capability update changes the canonical contract.
8. Save/update the GPT.
9. Perform the live readback steps below before claiming deployment or live parity complete.

## AFRICOM USB Reporting manual deployment

Use only the generated package under `project_sources/agent_runtime/generated/packages/openai_usb_reporting/` and the two Knowledge files enumerated by that package manifest.

1. Confirm the approved commit and a passing static release/parity report.
2. Run `python project_sources/agent_runtime/tools/build_openai_usb_reporting.py --check` immediately before deployment.
3. Open the company OpenAI/ChatGPT WebUI and edit the existing `AFRICOM USB Reporting` GPT. Do not convert the general DCOIR Analyst GPT into the USB target.
4. Apply the name, description, conversation starters, model/runtime selection, and capability settings from `GPT_Configuration.json`.
5. Replace the WebUI Instructions with the complete generated `Instructions.md` contents. Do not hand-edit generated wording during the normal release lane.
6. Remove stale Knowledge attachments and upload exactly the two ordered Knowledge paths and filenames listed by the package manifest.
7. Verify that the same unsupported OpenAI capabilities remain disabled unless a separately approved canonical capability change exists.
8. Save/update the GPT.
9. Perform the live readback steps below before claiming deployment or live parity complete.

## Live readback evidence

For each OpenAI GPT, record enough evidence to bind the live target back to the approved repository release without placing secrets or sensitive case data in GitHub.

Required readback:

1. Target name and unambiguous WebUI identity. Record a stable target identifier only when the platform exposes one safely; never invent an identifier.
2. Date/time of deployment and the approved repository commit.
3. Model/runtime shown by the WebUI.
4. Name, description, conversation starters, and capability-toggle state compared with `GPT_Configuration.json`.
5. Full Instructions readback compared with the generated `Instructions.md`. If the WebUI permits copying the full text back out, compare exact text or a locally computed SHA-256. If it does not, record that limitation and perform a complete visual/text review.
6. Knowledge attachment filenames and count compared with the package manifest: seven for DCOIR Analyst and two for USB Reporting.
7. A small live behavioral smoke set appropriate to the target. At minimum verify identity/scope, unsupported-capability truthfulness, evidence-versus-inference language, and the target-specific redirect/confirmation behavior represented by its offline cases.
8. Any discrepancy, editor normalization, platform limitation, or unresolved behavior as an explicit gap rather than silently treating it as parity.

Repository static parity, manual deployment completion, and live behavior readback are separate evidence states. Do not mark live parity complete because repository checks passed. The generated OpenAI package manifests currently record `live_webui_validation_performed: false`; changing that status requires separately governed evidence and source reconciliation rather than an ad-hoc target edit.

## Direct-target hotfix reverse reconciliation

A direct Gemini or OpenAI target edit is an emergency hotfix, not a new source of truth. Use this sequence before the next release:

1. Capture the exact target-side change and why it was made, including the affected target and deployment evidence.
2. Identify the owning canonical source: shared behavior module, atomic `knowledge/` source, provider-neutral knowledge module, provider adapter, or target configuration source.
3. Reproduce the intended change in the canonical source through a governed GitHub issue/branch/PR. Do not copy target text blindly into another provider.
4. Update any affected manifests, source snapshots, coverage maps, or projection membership required by the canonical change.
5. Rematerialize every affected generated target, not only the target that received the emergency edit.
6. Run the existing target checks, the unified reporter self-test, and the unified release/parity report. Resolve every blocking static parity gap.
7. Compare the newly generated output with the intended emergency behavior. If the generated output does not preserve the intended fix, revise the canonical source rather than retaining an unexplained target-only fork.
8. Redeploy the generated package to each affected live target and complete the live readback evidence again.
9. Record the reconciliation commit, deployment/readback evidence, and any accepted residual platform difference. Only then is the temporary target drift retired.

## Evidence boundaries

- Generated packages and reports are reproducible evidence surfaces, not editable authority.
- Provider-specific topology, runtime, and capability differences declared by the shared source contract are governed differences, not automatically semantic drift.
- Missing, extra, stale, contradictory, or failed target evidence is a parity gap until resolved or explicitly accepted through a separately governed decision.
- Static offline behavioral cases do not prove live hosted-model behavior.
- The release reporter does not mutate Gemini, OpenAI, Supabase, GitHub configuration, or any live target.
