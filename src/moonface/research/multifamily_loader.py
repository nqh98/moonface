"""Per-asset DataBundle loader for the multi-family drift screen's 16-asset 4h
pool. Each bundle carries candles + funding + one metrics field + per-bar mean
bookdepth imbalance, all aligned 1:1 with candles. Readers are injectable so
tests run with no network or disk; the default readers wire the existing CSV
caches."""
from __future__ import annotations

from collections.abc import Callable

from moonface.core.models import Candle
from moonface.core.bundle import DataBundle

CandleReader = Callable[[str, str], "list[Candle]"]
FundingReader = Callable[[str], "list[float | None] | None"]
MetricsReader = Callable[[str, str], "list[float | None] | None"]
BookdepthReader = Callable[[str], "list[float | None] | None"]


def load_pool_bundles(symbols: list[str], metrics_field: str,
                      candles: CandleReader, funding: FundingReader,
                      metrics: MetricsReader,
                      bookdepth: BookdepthReader,
                      timeframe: str = "4h") -> dict[str, DataBundle]:
    """Build {symbol: DataBundle} for the pool. A symbol whose candle reader
    returns nothing is omitted (no price series to score against). Optional
    series (funding/metrics/bookdepth) that return None are left None; the
    family generators raise on missing data and the screen drops that asset for
    that family."""
    pool: dict[str, DataBundle] = {}
    for sym in symbols:
        bars = candles(sym, timeframe)
        if not bars:
            continue
        pool[sym] = DataBundle(
            candles=bars,
            funding=funding(sym),
            feature=metrics(sym, metrics_field),
            bookdepth=bookdepth(sym))
    return pool


def default_readers(cache_dir: str, start_ms: int, end_ms: int) -> dict:
    """Concrete readers over the existing CSV caches. Candle reader uses
    OhlcvCache.load; optional readers swallow missing-file errors and return
    None so a family still screens on the assets that do have its data.
    Imbalance is aggregated to per-bar means via bar_mean_imbalance.

    Funding uses the ccxt perp symbol form (BASE/USDT:USDT) because the funding
    cache and ccxt both key on that form, not the plain pool symbol."""
    from moonface.data.orderbook import fetch_bookdepth_history
    from moonface.features.orderbook_features import imbalance_points
    from moonface.data.ohlcv import OhlcvCache
    from moonface.data.series import (FundingCache, align_funding,
                                                fetch_funding_history)
    from moonface.research.edge.ob_imbalance_signals import bar_mean_imbalance
    from moonface.data.series import (align_metric,
                                                fetch_metrics_history)

    ohlcv = OhlcvCache(cache_dir)

    def candles(sym, tf):
        bars = ohlcv.load(sym, tf)
        return bars or []

    def funding(sym):
        try:
            funding_symbol = f"{sym[:-4]}/USDT:USDT"   # DOGEUSDT -> DOGE/USDT:USDT
            pts = fetch_funding_history("binance", funding_symbol, start_ms,
                                        end_ms, FundingCache(cache_dir))
            if not pts:
                return None
            return align_funding(ohlcv.load(sym, "4h") or [], pts)
        except Exception:
            return None

    def metrics(sym, field):
        try:
            raw = fetch_metrics_history(sym, start_ms, end_ms, cache_dir)
            pts = [(ts, f[field]) for ts, f in raw if field in f]
            if not pts:
                return None
            return align_metric(ohlcv.load(sym, "4h") or [], pts)
        except Exception:
            return None

    def bookdepth(sym):
        try:
            rows = fetch_bookdepth_history(sym, start_ms, end_ms, cache_dir)
            pts = imbalance_points(rows)
            if not pts:
                return None
            return bar_mean_imbalance(ohlcv.load(sym, "4h") or [], pts)
        except Exception:
            return None

    return {"candles": candles, "funding": funding,
            "metrics": metrics, "bookdepth": bookdepth}
