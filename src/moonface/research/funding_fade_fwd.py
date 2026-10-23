# src/moonface/research/funding_fade_fwd.py
"""funding_fade_fwd — frozen identity, window math, and pre-cutoff loading.

Draft-preparation phase only (design 2026-07-13). Every numeric code path is
the SAME code that produced the original positioning_exits row; this module
only windows, clamps, orchestrates, and hashes. The hard clamp enforces the
data-hygiene rule: nothing at/after the burned-data boundary enters a frame.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from moonface.data.ohlcv import OhlcvCache, fetch_history
from moonface.core.exits import EXIT_REGISTRY
from moonface.core.metrics import summarize_r
from moonface.core.models import Candle
from moonface.data.series import (FundingCache, align_funding,
                                        fetch_funding_history)
from moonface.research.edge.exit_score import exit_r_streams
from moonface.research.edge.funding_signals import make_funding_fade
from moonface.research.sizing import split_research_tail

# Frozen strategy identity — copied verbatim from the original row
# (experiments/positioning_exits/20260610T065146Z, row 2). Never edit.
ENTRY_NAME = "funding_fade"
ENTRY_PARAMS = {"window": 60, "z_thr": 1.5}
EXIT_NAME = "fixed_bracket"
EXIT_PARAMS = {"k_stop": 2.0, "m_tp": 4.0, "atr_period": 14}
ASSET = {"exchange": "binance", "symbol": "BTC/USDT:USDT",
         "timeframe": "4h", "funding_symbol": "BTC/USDT:USDT"}
FRACTION = 0.01  # fixed fractional risk per R, of initial equity

# Original run mechanics (tools/positioning_exit_probe.py defaults at the
# 2026-06-10T06:51:46Z run). CUTOFF_MS is the burned-data boundary AND the
# forward-window start: no gap, no overlap.
CUTOFF_MS = int(datetime(2026, 6, 10, 6, 51, 46,
                         tzinfo=timezone.utc).timestamp() * 1000)
_DAY_MS = 86_400_000
ORIGINAL_YEARS = 3.0
ORIGINAL_START_MS = CUTOFF_MS - int(ORIGINAL_YEARS * 365 * _DAY_MS)
OOS_TAIL_BARS = 1095
WARMUP = 60
FUTURE_BARS = 48

# Archived row values at their reported precision — the VERBATIM citation
# record; never altered. The two OOS aggregates embed a mark-to-close against
# the forming 2026-06-10 04:00-08:00Z candle snapshotted at 06:51:46Z, which
# no feed can reproduce.
ARCHIVED = {
    "research_trades": 254, "research_net_r": 64.7507,
    "research_expectancy_r": 0.2549, "research_max_dd_r": -32.0,
    "oos_trades": 68, "oos_net_r": 76.7285, "oos_expectancy_r": 1.1284,
}

# Amendment 1 (2026-07-14, human ruling option a): the dry-run tolerance is
# exact match on all completed-candle figures. Only the two snapshot-
# contaminated OOS aggregates differ from ARCHIVED.
BASELINE = {**ARCHIVED, "oos_net_r": 77.3435, "oos_expectancy_r": 1.1374}

# Forward window opens at the first bar with open time >= 2026-06-10T08:00Z
# (Amendment 1): the 04:00-08:00Z bar belongs to the baseline side.
FORWARD_START_MS = int(datetime(2026, 6, 10, 8, 0, 0,
                                tzinfo=timezone.utc).timestamp() * 1000)


class CutoffViolation(RuntimeError):
    """Raised before any summary is produced if post-cutoff data is seen."""


def assert_pre_cutoff(candles: list[Candle],
                      funding: list[tuple[int, float]]) -> None:
    """Hard clamp at the data-return boundary (design §3)."""
    bad_c = sum(1 for c in candles if c.timestamp_ms >= CUTOFF_MS)
    bad_f = sum(1 for ts, _ in funding if ts >= CUTOFF_MS)
    if bad_c or bad_f:
        raise CutoffViolation(
            f"post-cutoff data reached the frame: candles={bad_c} "
            f"funding={bad_f} (cutoff_ms={CUTOFF_MS})")


@dataclass(frozen=True)
class Streams:
    research: list[tuple[int, float]]  # ordered (timestamp_ms, r)
    tail: list[tuple[int, float]]


def load_pre_cutoff(cache_dir: str) -> tuple[list[Candle], list[float | None]]:
    """Perp candles + aligned funding for the ORIGINAL window, clamped."""
    perp = fetch_history(ASSET["exchange"], ASSET["symbol"],
                         ASSET["timeframe"], ORIGINAL_START_MS, CUTOFF_MS,
                         OhlcvCache(cache_dir))
    points = fetch_funding_history(ASSET["exchange"], ASSET["funding_symbol"],
                                   ORIGINAL_START_MS, CUTOFF_MS,
                                   FundingCache(cache_dir))
    assert_pre_cutoff(perp, points)
    return perp, align_funding(perp, points)


def regenerate(perp: list[Candle], funding: list[float | None]) -> Streams:
    """Re-run the exact original row through the reused pipeline."""
    entries = make_funding_fade(funding)(perp, ENTRY_PARAMS)
    tail_start = split_research_tail(perp, OOS_TAIL_BARS, WARMUP, FUTURE_BARS)
    exit_fn = EXIT_REGISTRY[EXIT_NAME][0]
    research, tail = exit_r_streams(perp, entries, exit_fn, EXIT_PARAMS,
                                    tail_start)
    return Streams(research=research, tail=tail)


def reproduction_report(streams: Streams) -> tuple[bool, dict]:
    """Compare regenerated summaries with the completed-candle BASELINE
    (Amendment 1). A miss is a spec §5.2 STOP — callers must not patch
    around it."""
    rs = summarize_r([r for _, r in streams.research])
    ts = summarize_r([r for _, r in streams.tail])
    got = {
        "research_trades": rs.trade_count, "research_net_r": rs.total_r,
        "research_expectancy_r": rs.expectancy_r,
        "research_max_dd_r": rs.max_drawdown_r,
        "oos_trades": ts.trade_count, "oos_net_r": ts.total_r,
        "oos_expectancy_r": ts.expectancy_r,
    }
    return got == BASELINE, got


def identity_hash(dd_budget_r: float, verdict_n_trades: int,
                  verdict_months: int) -> str:
    """sha256 over canonical JSON of rules + all frozen parameters
    (MOE_ORTHO convention). Freezes at human sign-off."""
    payload = {
        "program": "funding_fade_fwd", "version": 1,
        "asset": ASSET,
        "entry": {"family": ENTRY_NAME, "params": ENTRY_PARAMS},
        "exit": {"name": EXIT_NAME, "params": EXIT_PARAMS},
        "fraction": FRACTION,
        "forward_start_ms": FORWARD_START_MS,
        "dd_budget_r": dd_budget_r,
        "verdict_trigger": {"later_of": {"n_trades": verdict_n_trades,
                                         "months": verdict_months}},
        "success": {"ci": 0.95, "method": "moving_block_bootstrap",
                    "block": 10, "resamples": 10000, "seed": 42,
                    "rule": "cum_r>0 and ci_low>0 and cum_r>null_p95"},
        "null_benchmark": {"runs": 200, "seeds": "0..199",
                           "percentile": "sorted[min(n-1,ceil(0.95n))]",
                           "comparison": "strict"},
        "null_guard": {"runs": 200, "seeds": "0..199",
                       "min_fail_fraction": 0.95,
                       "note": "validates machinery; <=5% holds by "
                               "construction under condition (iii)"},
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
