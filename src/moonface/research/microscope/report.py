"""CSV and markdown outputs. Every artifact carries the NOT-A-GATE header
and the multiplicity + null-calibration disclosures — the microscope's
findings are inputs to human judgment, never to a promotion decision."""
from __future__ import annotations

import csv
from pathlib import Path

HEADER = "DESCRIPTIVE DIAGNOSTIC — NOT A GATE, NOT A RESULT"


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns,
                                extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def render_study_report(buckets: list[dict], null_result: dict,
                        n_events: int, n_used: int,
                        n_unlabeled: int) -> str:
    lines = [
        f"# {HEADER}",
        "",
        f"- events supplied: {n_events}; usable: {n_used};"
        f" UNLABELED at event time: {n_unlabeled}",
        f"- regime buckets examined: {len(buckets)} (multiplicity: every"
        " bucket below is one implicit comparison)",
        f"- null calibration: real effect {null_result['real_effect']} vs"
        f" shuffled p95 {null_result['null_p95']}"
        f" → **{null_result['verdict']}**",
        "",
    ]
    if null_result["verdict"] == "INDISTINGUISHABLE_FROM_NULL":
        lines += ["**SELECTION ARTIFACT WARNING:** bucket differences below"
                  " are consistent with label shuffling; do not interpret.",
                  ""]
    lines.append("| bucket | n | fwd_r_12 mean | 95% CI | MFE med |"
                 " MAE med | P(stop first) | verdict |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for b in buckets:
        if b["verdict"] == "INSUFFICIENT_DATA":
            lines.append(f"| {b['label']} | {b['n']} | — | — | — | — | — |"
                         " INSUFFICIENT_DATA |")
            continue
        ci = b.get("fwd_r_12_ci")
        ci_txt = f"[{ci[0]}, {ci[1]}]" if ci else "—"
        mean = b.get("fwd_r_12_mean", "—")
        lines.append(f"| {b['label']} | {b['n']} | {mean} | {ci_txt} |"
                     f" {b['mfe_r_median']} | {b['mae_r_median']} |"
                     f" {b['p_stop_first']} | DESCRIPTIVE |")
    lines += ["",
              "Any pattern here requires a separate pre-registered lane"
              " before it may influence trading.", ""]
    return "\n".join(lines)
