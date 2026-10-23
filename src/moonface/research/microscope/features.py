"""Causal normalized feature matrix for the Market State Microscope.

Everything is computed from trailing data only. Rolling statistics use
incremental sums over a bounded deque, so truncating future bars can never
change past values (the causality regression test relies on this)."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle

Z_WINDOW = 180      # rolling z-score window in bars (30 days on 4h)
Z_MIN_FRAC = 0.9    # required non-None fraction inside a rolling window

MA_PERIOD = 50
PERSIST_BARS = 12
RVOL_WINDOW = 20
ATR_PERIOD = 14
OI_CHANGE_BARS = 6
RET_BARS = (1, 6, 42)


def rolling_z(values: list[float | None], window: int = Z_WINDOW,
              min_frac: float = Z_MIN_FRAC) -> list[float | None]:
    """Trailing z-score of each value against the last `window` entries
    (inclusive). None until the window is full, for None inputs, when fewer
    than min_frac of the window is non-None, or when the window std is ~0."""
    out: list[float | None] = []
    buf: deque[float | None] = deque()
    s = 0.0
    s2 = 0.0
    n = 0
    for v in values:
        buf.append(v)
        if v is not None:
            s += v
            s2 += v * v
            n += 1
        if len(buf) > window:
            old = buf.popleft()
            if old is not None:
                s -= old
                s2 -= old * old
                n -= 1
        if len(buf) < window or v is None or n < min_frac * window:
            out.append(None)
            continue
        mean = s / n
        var = max(s2 / n - mean * mean, 0.0)
        std = var ** 0.5
        out.append((v - mean) / std if std > 1e-12 else None)
    return out


def pct_returns(closes: list[float], k: int) -> list[float | None]:
    """Simple k-bar percentage return; None for the first k bars."""
    out: list[float | None] = []
    for i, c in enumerate(closes):
        if i < k or closes[i - k] <= 0:
            out.append(None)
        else:
            out.append(c / closes[i - k] - 1.0)
    return out


def dist_from_ma(closes: list[float],
                 period: int = MA_PERIOD) -> list[float | None]:
    """(close - SMA) / SMA with an incremental rolling sum."""
    out: list[float | None] = []
    s = 0.0
    for i, c in enumerate(closes):
        s += c
        if i >= period:
            s -= closes[i - period]
        if i + 1 < period:
            out.append(None)
            continue
        ma = s / period
        out.append((c - ma) / ma if ma > 0 else None)
    return out


def persistence(closes: list[float],
                bars: int = PERSIST_BARS) -> list[float | None]:
    """Sign-consistency of the last `bars` 1-bar returns, mapped to [-1, 1]."""
    rets = pct_returns(closes, 1)
    out: list[float | None] = []
    for i in range(len(rets)):
        window = rets[i - bars + 1: i + 1] if i + 1 >= bars else []
        vals = [r for r in window if r is not None]
        if len(vals) < bars:
            out.append(None)
        else:
            frac = sum(1 for r in vals if r > 0) / bars
            out.append(2.0 * frac - 1.0)
    return out


def realized_vol(closes: list[float],
                 window: int = RVOL_WINDOW) -> list[float | None]:
    """Population stdev of the last `window` 1-bar returns."""
    rets = pct_returns(closes, 1)
    out: list[float | None] = []
    for i in range(len(rets)):
        vals = [r for r in rets[max(0, i - window + 1): i + 1]
                if r is not None]
        if len(vals) < window:
            out.append(None)
            continue
        m = sum(vals) / window
        out.append((sum((r - m) ** 2 for r in vals) / window) ** 0.5)
    return out


def atr_frac(candles: list[Candle],
             period: int = ATR_PERIOD) -> list[float | None]:
    """ATR (simple mean of true range) as a fraction of close."""
    out: list[float | None] = []
    trs: list[float] = []
    s = 0.0
    for i, c in enumerate(candles):
        if i == 0:
            tr = c.high - c.low
        else:
            pc = candles[i - 1].close
            tr = max(c.high - c.low, abs(c.high - pc), abs(c.low - pc))
        trs.append(tr)
        s += tr
        if len(trs) > period:
            s -= trs[len(trs) - period - 1]
        if i + 1 < period or c.close <= 0:
            out.append(None)
        else:
            out.append((s / period) / c.close)
    return out


def range_frac(candles: list[Candle]) -> list[float | None]:
    """(high - low) / close per bar."""
    return [(c.high - c.low) / c.close if c.close > 0 else None
            for c in candles]


def series_change(series: list[float | None] | None,
                  k: int = OI_CHANGE_BARS) -> list[float | None] | None:
    """k-bar relative change of an optional aligned series (e.g. OI)."""
    if series is None:
        return None
    out: list[float | None] = []
    for i in range(len(series)):
        cur = series[i]
        prev = series[i - k] if i >= k else None
        if cur is None or prev is None or prev <= 0:
            out.append(None)
        else:
            out.append(cur / prev - 1.0)
    return out


BETA_WINDOW = 90
XS_MIN_ASSETS = 8

PER_ASSET_COLS = ("ret_1", "ret_6", "ret_42", "dist_ma", "persist", "rvol",
                  "atr", "range", "funding", "oi_chg", "volume")
FEATURE_KEYS = tuple(f"{k}_z" for k in PER_ASSET_COLS) + (
    "rs_xz", "resid_z", "beta_btc")


@dataclass(frozen=True)
class FeatureMatrix:
    """Normalized feature matrix on a shared timestamp axis. rows[sym][t] is
    a dict over FEATURE_KEYS (None where undefined). mkt_ret_z and breadth_z
    are pool-level series on the same axis."""

    symbols: list[str]
    timestamps: list[int]
    rows: dict[str, list[dict[str, float | None]]]
    mkt_ret_z: list[float | None]
    breadth_z: list[float | None]


def rolling_beta(x: list[float | None], y: list[float | None],
                 window: int = BETA_WINDOW,
                 min_frac: float = Z_MIN_FRAC) -> list[float | None]:
    """Trailing OLS beta of x on y over pairwise-complete bars."""
    n = len(x)
    out: list[float | None] = [None] * n
    for t in range(window - 1, n):
        pairs = [(x[j], y[j]) for j in range(t - window + 1, t + 1)
                 if x[j] is not None and y[j] is not None]
        if len(pairs) < min_frac * window:
            continue
        mx = sum(p for p, _ in pairs) / len(pairs)
        my = sum(q for _, q in pairs) / len(pairs)
        var = sum((q - my) ** 2 for _, q in pairs) / len(pairs)
        if var <= 1e-12:
            continue
        cov = sum((p - mx) * (q - my) for p, q in pairs) / len(pairs)
        out[t] = cov / var
    return out


def build_matrix(pool: dict[str, DataBundle],
                 btc_symbol: str = "BTCUSDT") -> FeatureMatrix:
    """Full feature matrix for a bundle pool. Assets may have different
    history lengths; the shared axis is the sorted union of bar-open
    timestamps and an asset's row is all-None where it has no bar."""
    symbols = sorted(pool)
    ts_set: set[int] = set()
    for b in pool.values():
        ts_set.update(c.timestamp_ms for c in b.candles)
    timestamps = sorted(ts_set)
    ts_index = {ts: i for i, ts in enumerate(timestamps)}
    n = len(timestamps)

    rows: dict[str, list[dict[str, float | None]]] = {}
    raw_ret1: dict[str, list[float | None]] = {}
    raw_ret42: dict[str, list[float | None]] = {}
    above_ma: dict[str, list[float | None]] = {}
    for sym in symbols:
        b = pool[sym]
        closes = [c.close for c in b.candles]
        blank: list[float | None] = [None] * len(closes)
        cols: dict[str, list[float | None]] = {
            "ret_1": pct_returns(closes, 1),
            "ret_6": pct_returns(closes, 6),
            "ret_42": pct_returns(closes, 42),
            "dist_ma": dist_from_ma(closes),
            "persist": persistence(closes),
            "rvol": realized_vol(closes),
            "atr": atr_frac(b.candles),
            "range": range_frac(b.candles),
            "funding": list(b.funding) if b.funding else blank,
            "oi_chg": series_change(b.feature) or blank,
            "volume": [c.volume for c in b.candles],
        }
        zcols = {k: rolling_z(v) for k, v in cols.items()}
        sym_rows = [dict.fromkeys(FEATURE_KEYS) for _ in range(n)]
        r1: list[float | None] = [None] * n
        r42: list[float | None] = [None] * n
        ama: list[float | None] = [None] * n
        for i, c in enumerate(b.candles):
            t = ts_index[c.timestamp_ms]
            for k in PER_ASSET_COLS:
                sym_rows[t][f"{k}_z"] = zcols[k][i]
            r1[t] = cols["ret_1"][i]
            r42[t] = cols["ret_42"][i]
            d = cols["dist_ma"][i]
            ama[t] = None if d is None else (1.0 if d > 0 else 0.0)
        rows[sym] = sym_rows
        raw_ret1[sym] = r1
        raw_ret42[sym] = r42
        above_ma[sym] = ama

    # cross-sectional features on the shared axis
    mkt_ret_z: list[float | None] = [None] * n
    breadth_raw: list[float | None] = [None] * n
    for t in range(n):
        r42s = {s: raw_ret42[s][t] for s in symbols
                if raw_ret42[s][t] is not None}
        if len(r42s) >= XS_MIN_ASSETS:
            vals = list(r42s.values())
            m = sum(vals) / len(vals)
            sd = (sum((v - m) ** 2 for v in vals) / len(vals)) ** 0.5
            if sd > 1e-12:
                for s, v in r42s.items():
                    rows[s][t]["rs_xz"] = (v - m) / sd
        z1s = [rows[s][t]["ret_1_z"] for s in symbols
               if rows[s][t]["ret_1_z"] is not None]
        if len(z1s) >= XS_MIN_ASSETS:
            mkt_ret_z[t] = sum(z1s) / len(z1s)
        flags = [above_ma[s][t] for s in symbols
                 if above_ma[s][t] is not None]
        if len(flags) >= XS_MIN_ASSETS:
            breadth_raw[t] = sum(flags) / len(flags)

    btc_r1 = raw_ret1.get(btc_symbol)
    for sym in symbols:
        z1 = [rows[sym][t]["ret_1_z"] for t in range(n)]
        beta_mkt = rolling_beta(z1, mkt_ret_z)
        beta_btc = (rolling_beta(raw_ret1[sym], btc_r1)
                    if btc_r1 is not None else [None] * n)
        for t in range(n):
            rows[sym][t]["beta_btc"] = beta_btc[t]
            if (z1[t] is not None and beta_mkt[t] is not None
                    and mkt_ret_z[t] is not None):
                rows[sym][t]["resid_z"] = z1[t] - beta_mkt[t] * mkt_ret_z[t]

    return FeatureMatrix(symbols=symbols, timestamps=timestamps, rows=rows,
                         mkt_ret_z=mkt_ret_z, breadth_z=rolling_z(breadth_raw))
