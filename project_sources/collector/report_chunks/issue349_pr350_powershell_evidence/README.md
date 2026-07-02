# Issue #349 / PR #350 PowerShell Evidence Chunks

This directory contains connector-sized additive chunks for generated PowerShell evidence reports. The chunks are intentionally smaller than the canonical report files so future connector-only sessions can read, validate, and refresh evidence without relying on oversized monolithic report downloads.

These chunks do not replace the canonical generated reports under `project_sources/collector/*.json` and `project_sources/collector/*.md` unless a future validation lane explicitly requires canonical parity. Use `project_sources/collector/tools/reassemble_powershell_evidence_chunks.py` to validate chunk integrity and reconstruct reports for review.

Current regenerated sidecar scope: collector 04F source split into 04F1/04F2, with loader, manifest, required-surface profile, harness capability metadata, event-window validator, and capability matrix references aligned.
