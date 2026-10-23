"""Macro event-window study: scheduled-release conditioning on BTC (event time).

Hypothesis (frozen before any data contact): BTC earns a positive
uncertainty-resolution premium in fixed windows anchored to scheduled US
macro releases (FOMC statements, CPI prints) — the pre-announcement drift
mechanism (Lucca-Moench) transmitted through BTC's post-2022 macro beta.
Exposure is episodic (~4 days/month), which is the one structure the
program's replicated drawdown-wall finding does not tax.

This is EVENT-TIME conditioning; the closed calseason family tested fixed
CALENDAR cells (weekday/weekend, funding settlement) and is not reopened.

Frozen design: 4 cells = {fomc, cpi} x {pre24h, post24h}, hypothesized
direction LONG in every cell, net of the house round-trip cost. A cell
clears only if net pooled mean > 0, one-sided bootstrap p(mean<=0) <
0.05/4 (Bonferroni across the 4 cells), both chronological halves agree
in sign, and n >= 20. Kill rule: no cell clears => closed_negative, the
family is CLOSED — no window, event-set, or direction drift afterward.
"""
from __future__ import annotations

import random
from statistics import fmean
from zoneinfo import ZoneInfo

import datetime as dt

from moonface.core.metrics import COST_FRACTION
from moonface.kernel.bootstrap import iid_resample_choices

_ET = ZoneInfo("America/New_York")
_HOUR_MS = 3_600_000

# Release times are fixed by the issuing agencies: FOMC statement 14:00 ET,
# CPI print 08:30 ET. Converted per-date via America/New_York (DST-correct).
EVENT_TYPES = ("fomc", "cpi")
_RELEASE_TIME = {"fomc": (14, 0), "cpi": (8, 30)}

# FOMC statement days (last day of each scheduled meeting), 2022-01..2026-06.
# Source: federalreserve.gov/monetarypolicy/fomccalendars.htm (fetched
# 2026-07-03); no unscheduled meetings in the window.
FOMC_DATES = (
    (2022, 1, 26), (2022, 3, 16), (2022, 5, 4), (2022, 6, 15),
    (2022, 7, 27), (2022, 9, 21), (2022, 11, 2), (2022, 12, 14),
    (2023, 2, 1), (2023, 3, 22), (2023, 5, 3), (2023, 6, 14),
    (2023, 7, 26), (2023, 9, 20), (2023, 11, 1), (2023, 12, 13),
    (2024, 1, 31), (2024, 3, 20), (2024, 5, 1), (2024, 6, 12),
    (2024, 7, 31), (2024, 9, 18), (2024, 11, 7), (2024, 12, 18),
    (2025, 1, 29), (2025, 3, 19), (2025, 5, 7), (2025, 6, 18),
    (2025, 7, 30), (2025, 9, 17), (2025, 10, 29), (2025, 12, 10),
    (2026, 1, 28), (2026, 3, 18), (2026, 4, 29), (2026, 6, 17),
)

# CPI news-release days, 2022-01..2026-06. Sources: BLS archive filenames
# (news.release/archives/cpi_MMDDYYYY.htm, spot-verified 2022-2024) and the
# published 2025/2026 schedules. 2025 has 11 releases: the October-2025 data
# month was never published (government shutdown; Sep data released 10-24,
# Nov data 12-18).
CPI_DATES = (
    (2022, 1, 12), (2022, 2, 10), (2022, 3, 10), (2022, 4, 12),
    (2022, 5, 11), (2022, 6, 10), (2022, 7, 13), (2022, 8, 10),
    (2022, 9, 13), (2022, 10, 13), (2022, 11, 10), (2022, 12, 13),
    (2023, 1, 12), (2023, 2, 14), (2023, 3, 14), (2023, 4, 12),
    (2023, 5, 10), (2023, 6, 13), (2023, 7, 12), (2023, 8, 10),
    (2023, 9, 13), (2023, 10, 12), (2023, 11, 14), (2023, 12, 12),
    (2024, 1, 11), (2024, 2, 13), (2024, 3, 12), (2024, 4, 10),
    (2024, 5, 15), (2024, 6, 12), (2024, 7, 11), (2024, 8, 14),
    (2024, 9, 11), (2024, 10, 10), (2024, 11, 13), (2024, 12, 11),
    (2025, 1, 15), (2025, 2, 12), (2025, 3, 12), (2025, 4, 10),
    (2025, 5, 13), (2025, 6, 11), (2025, 7, 15), (2025, 8, 12),
    (2025, 9, 11), (2025, 10, 24), (2025, 12, 18),
    (2026, 1, 13), (2026, 2, 13), (2026, 3, 11), (2026, 4, 10),
    (2026, 5, 12), (2026, 6, 10),
)

WINDOWS = ("pre24h", "post24h")
WINDOW_MS = 24 * _HOUR_MS
CELLS = tuple(f"{e}_{w}" for e in EVENT_TYPES for w in WINDOWS)

MIN_EVENTS = 20
N_BOOT = 10_000
BOOT_SEED = 20260703
ALPHA_BONFERRONI = 0.05 / len(CELLS)


def event_ts_ms(event_type: str) -> list[int]:
    """UTC ms release timestamps for one event type, DST-correct."""
    hour, minute = _RELEASE_TIME[event_type]
    dates = FOMC_DATES if event_type == "fomc" else CPI_DATES
    return [int(dt.datetime(y, m, d, hour, minute, tzinfo=_ET).timestamp() * 1000)
            for (y, m, d) in dates]


def price_at(candles, x_ms: int, interval_ms: int = _HOUR_MS) -> float | None:
    """Close of the last candle COMPLETED at or before x_ms (executable: a
    trade at time x can only reference finished bars). A close more than two
    intervals stale is treated as missing data, not a usable price."""
    best = None
    for c in candles:
        completed = c.timestamp_ms + interval_ms
        if completed <= x_ms:
            best = c.close if x_ms - completed < 2 * interval_ms else None
        else:
            break
    return best


def window_return(candles, a_ms: int, b_ms: int,
                  interval_ms: int = _HOUR_MS) -> float | None:
    entry = price_at(candles, a_ms, interval_ms)
    exit_ = price_at(candles, b_ms, interval_ms)
    if entry is None or exit_ is None or entry == 0.0:
        return None
    return exit_ / entry - 1.0


def cell_returns(candles, event_type: str, window: str,
                 interval_ms: int = _HOUR_MS) -> list[float]:
    """Chronological NET window returns (long, one round trip per event)."""
    out = []
    for t0 in event_ts_ms(event_type):
        a, b = (t0 - WINDOW_MS, t0) if window == "pre24h" else (t0, t0 + WINDOW_MS)
        r = window_return(candles, a, b, interval_ms)
        if r is not None:
            out.append(r - COST_FRACTION)
    return out


def bootstrap_p_le0(returns: list[float], n_boot: int = N_BOOT,
                    seed: int = BOOT_SEED) -> float:
    """One-sided percentile bootstrap: P(resampled mean <= 0)."""
    if not returns:
        return 1.0
    rng = random.Random(seed)
    le0 = sum(
        1 for _ in range(n_boot)
        if fmean(iid_resample_choices(rng, returns)) <= 0.0
    )
    return le0 / n_boot


def cell_summary(returns: list[float]) -> dict:
    n = len(returns)
    mean = fmean(returns) if returns else 0.0
    first = returns[: n // 2]
    second = returns[n // 2:]
    p = bootstrap_p_le0(returns)
    halves_ok = bool(first and second
                     and fmean(first) > 0.0 and fmean(second) > 0.0)
    return {
        "n": n,
        "net_mean": mean,
        "p_le0": p,
        "first_half_mean": fmean(first) if first else 0.0,
        "second_half_mean": fmean(second) if second else 0.0,
        "halves_sign_ok": halves_ok,
        "clears_gate": (n >= MIN_EVENTS and mean > 0.0
                        and p < ALPHA_BONFERRONI and halves_ok),
    }


def macro_event_verdict(cells: dict[str, dict]) -> dict:
    winners = [name for name in CELLS if cells[name]["clears_gate"]]
    winner = (max(winners, key=lambda n: cells[n]["net_mean"])
              if winners else None)
    return {
        "status": "forward_candidate" if winner else "closed_negative",
        "winner": winner,
        "reason": (
            f"{winner} clears the frozen event-window gate; next step is a "
            "human-gated forward paper registration, not promotion"
            if winner else
            "no event window clears the frozen gate; family CLOSED "
            "(no window, event-set, or direction drift)"
        ),
        "cells": cells,
    }
