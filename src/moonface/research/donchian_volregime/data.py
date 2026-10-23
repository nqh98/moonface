from __future__ import annotations

from moonface.research.donchian_volregime.grid import SYMBOL, TF
from moonface.research.universe_data import fetch_funding_rates, fetch_perp_candles


def load(start_ms: int, end_ms: int, cache_dir: str):
    candles = fetch_perp_candles(SYMBOL, TF, start_ms, end_ms, cache_dir)
    funding = fetch_funding_rates(SYMBOL, start_ms, end_ms, cache_dir)
    return candles, funding
