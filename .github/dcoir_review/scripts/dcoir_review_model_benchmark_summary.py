#!/usr/bin/env python3
"""Render a concise human-readable summary from a DCOIR model benchmark report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Benchmark report must be a JSON object")
    return data


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def render(report: dict[str, Any]) -> str:
    mode = str(report.get("mode", "unknown"))
    lines = [
        "# DCOIR Review model benchmark",
        "",
        f"- mode: `{_cell(mode)}`",
        f"- no_publication: `{bool(report.get('no_publication', False))}`",
    ]
    if mode == "plan-no-network":
        counts = report.get("case_counts") if isinstance(report.get("case_counts"), dict) else {}
        lines.extend(
            [
                "- paid_network_calls: `0`",
                f"- planned_requests_if_live: `{int(counts.get('planned_total_requests', 0) or 0)}`",
                f"- candidates: `{', '.join(str(item) for item in report.get('candidate_ids', []))}`",
                "",
                "Plan mode makes no OpenRouter inference calls. Re-run with the governed paid-live opt-in only after reviewing this request count.",
                "",
            ]
        )
        return "\n".join(lines)

    candidates = report.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("Live benchmark report is missing candidates")

    lines.extend(
        [
            "",
            "Quality is a hard gate: lower cost or latency never compensates for a known-defect miss, false positive, ambiguous result, or request error.",
            "",
            "| Candidate | Role | Quality floor | FN | FP | Errors | Cost USD | Serial seconds | p50 sec | p95 sec |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    eligible: list[tuple[str, float]] = []
    for row in candidates:
        if not isinstance(row, dict):
            continue
        candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
        quality = row.get("quality") if isinstance(row.get("quality"), dict) else {}
        economics = row.get("economics") if isinstance(row.get("economics"), dict) else {}
        candidate_id = str(candidate.get("id", "unknown"))
        is_eligible = bool(quality.get("acceptance_eligible_quality_floor", False))
        if is_eligible:
            eligible.append((candidate_id, float(economics.get("exact_cost_usd", 0.0) or 0.0)))
        lines.append(
            "| "
            + " | ".join(
                [
                    _cell(candidate_id),
                    _cell(candidate.get("benchmark_role", candidate.get("role", ""))),
                    "PASS" if is_eligible else "FAIL",
                    str(len(quality.get("false_negative_case_ids", []) or [])),
                    str(len(quality.get("false_positive_case_ids", []) or [])),
                    str(len(quality.get("request_error_case_ids", []) or [])),
                    f"{float(economics.get('exact_cost_usd', 0.0) or 0.0):.6f}",
                    f"{float(economics.get('serial_wall_seconds', 0.0) or 0.0):.3f}",
                    f"{float(economics.get('p50_request_seconds', 0.0) or 0.0):.3f}",
                    f"{float(economics.get('p95_request_seconds', 0.0) or 0.0):.3f}",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Eligible candidates", ""])
    if eligible:
        for candidate_id, cost in sorted(eligible, key=lambda item: (item[1], item[0])):
            lines.append(f"- `{_cell(candidate_id)}` — quality floor passed; measured cost `{cost:.6f} USD`")
    else:
        lines.append("- None passed the complete quality floor.")

    lines.extend(
        [
            "",
            "This report does not change production models. Promotion requires a separate governed configuration decision using the complete DCOIR evidence set.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rendered = render(_load(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
