#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib.gemini_behavioral_replay_runner import load_fixtures, load_response_pack
from lib.gemini_behavioral_replay_schema import ValidationMessage, validate_response_pack_shape
from lib.gemini_behavioral_replay_scoring import score_response_pack


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures-root", required=True)
    parser.add_argument("--response-pack", required=True)
    parser.add_argument("--fixture-id", required=True)
    parser.add_argument("--expected-mode", default="deterministic")
    args = parser.parse_args()

    fixtures = load_fixtures(Path(args.fixtures_root).resolve(), Path(__file__), args.fixture_id)
    if len(fixtures) != 1:
        raise SystemExit(f"Expected exactly one fixture for fixture_id={args.fixture_id!r}, found {len(fixtures)}")
    fixture = fixtures[0]["fixture"]
    response_pack = load_response_pack(Path(args.response_pack).resolve())
    validation_messages = validate_response_pack_shape(response_pack, fixture)
    if args.expected_mode and response_pack.get("mode") != args.expected_mode:
        validation_messages.append(
            ValidationMessage(
                "error",
                f"Response pack mode {response_pack.get('mode')!r} does not match expected mode {args.expected_mode!r}.",
            )
        )
    if any(message.level == "error" for message in validation_messages):
        payload = {"success": False, "validation_messages": [{"level": message.level, "message": message.message} for message in validation_messages]}
        print(json.dumps(payload, indent=2))
        return 1
    result = score_response_pack(fixture, response_pack)
    payload = {
        "success": result["success"],
        "validation_messages": [{"level": message.level, "message": message.message} for message in validation_messages],
        "result": result,
    }
    print(json.dumps(payload, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
