# Gemini Behavioral Replay Fixtures

This fixture family supports the broader behavioral replay harness described in issue `#145` and the Agent Designer runtime evaluation work in issue `#398`.

## Purpose

These fixtures are transcript-derived, not raw chat dumps.

Each fixture is expected to:

- preserve the real decision points and turn ordering
- constrain the assistant to only the evidence available at each turn
- encode expected and forbidden behaviors explicitly
- support deterministic scoring and the appropriate live-evidence lane

## Evidence-lane split

Do not collapse raw Gemini API replay and deployed Agent Designer behavior into one evidence class.

### Raw Gemini API replay

The existing `live_gemini` lane calls the Gemini `generateContent` API with fixture-derived prompts. It is useful for model-level comparison and evidence-discipline regressions, but it does not instantiate the governed Prime/sub-agent topology and does not prove deployed Agent Designer orchestration behavior.

The historical governed raw-API comparison split is:

- reference baseline: `gemini-3.1-pro-preview`
- simulated production lane: `gemini-3.5-flash`

Those identifiers describe the existing API replay harness, not the current deployed Agent Designer model.

### Agent Designer capture

Issue `#398` adds `agent_designer_capture` for responses copied from the actual deployed DCOIR Agent in Gemini Enterprise Agent Designer.

Current operator-confirmed deployed baseline:

- model: **Gemini 3.1 Pro**
- enabled external capability: **Enterprise web search only**
- Instructions, topology, starter prompts, and Knowledge attachments: governed Gemini bundle source

Fixtures marked `live_api_eligible: false` in `index.json` must not be treated as raw API live-replay cases. They exist to score actual Agent Designer visible output.

## Re-anchor A/B capture protocol for #398

Use the same governed fixture under paired session conditions. Do not manually reconstruct the bundle configuration before testing.

For a fresh-session pair:

1. **A - no re-anchor:** start a new deployed Agent Designer session and send the fixture user turn directly.
2. **B - with re-anchor:** start a separate new deployed Agent Designer session, send the pinned #398 re-anchor test input below first, then send the same fixture user turn.
3. Capture only the visible assistant response to the fixture turn. Do not include the re-anchor response, UI chrome, hidden state, or analyst commentary in the scored response.
4. Store each capture as a response pack with `mode` set to `agent_designer_capture` and metadata identifying the condition, for example `fresh_without_reanchor` or `fresh_with_reanchor`.

For multi-turn continuity, use the same pattern with the applicable multi-turn fixture: one clean session without re-anchor and one clean session with re-anchor, preserving fixture turn order exactly.

### Pinned #398 re-anchor test input

For the B and D arms of the controlled comparison, use the exact text below. This repository copy is the versioned test input for the capture protocol; do not substitute the current issue body or another starter-prompt variant, so repeated A/B measurements remain comparable even if issue text changes later.

```text
CLICK HERE: Re-Anchor. Enumerate your complete agent hierarchy and operational purpose, detailing your primary function and the specific role of each subordinate agent you orchestrate. Do not show communication between the primary and sub-agents. Do not show CSV, JSON, YAML, or internal routing dialogue in your responses. Do not show duplicative text in the responses. When we are triaging alerts, you must strictly adhere to the output contract during this session. Just show the user facing text. When you must transfer to a sub-agent for an intermediate task or any sub-agent transfers information elsewhere, you MUST pass them an instruction to not output their findings to the screen but instead pass them in the background as internal communications hidden from user facing view and the sub-agents are to be strictly silent. When transferring to the Output Contract Consistency Guard and Report Composer (or any final output agent), that agent will display the final report. When control returns to you (the Prime agent), you MUST NOT output any text, summaries, or acknowledgments. You must remain completely silent and just wait for my next prompt. Verify these conditions before responding. After enumeration, list all of the things you can do and ask me what I want to start on.
```

A minimal captured response pack is:

```json
{
  "schema_version": "gemini_behavioral_replay_response_pack_v1",
  "fixture_id": "dcoir_agent_designer_visible_writer_issue_398",
  "mode": "agent_designer_capture",
  "model_name": "Gemini 3.1 Pro",
  "turns": [
    {
      "turn_id": "turn-001",
      "assistant_response": "<paste only the visible response to the fixture turn>"
    }
  ],
  "metadata": {
    "capture_condition": "fresh_without_reanchor",
    "external_capability": "Enterprise web search only"
  }
}
```

Score a capture with:

```text
python project_sources/gemini/tools/score_gemini_behavioral_replay.py --fixtures-root project_sources/gemini/fixtures/behavioral_replay --response-pack <capture.json> --fixture-id dcoir_agent_designer_visible_writer_issue_398 --expected-mode agent_designer_capture
```

The `python` interpreter form is intentional: the governed Gemini behavioral replay workflow uses `python` after the repository workflow runtime is set up, so the operator-facing scoring example matches that repository execution contract.

The same scorer is used for the collector-procedure fixture by changing the fixture ID.

## Initial fixture family

The original governed fixture family covers failure modes including:

- workflow-state readback discipline
- cleanup/restage/execute/retrieve sequencing
- PowerShell boundedness
- collector contract boundedness
- chunk continuity and artifact recovery
- partial-evidence handling
- BYOVD evidence discipline
- long-transcript continuity
- KQL unique-value miss handling

Issue `#398` adds focused Agent Designer cases for:

- one visible final writer, no internal routing/delegation narration, and no repeated final sections
- complete collector operator procedures that remain multi-step instead of collapsing into singular-triage pacing

## Response-pack contract

A response pack mirrors one replay or capture attempt against one fixture.

At minimum it must include:

- `schema_version`
- `fixture_id`
- `mode`
- `model_name`
- `turns`

Each response-pack turn must include:

- `turn_id`
- `assistant_response`

Allowed replay/capture modes are:

- `deterministic`
- `live_gemini`
- `fallback_emulation`
- `agent_designer_capture`

## Supporting artifacts

This fixture family may include governed supporting artifacts alongside the fixtures themselves.

Deterministic validation uses known-good response packs that must pass and known-bad response packs that must fail, including targeted regression cases for scorer edge conditions. Agent Designer capture scorer self-tests may also use synthetic `agent_designer_capture` packs, but those synthetic packs are validation artifacts only and are never live runtime evidence.

Keep supporting artifacts behaviorally faithful to the governed scenario rather than turning them into synthetic filler.

## Registry

Use `index.json` as the family registry.

Each listed fixture must pass `validate_gemini_behavioral_replay_fixtures.py` before it is used by any replay or scoring lane.
