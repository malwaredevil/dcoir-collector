"""DCOIR Review v27 exact-anchor preservation overlay.

The re-anchoring heuristic exists to rescue findings whose model-provided line
is not an added changed line. It must not move an already-valid changed-line
anchor merely because nearby prose happens to score higher against finding
terms. A valid exact anchor is therefore immutable; heuristic re-anchoring is
reserved for genuinely unpostable original lines.
"""

from __future__ import annotations

from typing import Any


VERSION = "v27"


def apply_pareto_context_module(module: Any) -> None:
    storage = "_dcoir_required_v27_original_reanchor_finding_to_changed_line"
    original = getattr(module, storage, None)
    if original is None:
        original = getattr(module, "reanchor_finding_to_changed_line", None)
        if callable(original):
            setattr(module, storage, original)
    if not callable(original):
        return

    def reanchor_finding_to_changed_line(
        finding: dict[str, Any],
        line_index: dict[tuple[str, int], int],
        changed_lines_by_path: dict[str, list[Any]],
        risk_sentinels: list[Any],
    ) -> dict[str, Any]:
        path = str(finding.get("path", "") or "").strip()
        try:
            line = int(finding.get("line", 0) or 0)
        except (TypeError, ValueError):
            return original(finding, line_index, changed_lines_by_path, risk_sentinels)

        # The detector already supplied a GitHub-postable added line. Preserve
        # that evidence boundary exactly. Nearby comments/docstrings may be
        # useful context, but must never steal the finding anchor.
        if path and line > 0 and (path, line) in line_index:
            return dict(finding)

        return original(finding, line_index, changed_lines_by_path, risk_sentinels)

    module.reanchor_finding_to_changed_line = reanchor_finding_to_changed_line
