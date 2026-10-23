"""Lane-agnostic reproduction harness: re-run a lane's own compute pipeline
against a scratch directory and diff the result against its frozen record.

kernel/ must never import a lane (invariant 1), and a lane's run function
(e.g. tools.lanes.oibuild_study.run_analysis) is exactly the kind of
lane-specific dependency that would violate it if imported here. Instead
run_fn is a parameter -- the same dependency-injection shape kernel.runner
already uses for `loader`. The only caller that imports both this module and
a lane's run function is tools/research.py, which sits outside kernel/ and is
allowed to import either.

Also provides offline_fetch_perp_candles / offline_fetch_metrics_history --
cache-only replacements for research.universe_data.fetch_perp_candles and
core.series.fetch_metrics_history, both of which fall back to a live network
fetch (and write into cache_dir) on a cache miss or coverage gap. The spec's
G3 reproduction gate must "run offline against .backtest_cache/ so the
comparison is deterministic"; a network-fallback fetch function breaks that
guarantee silently -- discovered when reproducing liqladder mutated
.backtest_cache/ mid-run and shifted the recomputed numbers away from the
recorded verdict for reasons that had nothing to do with the kernel."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

_DAY_MS = 86_400_000


def offline_fetch_perp_candles(symbol: str, interval: str, start_ms: int,
                               end_ms: int, cache_dir: str) -> list:
    """Candles from .backtest_cache/ only -- no network fallback, no cache
    write, on a cache miss returns []. Same window-filter semantics as
    research.universe_data.fetch_perp_candles's cache-hit path
    ([c for c in candles if start_ms <= c.timestamp_ms < end_ms])."""
    from moonface.data.ohlcv import OhlcvCache

    cached = OhlcvCache(cache_dir).load(symbol, interval)
    if cached is None:
        return []
    return [c for c in cached if start_ms <= c.timestamp_ms < end_ms]


def offline_fetch_metrics_history(symbol: str, start_ms: int, end_ms: int,
                                  cache_dir: str) -> list:
    """Metric rows from .backtest_cache/ only -- no network fallback for
    missing days, no cache write, on a cache miss returns []. Same
    day-rounded window-filter semantics as core.series.fetch_metrics_history's
    return line ([r for r in rows if start_ms <= r[0] < last_day_end])."""
    from moonface.data.series import _cache_path, _read_cache

    rows = _read_cache(_cache_path(cache_dir, symbol))
    last_day_end = (end_ms // _DAY_MS + 1) * _DAY_MS
    return [r for r in rows if start_ms <= r[0] < last_day_end]


def offline_fetch_daily_klines(symbol: str, start_ms: int, end_ms: int,
                               cache_dir: str) -> list:
    """Daily rows from .backtest_cache/ only -- no network fallback, no cache
    write, on a cache miss returns []. Same window-filter semantics as
    data.universe.fetch_daily_klines's cache-hit path."""
    from moonface.data.universe import load_daily_cache

    cached = load_daily_cache(cache_dir, symbol)
    if cached is None:
        return []
    return [r for r in cached if start_ms <= r.ts_ms < end_ms]


def offline_fetch_funding_rates(symbol: str, start_ms: int, end_ms: int,
                                cache_dir: str) -> list:
    """Funding (timestamp, rate) pairs from .backtest_cache/ only -- no
    network fallback, no cache write, on a cache miss returns []. Same
    window-filter semantics as data.universe.fetch_funding_rates's
    cache-hit path."""
    import csv

    from moonface.data.universe import _funding_cache_path

    path = _funding_cache_path(cache_dir, symbol)
    if not path.exists():
        return []
    with open(path, newline="") as fh:
        cached = [(int(t), float(r)) for t, r in csv.reader(fh)]
    return [(t, r) for t, r in cached if start_ms <= t < end_ms]


def offline_fetch_bookdepth_history(symbol: str, start_ms: int, end_ms: int,
                                    cache_dir: str) -> list:
    """Bookdepth (ts_ms, bid_notional_1pct, ask_notional_1pct) rows from
    .backtest_cache/ only -- no network fallback, no cache write, on a cache
    miss returns []. Same window-filter semantics as
    data.orderbook.fetch_bookdepth_history's cache-hit path."""
    from moonface.data.orderbook import _cache_path, _read_cache

    rows = _read_cache(_cache_path(cache_dir, symbol))
    return [r for r in rows if start_ms <= r[0] < end_ms]


def offline_fetch_funding_history_series(funding_symbol: str, start_ms: int,
                                         end_ms: int, cache_dir: str) -> list:
    """Funding (timestamp, rate) pairs from .backtest_cache/ only, via
    data.series.FundingCache -- a distinct cache format/symbol convention from
    offline_fetch_funding_rates (data.universe's plain-symbol daily/funding
    pipeline for the B2 bucket). This one keys on the ccxt perp symbol form
    (e.g. "DOGE/USDT:USDT"), matching multifamily_loader.default_readers'
    funding reader. No network fallback, no cache write, on a cache miss
    returns []. Same window-filter semantics as data.series.fetch_funding_
    history's fully-cached-window return line."""
    from moonface.data.series import FundingCache

    cached = FundingCache(cache_dir).load(funding_symbol)
    if not cached:
        return []
    return [(ts, r) for ts, r in cached if start_ms <= ts < end_ms]


def offline_fetch_vision_1m(symbol: str, start_ms: int, end_ms: int,
                            cache_dir: str) -> list:
    """Minute klines from .backtest_cache/<symbol>/ only -- no network
    fallback and, unlike data.vision.fetch_vision_1m's live-fallback branch
    (which writes an empty cache file on a failed download), no cache write
    on a missing month either; a missing month just contributes zero bars.
    Same dedupe/sort/window-filter semantics as fetch_vision_1m's return
    line."""
    from moonface.data.vision import (MinuteBar, _cache_path, _month_iter,
                                      _read_cache, parse_vision_klines_csv)

    if end_ms <= start_ms:
        return []

    bars: list[MinuteBar] = []
    for year, month in _month_iter(start_ms, end_ms):
        text = _read_cache(_cache_path(cache_dir, symbol, year, month))
        if text is not None:
            bars.extend(parse_vision_klines_csv(text))

    deduped: dict[int, MinuteBar] = {}
    for bar in bars:
        deduped.setdefault(bar.ts_ms, bar)

    return [bar for ts, bar in sorted(deduped.items()) if start_ms <= ts < end_ms]


def offline_fetch_fred_series(series_id: str, cache_dir: str) -> list:
    """FRED macro points (MacroPoint, ts_ms ascending) from .backtest_cache/
    only -- no network fallback, no cache write, on a cache miss returns [].
    data.macro.fetch_fred_series already reads-then-returns with zero network
    call on a cache hit (its own cache path check comes before the live
    fetch), so this offline twin is just that same cache-hit branch with the
    live-fetch fallback removed entirely -- same shape as the other
    offline_fetch_* cache-only twins in this module."""
    from moonface.data.macro import parse_fred_csv

    path = Path(cache_dir) / f"fred_{series_id}.csv"
    if not path.exists():
        return []
    return parse_fred_csv(path.read_text())


def offline_list_um_perp_symbols(cache_dir: str) -> list:
    """Every symbol with a cached daily-klines file (uni1d_<SYM>.csv),
    sorted -- the offline substitute for data.universe.list_um_perp_symbols,
    which makes a live S3 listing request with no cache-only mode. Valid
    only for lanes whose cache already holds every symbol their original
    run fetched (true for a closed/historical lane's frozen cache)."""
    return sorted(p.stem.removeprefix("uni1d_")
                 for p in Path(cache_dir).glob("uni1d_*.csv"))


@dataclass(frozen=True)
class ReproductionResult:
    matched: bool
    mismatches: dict[str, tuple[Any, Any]]
    recomputed: dict


def reproduce(run_fn: Callable[..., dict], cfg: dict, recorded: dict,
              compare_fields: tuple[str, ...], scratch_dir: Path,
              run_args: tuple = (), run_kwargs: dict | None = None,
              ) -> ReproductionResult:
    """Call run_fn(cfg, *run_args, out_dir=scratch_dir, **run_kwargs), then
    compare the returned dict's compare_fields against recorded's. scratch_dir
    must not be the lane's real experiments/<lane>/ directory -- both
    oibuild_study.run_analysis and liqladder.run_analysis refuse to run a
    second time once out_dir/verdict.json already exists (a one-touch guard),
    so pointing this at the real directory would either crash on that guard
    or, if bypassed, risk overwriting the frozen record."""
    kwargs = dict(run_kwargs or {})
    recomputed = run_fn(cfg, *run_args, out_dir=scratch_dir, **kwargs)
    mismatches: dict[str, tuple[Any, Any]] = {}
    for f in compare_fields:
        rec_val = recorded.get(f)
        new_val = recomputed.get(f)
        if rec_val != new_val:
            mismatches[f] = (rec_val, new_val)
    return ReproductionResult(matched=not mismatches, mismatches=mismatches,
                              recomputed=recomputed)
