from __future__ import annotations

import json
from pathlib import Path


def render_gate0_report(result: dict) -> str:
    if "track_n_spread" not in result:
        lines = [
            "# SSE Gate 0 Report",
            "",
            f"- verdict: {result['verdict']}",
            f"- chosen_cell: {result.get('chosen_cell') or 'none'}",
        ]
        for cell in ("points", "trajectories"):
            cell_result = result.get(cell, {})
            lines.extend(
                [
                    f"- {cell}_verdict: {cell_result.get('verdict', 'UNKNOWN')}",
                    f"- {cell}_track_n_spread: {cell_result.get('track_n_spread', 0.0):.6f}",
                    f"- {cell}_track_l_spread: {cell_result.get('track_l_spread', 0.0):.6f}",
                ]
            )
        return "\n".join(lines) + "\n"
    lines = [
        "# SSE Gate 0 Report",
        "",
        f"- verdict: {result['verdict']}",
        f"- track_n_spread: {result['track_n_spread']:.6f}",
        f"- track_l_spread: {result['track_l_spread']:.6f}",
        f"- label_shuffle_pass: {str(result['label_shuffle']['pass']).lower()}",
        f"- circular_shift_pass: {str(result['circular_shift']['pass']).lower()}",
        f"- attribution_pass: {str(result['attribution_pass']).lower()}",
        f"- era_stability_pass: {str(result['era_stability'].get('pass', False)).lower()}",
    ]
    if result["verdict"] == "SUSPECT_HARNESS":
        lines.append("- harness: control track cleared a null; stop and debug")
    return "\n".join(lines) + "\n"


def write_gate0_artifacts(out_dir: Path, result: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "gate0_verdict.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    (out_dir / "gate0_report.md").write_text(render_gate0_report(result))
