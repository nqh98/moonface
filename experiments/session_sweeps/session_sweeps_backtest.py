"""Time-of-Day / Session-Sweep (fade) baseline backtest.

Pre-registered confirmatory study - see DESIGN.md. Fade prior-session high/low
liquidity sweeps on BTC 15m. numpy/pandas only; no network; deterministic.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

_OHLCV_COLS = ["open", "high", "low", "close", "volume"]


def load_data(
    ohlcv_path: str, start: str | None = None, end: str | None = None
) -> pd.DataFrame:
    """Load headerless 15m OHLCV cache: ts_ms, open, high, low, close, volume."""
    df = pd.read_csv(ohlcv_path, header=None, names=["ts", *_OHLCV_COLS])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("ts").sort_index()
    if start is not None:
        df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end, tz="UTC")]
    return df[_OHLCV_COLS]


def tag_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Tag each bar with its 8h UTC session and the prior block's high/low."""
    tagged = df.copy()
    block_start = tagged.index.floor("8h")
    codes, _ = pd.factorize(block_start)
    tagged["session_id"] = (block_start.hour // 8).to_numpy()
    tagged["session_key"] = codes
    block_high = tagged.groupby("session_key")["high"].max()
    block_low = tagged.groupby("session_key")["low"].min()
    tagged["prior_high"] = tagged["session_key"].map(block_high.shift(1))
    tagged["prior_low"] = tagged["session_key"].map(block_low.shift(1))
    return tagged


class SessionSweepStrategy:
    """Fade or follow prior-session high/low sweeps."""

    def __init__(self, mode="reversal", fwd_horizon=16, secondary_horizon=8):
        self.mode = mode
        self.fwd_horizon = fwd_horizon
        self.secondary_horizon = secondary_horizon

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        ph = df["prior_high"].to_numpy()
        pl = df["prior_low"].to_numpy()
        high = df["high"].to_numpy()
        low = df["low"].to_numpy()
        close = df["close"].to_numpy()

        with np.errstate(invalid="ignore"):
            if self.mode == "reversal":
                short_c = (high > ph) & (close < ph)
                long_c = (low < pl) & (close > pl)
            elif self.mode == "continuation":
                long_c = close > ph
                short_c = close < pl
            else:
                raise ValueError(f"unknown mode: {self.mode}")

        valid = ~(np.isnan(ph) | np.isnan(pl))
        short_c = short_c & valid
        long_c = long_c & valid
        ambiguous = short_c & long_c
        short_c = short_c & ~ambiguous
        long_c = long_c & ~ambiguous
        direction = np.where(long_c, 1, np.where(short_c, -1, 0))

        keys = df["session_key"].to_numpy()
        rows = []
        seen = set()
        for i in np.flatnonzero(direction != 0):
            key = keys[i]
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "entry_ts": df.index[i],
                    "entry_price": float(close[i]),
                    "direction": int(direction[i]),
                }
            )
        return pd.DataFrame(rows, columns=["entry_ts", "entry_price", "direction"])


def signed_forward_returns(
    df: pd.DataFrame, signals: pd.DataFrame, horizons=(8, 16)
) -> dict[int, np.ndarray]:
    closes = df["close"].to_numpy()
    n_closes = len(closes)
    if len(signals) == 0:
        return {h: np.asarray([], dtype=float) for h in horizons}

    positions = df.index.get_indexer(pd.DatetimeIndex(signals["entry_ts"]))
    directions = signals["direction"].to_numpy()
    out = {}
    for horizon in horizons:
        ok = (positions >= 0) & (positions + horizon < n_closes)
        ii = positions[ok]
        out[horizon] = directions[ok] * np.log(closes[ii + horizon] / closes[ii])
    return out


def block_bootstrap_ci(
    returns, block: int = 20, n_boot: int = 10000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float]:
    series = np.asarray(returns, dtype=float)
    series = series[~np.isnan(series)]
    n_series = len(series)
    if n_series == 0:
        return (float("nan"), float("nan"))

    rng = np.random.default_rng(seed)
    eff_block = min(block, n_series)
    n_blocks = int(np.ceil(n_series / eff_block))
    max_start = n_series - eff_block
    means = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, max_start + 1, size=n_blocks)
        sample = np.concatenate([series[s:s + eff_block] for s in starts])[:n_series]
        means[b] = sample.mean()
    return (
        float(np.quantile(means, alpha / 2)),
        float(np.quantile(means, 1 - alpha / 2)),
    )


def slice_stats(df_tagged: pd.DataFrame, strategy: SessionSweepStrategy) -> dict:
    signals = strategy.generate_signals(df_tagged)
    h2 = strategy.secondary_horizon
    h4 = strategy.fwd_horizon
    forward = signed_forward_returns(df_tagged, signals, horizons=(h2, h4))
    r2 = forward[h2]
    r4 = forward[h4]
    ci2_lo, ci2_hi = block_bootstrap_ci(r2)
    ci4_lo, ci4_hi = block_bootstrap_ci(r4)
    return {
        "n_signals": int(len(signals)),
        "win_rate": float(np.mean(r4 > 0)) if len(r4) else float("nan"),
        "mean_fwd_2h": float(np.mean(r2)) if len(r2) else float("nan"),
        "mean_fwd_4h": float(np.mean(r4)) if len(r4) else float("nan"),
        "ci2_lo": ci2_lo,
        "ci2_hi": ci2_hi,
        "ci4_lo": ci4_lo,
        "ci4_hi": ci4_hi,
    }


def verdict(oos_stats: dict, min_n: int = 30) -> str:
    if oos_stats["n_signals"] < min_n:
        return "UNDERPOWERED - inconclusive"
    return "PASS" if oos_stats["ci4_lo"] > 0 else "FAIL"


def format_tear_sheet(label: str, stats: dict) -> str:
    return (
        f"── {label} ──\n"
        f"  signals            : {stats['n_signals']}\n"
        f"  hit-rate (4H>0)    : {stats['win_rate']:.3f}   [descriptive]\n"
        f"  mean signed  2H    : {stats['mean_fwd_2h']:+.5f}\n"
        f"  mean signed  4H    : {stats['mean_fwd_4h']:+.5f}\n"
        f"  95% CI  2H         : [{stats['ci2_lo']:+.5f}, {stats['ci2_hi']:+.5f}]\n"
        f"  95% CI  4H (GATE)  : [{stats['ci4_lo']:+.5f}, {stats['ci4_hi']:+.5f}]\n"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Session-Sweep fade backtest")
    parser.add_argument("--ohlcv", default=".backtest_cache/BTCUSDT_15m.csv")
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--oos-cutoff", default="2024-07-01")
    parser.add_argument("--mode", choices=["reversal", "continuation"], default="reversal")
    parser.add_argument("--fwd-horizon", type=int, default=16)
    parser.add_argument("--secondary-horizon", type=int, default=8)
    parser.add_argument("--min-oos", type=int, default=30)
    args = parser.parse_args(argv)

    df = load_data(args.ohlcv, start=args.start)
    tagged = tag_sessions(df)
    strategy = SessionSweepStrategy(
        mode=args.mode,
        fwd_horizon=args.fwd_horizon,
        secondary_horizon=args.secondary_horizon,
    )
    cutoff = pd.Timestamp(args.oos_cutoff, tz="UTC")
    in_stats = slice_stats(tagged[tagged.index < cutoff], strategy)
    oos_stats = slice_stats(tagged[tagged.index >= cutoff], strategy)
    outcome = verdict(oos_stats, min_n=args.min_oos)

    print(f"Session Sweeps - mode={args.mode} cutoff={args.oos_cutoff}")
    print(format_tear_sheet("IN-SAMPLE (descriptive)", in_stats))
    print(format_tear_sheet("SEALED OOS (confirmatory)", oos_stats))
    print(f"VERDICT (sealed OOS, 4H CI vs 0): {outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
