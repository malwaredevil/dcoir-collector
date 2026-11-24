DCOIR generation_validation

Purpose
- Deterministic verification and QC support for generated standalone prompt bundles, Gemini bundles, and collector-facing attachment sets.

Contents
- Gemini bundle verification is owned by project_sources/gemini/tools/validate_dcoir_gemini_bundle.py. The legacy
  verify_dcoir_bundle.py checked a standalone-prompt layout that no builder produces and was removed (issue #223).
- DCOIR_Generated_Bundle_QC_And_Verification_Spec_v1_0_0.txt: human-readable verification and QC rules
- DCOIR_Gemini_And_Standalone_Test_Plan_v1_0_0.txt: test plan for collector, harness, Gemini, and standalone paths
- fixtures/: fake alert and fake collector artifacts for bounded pre-live testing
