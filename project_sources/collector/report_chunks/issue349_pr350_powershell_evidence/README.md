# Issue #349 / PR #350 PowerShell Evidence Chunks

This directory contains connector-sized additive chunks for generated PowerShell evidence reports. The chunks are intentionally smaller than the canonical report files so future connector-only sessions can read, validate, and refresh evidence without relying on oversized monolithic report downloads.

These chunks now mirror the canonical generated reports under `project_sources/collector/*.json` and `project_sources/collector/*.md` when `reassemble_powershell_evidence_chunks.py --compare-canonical --require-canonical-parity` passes. Use that validator before treating the sidecar as a byte-exact replacement source.

Current regenerated sidecar scope: collector 05A2/05A3 main-entry split, with loader, manifest, required-surface profile, runtime validators, reachability helper modules, and canonical PowerShell evidence reports aligned.
