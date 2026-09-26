# USB Reporting Test Artifacts

Reusable sanitized inputs for the governed weekly USB Violations reporting workflow.

## Intended targets

- Gemini Agent: USB Violations Report Composer (`sub_agent.11`)
- OpenAI: `openai_usb_reporting` / AFRICOM USB Reporting GPT

The two runtimes may use different internal topology. These fixtures exist to compare the **operator-visible reporting behavior** against the same governed source data.

## Canonical behavior sources

- `project_sources/gemini/bundle_source/01_GEMINI_AGENT_BUILD/Sub_Agent_11_USB_Violations_Report_Composer.md.txt`
- `project_sources/agent_runtime/provider_adapters/openai_usb_reporting/Instructions.md`
- `project_sources/agent_runtime/Shared_Agent_Source_Manifest.json`

Those sources own the reporting contract. This directory owns stable test inputs and discovery metadata, not a duplicate instruction contract.

## Fixtures

### `inputs/violations_sanitized_nipr.csv`

Seven sanitized INCN rows. Use this for the NIPR-only path. The fixture intentionally omits the previous week's overall USB violation count so the runtime can demonstrate the governed clarification behavior before producing the final Recipient / Subject / Message Draft output.

### `inputs/violations_sanitized_mixed.csv`

The same seven-row shape, with five INCN rows and two INCS rows. Use this to exercise the split NIPR/SIPR reporting path and SIPR transfer instructions.

## Manual testing

Start a clean runtime session, provide the fixture as the USB violation input, and do not pre-answer information the governed workflow is expected to request. Capture the complete visible interaction.

A conforming runtime should stay in the narrow report-composer workflow, ask only required bounded clarification questions, and then produce the governed templated report/email output. Generic BLUF or analyst-assistant scaffolding is not equivalent behavior.

## Automated testing

Automation should load artifact paths and hashes from `manifest.json` rather than hard-coding ad hoc copies. Scoring should validate semantic construction of the required output, not mere marker presence.

## Privacy

These CSVs are sanitized regression fixtures derived from an operator-provided source structure. User, Location, Computer Name, User Information, and SNOW ticket identifiers are synthetic. Serial Number values are intentionally retained under operator approval because they are randomized device identifiers for this test context.
