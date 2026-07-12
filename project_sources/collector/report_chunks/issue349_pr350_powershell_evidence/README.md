# Issue #349 / PR #350 PowerShell Evidence Chunks

This directory contains connector-sized additive chunks for generated PowerShell evidence reports. The chunks are intentionally smaller than the canonical report files so future connector-only sessions can read, validate, and refresh evidence without relying on oversized monolithic report downloads.

These chunks now mirror the canonical generated reports under `project_sources/collector/*.json` and `project_sources/collector/*.md` when `reassemble_powershell_evidence_chunks.py --compare-canonical --require-canonical-parity` passes. Use that validator before treating the sidecar as a byte-exact replacement source.

Current regenerated sidecar scope: the PR #350 15,000-byte source-policy pass, including the 02D1C and 04E3 collector splits, loader/manifest/required-surface updates, connector-sized tooling modules, and aligned canonical PowerShell evidence reports.

Sidecar chunks use a conservative 14,000-byte target so each generated evidence slice remains below the repository's 15,000-byte connector-safe policy margin.
