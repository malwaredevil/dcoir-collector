#!/usr/bin/env python3
"""Bounded HTTP 429 unreadable-body regression cases for all replay clients.

These unittest mixin methods use the shared transport harness in
transport_retry_safety_selftest.py. Its standard entrypoint runs both cases.
"""
from __future__ import annotations

import io
import urllib.error


class UnreadableHttp429Cases:
    def test_unreadable_http_429_body_keeps_safe_marker_and_retries(self):
        class FailingErrorBody(io.BytesIO):
            def read(self, *args, **kwargs):
                raise TimeoutError("secret error-body diagnostic")

        for engine in ("gemini_replay", "gemini_compare", "openai_shared"):
            with self.subTest(engine=engine):
                requests = []

                def opener(request, *, timeout):
                    requests.append(request)
                    if len(requests) == 1:
                        raise urllib.error.HTTPError(
                            "https://invalid.test/v1", 429, "mock", {}, FailingErrorBody(),
                        )
                    return self._success(engine)

                outcome = self._call(engine, opener)
                self.assertTrue(outcome["ok"], outcome)
                self.assertEqual(len(requests), 2)
                self.assertEqual(len(outcome["attempts"]), 2)
                self.assertEqual(outcome["attempts"][0]["status_code"], 429)
                self.assertEqual(
                    outcome["attempts"][0]["error_body_error"],
                    "error_body_unavailable",
                )
                self.assertNotIn("secret error-body diagnostic", repr(outcome))

    def test_unreadable_http_429_retries_remain_bounded(self):
        class FailingErrorBody(io.BytesIO):
            def read(self, *args, **kwargs):
                raise TimeoutError("secret error-body diagnostic")

        for engine in ("gemini_replay", "gemini_compare", "openai_shared"):
            with self.subTest(engine=engine):
                requests = []

                def opener(request, *, timeout):
                    requests.append(request)
                    raise urllib.error.HTTPError(
                        "https://invalid.test/v1", 429, "mock", {}, FailingErrorBody(),
                    )

                outcome = self._call(engine, opener)
                self.assertFalse(outcome["ok"])
                self.assertEqual(outcome["error"], "http_429")
                self.assertEqual(len(requests), 3)
                self.assertEqual(len(outcome["attempts"]), 3)
                self.assertTrue(all(
                    attempt["error_body_error"] == "error_body_unavailable"
                    for attempt in outcome["attempts"]
                ))
                self.assertNotIn("secret error-body diagnostic", repr(outcome))
