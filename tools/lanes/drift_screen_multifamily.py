#!/usr/bin/env python
# tools/drift_screen_multifamily.py
"""Multi-family exit-free drift screen CLI.

phase-a : recalibrate the path-ratio floor AT A GIVEN HORIZON from the existing
          edge/positioning result files (the same known-dead evidence the
          original floor used). Run once per primary horizon (h=3, h=6).
register: freeze the design — families, per-family primary horizons, params,
          and the per-horizon floors.
run     : build the 16-asset 4h pool (candles + funding + metrics + bookdepth),
          screen each family at its primary horizon under the path-aware gate,
          attach the descriptive multi-horizon curve, write the leaderboard.

Mechanism science only: no exits, stops, TPs, or grids. Per-family primary
horizon for PASS/FAIL; all other horizons are descriptive.
Design frozen in experiments/drift_screen_multifamily/PREREGISTRATION.md."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.drift_screen import horizon_curve, screen_family
from moonface.research.multifamily_loader import (default_readers,
                                                  load_pool_bundles)
# Reuse the price screen's floor calibration helpers verbatim.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from drift_screen import (compute_floor_from_rows, load_edge_rows,  # noqa: E402
                          load_positioning_rows)

UNIVERSE = ["1000PEPEUSDT", "PEOPLEUSDT", "DOGEUSDT", "BNBUSDT",
            "1000SHIBUSDT", "1000FLOKIUSDT", "XRPUSDT", "LINKUSDT",
            "HIGHUSDT", "NEARUSDT", "JASMYUSDT", "TRBUSDT", "FILUSDT",
            "ARBUSDT", "AVAXUSDT", "ETCUSDT"]
DISCOVERY = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

FAMILIES = [
    {"family": "funding_fade",        "params": {"window": 60, "z_thr": 1.5},  "h": 6},
    {"family": "funding_confirm",     "params": {"persist": 6, "lvl": 0.0003}, "h": 6},
    {"family": "funding_flip",        "params": {"debounce": 6},               "h": 6},
    {"family": "oi_build_momentum",   "params": {"window": 180, "lookback": 6, "z_thr": 1.5}, "h": 6},
    {"family": "oi_flush_reversal",   "params": {"window": 180, "lookback": 6, "z_thr": 1.5}, "h": 6},
    {"family": "toptrader_follow",    "params": {"window": 180, "z_thr": 1.5}, "h": 6},
    {"family": "taker_flow_momentum", "params": {"window": 180, "z_thr": 1.5}, "h": 6},
    {"family": "ob_imbalance_follow", "params": {"window": 180, "z_thr": 1.5}, "h": 3},
    {"family": "ob_imbalance_follow", "params": {"window": 180, "z_thr": 2.0}, "h": 3},
]

METRICS_FIELD = {
    "oi_build_momentum": "sum_open_interest",
    "oi_flush_reversal": "sum_open_interest",
    "toptrader_follow": "sum_toptrader_long_short_ratio",
    "taker_flow_momentum": "sum_taker_long_short_vol_ratio",
}
DEFAULT_FIELD = "sum_open_interest"  # funding/orderbook families ignore feature

CURVE_HORIZONS = [3, 6, 12, 18, 24]   # 12h,24h,48h,72h,96h (4h bars; 6h sub-bar)
ATR_PERIOD = 14
MIN_EVENTS = 10
MIN_ASSETS = 8

DESIGN = {"timeframe": "4h", "atr_period": ATR_PERIOD, "min_events": MIN_EVENTS,
          "min_assets": MIN_ASSETS, "universe": UNIVERSE, "discovery": DISCOVERY,
          "families": FAMILIES, "curve_horizons": CURVE_HORIZONS}


def _read_json(path: Path):
    return json.loads(path.read_text())


def cmd_phase_a(out_dir: Path, positioning: Path, edge: Path, h: int) -> float:
    """Floor recalibrated at horizon h. The dead-row ratios are horizon-
    agnostic R magnitudes from the prior result files; this re-derives the bar
    so it is frozen per primary horizon rather than reused from h=24."""
    dead = (load_positioning_rows(_read_json(positioning))
            + load_edge_rows(_read_json(edge)))
    floor = compute_floor_from_rows(dead)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# Multi-family drift screen — Phase A floor at h={h}", "",
             f"- known-dead drifting rows: {len(dead)}",
             f"- **calibrated floor (ret_r/|mae_r|) at h={h}: {floor:.4f}**", ""]
    (out_dir / f"phaseA_gap_h{h}.md").write_text("\n".join(lines) + "\n")
    return floor


def cmd_register(out_dir: Path, floors: dict) -> None:
    path = out_dir / "registration.json"
    if path.exists():
        sys.exit(f"{path} already exists; the design is frozen")
    # deepcopy so the frozen snapshot owns its families/universe/curve_horizons
    # lists — a later run can't mutate the module-level DESIGN.
    reg = copy.deepcopy(DESIGN)
    reg["floors"] = floors          # {"3": <h3 floor>, "6": <h6 floor>}
    reg["registered_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2))
    print(f"registered: {path} ({len(FAMILIES)} families, floors={floors})")


def cmd_run(out_dir: Path, readers: dict | None = None,
            symbols: list[str] | None = None,
            cache_dir: str = ".backtest_cache",
            days: int = 3 * 365) -> None:
    reg = json.loads((out_dir / "registration.json").read_text())
    symbols = symbols or reg["universe"]
    if readers is None:
        # `days` of trailing 4h history. The default (3y) matches the price
        # screen; a shorter window is used for the fresh universe where the
        # funding/bookdepth archives are not pre-cached and a multi-year ccxt
        # pull is rate-limit-bound. The mechanisms need only a ~30-day lookback.
        end_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
        start_ms = end_ms - int(days * 86_400_000)
        readers = default_readers(cache_dir, start_ms, end_ms)

    # One pool per distinct metrics field (positioning families differ); funding
    # and orderbook families ignore `feature`, so they reuse the default-field
    # pool. Build lazily and cache.
    pools: dict[str, dict] = {}

    def pool_for(field: str):
        if field not in pools:
            pools[field] = load_pool_bundles(
                symbols, metrics_field=field, **readers)
        return pools[field]

    results = []
    for spec in reg["families"]:
        fam, params, h = spec["family"], spec["params"], spec["h"]
        field = METRICS_FIELD.get(fam, DEFAULT_FIELD)
        pool = pool_for(field)
        floor = reg["floors"][str(h)]
        res = screen_family(fam, params, pool, h=h, atr_period=reg["atr_period"],
                            floor=floor, min_events=reg["min_events"],
                            min_assets=reg["min_assets"])
        res["curve"] = horizon_curve(fam, params, pool,
                                     horizons=reg["curve_horizons"],
                                     atr_period=reg["atr_period"],
                                     min_events=reg["min_events"],
                                     min_assets=reg["min_assets"])
        results.append(res)

    results.sort(key=lambda r: -1.0 if r["verdict"]["ratio"] is None
                 else r["verdict"]["ratio"], reverse=True)
    (out_dir / "leaderboard.json").write_text(json.dumps(results, indent=2))
    (out_dir / "leaderboard.md").write_text(_render_md(results))
    print(f"screened {len(results)} families -> {out_dir / 'leaderboard.md'}")


def _f(x) -> str:
    return "" if x is None else f"{x:.4f}"


def _render_md(results: list[dict]) -> str:
    lines = ["# Multi-family drift screen — leaderboard", "",
             "| family | params | h | m | p_sign | Z | pooled_ret_r "
             "| pooled_abs_mae_r | pooled_mfe_r | sign_rate | ratio | verdict |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        v = r["verdict"]
        sr = (sum(a["sign_rate"] for a in r["assets"]) / len(r["assets"])
              if r["assets"] else None)
        mfe = (sum(a["mean_mfe_r"] for a in r["assets"]) / len(r["assets"])
               if r["assets"] else None)
        lines.append(
            f"| {r['signal']} | {r['params']} | {r['h']} | {v['m_assets']} "
            f"| {_f(v['p_sign'])} | {_f(v['stouffer_z'])} "
            f"| {_f(v['pooled_ret_r'])} | {_f(v['pooled_abs_mae_r'])} "
            f"| {_f(mfe)} | {_f(sr)} | {_f(v['ratio'])} | {v['verdict']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="multi-family drift screen")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("phase-a", help="calibrate floor at one horizon")
    pa.add_argument("--positioning", type=Path, required=True)
    pa.add_argument("--edge", type=Path, required=True)
    pa.add_argument("--h", type=int, required=True)
    pa.add_argument("--out", type=Path,
                    default=Path("experiments/drift_screen_multifamily"))

    pr = sub.add_parser("register", help="freeze design + per-horizon floors")
    pr.add_argument("--floor-h3", type=float, required=True)
    pr.add_argument("--floor-h6", type=float, required=True)
    pr.add_argument("--out", type=Path,
                    default=Path("experiments/drift_screen_multifamily"))

    rn = sub.add_parser("run", help="screen all families -> leaderboard")
    rn.add_argument("--out", type=Path,
                    default=Path("experiments/drift_screen_multifamily"))
    rn.add_argument("--days", type=int, default=3 * 365,
                    help="trailing days of history to load (default 3y)")

    args = parser.parse_args(argv)
    if args.cmd == "phase-a":
        floor = cmd_phase_a(args.out, positioning=args.positioning,
                            edge=args.edge, h=args.h)
        print(f"calibrated floor at h={args.h}: {floor:.4f}")
    elif args.cmd == "register":
        cmd_register(args.out, floors={"3": args.floor_h3, "6": args.floor_h6})
    elif args.cmd == "run":
        cmd_run(args.out, days=args.days)


if __name__ == "__main__":
    main()
