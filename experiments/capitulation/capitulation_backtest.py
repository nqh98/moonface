"""Quantitative Capitulation (mean-reversion) baseline backtest.

Pre-registered confirmatory study — see DESIGN.md. Long-only capitulation fade on
BTC 1H. numpy/pandas only; no network; deterministic.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

_OHLCV_COLS = ["open", "high", "low", "close", "volume"]


def load_data(
    ohlcv_path: str,
    funding_path: str,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    """Load headerless OHLCV + funding caches, align funding onto the hourly grid."""
    ohlcv = pd.read_csv(ohlcv_path, header=None, names=["ts", *_OHLCV_COLS])
    ohlcv["ts"] = pd.to_datetime(ohlcv["ts"], unit="ms", utc=True)
    ohlcv = ohlcv.set_index("ts").sort_index()

    funding = pd.read_csv(funding_path, header=None, names=["ts", "funding"])
    funding["ts"] = pd.to_datetime(funding["ts"], unit="ms", utc=True)
    funding = funding.set_index("ts").sort_index()

    merged = pd.merge_asof(
        ohlcv,
        funding,
        left_index=True,
        right_index=True,
        direction="backward",
    )
    merged = merged.dropna(subset=["funding"])

    if start is not None:
        merged = merged[merged.index >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        merged = merged[merged.index <= pd.Timestamp(end, tz="UTC")]

    return merged[_OHLCV_COLS + ["funding"]]


def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def keltner_lower(df: pd.DataFrame, ema_n: int, atr_n: int, mult: float) -> pd.Series:
    mid = ema(df["close"], ema_n)
    lower = mid - mult * atr(df, atr_n)
    return lower.shift(1)


def rolling_pct_threshold(series: pd.Series, window: int, pct: float) -> pd.Series:
    return series.shift(1).rolling(window, min_periods=window).quantile(pct / 100.0)


class CapitulationStrategy:
    """Long-only capitulation-fade signal generator."""

    def __init__(
        self,
        ema_period=20,
        atr_period=20,
        atr_mult=3.0,
        vol_pct=95,
        vol_window_days=30,
        funding_pct=5,
        funding_window_days=30,
        funding_mode="percentile",
        fixed_funding_thresh=-0.0001,
        cooldown_bars=24,
        tp=0.02,
        sl=0.01,
        timeout_bars=48,
    ):
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.vol_pct = vol_pct
        self.vol_window = vol_window_days * 24
        self.funding_pct = funding_pct
        self.funding_window = funding_window_days * 24
        self.funding_mode = funding_mode
        self.fixed_funding_thresh = fixed_funding_thresh
        self.cooldown_bars = cooldown_bars
        self.tp = tp
        self.sl = sl
        self.timeout_bars = timeout_bars

    def _raw_conditions(self, df: pd.DataFrame) -> pd.Series:
        lower = keltner_lower(df, self.ema_period, self.atr_period, self.atr_mult)
        cond1 = df["close"] < lower

        vol_thr = rolling_pct_threshold(df["volume"], self.vol_window, self.vol_pct)
        cond2 = (df["volume"] >= vol_thr) & (df["close"] < df["open"])

        if self.funding_mode == "percentile":
            fund_thr = rolling_pct_threshold(
                df["funding"], self.funding_window, self.funding_pct
            )
            cond3 = df["funding"] <= fund_thr
        elif self.funding_mode == "fixed":
            cond3 = df["funding"] <= self.fixed_funding_thresh
        else:
            raise ValueError(f"unknown funding_mode: {self.funding_mode}")

        return (cond1 & cond2 & cond3).fillna(False)

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        raw = self._raw_conditions(df).to_numpy()
        accepted = np.zeros(len(raw), dtype=bool)
        last = -10**9
        for i in np.flatnonzero(raw):
            if i - last >= self.cooldown_bars:
                accepted[i] = True
                last = i
        return pd.Series(accepted, index=df.index)


def simulate_trades(
    df: pd.DataFrame,
    signals: pd.Series,
    tp: float = 0.02,
    sl: float = 0.01,
    timeout_bars: int = 48,
) -> pd.DataFrame:
    """Long-only SL-first TP/SL/timeout simulation. Entry = signal bar close."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    n = len(df)
    sig_pos = np.flatnonzero(signals.to_numpy())

    rows = []
    for i in sig_pos:
        entry = closes[i]
        tp_price = entry * (1 + tp)
        sl_price = entry * (1 - sl)
        outcome = None
        bars_held = 0
        last_close = entry
        end = min(i + timeout_bars, n - 1)
        for j in range(i + 1, end + 1):
            bars_held = j - i
            last_close = closes[j]
            if lows[j] <= sl_price:
                outcome = "loss"
                break
            if highs[j] >= tp_price:
                outcome = "win"
                break
        if outcome is None:
            outcome = "scratch_win" if last_close > entry else "scratch_loss"
        rows.append(
            {
                "entry_ts": df.index[i],
                "entry_price": entry,
                "outcome": outcome,
                "bars_held": bars_held,
            }
        )

    return pd.DataFrame(
        rows, columns=["entry_ts", "entry_price", "outcome", "bars_held"]
    )


def forward_log_returns(
    df: pd.DataFrame, signals: pd.Series, horizons=(4, 24)
) -> dict[int, np.ndarray]:
    closes = df["close"].to_numpy()
    n = len(closes)
    sig_pos = np.flatnonzero(signals.to_numpy())
    out = {}
    for h in horizons:
        vals = [np.log(closes[i + h] / closes[i]) for i in sig_pos if i + h < n]
        out[h] = np.asarray(vals, dtype=float)
    return out


def block_bootstrap_ci(
    returns,
    block: int = 24,
    n_boot: int = 10000,
    alpha: float = 0.05,
    seed: int = 0,
):
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
        sample = np.concatenate([r[s : s + eff_block] for s in starts])[:n]
        means[b] = sample.mean()
    return (
        float(np.quantile(means, alpha / 2)),
        float(np.quantile(means, 1 - alpha / 2)),
    )


def slice_stats(df: pd.DataFrame, strategy: "CapitulationStrategy") -> dict:
    sig = strategy.generate_signals(df)
    trades = simulate_trades(df, sig, strategy.tp, strategy.sl, strategy.timeout_bars)
    fwd = forward_log_returns(df, sig, horizons=(4, 24))

    n = int(sig.sum())
    if len(trades):
        wins = trades["outcome"].isin(["win", "scratch_win"]).sum()
        win_rate = wins / len(trades)
    else:
        win_rate = float("nan")

    ci4 = block_bootstrap_ci(fwd[4])
    ci24 = block_bootstrap_ci(fwd[24])
    return {
        "n_signals": n,
        "win_rate": win_rate,
        "mean_fwd_4h": float(np.mean(fwd[4])) if len(fwd[4]) else float("nan"),
        "mean_fwd_24h": float(np.mean(fwd[24])) if len(fwd[24]) else float("nan"),
        "ci4_lo": ci4[0],
        "ci4_hi": ci4[1],
        "ci24_lo": ci24[0],
        "ci24_hi": ci24[1],
    }


def verdict(oos_stats: dict, min_n: int = 20) -> str:
    if oos_stats["n_signals"] < min_n:
        return "UNDERPOWERED — inconclusive"
    return "PASS" if oos_stats["ci24_lo"] > 0 else "FAIL"


def format_tear_sheet(label: str, stats: dict) -> str:
    return (
        f"── {label} ──\n"
        f"  signals            : {stats['n_signals']}\n"
        f"  win-rate (TP/SL)   : {stats['win_rate']:.3f}   [descriptive]\n"
        f"  mean fwd  4H logret : {stats['mean_fwd_4h']:+.5f}\n"
        f"  mean fwd 24H logret : {stats['mean_fwd_24h']:+.5f}\n"
        f"  95% CI  4H         : [{stats['ci4_lo']:+.5f}, {stats['ci4_hi']:+.5f}]\n"
        f"  95% CI 24H (GATE)  : [{stats['ci24_lo']:+.5f}, {stats['ci24_hi']:+.5f}]\n"
    )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Quantitative Capitulation backtest")
    p.add_argument("--ohlcv", default=".backtest_cache/BTCUSDT_1h.csv")
    p.add_argument("--funding", default=".backtest_cache/unifunding_BTCUSDT.csv")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--oos-cutoff", default="2024-07-01")
    p.add_argument("--funding-mode", choices=["percentile", "fixed"], default="percentile")
    p.add_argument("--ema-period", type=int, default=20)
    p.add_argument("--atr-period", type=int, default=20)
    p.add_argument("--atr-mult", type=float, default=3.0)
    p.add_argument("--vol-pct", type=float, default=95)
    p.add_argument("--vol-window-days", type=int, default=30)
    p.add_argument("--funding-pct", type=float, default=5)
    p.add_argument("--funding-window-days", type=int, default=30)
    p.add_argument("--cooldown-bars", type=int, default=24)
    p.add_argument("--min-oos", type=int, default=20)
    args = p.parse_args(argv)

    df = load_data(args.ohlcv, args.funding, start=args.start)
    strat = CapitulationStrategy(
        ema_period=args.ema_period,
        atr_period=args.atr_period,
        atr_mult=args.atr_mult,
        vol_pct=args.vol_pct,
        vol_window_days=args.vol_window_days,
        funding_pct=args.funding_pct,
        funding_window_days=args.funding_window_days,
        funding_mode=args.funding_mode,
        cooldown_bars=args.cooldown_bars,
    )
    cutoff = pd.Timestamp(args.oos_cutoff, tz="UTC")
    in_df = df[df.index < cutoff]
    oos_df = df[df.index >= cutoff]

    in_stats = slice_stats(in_df, strat)
    oos_stats = slice_stats(oos_df, strat)
    v = verdict(oos_stats, min_n=args.min_oos)

    print(
        f"Quantitative Capitulation — funding_mode={args.funding_mode} "
        f"cutoff={args.oos_cutoff}"
    )
    print(format_tear_sheet("IN-SAMPLE (descriptive)", in_stats))
    print(format_tear_sheet("SEALED OOS (confirmatory)", oos_stats))
    print(f"VERDICT (sealed OOS, 24H CI vs 0): {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
