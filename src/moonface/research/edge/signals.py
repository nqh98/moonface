from __future__ import annotations

from moonface.core.indicators import roc, rolling_std, rsi, sma
from moonface.research.edge._smc import (detect_choch, detect_liquidity,
                                         detect_sweeps, find_swings)
from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.research.edge.filters import pivot_bias, pivot_levelbreak, pivot_proximity
from moonface.research.edge.pivots import daily_pivots

Entry = tuple[int, str]  # (entry_index, "LONG" | "SHORT")


def ma_cross(h1: list[Candle], params: dict) -> list[Entry]:
    fast, slow = params["fast"], params["slow"]
    closes = [c.close for c in h1]
    out: list[Entry] = []
    for i in range(slow, len(h1) - 1):
        # sma reads only the last `period` closes, so pass a bounded window
        # instead of the full prefix -- avoids O(n^2) slicing. Output identical.
        f_now, s_now = (sma(closes[max(0, i - fast): i + 1], fast),
                        sma(closes[max(0, i - slow): i + 1], slow))
        f_prev, s_prev = (sma(closes[max(0, i - 1 - fast): i], fast),
                          sma(closes[max(0, i - 1 - slow): i], slow))
        if f_prev <= s_prev and f_now > s_now:
            out.append((i, "LONG"))
        elif f_prev >= s_prev and f_now < s_now:
            out.append((i, "SHORT"))
    return out


def price_vs_ma(h1: list[Candle], params: dict) -> list[Entry]:
    period = params["period"]
    closes = [c.close for c in h1]
    out: list[Entry] = []
    for i in range(period, len(h1) - 1):
        ma_now, ma_prev = (sma(closes[max(0, i - period): i + 1], period),
                           sma(closes[max(0, i - 1 - period): i], period))
        if closes[i - 1] <= ma_prev and closes[i] > ma_now:
            out.append((i, "LONG"))
        elif closes[i - 1] >= ma_prev and closes[i] < ma_now:
            out.append((i, "SHORT"))
    return out


def roc_sign(h1: list[Candle], params: dict) -> list[Entry]:
    period = params["period"]
    closes = [c.close for c in h1]
    out: list[Entry] = []
    for i in range(period + 1, len(h1) - 1):
        now = roc(closes[max(0, i - period): i + 1], period)
        prev = roc(closes[max(0, i - 1 - period): i], period)
        if prev <= 0 < now:
            out.append((i, "LONG"))
        elif prev >= 0 > now:
            out.append((i, "SHORT"))
    return out


def donchian_break(h1: list[Candle], params: dict) -> list[Entry]:
    n = params["n"]
    long_only = params.get("long_only", False)  # deployable swing trades longs only
    out: list[Entry] = []
    for i in range(n, len(h1) - 1):
        prior_high = max(c.high for c in h1[i - n:i])
        prior_low = min(c.low for c in h1[i - n:i])
        if h1[i].close > prior_high:
            out.append((i, "LONG"))
        elif not long_only and h1[i].close < prior_low:
            out.append((i, "SHORT"))
    return out


def atr_channel_break(h1: list[Candle], params: dict) -> list[Entry]:
    k, period = params["k"], params["atr_period"]
    out: list[Entry] = []
    for i in range(period + 1, len(h1) - 1):
        # atr reads only the last `period` candles (plus one prior close), so a
        # bounded window matches the full-prefix value without O(n^2) slicing.
        a = atr(h1[max(0, i - period): i + 1], period)
        if a <= 0:
            continue
        upper = h1[i - 1].close + k * a
        lower = h1[i - 1].close - k * a
        if h1[i].close > upper:
            out.append((i, "LONG"))
        elif h1[i].close < lower:
            out.append((i, "SHORT"))
    return out


_SMC_WARMUP = 60
_SMC_N_PERIODS = 5
_SMC_ATR_PERIOD = 14
_SMC_DISPLACEMENT_MULT = 1.5
# Mirrors runner.H1_WINDOW_CAP: the production advisor only ever sees the last
# 100 H1 bars, so the SMC detectors must run on the same bounded window. This is
# both faithful (we invert exactly what the advisor would do) and what keeps the
# detectors' per-bar cost constant instead of growing with history.
_SMC_WINDOW_CAP = 100


def smc_continuation(h1: list[Candle], params: dict) -> list[Entry]:
    """Invert the advisor's reversal entry: emit the opposite side of the sweep
    reversal it would have taken. Tests whether the SMC signal is anti-predictive."""
    lookback = params["lookback"]
    out: list[Entry] = []
    for i in range(_SMC_WARMUP, len(h1) - 1):
        window = h1[max(0, i + 1 - _SMC_WINDOW_CAP): i + 1]
        a = atr(window, _SMC_ATR_PERIOD)
        if a <= 0:
            continue
        tol = max(0.25 * a, 1e-9)
        pools = detect_liquidity(window, tolerance=tol).pools
        sweeps = detect_sweeps(window, pools)
        min_index = max(0, len(window) - lookback)
        recent = [s for s in sweeps if s.index >= min_index]
        if not recent:
            continue
        sweep = recent[-1]
        # Advisor's reversal: SELL-side sweep -> bullish CHOCH -> LONG (and vice versa).
        rev_direction = "BULLISH" if sweep.side == "SELL" else "BEARISH"
        event = detect_choch(window, rev_direction, sweep.index, a,
                             _SMC_DISPLACEMENT_MULT, _SMC_N_PERIODS)
        if event is None:
            continue
        reversal_side = "LONG" if rev_direction == "BULLISH" else "SHORT"
        flipped = "SHORT" if reversal_side == "LONG" else "LONG"
        out.append((i, flipped))
    return out


_REVERSION_N_PERIODS = 5


def _structure_trend_series(h1: list[Candle], n_periods: int) -> list[str]:
    """Per-bar structure trend, identical to evaluating
    ``classify_structure(h1[: i + 1], n_periods).trend`` at every bar but O(n)
    instead of O(n^2). Swings are computed once over the full series and walked
    forward: a swing at index ``s`` is confirmed by bars in ``[s-n, s+n]``, so
    the swings ``find_swings(h1[: i + 1])`` would surface are exactly those with
    index ``<= i - n_periods`` -- the same set the forward walk accumulates."""
    swings = find_swings(h1, n_periods)
    highs, lows = swings.highs, swings.lows
    out = ["NEUTRAL"] * len(h1)
    hi = lo = 0  # count of swings eligible at the current bar
    for i in range(len(h1)):
        limit = i - n_periods
        while hi < len(highs) and highs[hi][0] <= limit:
            hi += 1
        while lo < len(lows) and lows[lo][0] <= limit:
            lo += 1
        if hi >= 2 and lo >= 2:
            higher_high = highs[hi - 1][1] > highs[hi - 2][1]
            higher_low = lows[lo - 1][1] > lows[lo - 2][1]
            lower_high = highs[hi - 1][1] < highs[hi - 2][1]
            lower_low = lows[lo - 1][1] < lows[lo - 2][1]
            if higher_high and higher_low:
                out[i] = "BULLISH"
            elif lower_high and lower_low:
                out[i] = "BEARISH"
    return out


def reversion_in_range(h1: list[Candle], params: dict) -> list[Entry]:
    period, low, high = params["period"], params["low"], params["high"]
    closes = [c.close for c in h1]
    trend = _structure_trend_series(h1, _REVERSION_N_PERIODS)
    out: list[Entry] = []
    for i in range(period + 1, len(h1) - 1):
        if trend[i] != "NEUTRAL":
            continue
        # rsi reads only the last `period` closes; bounded window == full prefix.
        value = rsi(closes[max(0, i - period): i + 1], period)
        if value <= low:
            out.append((i, "LONG"))
        elif value >= high:
            out.append((i, "SHORT"))
    return out


def bb_revert(h1: list[Candle], params: dict) -> list[Entry]:
    """Mean-reversion fade of Bollinger bands. LONG when close crosses below the
    lower band, SHORT when it crosses above the upper band. Bounded windows keep
    per-bar cost O(period) (no O(n^2) slicing); output is identical to a full prefix."""
    period = params["period"]
    mult = params["mult"]
    closes = [c.close for c in h1]
    out: list[Entry] = []
    for i in range(period + 1, len(h1) - 1):
        now = closes[max(0, i - period + 1): i + 1]      # last `period` closes incl. i
        prev = closes[max(0, i - period): i]             # prior `period` closes (.. i-1)
        mid_n, sd_n = sma(now, period), rolling_std(now, period)
        mid_p, sd_p = sma(prev, period), rolling_std(prev, period)
        lower_n, upper_n = mid_n - mult * sd_n, mid_n + mult * sd_n
        lower_p, upper_p = mid_p - mult * sd_p, mid_p + mult * sd_p
        c_prev, c_now = closes[i - 1], closes[i]
        if c_prev >= lower_p and c_now < lower_n:
            out.append((i, "LONG"))
        elif c_prev <= upper_p and c_now > upper_n:
            out.append((i, "SHORT"))
    return out


def bb_breakout(h1: list[Candle], params: dict) -> list[Entry]:
    """Momentum breakout of Bollinger bands (the mirror of bb_revert). LONG when
    close crosses above the upper band, SHORT when it crosses below the lower band.
    Bounded windows keep per-bar cost O(period) (no O(n^2) slicing); output is
    identical to a full prefix."""
    period = params["period"]
    mult = params["mult"]
    closes = [c.close for c in h1]
    out: list[Entry] = []
    for i in range(period + 1, len(h1) - 1):
        now = closes[max(0, i - period + 1): i + 1]      # last `period` closes incl. i
        prev = closes[max(0, i - period): i]             # prior `period` closes (.. i-1)
        mid_n, sd_n = sma(now, period), rolling_std(now, period)
        mid_p, sd_p = sma(prev, period), rolling_std(prev, period)
        lower_n, upper_n = mid_n - mult * sd_n, mid_n + mult * sd_n
        lower_p, upper_p = mid_p - mult * sd_p, mid_p + mult * sd_p
        c_prev, c_now = closes[i - 1], closes[i]
        if c_prev <= upper_p and c_now > upper_n:
            out.append((i, "LONG"))
        elif c_prev >= lower_p and c_now < lower_n:
            out.append((i, "SHORT"))
    return out


def with_filter(base_gen, filter_fn):
    """Compose a base signal generator with a pivot filter. The grid params dict
    carries both halves: params["base"] for the generator, params["filter"] for
    the filter, so each leaderboard row is self-describing."""
    def gen(h1: list[Candle], params: dict) -> list[Entry]:
        pivots = daily_pivots(h1)
        base_entries = base_gen(h1, params["base"])
        return filter_fn(h1, base_entries, pivots, params["filter"])
    return gen


_ATR_BASE = {"k": 2.0, "atr_period": 14}   # highest-drift atr_channel_break param
_DON_BASE = {"n": 100}                      # highest-drift donchian_break param


# name -> (generator, list of param dicts). Grids kept small (YAGNI).
REGISTRY: dict[str, tuple] = {
    "ma_cross": (ma_cross, [{"fast": 10, "slow": 50}, {"fast": 20, "slow": 100},
                            {"fast": 50, "slow": 200}]),
    "price_vs_ma": (price_vs_ma, [{"period": 50}, {"period": 100}, {"period": 200}]),
    "roc_sign": (roc_sign, [{"period": 12}, {"period": 24}, {"period": 48}]),
    "donchian_break": (donchian_break, [{"n": 20}, {"n": 55}, {"n": 100}]),
    "atr_channel_break": (atr_channel_break, [{"k": 1.0, "atr_period": 14},
                                              {"k": 1.5, "atr_period": 14},
                                              {"k": 2.0, "atr_period": 14}]),
    "smc_continuation": (smc_continuation, [{"lookback": 10}, {"lookback": 30}]),
    "reversion_in_range": (reversion_in_range,
                           [{"period": 14, "low": 30, "high": 70},
                            {"period": 14, "low": 20, "high": 80}]),
    "atr_channel_break|pivot_bias": (
        with_filter(atr_channel_break, pivot_bias),
        [{"base": _ATR_BASE, "filter": {}}]),
    "atr_channel_break|pivot_proximity": (
        with_filter(atr_channel_break, pivot_proximity),
        [{"base": _ATR_BASE, "filter": {"x": 0.25, "atr_period": 14}},
         {"base": _ATR_BASE, "filter": {"x": 0.5, "atr_period": 14}}]),
    "atr_channel_break|pivot_levelbreak": (
        with_filter(atr_channel_break, pivot_levelbreak),
        [{"base": _ATR_BASE, "filter": {}}]),
    "donchian_break|pivot_bias": (
        with_filter(donchian_break, pivot_bias),
        [{"base": _DON_BASE, "filter": {}}]),
    "donchian_break|pivot_proximity": (
        with_filter(donchian_break, pivot_proximity),
        [{"base": _DON_BASE, "filter": {"x": 0.25, "atr_period": 14}},
         {"base": _DON_BASE, "filter": {"x": 0.5, "atr_period": 14}}]),
    "donchian_break|pivot_levelbreak": (
        with_filter(donchian_break, pivot_levelbreak),
        [{"base": _DON_BASE, "filter": {}}]),
}
