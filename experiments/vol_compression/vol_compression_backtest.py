"""Volatility Compression -> Expansion (straddle-proxy) baseline backtest.

Pre-registered confirmatory study -- see DESIGN.md. Direction-agnostic
volatility-expansion capture on BTC 1h: at a volatility squeeze, "buy" a straddle
priced off the compressed vol and win only if realized expansion beats that fair
price plus cost. numpy/pandas only; no network; deterministic.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

_OHLCV = ["open", "high", "low", "close", "volume"]
_SQRT_2_OVER_PI = float(np.sqrt(2.0 / np.pi))  # E|N(0,1)| -- fair ATM straddle payoff


def load_data(ohlcv_path: str, start: str | None = None,
              end: str | None = None) -> pd.DataFrame:
    """Load headerless 1h OHLCV cache: ts_ms, open, high, low, close, volume."""
    df = pd.read_csv(ohlcv_path, header=None, names=["ts", *_OHLCV])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("ts").sort_index()
    if start is not None:
        df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end, tz="UTC")]
    return df[_OHLCV]


def log_returns(close: pd.Series) -> pd.Series:
    return np.log(close / close.shift(1))


def realized_vol(close: pd.Series, n: int) -> pd.Series:
    """Rolling per-bar sigma = std (ddof=1) of the last n hourly log-returns."""
    return log_returns(close).rolling(n, min_periods=n).std(ddof=1)


def atr_pct(df: pd.DataFrame, n: int) -> pd.Series:
    prev = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"],
                    (df["high"] - prev).abs(),
                    (df["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean() / df["close"]


def rolling_pct_threshold(series: pd.Series, window: int, pct: float) -> pd.Series:
    """pct-percentile of the trailing `window` values ending at t-1 (causal)."""
    return series.shift(1).rolling(window, min_periods=window).quantile(pct / 100.0)


def _apply_cooldown(raw: np.ndarray, cooldown: int) -> np.ndarray:
    """Accept a fire only if >= cooldown bars since the previous accepted fire."""
    accepted = np.zeros(len(raw), dtype=bool)
    last = -(10 ** 9)
    for i in np.flatnonzero(raw):
        if i - last >= cooldown:
            accepted[i] = True
            last = i
    return accepted


class VolCompressionStrategy:
    """Volatility-squeeze detector + straddle-proxy pricing. Frozen params per
    DESIGN.md; parameterized only for robustness/stability checks."""

    def __init__(self, rv_period=24, comp_window_days=30, comp_pct=20,
                 cooldown_bars=24, fwd_horizon=24, secondary_horizon=48,
                 cost=0.0006, feature="rv"):
        self.rv_period = rv_period
        self.comp_window = int(round(comp_window_days * 24))
        self.comp_pct = comp_pct
        self.cooldown_bars = cooldown_bars
        self.fwd_horizon = fwd_horizon
        self.secondary_horizon = secondary_horizon
        self.cost = cost
        self.feature = feature

    def feature_vol(self, df: pd.DataFrame) -> pd.Series:
        if self.feature == "rv":
            return realized_vol(df["close"], self.rv_period)
        if self.feature == "atr":
            return atr_pct(df, self.rv_period)
        raise ValueError(f"unknown feature: {self.feature}")

    def compression_signals(self, df: pd.DataFrame) -> pd.Series:
        vol = self.feature_vol(df)
        thr = rolling_pct_threshold(vol, self.comp_window, self.comp_pct)
        raw = (vol <= thr).fillna(False).to_numpy()
        accepted = _apply_cooldown(raw, self.cooldown_bars)
        return pd.Series(accepted, index=df.index)


def straddle_payoffs(df: pd.DataFrame, signals, sigma,
                     horizons=(24, 48), cost: float = 0.0006) -> pd.DataFrame:
    """Per-signal direction-agnostic net straddle payoff for each horizon:
    net_h = |ln(close[i+h]/close[i])| - sqrt(2/pi)*sigma[i]*sqrt(h) - cost.
    Premium is priced off the compressed vol sigma[i]. Right-edge / NaN-sigma
    signals get NaN for that horizon. Returns columns: entry_ts, net_<h>..."""
    closes = df["close"].to_numpy()
    sig = np.asarray(signals.to_numpy() if hasattr(signals, "to_numpy") else signals)
    sigma_a = np.asarray(sigma.to_numpy() if hasattr(sigma, "to_numpy") else sigma)
    n = len(closes)
    cols = ["entry_ts"] + [f"net_{h}" for h in horizons]
    rows = []
    for i in np.flatnonzero(sig):
        rec = {"entry_ts": df.index[i]}
        s = sigma_a[i]
        for h in horizons:
            if i + h < n and not np.isnan(s):
                move = abs(np.log(closes[i + h] / closes[i]))
                premium = _SQRT_2_OVER_PI * s * np.sqrt(h)
                rec[f"net_{h}"] = move - premium - cost
            else:
                rec[f"net_{h}"] = np.nan
        rows.append(rec)
    return pd.DataFrame(rows, columns=cols)


def block_bootstrap_ci(returns, block: int = 20, n_boot: int = 10000,
                       alpha: float = 0.05, seed: int = 0):
    """Moving-block bootstrap 95% CI on the mean. (nan, nan) if empty."""
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    n = len(r)
    if n == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    eff_block = min(block, n)
    n_blocks = int(np.ceil(n / eff_block))
    max_start = n - eff_block
    means = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, max_start + 1, size=n_blocks)
        sample = np.concatenate([r[s:s + eff_block] for s in starts])[:n]
        means[b] = sample.mean()
    return (float(np.quantile(means, alpha / 2)),
            float(np.quantile(means, 1 - alpha / 2)))


def compute_payoffs(df: pd.DataFrame, strategy: "VolCompressionStrategy") -> pd.DataFrame:
    """Full-series signals + payoffs (so slicing by cutoff keeps warmup intact)."""
    sig = strategy.compression_signals(df)
    sigma = strategy.feature_vol(df)
    return straddle_payoffs(df, sig, sigma,
                            horizons=(strategy.fwd_horizon, strategy.secondary_horizon),
                            cost=strategy.cost)


def slice_stats(payoffs: pd.DataFrame, h1: int = 24, h2: int = 48) -> dict:
    r1 = payoffs[f"net_{h1}"].dropna().to_numpy()
    r2 = payoffs[f"net_{h2}"].dropna().to_numpy()
    ci1 = block_bootstrap_ci(r1)
    ci2 = block_bootstrap_ci(r2)
    return {
        "n_signals": int(len(payoffs)),
        "win_rate": float(np.mean(r1 > 0)) if len(r1) else float("nan"),
        "mean_net_1d": float(np.mean(r1)) if len(r1) else float("nan"),
        "mean_net_2d": float(np.mean(r2)) if len(r2) else float("nan"),
        "ci1d_lo": ci1[0], "ci1d_hi": ci1[1],
        "ci2d_lo": ci2[0], "ci2d_hi": ci2[1],
    }


def verdict(oos_stats: dict, min_n: int = 30) -> str:
    if oos_stats["n_signals"] < min_n:
        return "UNDERPOWERED — inconclusive"
    return "PASS" if oos_stats["ci1d_lo"] > 0 else "FAIL"


def format_tear_sheet(label: str, s: dict) -> str:
    return (
        f"── {label} ──\n"
        f"  signals            : {s['n_signals']}\n"
        f"  win-rate (1d net>0): {s['win_rate']:.3f}   [descriptive]\n"
        f"  mean net  1d       : {s['mean_net_1d']:+.6f}\n"
        f"  mean net  2d       : {s['mean_net_2d']:+.6f}\n"
        f"  95% CI 2d          : [{s['ci2d_lo']:+.6f}, {s['ci2d_hi']:+.6f}]\n"
        f"  95% CI 1d (GATE)   : [{s['ci1d_lo']:+.6f}, {s['ci1d_hi']:+.6f}]\n"
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Vol Compression -> Expansion straddle-proxy backtest")
    p.add_argument("--ohlcv", default=".backtest_cache/BTCUSDT_1h.csv")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--oos-cutoff", default="2024-07-01")
    p.add_argument("--feature", choices=["rv", "atr"], default="rv")
    p.add_argument("--rv-period", type=int, default=24)
    p.add_argument("--comp-pct", type=float, default=20)
    p.add_argument("--fwd-horizon", type=int, default=24)
    p.add_argument("--secondary-horizon", type=int, default=48)
    p.add_argument("--cost", type=float, default=0.0006)
    p.add_argument("--min-oos", type=int, default=30)
    args = p.parse_args(argv)

    df = load_data(args.ohlcv, start=args.start)
    strat = VolCompressionStrategy(rv_period=args.rv_period, comp_pct=args.comp_pct,
                                   fwd_horizon=args.fwd_horizon,
                                   secondary_horizon=args.secondary_horizon,
                                   cost=args.cost, feature=args.feature)
    payoffs = compute_payoffs(df, strat)
    cutoff = pd.Timestamp(args.oos_cutoff, tz="UTC")
    in_p = payoffs[payoffs["entry_ts"] < cutoff]
    oos_p = payoffs[payoffs["entry_ts"] >= cutoff]
    h1, h2 = strat.fwd_horizon, strat.secondary_horizon
    in_stats = slice_stats(in_p, h1, h2)
    oos_stats = slice_stats(oos_p, h1, h2)
    v = verdict(oos_stats, min_n=args.min_oos)

    print(f"Vol Compression -> Expansion — feature={args.feature} cutoff={args.oos_cutoff}")
    print(format_tear_sheet("IN-SAMPLE (descriptive)", in_stats))
    print(format_tear_sheet("SEALED OOS (confirmatory)", oos_stats))
    print(f"VERDICT (sealed OOS, 1d net CI vs 0): {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
