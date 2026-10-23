"""Shared test helpers for consolidated adapter tests."""
from __future__ import annotations

import types

from moonface.core.models import Candle
from moonface.research.universe_data import DailyRow


def fake_ctx(n: int = 250) -> types.SimpleNamespace:
    """Return a duck-typed context with synthetic 4h candles and funding.

    Candles use varied closes + per-bar wicks so ATR > 0 (avoids divide-by-zero
    in the ``atr_trail`` exit resolver).  Funding is loader-native raw
    ``(timestamp_ms, rate)`` points (the form ``ctx.funding`` carries in the
    real runner); btc_classic aligns internally, donchian consumes them raw.
    Small rate variation keeps any z-score well-defined.
    """
    candles: list[Candle] = []
    funding: list[tuple[int, float]] = []
    for i in range(n):
        close = 100 + i * 0.5 + (i % 7)
        candles.append(Candle(
            timestamp_ms=i * 14_400_000,
            open=float(close),
            high=float(close) + 1.0,
            low=float(close) - 1.0,
            close=float(close),
            volume=1.0,
        ))
        funding.append((i * 14_400_000, 0.0001 + (i % 5) * 0.00003))

    # Synthetic 1h candles (~250 bars) for multi-timeframe adapters.
    btc_1h: list[Candle] = []
    for i in range(n):
        close = 100 + i * 0.1 + (i % 7) * 0.5
        btc_1h.append(Candle(
            timestamp_ms=i * 3_600_000,
            open=float(close),
            high=float(close) + 1.0,
            low=float(close) - 1.0,
            close=float(close),
            volume=1.0,
        ))

    # Synthetic 2h candles (~250 bars) for multi-timeframe adapters.
    btc_2h: list[Candle] = []
    for i in range(n):
        close = 100 + i * 0.25 + (i % 7) * 0.5
        btc_2h.append(Candle(
            timestamp_ms=i * 7_200_000,
            open=float(close),
            high=float(close) + 1.0,
            low=float(close) - 1.0,
            close=float(close),
            volume=1.0,
        ))

    return types.SimpleNamespace(
        btc_4h=candles,
        btc_1h=btc_1h,
        btc_2h=btc_2h,
        daily=[],
        funding=funding,
        is_member=lambda ts: True,
        macro={},
        start_ms=0,
        end_ms=0,
        cache_dir=".backtest_cache",
    )


_DAY = 86_400_000


def fake_breadth_ctx(n_days: int = 250, n_symbols: int = 5) -> types.SimpleNamespace:
    """Return a duck-typed context for breadth_internal adapter tests.

    Builds ~*n_days* daily rows for each of *n_symbols* symbols with varied
    closes so that the breadth builders can compute state without crashing.
    The ``btc_4h`` candles span the same calendar window (n_days * 6 bars)
    with ATR > 0.  Builders may emit 0 entries on this synthetic data — that
    is acceptable; tests assert only key presence.
    """
    daily: dict[str, list[DailyRow]] = {}
    for sym_idx in range(n_symbols):
        sym = f"SYM{sym_idx}"
        rows: list[DailyRow] = []
        for i in range(n_days):
            close = 10.0 + sym_idx * 5.0 + i * 0.1 + (i % 7) * 0.05
            rows.append(DailyRow(ts_ms=i * _DAY, close=close, quote_volume=1000.0))
        daily[sym] = rows

    n_bars = n_days * 6
    candles: list[Candle] = []
    for i in range(n_bars):
        close = 100.0 + i * 0.05 + (i % 7) * 0.5
        candles.append(Candle(
            timestamp_ms=i * 14_400_000,
            open=float(close),
            high=float(close) + 1.0,
            low=float(close) - 1.0,
            close=float(close),
            volume=1.0,
        ))

    return types.SimpleNamespace(
        daily=daily,
        btc_4h=candles,
        btc_1h=[],
        funding=[],
        is_member=lambda sym, ts: True,
        macro={},
        start_ms=0,
        end_ms=0,
        cache_dir=".backtest_cache",
    )


def fake_playbook_ctx(n_days: int = 60) -> types.SimpleNamespace:
    """Return a duck-typed context with synthetic aligned 1h/2h/4h candles.

    Timestamps are aligned so that MTFView.build's ``align_higher`` produces
    correct prefix mappings:
      - h1: every hour  (n_days * 24 bars)
      - h2: every even hour (n_days * 12 bars)
      - h4: every 4-hour boundary (n_days * 6 bars)

    All candles have high > low (ATR > 0) and varied closes so the replay
    engine can compute indicators without crashing.  r_stream may be empty
    on this synthetic data; tests only assert structural correctness.
    """
    H1_MS = 3_600_000
    H2_MS = 7_200_000
    H4_MS = 14_400_000
    start_ms = 1_600_000_000_000  # arbitrary epoch-aligned base
    h1: list[Candle] = []
    h2: list[Candle] = []
    h4: list[Candle] = []
    n_h1 = n_days * 24
    for i in range(n_h1):
        close = 100.0 + i * 0.05 + (i % 7) * 0.3
        h1.append(Candle(
            timestamp_ms=start_ms + i * H1_MS,
            open=float(close),
            high=float(close) + 1.0,
            low=float(close) - 1.0,
            close=float(close),
            volume=10.0,
        ))
    n_h2 = n_days * 12
    for i in range(n_h2):
        close = 100.0 + (i * 2) * 0.05 + (i % 7) * 0.3
        h2.append(Candle(
            timestamp_ms=start_ms + i * H2_MS,
            open=float(close),
            high=float(close) + 1.0,
            low=float(close) - 1.0,
            close=float(close),
            volume=40.0,
        ))
    n_h4 = n_days * 6
    for i in range(n_h4):
        close = 100.0 + (i * 4) * 0.05 + (i % 7) * 0.3
        h4.append(Candle(
            timestamp_ms=start_ms + i * H4_MS,
            open=float(close),
            high=float(close) + 1.0,
            low=float(close) - 1.0,
            close=float(close),
            volume=160.0,
        ))
    return types.SimpleNamespace(
        btc_1h=h1,
        btc_2h=h2,
        btc_4h=h4,
        daily=[],
        funding=[],
        is_member=lambda ts: True,
        macro={},
        start_ms=start_ms,
        end_ms=start_ms + n_h1 * H1_MS,
        cache_dir=".backtest_cache",
    )
