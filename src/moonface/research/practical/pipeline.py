"""Practical-lane orchestration + rendering. The phases are run by the CLI in
separate invocations (so the Explore/Validate/Sealed split is enforced
structurally); this module provides the in-process building blocks and the
result renderers. Nothing here reads data or touches Donchian/promotion files."""
from __future__ import annotations

_FROZEN_KEYS = ("label", "timeframe", "family", "params", "exit_name",
                "exit_params", "h", "group", "axis")


def freeze_candidates(survivors) -> list[dict]:
    return [{k: r[k] for k in _FROZEN_KEYS} for r in survivors]


def to_leaderboard(result_rows) -> list[dict]:
    out = []
    for r in result_rows:
        v, s = r.get("validate", {}), r.get("sealed", {})
        out.append({
            "label": r["label"], "timeframe": r["timeframe"],
            "family": r["family"], "verdict": r["verdict"],
            "validate_pf": v.get("profit_factor"),
            "validate_exp": v.get("expectancy_r"),
            "sealed_pf": s.get("profit_factor"),
            "sealed_exp": s.get("expectancy_r"),
            "dsr": r.get("dsr")})
    return out


def _f(x):
    return "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def render_result(result_rows, asof, data_shas: dict) -> str:
    any_accept = any(r["verdict"] == "paper_accept" for r in result_rows)
    overall = ("PAPER CANDIDATE(S) FOUND (PAPER ONLY — not live)"
               if any_accept else "NEGATIVE")
    shas = ", ".join(f"{tf}={s}" for tf, s in sorted(data_shas.items()))
    head = (f"# BTC Practical Signal Discovery — 15m to 4h (slice: 1h, 4h)\n\n"
            f"## Verdict: {overall}\n\n- asof: {asof}\n- data_sha: {shas}\n"
            f"- gate: explore(wide) -> selection -> dual-replication "
            f"(validate AND sealed), DSR reported not gated\n\n"
            "| cell | tf | family | dsr | val_pf | val_exp | seal_pf | seal_exp | verdict |\n"
            "|---|---|---|---|---|---|---|---|---|\n")
    lines = []
    for lb in to_leaderboard(result_rows):
        lines.append(
            f"| {lb['label']} | {lb['timeframe']} | {lb['family']} | "
            f"{_f(lb['dsr'])} | {_f(lb['validate_pf'])} | {_f(lb['validate_exp'])} | "
            f"{_f(lb['sealed_pf'])} | {_f(lb['sealed_exp'])} | {lb['verdict']} |")
    caveat = ("A NEGATIVE is the expected, valid outcome. Any accepted candidate "
              "is a single-asset BTC PAPER ONLY signal — it does NOT authorize live "
              "capital or automatic execution, must get its own frozen paper-forward "
              "protocol, and never inherits the live/Donchian slot. The frozen 4h "
              "Donchian Slice-3 strategy is untouched by this lane.")
    return head + "\n".join(lines) + f"\n\n## Honest caveat\n\n{caveat}\n"
