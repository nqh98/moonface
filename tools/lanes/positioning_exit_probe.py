#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.data.ohlcv import OhlcvCache, fetch_history
from moonface.data.series import align_basis
from moonface.research.edge.basis_signals import make_basis_discount_reversion
from moonface.research.edge.exit_score import run_exit_battery
from moonface.core.exits import EXIT_REGISTRY
from moonface.data.series import (
    FundingCache, align_funding, fetch_funding_history)
from moonface.research.edge.funding_signals import make_funding_fade
from moonface.core.models import Candle

# The four exit styles judged for survival; horizon_hold is the diagnostic baseline.
SEARCH_EXITS = frozenset(
    {"atr_trail", "horizon_wide_stop", "breakeven_horizon", "fixed_bracket"})

_DAY_MS = 86_400_000


def build_entry_specs(
    basis: list[float | None], funding: list[float | None],
) -> list[tuple]:
    """The three frozen drift-surviving positioning entries, as (name, generator,
    params). Generators are closures over the perp-aligned indicator arrays and
    match exit_score's Generator type."""
    return [
        ("basis_discount", make_basis_discount_reversion(basis),
         {"window": 60, "pct": 5}),
        ("basis_discount", make_basis_discount_reversion(basis),
         {"window": 180, "pct": 5}),
        ("funding_fade", make_funding_fade(funding),
         {"window": 60, "z_thr": 1.5}),
    ]


def _entry_key(row) -> tuple:
    """Hashable identity of an entry cell (name + its params)."""
    return (row.entry, tuple(sorted(row.entry_params.items())))


def robustness_verdict(rows: list) -> tuple[str, list[str], dict]:
    """Group valid=True SEARCH_EXITS rows by exit style, count the distinct entry
    cells each passes on. A style is a survivor iff it passes on >= 2 of the 3
    entries. Returns (outcome, survivors, passing) where outcome is 'B' if any
    survivor exists else 'A', and passing maps exit style -> set of entry keys."""
    passing: dict[str, set] = {}
    for r in rows:
        if r.exit in SEARCH_EXITS and r.valid:
            passing.setdefault(r.exit, set()).add(_entry_key(r))
    survivors = sorted(name for name, cells in passing.items() if len(cells) >= 2)
    outcome = "B" if survivors else "A"
    return outcome, survivors, passing


def render_markdown(
    rows: list, timeframe: str, spot_symbol: str, perp_symbol: str,
) -> str:
    outcome, survivors, passing = robustness_verdict(rows)
    lines = [
        "# MoonFace Positioning-Entry Exit Probe",
        "",
        f"- generated: {datetime.now(timezone.utc).isoformat()}",
        f"- timeframe: {timeframe}",
        f"- spot symbol: {spot_symbol}",
        f"- perp symbol: {perp_symbol}",
        f"- rows scored: {len(rows)}",
        "",
        "| entry | entry params | exit | exit params | rsch trades | rsch net R | "
        "rsch exp | rsch maxDD R | OOS trades | OOS net R | OOS exp | valid |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.entry} | {r.entry_params} | {r.exit} | {r.exit_params} | "
            f"{r.research_trades} | {r.research_net_r} | {r.research_expectancy_r} | "
            f"{r.research_max_dd_r} | {r.oos_trades} | {r.oos_net_r} | "
            f"{r.oos_expectancy_r} | {r.valid} |")
    lines += ["", "## Verdict", "",
              f"- **Outcome {outcome}** "
              + ("(robust survivor found)" if outcome == "B"
                 else "(no robust survivor; drift unharvestable by fixed exits)")]
    if survivors:
        for name in survivors:
            cells = sorted(k[0] + " " + str(dict(k[1])) for k in passing[name])
            lines.append(f"- survivor `{name}` passed on: {cells}")
    else:
        for name, cells in sorted(passing.items()):
            if len(cells) == 1:
                only = sorted(k[0] + " " + str(dict(k[1])) for k in cells)[0]
                lines.append(
                    f"- artifact: `{name}` passed on a single entry ({only}) "
                    "-> multiple-comparison artifact, not a survivor")
    return "\n".join(lines) + "\n"


def write_report(
    out_dir: Path, rows: list, timeframe: str, spot_symbol: str, perp_symbol: str,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "positioning_exit_probe.json").write_text(
        json.dumps([asdict(r) for r in rows], indent=2, sort_keys=True),
        encoding="utf-8")
    (out_dir / "positioning_exit_probe.md").write_text(
        render_markdown(rows, timeframe, spot_symbol, perp_symbol),
        encoding="utf-8")
    return out_dir


def run_positioning_exit_probe(
    exchange: str, spot_symbol: str, perp_symbol: str, funding_symbol: str,
    start_ms: int, end_ms: int, cache_dir: str, timeframe: str,
    oos_tail_bars: int, warmup: int, future_bars: int, out_root: Path,
) -> Path:
    cache = OhlcvCache(cache_dir)
    spot: list[Candle] = fetch_history(
        exchange, spot_symbol, timeframe, start_ms, end_ms, cache)
    perp: list[Candle] = fetch_history(
        exchange, perp_symbol, timeframe, start_ms, end_ms, cache)
    basis = align_basis(perp, spot)
    points = fetch_funding_history(
        exchange, funding_symbol, start_ms, end_ms, FundingCache(cache_dir))
    funding = align_funding(perp, points)
    specs = build_entry_specs(basis, funding)
    rows = run_exit_battery(perp, specs, EXIT_REGISTRY, oos_tail_bars=oos_tail_bars,
                            warmup=warmup, future_bars=future_bars)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return write_report(out_root / stamp, rows, timeframe, spot_symbol, perp_symbol)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MoonFace positioning-entry exit probe.")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--spot-symbol", default="BTC/USDT")
    parser.add_argument("--perp-symbol", default="BTC/USDT:USDT")
    parser.add_argument("--funding-symbol", default="BTC/USDT:USDT")
    parser.add_argument("--years", type=float, default=3.0)
    parser.add_argument("--cache-dir", default=".backtest_cache")
    parser.add_argument("--timeframe", default="4h")
    parser.add_argument("--oos-tail-bars", type=int, default=1095)
    parser.add_argument("--warmup", type=int, default=60)
    parser.add_argument("--future-bars", type=int, default=48)
    parser.add_argument("--out-root", default="experiments/positioning_exits")
    args = parser.parse_args()

    now_ms = int(time.time() * 1000)
    start_ms = now_ms - int(args.years * 365 * _DAY_MS)
    out_dir = run_positioning_exit_probe(
        exchange=args.exchange, spot_symbol=args.spot_symbol,
        perp_symbol=args.perp_symbol, funding_symbol=args.funding_symbol,
        start_ms=start_ms, end_ms=now_ms, cache_dir=args.cache_dir,
        timeframe=args.timeframe, oos_tail_bars=args.oos_tail_bars,
        warmup=args.warmup, future_bars=args.future_bars,
        out_root=Path(args.out_root))
    print(f"Positioning exit-probe report written to {out_dir}")


if __name__ == "__main__":
    main()
