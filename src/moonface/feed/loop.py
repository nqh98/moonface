"""The scan loop. ``run_once`` scans the universe once (testable, injectable);
``run_watch`` is the cadence loop that mirrors signal.cli.watch. Dry-run by
default: a posted card only goes to Telegram via the injected ``post`` seam when
``args.post`` is set."""
from __future__ import annotations

import time
from collections.abc import Callable

from moonface.data.ohlcv import TIMEFRAME_MS
from moonface.core.pivots import daily_pivots
from moonface.feed.card import render_card
from moonface.feed.levels import derive_levels
from moonface.feed.setups import detect_last
from moonface.feed.state import is_open, open_setup, resolve_open

LOOKBACK_BARS = 600


def _levels_for(setup, candles, atr_value):
    pivots = daily_pivots(candles)
    piv = pivots[-1] if pivots else None
    return derive_levels(setup, piv, atr_value)


def run_once(args, *, fetch_bundle: Callable, select_universe: Callable,
             post: Callable[[str], None], out=print) -> int:
    """Scan the universe once. Prints every card; posts + writes state only when
    args.post — dry-run is side-effect-free and repeatable (freshness is never
    consumed by a preview)."""
    universe = select_universe(args.exchange, args.universe_size)
    tf_ms = TIMEFRAME_MS[args.timeframe]
    end_ms = (int(time.time() * 1000) // tf_ms) * tf_ms
    start_ms = end_ms - LOOKBACK_BARS * tf_ms
    posted = 0
    stop = False
    for symbol in universe:
        if stop:
            break
        bundle = fetch_bundle(symbol, start_ms, end_ms, args.cache_dir)
        candles = bundle.candles
        for setup in detect_last(candles):
            if args.post and is_open(args.state, symbol):
                continue                  # one open setup per symbol (fresh-only)
            levels = _levels_for(setup, candles, setup.atr_value)
            card = render_card(symbol, setup, levels)
            out(card)
            if args.post:
                post(card)
                posted += 1
                open_setup(args.state, symbol, setup, levels,
                           candles[-1].timestamp_ms)
                if posted >= args.max_posts:
                    stop = True
                    break
        if args.post:
            resolve_open(args.state, candles, tf_ms, symbol=symbol)
    return 0


def run_watch(args, *, fetch_bundle, select_universe, post,
              sleep_fn=time.sleep, out=print) -> int:
    """Forever loop: scan once per closed candle, sleep until next close + grace.
    Mirrors signal.cli.watch's cadence/restart-safe handling."""
    tf_ms = TIMEFRAME_MS[args.timeframe]
    while True:
        now_ms = int(time.time() * 1000)
        next_close = (now_ms // tf_ms + 1) * tf_ms
        try:
            run_once(args, fetch_bundle=fetch_bundle,
                     select_universe=select_universe, post=post, out=out)
        except Exception as exc:  # noqa: BLE001 - never kill the daemon
            out(f"FEED TICK ERROR: {exc!r}")
        sleep_fn((next_close - int(time.time() * 1000)) / 1000.0 + args.grace_seconds)
    return 0
