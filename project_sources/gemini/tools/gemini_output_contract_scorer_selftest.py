#!/usr/bin/env python3
"""Offline scorer tests, NOT a claim that a compiled bundle was evaluated."""
from __future__ import annotations

import unittest

from lib.gemini_behavioral_replay_output_contract_diagnostics import analyze_visible_output
from lib.gemini_behavioral_replay_scoring import detect_anomalies
from lib.gemini_behavioral_replay_text_scoring import CONTRADICTION_PAIRS
from lib import gemini_model_comparison_eval


# Original three concrete cases from the retired release-only canned validator.
CASES = [{'id': 'GEM-OUT-LEAK-001',
  'expected': 'reject',
  'must_trigger': ['malformed_preamble', 'internal_state_leakage', 'yaml_or_json_scaffold'],
  'response': 'readiness_confirmed: false\n'
              "enterprise_web_search_status: 'unknown'\n"
              'missing_minimum_evidence:\n'
              '  - analyst-facing answer not started\n'
              '```yaml\n'
              'routing_state:\n'
              '  active_branch: continue\n'
              '  candidate_datasets:\n'
              '    - elastic_alert\n'
              '  planner_payloads:\n'
              '    - collect bundle review\n'
              '```\n'
              '## BLUF\n'
              'Current evidence supports continued review of the alert.\n'
              '\n'
              '## FACTS AND SOURCES\n'
              '- Uploaded alert evidence was reviewed.\n'
              '\n'
              '## ANALYSIS\n'
              '- The operator-facing answer should have started here without the leaked '
              'preamble.\n'},
 {'id': 'GEM-OUT-DUPE-001',
  'expected': 'reject',
  'must_trigger': ['duplicate_final_sections'],
  'response': '## BLUF\n'
              'Current evidence supports a benign explanation for the observed activity.\n'
              '\n'
              '## FACTS AND SOURCES\n'
              '- Uploaded alert evidence reviewed.\n'
              '\n'
              '## ANALYSIS\n'
              '- No malicious follow-on evidence was observed in the reviewed material.\n'
              '\n'
              '## BLUF\n'
              'Current evidence supports a benign explanation for the observed activity.\n'
              '\n'
              '## FACTS AND SOURCES\n'
              '- Uploaded alert evidence reviewed.\n'
              '\n'
              '## ANALYSIS\n'
              '- No malicious follow-on evidence was observed in the reviewed material.\n'},
 {'id': 'GEM-OUT-CONTROL-001',
  'expected': 'accept',
  'response': '## BLUF\n'
              'Current evidence supports continued review because the alert evidence alone does '
              'not prove a malicious outcome.\n'
              '\n'
              '## FACTS AND SOURCES\n'
              '- Uploaded alert evidence was reviewed.\n'
              '- No additional grounded source was returned in this example.\n'
              '\n'
              '## ANALYSIS\n'
              '- The current record supports a bounded continue posture.\n'
              '\n'
              '## SINGULAR TRIAGE COMMAND\n'
              '```text\n'
              'get-file --path "C:\\ProgramData\\DCOIR\\example.txt"\n'
              '```\n'}]


class OutputContractScorerTests(unittest.TestCase):
    def test_three_retained_cases_check_real_scorer_helpers(self):
        for case in CASES:
            with self.subTest(case=case["id"]):
                result=analyze_visible_output(
                    case["response"],
                    require_bluf_preamble=case["id"]=="GEM-OUT-LEAK-001",
                )
                self.assertEqual(result["accepted"],case["expected"]=="accept",result)
                self.assertTrue(set(case.get("must_trigger",[]))<=set(result["findings"]),result)
                scorer_types={x["type"] for x in detect_anomalies(
                    case["response"],["duplicate_final_sections"],
                )}
                self.assertEqual("duplicate_final_sections" in scorer_types,
                                 "duplicate_final_sections" in result["findings"])

    def test_canonical_duplicate_header_polarity(self):
        duplicate="## BLUF\\nOne.\\n## Analysis\\nTwo.\\nBLUF: again\\nThree.".replace("\\n","\n")
        self.assertIn("duplicate_final_sections",
            [row["type"] for row in detect_anomalies(duplicate,["duplicate_final_sections"])])
        self.assertIn("bluf",analyze_visible_output(duplicate)["details"]["duplicate_headers"])
        benign_notes="## Notes\nFirst.\n## Notes\nSecond."
        self.assertNotIn("duplicate_final_sections",
                         analyze_visible_output(benign_notes)["findings"])
        self.assertEqual(detect_anomalies(benign_notes,["duplicate_final_sections"]),[])

    def test_preamble_gate_is_opt_in_not_global(self):
        response="## Analysis\nKnown-good replay output without a BLUF preamble."
        self.assertTrue(analyze_visible_output(response)["accepted"])
        self.assertIn("malformed_preamble",analyze_visible_output(
            response,require_bluf_preamble=True)["findings"])
        self.assertTrue(analyze_visible_output(
            "## Executive summary\nEvidence.",require_bluf_preamble=True)["accepted"])

    def test_empty_output_fails_opt_in_preamble(self):
        for response in ("", " ", "\n\t", "## BLUF\n", "## Executive summary\n\n"):
            with self.subTest(response=response):
                result = analyze_visible_output(response, require_bluf_preamble=True)
                self.assertIn("malformed_preamble", result["findings"])
                self.assertFalse(result["accepted"])
                self.assertTrue(analyze_visible_output(response)["accepted"])

    def test_bluf_requires_substantive_content_before_next_heading_when_opted_in(self):
        for heading in ("## BLUF", "## Executive summary"):
            for next_section in ("## FACTS AND SOURCES", "## ANALYSIS", "### Subsection"):
                response = f"{heading}\n  \n{next_section}\nGrounded evidence."
                with self.subTest(heading=heading, next_section=next_section):
                    result = analyze_visible_output(response, require_bluf_preamble=True)
                    self.assertIn("malformed_preamble", result["findings"], result)
                    self.assertFalse(result["accepted"], result)
                    self.assertTrue(analyze_visible_output(response)["accepted"])
            substantive = f"{heading}\nEvidence supports further investigation.\n\n## FACTS AND SOURCES\nA finding."
            self.assertTrue(analyze_visible_output(substantive, require_bluf_preamble=True)["accepted"])

    def test_bluf_body_cannot_be_only_formatting_or_invisible_characters(self):
        for marker in ("---", "-", "** **", "\u200b", "\u2060"):
            response = f"## BLUF\n{marker}\n## FACTS AND SOURCES\nEvidence."
            with self.subTest(marker=repr(marker)):
                self.assertIn("malformed_preamble", analyze_visible_output(
                    response, require_bluf_preamble=True)["findings"])
                self.assertTrue(analyze_visible_output(response)["accepted"])

    def test_windows_line_endings_are_valid_for_substantive_bluf(self):
        for heading in ("## BLUF", "## Executive summary"):
            response = f"{heading}\r\nEvidence supports review.\r\n## FACTS AND SOURCES\r\nDetails."
            with self.subTest(heading=heading):
                self.assertTrue(analyze_visible_output(response, require_bluf_preamble=True)["accepted"])

    def test_narrow_internal_state_and_scaffold_detection(self):
        self.assertTrue(analyze_visible_output(
            "The analyst handoff summarizes normalized evidence.")["accepted"])
        self.assertTrue(analyze_visible_output(
            "A string mentioning yaml formatting is not a fenced scaffold.")["accepted"])
        self.assertIn("internal_state_leakage",
            analyze_visible_output("Routing_State: internal")["findings"])
        self.assertTrue(analyze_visible_output("routing_stateful is a distinct token")["accepted"])
        self.assertIn("yaml_or_json_scaffold",
            analyze_visible_output("Evidence:\n"+chr(96)*3+"json\n{}")["findings"])

    def test_contradiction_vocabulary_single_owner(self):
        self.assertIs(gemini_model_comparison_eval.CONTRADICTION_PAIRS,CONTRADICTION_PAIRS)
        self.assertEqual(len(CONTRADICTION_PAIRS),3)


if __name__=="__main__":
    unittest.main()
