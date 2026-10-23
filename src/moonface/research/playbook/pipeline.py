# src/moonface/research/playbook/pipeline.py
"""Playbook-lane freeze + render building blocks. Nothing here reads data or
touches Donchian/promotion/journal files."""
from __future__ import annotations


def freeze_survivors(survivor_rows) -> list[str]:
    return [r["label"] for r in survivor_rows]


def _f(x):
    return "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def render_result(result_rows, asof, data_shas: dict) -> str:
    any_accept = any(r["verdict"] == "paper_accept" for r in result_rows)
    overall = ("PAPER CANDIDATE(S) FOUND (PAPER ONLY — not live)"
               if any_accept else "NEGATIVE")
    shas = ", ".join(f"{tf}={s}" for tf, s in sorted(data_shas.items()))
    head = (f"# BTC Multi-Timeframe Trend Playbook — Signal Engine\n\n"
            f"## Verdict: {overall}\n\n- asof: {asof}\n- data_sha: {shas}\n"
            f"- gate: explore(reported DSR) -> conjunctive selection -> dual "
            f"replication (validate AND sealed, same sign); DSR NOT gated\n\n"
            "| config | val_pf | val_exp | seal_pf | seal_exp | verdict |\n"
            "|---|---|---|---|---|---|\n")
    lines = []
    for r in result_rows:
        v, s = r.get("validate", {}), r.get("sealed", {})
        lines.append(f"| {r['label']} | {_f(v.get('profit_factor'))} | "
                     f"{_f(v.get('expectancy_r'))} | {_f(s.get('profit_factor'))} | "
                     f"{_f(s.get('expectancy_r'))} | {r['verdict']} |")
    caveat = ("A NEGATIVE is the expected, valid outcome. Any accepted candidate is a "
              "single-asset BTC PAPER ONLY signal — it does NOT authorize live capital "
              "or automatic execution, must get its own frozen paper-forward protocol, "
              "and never inherits the live/Donchian slot. The frozen 4h Donchian "
              "Slice-3 strategy is untouched by this lane.")
    return head + "\n".join(lines) + f"\n\n## Honest caveat\n\n{caveat}\n"
