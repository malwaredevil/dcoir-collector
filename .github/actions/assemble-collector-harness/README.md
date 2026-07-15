# assemble-collector-harness

Composite action scaffold for assembling the generated collector harness from checked-in source parts.

Contract:

- Callers choose the generated harness output path explicitly or accept the default `project_sources/collector/harness/run_DCOIR_Tests.generated.ps1`.
- Callers keep triggers, permissions, runner choice, artifacts, and report paths visible in the workflow file.
- The action assembles `project_sources/collector/harness/source/parts/*.ps1` through `assemble_run_DCOIR_Tests.ps1` and may parse the generated harness for syntax evidence.
- The action must not directly reference `secrets.*`, mutate repository content, or treat the generated harness as maintained source.
- Compensating evidence is the caller-visible step name, explicit output path, assembler stdout markers, and optional generated-harness syntax parse result.
