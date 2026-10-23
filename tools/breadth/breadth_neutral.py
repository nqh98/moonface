#!/usr/bin/env python3
"""Market-neutral falsification for the breadth-internal leads (paper-only).

The cross-asset lane left one confound: every OOS window is the same regime and
BTC/ETH/SOL are highly correlated, so "positive on ETH and SOL" might just be
crypto beta. This lane beta-hedges each ETH/SOL breadth trade against BTC over
its actual holding window and re-judges. If the edge survives the hedge it is a
real timing signal on the beta-residual; if it collapses, the cross-asset
"breadth of evidence" was a single beta bet. beta=0 reproduces the raw
cross-asset result (the correctness gate)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from breadth import _load, _sha, split_60_20_20  # noqa: E402
from moonface.research.breadth.evaluate import summarize  # noqa: E402
from moonface.research.breadth_confirm.neutral import (  # noqa: E402
    BETA_WINDOW,
    aligned_returns,
    entries_provider,
    hedge_entries,
    rolling_betas,
)
from moonface.research.breadth_confirm.xasset_grid import lead_specs  # noqa: E402
from moonface.kernel.power_harness import bonferroni_level, judge_signal  # noqa: E402
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

TF = "4h"
MARKET = "BTCUSDT"
ASSETS = ("ETHUSDT", "SOLUSDT")
K = len(ASSETS) * len(lead_specs())
LEAD_BLOCK = {"net_new_highs": (False, 1), "breadth_momentum": (True, 8)}

# Raw (unhedged) pooled OOS expectancy per cell — must reproduce the cross-asset
# lane (experiments/breadth_xasset_confirm/RESULT.json) when beta=0.
ANCHOR_RAW = {
    ("ETHUSDT", "net_new_highs"): 0.474,
    ("ETHUSDT", "breadth_momentum"): 0.193,
    ("SOLUSDT", "net_new_highs"): 0.407,
    ("SOLUSDT", "breadth_momentum"): 0.093,
}


def _write_json(path: Path, doc) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True, default=str) + "\n")


def _window_bounds(args) -> dict[str, list[int]]:
    span = args.end_ms - args.start_ms
    t = args.start_ms + int(span * 0.6)
    v = args.start_ms + int(span * 0.8)
    return {"train": [args.start_ms, t], "validate": [t, v], "sealed": [v, args.end_ms]}


def _fetch(args, symbol):
    return fetch_perp_candles(symbol, TF, args.start_ms, args.end_ms, args.cache_dir)


def _cell_records(daily, asset_slice, btc_full, spec, is_member, beta_lookup, beta):
    """Hedged + raw records for one lead on one window slice."""
    provider = entries_provider(spec.key)
    entries = provider(daily, asset_slice, spec, is_member=is_member)
    return hedge_entries(
        asset_slice, btc_full, entries, spec.exit_name, dict(spec.exit_params),
        beta=beta, beta_lookup=beta_lookup,
    )


def _evaluate_asset(daily, asset_full, btc_full, is_member, beta):
    """For one asset return per-lead hedged/raw metrics + judge + beta stats.

    beta=None uses the rolling full-history per-entry beta; beta=0.0 is the raw
    correctness gate.
    """
    beta_lookup = None
    if beta is None:
        beta_lookup = rolling_betas(aligned_returns(asset_full, btc_full))
    _, val, seal = split_60_20_20(asset_full)
    out = []
    for spec in lead_specs():
        block, block_len = LEAD_BLOCK[spec.key]
        rv = _cell_records(daily, val, btc_full, spec, is_member, beta_lookup, beta)
        rs = _cell_records(daily, seal, btc_full, spec, is_member, beta_lookup, beta)
        hedged = rv["hedged"] + rs["hedged"]
        raw = rv["raw"] + rs["raw"]
        judge = judge_signal(
            summarize(rv["hedged"]), summarize(rs["hedged"]), hedged, K,
            block=block, block_len=block_len,
        )
        betas = rv["betas"] + rs["betas"]
        out.append({
            "lead": spec.key,
            "raw_pooled_exp": summarize(raw)["expectancy_r"],
            "hedged_pooled_exp": judge["pooled"]["expectancy_r"],
            "hedged_pooled_pf": judge["pooled"]["profit_factor"],
            "hedged_pooled_dd": judge["pooled"]["max_drawdown_r"],
            "pooled_n": judge["pooled"]["trade_count"],
            "beta_contribution": round(
                summarize(raw)["expectancy_r"] - judge["pooled"]["expectancy_r"], 4),
            "mean_beta": round(sum(betas) / len(betas), 3) if betas else None,
            "boot_lo": judge["boot_lo"],
            "p_le_zero": judge["p_le_zero"],
            "same_sign": judge["same_sign"],
            "practical": judge["practical"],
            "cost": judge["cost"],
            "significant": judge["significant"],
            "verdict": judge["verdict"],
        })
    return out


def _cell_status(row) -> str:
    if row["verdict"] == "paper_candidate":
        return "neutral_confirmed"
    if row["hedged_pooled_exp"] > 0 and row["same_sign"]:
        return "residual_positive"
    return "beta_explained"


def _register(args) -> int:
    btc, _, _ = _load(args)
    prereg = {
        "lane": "breadth_neutral",
        "lane_description": (
            "Market-neutral falsification: beta-hedge each ETH/SOL breadth-lead "
            "trade against BTC over its holding window; re-judge the residual. "
            "Tests whether the leads predict the beta-residual or just ride crypto "
            "beta. beta=0 reproduces the cross-asset raw result (anchor)."
        ),
        "asof": datetime.now(timezone.utc).isoformat(),
        "assets": list(ASSETS),
        "market": MARKET,
        "timeframe": TF,
        "leads": [s.key for s in lead_specs()],
        "beta_window": BETA_WINDOW,
        "k": K,
        "bonferroni_level": bonferroni_level(K),
        "btc_anchor_sha": _sha(btc),
        "windows": _window_bounds(args),
        "gate": (
            "per (lead x asset) cell on BTC-hedged residual: neutral_confirmed iff "
            f"judge==paper_candidate (same-sign+practical+2x/3x cost+p<{bonferroni_level(K)}); "
            "residual_positive iff hedged exp>0 & same-sign; else beta_explained. "
            "raw (beta=0) anchor-x-checked against the cross-asset lane."
        ),
    }
    _write_json(Path(args.out_dir) / "PREREGISTRATION.json", prereg)
    return 0


def _explore(args) -> int:
    btc, daily, is_member = _load(args)
    rows = []
    for symbol in ASSETS:
        asset = _fetch(args, symbol)
        for row in _evaluate_asset(daily, asset, btc, is_member, beta=None):
            rows.append({"asset": symbol, **row})
    _write_json(Path(args.out_dir) / "explore_leaderboard.json", rows)
    return 0


def _validate(args) -> int:
    btc, daily, is_member = _load(args)

    # Raw correctness gate (beta=0 must reproduce the cross-asset pooled exp).
    anchor_rows = {}
    for symbol in ASSETS:
        asset = _fetch(args, symbol)
        for row in _evaluate_asset(daily, asset, btc, is_member, beta=0.0):
            anchor_rows[(symbol, row["lead"])] = row["raw_pooled_exp"]
    anchor_ok = all(
        abs(anchor_rows[k] - v) <= 0.01 for k, v in ANCHOR_RAW.items()
    )

    rows = []
    for symbol in ASSETS:
        asset = _fetch(args, symbol)
        for row in _evaluate_asset(daily, asset, btc, is_member, beta=None):
            row = {"asset": symbol, "status": _cell_status(row), **row}
            rows.append(row)

    if any(r["status"] == "neutral_confirmed" for r in rows):
        verdict = "confirmed"
    elif any(r["status"] == "residual_positive" for r in rows):
        verdict = "residual_survives"
    else:
        verdict = "beta_explained"

    asof = datetime.now(timezone.utc).isoformat()
    out_dir = Path(args.out_dir)
    _write_json(out_dir / "RESULT.json", {
        "lane": "breadth_neutral",
        "asof": asof,
        "assets": list(ASSETS),
        "market": MARKET,
        "beta_window": BETA_WINDOW,
        "bonferroni_alpha": bonferroni_level(K),
        "anchor_ok": anchor_ok,
        "anchor_raw_expected": {f"{a}/{ld}": v for (a, ld), v in ANCHOR_RAW.items()},
        "anchor_raw_got": {f"{a}/{ld}": v for (a, ld), v in anchor_rows.items()},
        "verdict": verdict,
        "rows": rows,
    })

    lines = [
        "# Breadth-internal leads — market-neutral (BTC-hedged) falsification",
        "",
        f"## Verdict: {verdict.upper()}",
        "",
        f"- asof: {asof}",
        f"- market factor: {MARKET}   beta_window: {BETA_WINDOW} bars",
        f"- bonferroni_alpha: {bonferroni_level(K)}",
        f"- raw anchor_ok (beta=0 reproduces cross-asset): {anchor_ok}",
        "",
        "| asset | lead | status | raw_exp | hedged_exp | beta_contrib | mean_beta | "
        "pooled_n | boot_lo | p_le0 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['asset']} | {r['lead']} | {r['status']} | {r['raw_pooled_exp']:.3f} | "
            f"{r['hedged_pooled_exp']:.3f} | {r['beta_contribution']:.3f} | "
            f"{r['mean_beta']} | {r['pooled_n']} | {r['boot_lo']:.3f} | {r['p_le_zero']:.4f} |"
        )
    lines.append(
        "\nPaper-only. Each ETH/SOL breadth trade is hedged against BTC over its "
        "holding window (rolling trailing beta, no look-ahead). `beta_contrib` = "
        "raw_exp − hedged_exp is how much of the edge was crypto beta. If hedged_exp "
        "collapses to ~0/negative, the cross-asset confirmation was a single beta "
        "bet, not an independent breadth edge.\n"
    )
    (out_dir / "FINDINGS.md").write_text("\n".join(lines))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="breadth-neutral")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--register", action="store_true")
    mode.add_argument("--explore", action="store_true")
    mode.add_argument("--validate", action="store_true")
    p.add_argument("--start-ms", type=int, required=True)
    p.add_argument("--end-ms", type=int, required=True)
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--out-dir", required=True)
    return p


def run(argv=None) -> int:
    args = build_parser().parse_args(argv)
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    if args.register:
        return _register(args)
    if args.explore:
        return _explore(args)
    if args.validate:
        return _validate(args)
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
