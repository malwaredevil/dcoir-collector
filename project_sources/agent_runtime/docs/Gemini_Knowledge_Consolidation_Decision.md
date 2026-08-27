# Gemini Knowledge Consolidation Decision

## Decision

**DEFER** consolidation of the active Gemini runtime Knowledge attachments.

The evaluated candidate is statically lossless and reduces the Gemini runtime Knowledge file count from 28 direct canonical attachments to 8 projected files, but there is no candidate-specific live Gemini retrieval or behavioral evidence. Static file-count reduction is not evidence that Gemini will select, retrieve, ground, or apply the consolidated content at least as well as the current direct-attachment model. The active Gemini target therefore remains on all 28 direct canonical attachments.

This decision is an evaluation result, not a rejection of consolidation as a future option. Reconsideration requires candidate-specific live evidence under the gates listed below.

## Scope and authority boundary

- Parent work: #399, stage 7.
- Evaluation work item: #416.
- Live Gemini behavior risk remains tracked separately by #184 and is not weakened or closed by this decision.
- `knowledge/` remains the canonical atomic Knowledge authority.
- `Shared_Agent_Source_Manifest.json` remains the ownership/applicability/projection contract.
- `Knowledge_Projection_Manifest.json` remains the active Knowledge target contract.
- `project_sources/gemini/bundle_source/Gemini_Bundle_Source_Manifest.json` remains the active Gemini bundle contract.
- The active Gemini Knowledge mode remains `direct_canonical_attachments`.
- No candidate projection file is promoted into the active Gemini bundle by this stage, and no live Gemini Agent mutation is performed.

The evaluation intentionally reuses the existing lossless projection/recovery implementation in `tools/project_agent_knowledge.py`. It does not create a second source/hash/reconstruction authority.

## Baseline identity

The active source baseline inherited by the stage-7 branch is repository commit:

`eb5fd8c2110cb242805eba87d3c998d7ed9a8178`

That commit contains the merged stage-6 unified release/parity baseline. The first complete real-repository consolidation evaluation ran at branch head:

`49dd38632124a05e374b50d897579cf13102eb19`

The evaluator was subsequently hardened and integrated into the existing Knowledge self-test command at:

`7601fa878786a300432a99d67362f6618e5bd216`

The canonical manifests were not changed by the evaluation implementation or hardening. The measured manifest identities used by the real-repository evaluation were:

| Surface | SHA-256 |
| --- | --- |
| `Knowledge_Projection_Manifest.json` | `5d7f418a77550c8c4fd5019e4550dc4ec171ed02d5b60132a24cdf8b238561be` |
| `Shared_Agent_Source_Manifest.json` | `80cd4ea44efe2a773b815b79633df244161d3eda104cdcde941a9053b34f8b5a` |
| `Gemini_Bundle_Source_Manifest.json` | `dfe559d6b04ccfd444f0f94d48510acec3e2c22c0b2f1b67603c3eb1df90c56b` |

The active Gemini bundle is version `3_0_5` and uses `stored_source_compile_with_direct_knowledge_attachment_generation`.

## Candidate construction

The candidate is evaluation-only. It groups the **full canonical Gemini source documents**; it does not substitute the provider-neutral split files used by OpenAI packages.

Seven candidate groups reuse the already reviewed `openai_dcoir_analyst` projection taxonomy where a Gemini-applicable canonical source already declares that group. A final `gemini_provider_specific` group preserves the three Gemini-only canonical sources that have no OpenAI DCOIR projection group:

- `knowledge.gemini.ai_design`
- `knowledge.gemini.topology_routing`
- `knowledge.gemini.runtime_bundle`

Each projected source boundary carries the source id, canonical repository path, Git blob SHA, SHA-256, and byte count. The evaluator generates each candidate group in memory, recovers it with the existing projection parser, and requires byte-for-byte source order/content recovery before reporting a clean static result.

## Measured result

The exact-head evaluation run `33044478609` produced the following real-repository result:

| Metric | Active Gemini | Candidate |
| --- | ---: | ---: |
| Runtime Knowledge files | 28 | 8 |
| Canonical sources represented | 28 | 28 |
| Canonical source bytes | 406,462 | 406,462 |
| Candidate bytes including source-boundary metadata | — | 421,244 |
| File-count reduction | — | 20 files / 71.43% |
| Exact source coverage | — | Pass (28/28) |
| Lossless reconstruction | — | Pass |
| Active Gemini contract changed | No | No |

### Candidate groups

| Order | Candidate group | Sources | Bytes | SHA-256 |
| ---: | --- | ---: | ---: | --- |
| 1 | `dcoir_core` | 3 | 15,510 | `ca125ca755b9d1710f8a022d55c8f69df08d7452e1c16c20857a61c9ecf7d415` |
| 2 | `dcoir_elastic_ops` | 1 | 4,641 | `bec4d0108674e0ad0edfb9805673318f56b6f8e35b3fa1e7f8863bcb3be918d1` |
| 3 | `dcoir_collection` | 7 | 65,962 | `76576435e57cd4567557b611adc486a7841153139e37b4eac283f1acce96ef60` |
| 4 | `dcoir_artifacts` | 1 | 9,656 | `820eb6a5bd51340825b48c816bcdb3ee78db6e1e53e7f1216cb8e19d5401fe0a` |
| 5 | `dcoir_ioc_enrichment` | 1 | 2,831 | `2ad8bbe76ec698ef233f368773ad91b59b2e606ab05ac1b35876950312ca93d4` |
| 6 | `dcoir_elastic_reference` | 2 | 79,720 | `e7197e2068dd2427ee14e82645ebd371163e3e12d9e0c9db530d88f5363c2cff` |
| 7 | `dcoir_osquery_reference` | 10 | 234,722 | `2c954d86f0e954a5a9087d8366cf693047ecbcf3813bfe755a4d7b2ef55689d3` |
| 8 | `gemini_provider_specific` | 3 | 8,202 | `71347d9591c1a1a17bae633d6a62b1719b73a3ba5f4e7de94b2c3860d86c2622` |

The largest candidate is `dcoir_osquery_reference`: 10 canonical sources and 234,722 bytes. Its static reconstruction is lossless, but its effect on Gemini retrieval granularity is unproven.

## Benefits demonstrated by static evidence

- The candidate reduces runtime Knowledge attachments from 28 to 8 while retaining the 28 canonical atomic sources unchanged.
- Every source remains individually attributable through source id, canonical path, Git blob SHA, SHA-256, and byte count.
- Candidate grouping reuses the existing DCOIR projection taxonomy instead of introducing another hand-maintained taxonomy.
- Gemini-only topology/runtime/maintainer Knowledge remains explicitly present rather than being accidentally replaced by the OpenAI projection shape.
- The evaluator is read-only: candidate outputs are virtual evaluation surfaces and do not modify the active Gemini bundle or canonical Knowledge.

## Risks and unresolved evidence

- Consolidation changes Gemini's retrieval granularity from 28 attachments to 8 larger mixed-source attachments even though the source payload is recoverable byte-for-byte.
- The largest proposed group combines 10 sources into approximately 234.7 KB. Static reconstruction does not show whether Gemini will retrieve the correct embedded source boundary for a given investigation question.
- Repository tests can prove source coverage, provenance, deterministic projection, and reconstruction; they cannot prove live Gemini retrieval selection, grounding quality, or final response behavior.
- #184 remains open with unresolved live Gemini behavioral replay failures. This evaluation does not attribute those failures to Knowledge file count and does not claim consolidation would fix them.
- No live Gemini environment was deployed with this candidate, so there is no candidate-specific retrieval/behavior run to support promotion.

## Promotion gates for reconsideration

A future **PROMOTE** decision requires all of the following evidence rather than file-count reduction alone:

1. A specifically identified candidate build that is reproducible from the canonical source contract and reports the same lossless 28/28 source coverage.
2. A controlled Gemini deployment/readback showing the intended 8-file candidate is actually attached, with the projected file hashes/source maps recorded.
3. Candidate-specific retrieval tests that exercise material from every candidate group, including multiple independent sources inside the 10-source OSQuery group and the Gemini-only provider-specific group.
4. Candidate-specific behavioral replay against the existing #184 scorer/safety gates without weakening thresholds, suppressing failing cases, or treating workflow execution success as behavioral success.
5. No regression in provenance, evidence labeling, tool-boundary behavior, investigation completeness, or required output contracts.
6. A recorded live evidence run URL/identifier. The evaluator must then be rerun with `--live-evidence-status pass --live-evidence-run <evidence>` before a repository-side activation is considered.
7. A separate governed activation/deployment change with its own validation and live readback. Passing this evaluation alone must never silently change `Knowledge_Projection_Manifest.json` or the live Gemini Agent.

A candidate-specific live failure should be recorded with `--live-evidence-status fail --live-evidence-run <evidence>` and keeps the decision at **DEFER**. Blocking static source/projection errors produce **REVISE**.

## Validation evidence

Initial real-repository evaluation:

- GitHub Actions run: `33044478609`
- evaluated head: `49dd38632124a05e374b50d897579cf13102eb19`
- artifact: `9635093749`
- artifact SHA-256: `3e578015bf8eb521567a9a7bcda602aa6b3c4ec8dab4206c3ae23d52d57c2334`
- evaluator self-tests: 18/18
- existing Knowledge projection self-tests: 10/10
- active Knowledge projection check: pass
- real-repository JSON and Markdown evaluation: pass
- tracked repository mutation: none

Hardening and governed validation integration:

- GitHub Actions run: `33044669478`
- hardened branch head: `7601fa878786a300432a99d67362f6618e5bd216`
- artifact: `9635160168`
- artifact SHA-256: `8b3f02548d5ef78c54c71900f93481ab392f8c45261cd0dd4c4f8fe155bcc322`
- standalone evaluator self-tests: 20/20
- existing governed `project_agent_knowledge_selftest.py`: 30/30 (20 evaluator + 10 existing projection tests)
- active Knowledge projection check: pass
- real-repository evaluator: pass
- `git diff --check`: pass

The evaluator self-tests are imported by the existing Knowledge projection self-test entry point, so the established agent-runtime validation lane exercises them without workflow-YAML changes.

## Next action

Retain the active **28 direct canonical Gemini Knowledge attachments**. Do not deploy the 8-file candidate as part of #416. Reconsider consolidation only when candidate-specific live retrieval and behavior evidence can satisfy the promotion gates above.
