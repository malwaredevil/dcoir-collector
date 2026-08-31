# Issue #456 — DCOIR v39 pre-blind checkpoint

- v39 focused validation: run `33392385497`, success.
- v39 full governed validation: run `33392480481`, success; artifact `9758026746`.
- semantic recall corpus: 12 cases, 10 finding classes, 2 clean classes.
- precision regression: 2/2 context precision; 5/5 known false positives suppressed; 5/5 known true positives retained; no regressions.
- actual CodeQL Security: run `33392713309`; Python, GitHub Actions, and aggregate jobs all success.
- CodeQL source provenance: no DCOIR runtime/config source changed after commit `c5fb0b9aecd2bff770993429195c4913e5bd4000` through scan head `93ba8bf0948c07ebf89732cba6415a71dae66975`.
- PR #448 remains open/draft at exact head `6355adf7b560736f5c202e251070b52516c3a1e6`.
- Blind target remains unchanged: `explicit_no_mix` still omits `skip_negated=True`.
- Next: trigger a fresh hint-free `/dcoir-review deep debug` on unchanged PR #448 and require recall → v39 confidence normalization if needed → v21 verification → v38 independent repair critic → safe GitHub suggestion/publication.
