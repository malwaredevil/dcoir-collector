#!/usr/bin/env python3
"""No-network request-contract regressions for Gemini and OpenAI replay clients."""
from __future__ import annotations

import argparse
import json
import unittest
from unittest.mock import patch

from lib import gemini_behavioral_replay_live as gemini_replay
from lib import gemini_behavioral_replay_models as gemini_models
from lib import openai_dcoir_replay_live as openai_shared
import run_gemini_model_comparison as comparison_runner


class MockResponse:
    status = 200

    def __init__(self, content: bytes):
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.content


class TransportRequestContractTests(unittest.TestCase):
    def test_gemini_comparison_uses_the_canonical_client(self):
        self.assertIs(comparison_runner.call_gemini, gemini_replay.call_gemini)
        self.assertEqual(
            comparison_runner.DEFAULT_API_BASE, gemini_models.DEFAULT_API_BASE,
        )

    def test_gemini_request_contracts_and_called_model(self):
        for engine in ("gemini_replay", "gemini_compare"):
            with self.subTest(engine=engine):
                requests = []

                def opener(request, *, timeout):
                    requests.append((request, timeout))
                    return MockResponse(json.dumps({
                        "candidates": [{"content": {"parts": [{"text": "ready"}]}}],
                        "usageMetadata": {"totalTokenCount": 17},
                    }).encode("utf-8"))

                args = argparse.Namespace(
                    api_base="https://invalid.test/v1", max_retries=3,
                    retry_base_seconds=0.0, temperature=0.0,
                )
                with patch.object(
                    gemini_replay.urllib.request, "urlopen", side_effect=opener,
                ), patch.object(gemini_replay.time, "sleep", return_value=None):
                    if engine == "gemini_replay":
                        result = gemini_replay.call_gemini(
                            "fake-key", args, "mock-model", "prompt",
                        )
                    else:
                        result = comparison_runner.call_gemini(
                            "fake-key", args, "models/mock-model", "prompt",
                            generation_config={
                                "temperature": 0.0,
                                "responseMimeType": "application/json",
                            },
                        )
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["response_text"], "ready")
                self.assertEqual(result["usage_metadata"], {"totalTokenCount": 17})
                self.assertEqual(result["called_model"], "models/mock-model")
                self.assertEqual(len(requests), 1)
                request, timeout = requests[0]
                self.assertEqual(timeout, 120)
                self.assertEqual(request.get_method(), "POST")
                self.assertEqual(
                    request.full_url,
                    "https://invalid.test/v1/models/mock-model:generateContent",
                )
                body = json.loads(request.data)
                self.assertEqual(body["contents"], [{"parts": [{"text": "prompt"}]}])
                if engine == "gemini_replay":
                    self.assertEqual(body["generationConfig"], {
                        "temperature": 0.0, "candidateCount": 1,
                    })
                else:
                    self.assertEqual(body["generationConfig"], {
                        "temperature": 0.0, "responseMimeType": "application/json",
                    })

    def test_invalid_model_reference_cannot_generate(self):
        args = argparse.Namespace(
            api_base="https://invalid.test/v1", max_retries=3,
            retry_base_seconds=0.0, temperature=0.0,
        )
        for model in (
            "", "models/nested/model", "gemini-demo:generateContent",
            "gemini-demo?query=1", "models/gemini-demo#fragment",
            "gemini-demo%2Fhidden", "gemini-3.5-flash-latest",
        ):
            with self.subTest(model=model):
                with patch.object(
                    gemini_replay.urllib.request, "urlopen",
                    side_effect=AssertionError("unexpected network"),
                ):
                    result = gemini_replay.call_gemini(
                        "fake-key", args, model, "prompt",
                    )
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["error"], "invalid_model_name")
                    self.assertEqual(result["attempts"], [])

    def test_both_openai_replays_share_the_guarded_client(self):
        import run_openai_usb_reporting_behavioral_replay as usb_replay
        self.assertIs(usb_replay.call_openai_body, openai_shared.call_openai_body)
        self.assertIs(
            openai_shared.make_pack.__globals__["call_openai_body"],
            openai_shared.call_openai_body,
        )


if __name__ == "__main__":
    unittest.main()
