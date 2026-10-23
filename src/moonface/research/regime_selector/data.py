from __future__ import annotations

from moonface.data.macro import fetch_fred_series
from moonface.research.regime_selector.grid import (BTC_SYMBOL, BTC_TF,
                                                    FRED_SERIES)
from moonface.data.universe import fetch_perp_candles


def load_macro(cache_dir: str, fetch=fetch_fred_series) -> dict[str, list]:
    return {sid: fetch(sid, cache_dir) for sid in FRED_SERIES}


def load_btc(start_ms: int, end_ms: int, cache_dir: str):
    return fetch_perp_candles(BTC_SYMBOL, BTC_TF, start_ms, end_ms, cache_dir)
