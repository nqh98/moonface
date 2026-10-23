"""Deterministic, no-network synthetic data for macro_regime tests."""
import numpy as np
import pandas as pd


def make_synthetic_raw(n=900, seed=0):
    """A `raw`-shaped frame: bdate index, level columns DXY, TNX, GOLD, BTC."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-01", periods=n)
    dxy = 95 + rng.normal(0, 0.3, n).cumsum() * 0.1
    gold = 1500 + rng.normal(0, 5, n).cumsum() * 0.1
    tnx = 25 + rng.normal(0, 0.05, n).cumsum() * 0.1
    btc = 8000 + rng.normal(0, 200, n).cumsum() * 0.1
    return pd.DataFrame({"DXY": dxy, "TNX": tnx, "GOLD": gold, "BTC": btc}, index=dates)


def make_synthetic_fetcher(n=900, seed=0):
    """A fetcher(ticker, start, end) -> Series, backed by make_synthetic_raw columns."""
    raw = make_synthetic_raw(n=n, seed=seed)
    col_by_ticker = {"DX-Y.NYB": "DXY", "^TNX": "TNX", "GC=F": "GOLD", "BTC-USD": "BTC"}

    def fetch(ticker, start, end):
        col = col_by_ticker[ticker]
        return raw[col].rename(ticker).copy()

    return fetch
