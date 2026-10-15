#!/usr/bin/env python3
"""No-network replay POST retry regressions for Gemini and both OpenAI GPTs.

Run directly: python project_sources/gemini/tools/transport_retry_safety_selftest.py
No live provider calls or credentials. Unknown-outcome errors fail closed;
only explicit HTTP 429 rate limiting retains its bounded retry path.
"""
from __future__ import annotations

import argparse
import io
import json
import urllib.error
import unittest
from unittest.mock import patch

from lib import gemini_behavioral_replay_live as gemini_replay
from lib import gemini_model_comparison_api as gemini_compare
from lib import openai_dcoir_replay_live as openai_shared


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


class TransportRetrySafetyTests(unittest.TestCase):
    def _call(self, engine: str, opener):
        args = argparse.Namespace(
            api_base="https://invalid.test/v1", max_retries=3,
            retry_base_seconds=0.0, temperature=0.0,
        )
        # All three clients call urllib.request.urlopen; patch the exact HTTP
        # boundary, not the scorer or the generation implementation.
        with patch.object(gemini_replay.urllib.request, "urlopen", side_effect=opener), \
             patch.object(gemini_replay.time, "sleep", return_value=None):
            if engine == "gemini_replay":
                return gemini_replay.call_gemini("fake-key", args, "mock-model", "prompt")
            if engine == "gemini_compare":
                return gemini_compare.call_model(
                    "fake-key", args.api_base, {"name": "models/mock-model"},
                    "prompt", 0.0, 3, 0.0,
                )
            if engine == "openai_shared":
                return openai_shared.call_openai_body(
                    "fake-key", "", args, {"model": "mock-model"},
                )
            raise AssertionError(f"Unknown client: {engine}")

    @staticmethod
    def _failure(kind: str):
        if kind == "timeout":
            return TimeoutError("read timed out")
        if kind == "wrapped_timeout":
            return urllib.error.URLError(TimeoutError("read timed out"))
        if kind == "urlerror":
            return urllib.error.URLError("connection refused")
        if kind == "runtime_error":
            return RuntimeError("unexpected transport error")
        if kind in ("http_429", "http_500", "http_502", "http_503", "http_504"):
            code = int(kind.split("_")[1])
            return urllib.error.HTTPError(
                "https://invalid.test/v1", code, "mock", {},
                io.BytesIO(b"mock"),
            )
        raise AssertionError(kind)

    @staticmethod
    def _success(engine: str):
        if engine == "openai_shared":
            payload = {"id": "resp_mock123", "status": "completed", "output_text": "good", "output": []}
        else:
            payload = {"candidates": [{"content": {"parts": [{"text": "good"}]}}]}
        return MockResponse(json.dumps(payload).encode("utf-8"))

    def test_failures_are_bounded_and_accounted_for(self):
        expected = {
            "gemini_replay": (1, 1, 1, 1, 3, 1, 1, 1, 1, 1),
            "gemini_compare": (1, 1, 1, 1, 3, 1, 1, 1, 1, 1),
            "openai_shared": (1, 1, 1, 1, 3, 1, 1, 1, 1, 1),
        }
        kinds = (
            "timeout", "wrapped_timeout", "urlerror", "runtime_error",
            "http_429", "http_500", "http_502", "http_503", "http_504",
            "malformed_http_200",
        )
        for engine, counts in expected.items():
            for kind, count in zip(kinds, counts):
                with self.subTest(engine=engine, failure=kind):
                    seen = []

                    def urlopen(request, *, timeout):
                        self.assertEqual(request.get_method(), "POST")
                        self.assertTrue(request.data)
                        seen.append(request)
                        if kind == "malformed_http_200":
                            return MockResponse(b"{broken-json")
                        raise self._failure(kind)

                    result = self._call(engine, urlopen)
                    self.assertFalse(result["ok"])
                    self.assertEqual(len(seen), count)
                    self.assertEqual(len(result["attempts"]), count)
                    if kind in ("timeout", "wrapped_timeout") and engine == "openai_shared":
                        self.assertEqual(result["error"], "read_timeout")

    def test_429_then_success_still_recovers(self):
        for engine in ("gemini_replay", "gemini_compare", "openai_shared"):
            with self.subTest(engine=engine):
                seen = []

                def urlopen(request, *, timeout):
                    seen.append(request)
                    if len(seen) == 1:
                        raise self._failure("http_429")
                    return self._success(engine)

                result = self._call(engine, urlopen)
                self.assertTrue(result["ok"], result)
                self.assertEqual(len(seen), 2)
                self.assertEqual(len(result["attempts"]), 2)
                self.assertEqual(result["response_text"], "good")

    def test_rate_limit_then_ambiguous_outcome_never_posts_third_time(self):
        # 429 permits one bounded retry. If that attempt might have been
        # accepted, it must fail rather than send a third generation POST.
        for engine in ("gemini_replay", "gemini_compare", "openai_shared"):
            for kind in (
                "timeout", "wrapped_timeout", "urlerror", "runtime_error",
                "http_503", "malformed_http_200",
            ):
                with self.subTest(engine=engine, next_failure=kind):
                    seen = []

                    def urlopen(request, *, timeout):
                        seen.append(request)
                        if len(seen) == 1:
                            raise self._failure("http_429")
                        if kind == "malformed_http_200":
                            return MockResponse(b"{broken-json")
                        raise self._failure(kind)

                    result = self._call(engine, urlopen)
                    self.assertFalse(result["ok"])
                    self.assertEqual(len(seen), 2)
                    self.assertEqual(len(result["attempts"]), 2)

    def test_5xx_never_resends_even_if_second_attempt_would_succeed(self):
        for engine in ("gemini_replay", "gemini_compare", "openai_shared"):
            for code in ("http_500", "http_502", "http_503", "http_504"):
                with self.subTest(engine=engine, status=code):
                    seen = []

                    def urlopen(request, *, timeout):
                        seen.append(request)
                        if len(seen) == 1:
                            raise self._failure(code)
                        return self._success(engine)

                    result = self._call(engine, urlopen)
                    self.assertFalse(result["ok"], result)
                    self.assertEqual(result["error"], code)
                    self.assertEqual(len(seen), 1)
                    self.assertEqual(len(result["attempts"]), 1)

    def test_one_success_is_one_request(self):
        for engine in ("gemini_replay", "gemini_compare", "openai_shared"):
            with self.subTest(engine=engine):
                seen = []

                def urlopen(request, *, timeout):
                    seen.append(request)
                    return self._success(engine)

                result = self._call(engine, urlopen)
                self.assertTrue(result["ok"], result)
                self.assertEqual(len(seen), 1)
                self.assertEqual(len(result["attempts"]), 1)

    def test_both_openai_replays_share_the_guarded_client(self):
        import run_openai_usb_reporting_behavioral_replay as usb_replay
        self.assertIs(usb_replay.call_openai_body, openai_shared.call_openai_body)
        self.assertIs(
            openai_shared.make_pack.__globals__["call_openai_body"],
            openai_shared.call_openai_body,
        )


if __name__ == "__main__":
    unittest.main()
