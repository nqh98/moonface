#!/usr/bin/env python
# tools/drift_screen.py
"""Drawdown-aware drift screen CLI.

phase-a : calibrate the path-ratio floor from existing edge/positioning
          result files and write the descriptive gap report.
register: freeze the design (horizon, floor, universe, exclude set).
run     : load 4h candles for the frozen universe, screen every registered
          signal under the path-aware gate, write the leaderboard.

Mechanism science only: a single fixed horizon, no exits/stops/TPs/grids.
Design frozen in experiments/drift_screen/PREREGISTRATION.md."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from collections.abc import Callable

from moonface.core.models import Candle
from moonface.research.edge.signals import (atr_channel_break, donchian_break,
                                             ma_cross, price_vs_ma, roc_sign)
from moonface.research.drift_screen import screen_signal


def compute_floor_from_rows(rows: list[dict]) -> float:
    """Floor = the largest drift/drawdown ratio observed among known-dead
    rows, so the gate (ratio >= floor) rejects everything already known dead.
    Falls back to the conservative a-priori bar 1.0 when there is no evidence."""
    if not rows:
        return 1.0
    ratios = [r["drift_r"] / r["dd_r"] for r in rows if r["dd_r"] > 0]
    return max(ratios) if ratios else 1.0


def load_positioning_rows(payload: dict | list) -> list[dict]:
    """Positioning exit probe rows -> dead-but-drifting evidence: OOS
    expectancy (R/trade) as drift, |research max drawdown R| as the path cost.
    Only positive-drift rows are evidence of harvestable-looking drift.
    Accepts either a {"rows": [...]} wrapper or a bare list (the real file)."""
    rows = payload["rows"] if isinstance(payload, dict) else payload
    out: list[dict] = []
    for r in rows:
        drift = float(r["oos_expectancy_r"])
        if drift > 0:
            out.append({"drift_r": drift,
                        "dd_r": abs(float(r["research_max_dd_r"]))})
    return out


def load_edge_rows(payload: dict | list) -> list[dict]:
    """Edge leaderboard rows -> evidence: horizon OOS expectancy as drift,
    |bracket net R| as the path-cost proxy (the R-scale bracket P&L the spec
    cites, e.g. atr_channel_break|pivot_bias '-9.6 bracket net R' — NOT the
    per-trade bracket expectancy, which would inflate ratios ~100x and make
    the floor vacuously high). Only positive-drift rows count. Accepts a
    {"rows": [...]} wrapper or a bare list."""
    rows = payload["rows"] if isinstance(payload, dict) else payload
    out: list[dict] = []
    for r in rows:
        drift = float(r.get("horizon_oos_expectancy_r", 0.0))
        if drift > 0:
            dd = abs(float(r.get("bracket_net_r", 0.0))) or 1e-6
            out.append({"drift_r": drift, "dd_r": dd})
    return out


def _read_json(path: Path) -> dict | list:
    return json.loads(path.read_text())


def cmd_phase_a(out_dir: Path, positioning: Path, edge: Path) -> float:
    pos_rows = load_positioning_rows(_read_json(positioning))
    edge_rows = load_edge_rows(_read_json(edge))
    dead = pos_rows + edge_rows
    floor = compute_floor_from_rows(dead)
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Drift screen — Phase A gap characterization", "",
             f"- known-dead drifting rows: {len(dead)}",
             f"- **calibrated floor (ret_r/|mae_r|): {floor:.4f}**",
             "  (largest drift/drawdown ratio among known-dead families;",
             "   the gate ratio >= floor therefore rejects all of them)", "",
             "## Known-dead drift-vs-drawdown rows", "",
             "| drift_r | dd_r | ratio |", "|---|---|---|"]
    for r in sorted(dead, key=lambda x: x["drift_r"] / x["dd_r"], reverse=True):
        lines.append(f"| {r['drift_r']:.4f} | {r['dd_r']:.4f} "
                     f"| {r['drift_r'] / r['dd_r']:.4f} |")
    (out_dir / "phaseA_gap.md").write_text("\n".join(lines) + "\n")
    return floor


def _add_phase_a(sub) -> None:
    p = sub.add_parser("phase-a", help="calibrate floor from existing results")
    p.add_argument("--positioning", type=Path, required=True)
    p.add_argument("--edge", type=Path, required=True)
    p.add_argument("--out", type=Path,
                   default=Path("experiments/drift_screen"))


# The 16 fresh confirmation assets from the oibuild study (discovery set
# BTC/ETH/SOL excluded). 4h OHLC for these lives in .backtest_cache.
UNIVERSE = ["1000PEPEUSDT", "PEOPLEUSDT", "DOGEUSDT", "BNBUSDT",
            "1000SHIBUSDT", "1000FLOKIUSDT", "XRPUSDT", "LINKUSDT",
            "HIGHUSDT", "NEARUSDT", "JASMYUSDT", "TRBUSDT", "FILUSDT",
            "ARBUSDT", "AVAXUSDT", "ETCUSDT"]

DISCOVERY = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

# Existing-registry signals to re-score. Resolved to generators at run time
# (kept as names here so registration.json stays pure JSON).
SIGNALS = [
    {"name": "donchian_break", "params": {"n": 100}},
    {"name": "donchian_break", "params": {"n": 55}},
    {"name": "atr_channel_break", "params": {"k": 1.5, "atr_period": 14}},
    {"name": "atr_channel_break", "params": {"k": 2.0, "atr_period": 14}},
    {"name": "ma_cross", "params": {"fast": 50, "slow": 200}},
    {"name": "roc_sign", "params": {"period": 24}},
    {"name": "price_vs_ma", "params": {"period": 100}},
]

DESIGN = {
    "timeframe": "4h", "h": 24, "atr_period": 14,
    "min_events": 10, "min_assets": 8,
    "universe": UNIVERSE, "discovery": DISCOVERY, "signals": SIGNALS,
}


def cmd_register(out_dir: Path, floor: float) -> None:
    path = out_dir / "registration.json"
    if path.exists():
        sys.exit(f"{path} already exists; the design is frozen")
    reg = dict(DESIGN)
    reg["floor"] = floor
    reg["registered_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2))
    print(f"registered: {path} (floor={floor}, {len(SIGNALS)} signals frozen)")


_REGISTRY = {
    "donchian_break": donchian_break, "atr_channel_break": atr_channel_break,
    "ma_cross": ma_cross, "price_vs_ma": price_vs_ma, "roc_sign": roc_sign,
}

Loader = Callable[[str, str], "list[Candle] | None"]


def resolve_signal(name: str):
    return _REGISTRY[name]


def _default_loader(cache_dir: str = ".backtest_cache") -> Loader:
    from moonface.data.ohlcv import OhlcvCache
    cache = OhlcvCache(cache_dir)
    return lambda sym, tf: cache.load(sym, tf)


def cmd_run(out_dir: Path, loader: Loader | None = None) -> None:
    reg = json.loads((out_dir / "registration.json").read_text())
    if loader is None:
        loader = _default_loader()
    tf = reg["timeframe"]
    pool: dict[str, list[Candle]] = {}
    for sym in reg["universe"]:
        candles = loader(sym, tf)
        if candles:
            pool[sym] = candles
    results = []
    for sig in reg["signals"]:
        results.append(screen_signal(
            sig["name"], resolve_signal(sig["name"]), sig["params"], pool,
            h=reg["h"], atr_period=reg["atr_period"], floor=reg["floor"],
            min_events=reg["min_events"], min_assets=reg["min_assets"]))
    results.sort(key=lambda r: -1.0 if r["verdict"]["ratio"] is None
                 else r["verdict"]["ratio"], reverse=True)
    (out_dir / "leaderboard.json").write_text(json.dumps(results, indent=2))
    (out_dir / "leaderboard.md").write_text(_render_md(results))
    print(f"screened {len(results)} signals over {len(pool)} assets "
          f"-> {out_dir / 'leaderboard.md'}")


def _render_md(results: list[dict]) -> str:
    lines = ["# Drift screen — leaderboard", "",
             "| signal | params | m | p_sign | Z | pooled_ret_r "
             "| pooled_|mae|_r | ratio | verdict |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        v = r["verdict"]
        lines.append(
            f"| {r['signal']} | {r['params']} | {v['m_assets']} "
            f"| {_f(v['p_sign'])} | {_f(v['stouffer_z'])} "
            f"| {_f(v['pooled_ret_r'])} | {_f(v['pooled_abs_mae_r'])} "
            f"| {_f(v['ratio'])} | {v['verdict']} |")
    return "\n".join(lines) + "\n"


def _f(x) -> str:
    return "" if x is None else f"{x:.4f}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="drawdown-aware drift screen")
    sub = parser.add_subparsers(dest="cmd", required=True)
    _add_phase_a(sub)

    pr = sub.add_parser("register", help="freeze design (floor from phase-a)")
    pr.add_argument("--floor", type=float, required=True)
    pr.add_argument("--out", type=Path, default=Path("experiments/drift_screen"))

    rn = sub.add_parser("run", help="screen all signals -> leaderboard")
    rn.add_argument("--out", type=Path, default=Path("experiments/drift_screen"))

    args = parser.parse_args(argv)
    if args.cmd == "phase-a":
        floor = cmd_phase_a(args.out, positioning=args.positioning, edge=args.edge)
        print(f"calibrated floor: {floor:.4f}")
    elif args.cmd == "register":
        cmd_register(args.out, floor=args.floor)
    elif args.cmd == "run":
        cmd_run(args.out)


if __name__ == "__main__":
    main()
