"""Rendering helpers for the BTC long/short tournament."""
from __future__ import annotations

_FROZEN_KEYS = (
    "label", "timeframe", "long_rule", "short_rule", "filters",
    "exit_name", "exit_params", "h", "group", "axis",
)


def freeze_candidates(survivors) -> list[dict]:
    return [{k: r[k] for k in _FROZEN_KEYS} for r in survivors]


def _f(x):
    return "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def to_leaderboard(result_rows) -> list[dict]:
    out = []
    for r in result_rows:
        v, s = r.get("validate", {}), r.get("sealed", {})
        t = r.get("train", {})
        out.append({
            "label": r["label"],
            "timeframe": r["timeframe"],
            "long_family": r["long_rule"]["family"],
            "short_family": r["short_rule"]["family"],
            "verdict": r["verdict"],
            "train_pf": t.get("profit_factor"),
            "train_exp": t.get("expectancy_r"),
            "train_total_r": t.get("total_r"),
            "train_twin_total_r": t.get("twin_total_r"),
            "validate_pf": v.get("profit_factor"),
            "validate_exp": v.get("expectancy_r"),
            "validate_total_r": v.get("total_r"),
            "validate_twin_total_r": v.get("twin_total_r"),
            "sealed_pf": s.get("profit_factor"),
            "sealed_exp": s.get("expectancy_r"),
            "sealed_total_r": s.get("total_r"),
            "sealed_twin_total_r": s.get("twin_total_r"),
        })
    return out


def render_result(result_rows, asof, data_shas: dict) -> str:
    any_accept = any(r["verdict"] == "paper_candidate" for r in result_rows)
    overall = "PAPER CANDIDATE(S) FOUND (PAPER ONLY — not live)" if any_accept else "NEGATIVE"
    shas = ", ".join(f"{tf}={s}" for tf, s in sorted(data_shas.items()))
    head = (
        f"# BTC Long/Short Tournament\n\n## Verdict: {overall}\n\n"
        f"- asof: {asof}\n- data_sha: {shas}\n"
        "- gate: train practical bar + twin beat -> validate and sealed practical "
        "bar with same expectancy sign + twin beat on both\n\n"
        "| cell | tf | long | short | train_r | train_twin | val_r | val_twin | seal_r | seal_twin | verdict |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|\n"
    )
    lines = []
    for lb in to_leaderboard(result_rows):
        lines.append(
            f"| {lb['label']} | {lb['timeframe']} | {lb['long_family']} | "
            f"{lb['short_family']} | {_f(lb['train_total_r'])} | "
            f"{_f(lb['train_twin_total_r'])} | {_f(lb['validate_total_r'])} | "
            f"{_f(lb['validate_twin_total_r'])} | {_f(lb['sealed_total_r'])} | "
            f"{_f(lb['sealed_twin_total_r'])} | {lb['verdict']} |"
        )
    caveat = (
        "A negative outcome is expected and valid. Any accepted candidate is paper-only, "
        "BTC futures only, and does not authorize live capital or promotion."
    )
    return head + "\n".join(lines) + f"\n\n## Honest caveat\n\n{caveat}\n"


def render_findings(result_rows, asof, data_shas: dict | None = None) -> str:
    return render_result(result_rows, asof, data_shas or {})
