"""BTC-Specialized lane orchestration helpers + result rendering. The staged CLI runs
the phases in separate invocations (Explore/Validate/Sealed split enforced
structurally); this module provides freeze + render building blocks. Nothing here
reads data or touches Donchian/promotion files."""
from __future__ import annotations

_FROZEN_KEYS = ("label", "timeframe", "family", "params", "exit_name",
                "exit_params", "h", "group", "axis")


def freeze_candidates(survivors) -> list[dict]:
    return [{k: r[k] for k in _FROZEN_KEYS} for r in survivors]


def to_leaderboard(result_rows) -> list[dict]:
    out = []
    for r in result_rows:
        v = r.get("validate") or {}
        s = (r.get("sealed") or {}).get("metrics", {}) if r.get("sealed") else {}
        out.append({
            "label": r["label"], "timeframe": r["timeframe"], "family": r["family"],
            "verdict": r["verdict"], "dsr": r.get("dsr"),
            "val_robust": v.get("robust_frac"), "val_total_r": v.get("agg_total_r"),
            "seal_pf": s.get("profit_factor"), "seal_exp": s.get("expectancy_r")})
    return out


def _f(x):
    return "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def render_result(result_rows, asof, data_shas: dict) -> str:
    any_accept = any(r["verdict"] == "paper_accept" for r in result_rows)
    overall = ("PAPER CANDIDATE(S) FOUND (PAPER ONLY — not live)"
               if any_accept else "NEGATIVE")
    shas = ", ".join(f"{tf}={s}" for tf, s in sorted(data_shas.items()))
    head = (f"# BTC-Specialized Practical Signal Optimization — Slice 1 (2h, 4h)\n\n"
            f"## Verdict: {overall}\n\n- asof: {asof}\n- data_sha: {shas}\n"
            f"- gate: explore(wide, net-R) -> top-K freeze -> walk-forward robust_frac"
            f">=0.60 -> single SEALED-tail full econ bar (DSR reported, not gated)\n\n"
            "| cell | tf | family | dsr | val_robust | val_total_r | seal_pf | "
            "seal_exp | verdict |\n|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for lb in to_leaderboard(result_rows):
        lines.append(
            f"| {lb['label']} | {lb['timeframe']} | {lb['family']} | {_f(lb['dsr'])} | "
            f"{_f(lb['val_robust'])} | {_f(lb['val_total_r'])} | {_f(lb['seal_pf'])} | "
            f"{_f(lb['seal_exp'])} | {lb['verdict']} |")
    caveat = ("A NEGATIVE is the expected, valid outcome. Any accepted candidate is a "
              "single-asset BTC PAPER ONLY signal — it does NOT authorize live capital "
              "or automatic execution, must get its own frozen paper-forward protocol, "
              "and never inherits the live/Donchian slot. The frozen 4h Donchian "
              "Slice-3 strategy is untouched by this lane.")
    return head + "\n".join(lines) + f"\n\n## Honest caveat\n\n{caveat}\n"
