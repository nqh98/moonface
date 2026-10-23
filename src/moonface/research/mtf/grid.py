"""Frozen MTF grid: HTF bias functions, LTF triggers, TF-scaled 15m exits, cells.

Bias functions return a +1/-1/0 regime per HTF bar (long-only / short-only /
flat). Triggers are reused verbatim from the price-signal library so the L/S
entry semantics are identical to every other lane. Exits are scaled to 15m bars
(1 day = 96 bars). The cell grid is small and explicit (YAGNI); n_trials for the
DSR deflation is exactly len(CELLS)."""
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.indicators import roc, rolling_std, sma
from moonface.core.models import Candle
from moonface.research.edge.signals import (bb_breakout, donchian_break,
                                            roc_sign)
from moonface.research.mtf.triggers import ma_reclaim, rsi_reversion

BASE_TF = "15m"
_BARS_PER_DAY = 96               # 15m bars in a day
_ATR_PERIOD = 14                 # 14 * 15m = 3.5h, standard


# --- HTF bias functions (per-HTF-bar +1/-1/0) --------------------------------
def bias_price_vs_sma(candles: list[Candle], params: dict) -> list[int]:
    """+1 when close is above its SMA, -1 below, 0 before warmup. The plainest
    HTF regime read: are we above or below the slow average."""
    n = params["n"]
    closes = [c.close for c in candles]
    out = [0] * len(candles)
    for i in range(n - 1, len(candles)):
        ma = sma(closes[i - n + 1: i + 1], n)
        out[i] = 1 if closes[i] > ma else (-1 if closes[i] < ma else 0)
    return out


def bias_roc(candles: list[Candle], params: dict) -> list[int]:
    """+1/-1 by the sign of the n-bar HTF return (0 before warmup or flat)."""
    n = params["n"]
    closes = [c.close for c in candles]
    out = [0] * len(candles)
    for i in range(n, len(candles)):
        r = roc(closes[i - n: i + 1], n)
        out[i] = 1 if r > 0 else (-1 if r < 0 else 0)
    return out


def bias_trend_strength(candles: list[Candle], params: dict) -> list[int]:
    """Directional regime that TRADES ONLY in a strong trend: +1/-1 by close vs
    SMA(n), but 0 (no trade) when |close - SMA| < k * rolling_std(n) -- i.e. when
    price hugs its mean (chop). Skipping the chop targets the whipsaw losers a
    plain trend-sign gate keeps in ranging regimes (the program's recurring
    weak-trend drawdown). A regime-QUALITY gate, not just a regime-sign gate."""
    n, k = params["n"], params["k"]
    closes = [c.close for c in candles]
    out = [0] * len(candles)
    for i in range(n - 1, len(candles)):
        window = closes[i - n + 1: i + 1]
        ma = sma(window, n)
        sd = rolling_std(window, n)
        dev = closes[i] - ma
        if sd > 0 and abs(dev) >= k * sd:
            out[i] = 1 if dev > 0 else -1
    return out


BIAS_FNS = {"price_vs_sma": bias_price_vs_sma, "roc": bias_roc,
            "trend_strength": bias_trend_strength}
# Momentum entries (buy strength) vs counter-trend entries (buy weakness in an
# uptrend). The HTF bias gates direction either way; the contrast is the point.
TRIGGER_FNS = {"donchian_break": donchian_break, "bb_breakout": bb_breakout,
               "roc_sign": roc_sign, "rsi_reversion": rsi_reversion,
               "ma_reclaim": ma_reclaim}


@dataclass(frozen=True)
class MtfCell:
    label: str
    htf: str
    bias_fn: str
    bias_params: dict
    trigger_fn: str
    trigger_params: dict
    exit_name: str
    exit_params: dict
    h: int                       # fixed horizon for nonoverlap + prescreen
    test_bars: int               # walk-forward window length (bars)
    step_bars: int               # walk-forward step (bars)


# Exits scaled to 15m. atr_trail rides the HTF trend; horizon_hold is the
# neutral control. max_bars/n_bars in 15m units; h matches the exit horizon so
# nonoverlap spacing is consistent with how long a trade is actually held.
def _atr_trail(max_days: int, k_trail: float) -> dict:
    return {"k_trail": k_trail, "max_bars": max_days * _BARS_PER_DAY,
            "atr_period": _ATR_PERIOD}


def _hold(max_days: int) -> dict:
    return {"n_bars": max_days * _BARS_PER_DAY, "atr_period": _ATR_PERIOD}


def _wide_stop(max_days: int, k_stop: float) -> dict:
    """Time-capped hold with a wide ATR stop -- the drawdown lever. A tight
    trailing stop whipsaws on 15m and destroys the edge; a wide stop caps the
    tail loss while leaving the trade room to work."""
    return {"n_bars": max_days * _BARS_PER_DAY, "k_stop": k_stop,
            "atr_period": _ATR_PERIOD}


def _regime_flip(max_days: int) -> dict:
    """Structural exit: close when the HTF regime bias stops supporting the trade
    side -- it flips sign or decays into chop (bias -> 0) -- with max_days as a
    backstop cap. No price stop: the exit IS the same regime read that authorized
    the entry, inverted. Resolved in mtf.regime_exit (needs the HTF bias), not the
    frozen foundation exit registry."""
    return {"max_bars": max_days * _BARS_PER_DAY, "atr_period": _ATR_PERIOD}


# The grid: HTF in {4h, 1d} (the meaningful regime gates for a 15m entry) x
# trigger in {2 momentum, 2 counter-trend} x exit in {atr_trail (tight trail),
# horizon_hold (no stop), horizon_wide_stop (drawdown lever)}, bias fixed to
# price_vs_sma (the cleanest regime). 2 x 4 x 3 = 24 cells.
# The momentum/counter-trend contrast is the experiment: does entering on LTF
# weakness inside an HTF trend cut the drawdown that killed the breakouts?
# h = 2 days (192 bars) -> ~independent swing events.
_HTFS = ["4h", "1d"]
_BIAS = ("price_vs_sma", {"n": 50})
_TRIGGERS = {
    "donchian_break": {"n": 55},                       # momentum
    "bb_breakout": {"period": 20, "mult": 2.0},        # momentum
    "rsi_reversion": {"n": 14, "low": 30, "high": 70},  # counter-trend
    "ma_reclaim": {"n": 50},                            # pullback reclaim
}
_H = 2 * _BARS_PER_DAY           # 192 bars (2 days)
_TEST_BARS = 90 * _BARS_PER_DAY  # 90-day walk-forward windows
_STEP_BARS = 30 * _BARS_PER_DAY  # stepped 30 days


def all_cells() -> list[MtfCell]:
    cells: list[MtfCell] = []
    for htf in _HTFS:
        for tname, tparams in _TRIGGERS.items():
            for ename, eparams in (("atr_trail", _atr_trail(2, 3.0)),
                                   ("horizon_hold", _hold(2)),
                                   ("horizon_wide_stop", _wide_stop(2, 3.0))):
                cells.append(MtfCell(
                    label=f"{htf}:{_BIAS[0]}|{tname}|{ename}",
                    htf=htf, bias_fn=_BIAS[0], bias_params=dict(_BIAS[1]),
                    trigger_fn=tname, trigger_params=dict(tparams),
                    exit_name=ename, exit_params=eparams,
                    h=_H, test_bars=_TEST_BARS, step_bars=_STEP_BARS))
    return cells


# The single best cell from the 24-cell diagnostic: 1d trend regime gating a 15m
# counter-trend (RSI dip/rip) entry, held 2 days behind a 3xATR wide stop. The
# one config that stayed positive in the recent out-of-sample period. The
# transfer test and the forward paper registration both reference this, so the
# frozen spec lives in exactly one place.
HEADLINE_LABEL = "1d:price_vs_sma|rsi_reversion|horizon_wide_stop"


def headline_cell() -> MtfCell:
    return next(c for c in all_cells() if c.label == HEADLINE_LABEL)


# --- Broadened search grid (separate from the frozen all_cells above) --------
# The 24-cell grid fixed bias=price_vs_sma and a 2-day hold. This broadens the
# 15m-1d search along genuinely NEW structural axes without touching the frozen
# headline spec: (a) regime DEFINITION -- price_vs_sma (sign), roc (momentum
# sign), trend_strength (regime QUALITY: skip chop); (b) hold horizon -- 1d and
# 2d swings. Triggers narrow to the diagnostic's three best (the two counter-
# trend winners + the best momentum entry); the two losing exits (atr_trail, and
# the never-competitive momentum-trail pairings) are dropped. The price_vs_sma /
# rsi_reversion / wide_stop / 2d cell reproduces the frozen headline as a control.
_BROAD_BIAS = {
    "price_vs_sma": {"n": 50},                # trend sign (frozen-headline control)
    "roc": {"n": 50},                          # momentum sign (never gridded)
    "trend_strength": {"n": 50, "k": 1.0},     # regime QUALITY: skip chop (new)
}
_BROAD_TRIGGERS = {
    "rsi_reversion": {"n": 14, "low": 30, "high": 70},  # counter-trend winner
    "ma_reclaim": {"n": 50},                             # pullback reclaim
    "donchian_break": {"n": 55},                         # best momentum entry
}
_BROAD_HOLDS = (1, 2)             # 1-day and 2-day swings (15m base)


def broadened_cells() -> list[MtfCell]:
    """3 biases x 2 HTF x 3 triggers x (2 exits x 2 holds) = 72 cells. Each cell
    carries its own h (= hold) and exit params, so the nonoverlap spacing and the
    walk-forward horizon stay consistent with how long the trade is held."""
    cells: list[MtfCell] = []
    for htf in _HTFS:
        for bname, bparams in _BROAD_BIAS.items():
            for tname, tparams in _BROAD_TRIGGERS.items():
                for hold in _BROAD_HOLDS:
                    for ename, eparams in (
                            ("horizon_wide_stop", _wide_stop(hold, 3.0)),
                            ("horizon_hold", _hold(hold))):
                        cells.append(MtfCell(
                            label=f"{htf}:{bname}|{tname}|{ename}@{hold}d",
                            htf=htf, bias_fn=bname, bias_params=dict(bparams),
                            trigger_fn=tname, trigger_params=dict(tparams),
                            exit_name=ename, exit_params=eparams,
                            h=hold * _BARS_PER_DAY, test_bars=_TEST_BARS,
                            step_bars=_STEP_BARS))
    return cells


# The broadened search's single-path winner: a 4h regime-QUALITY gate (trade only
# when price is >=1 sigma from its 4h SMA50 -- skip the chop) gating a 15m RSI
# counter-trend entry, held 2 days with NO stop. On the full single path it beats
# the frozen headline on MAR/expectancy/robustness (positive in all 7 years vs
# 6/7) and is materially stronger in the recent OOS window and on SOL; it
# transfers in sign to ETH/SOL. It is STILL paper-only: DSR 0.376 (selection-
# consistent vs 72 trials) and single-path drawdown far over the 30R fixed-f cap.
# A re-ranked paper candidate tracked in parallel with -- not replacing -- the
# frozen headline. Frozen spec lives here, in one place.
BROADEN_BEST_LABEL = "4h:trend_strength|rsi_reversion|horizon_hold@2d"


def broaden_best_cell() -> MtfCell:
    return next(c for c in broadened_cells() if c.label == BROADEN_BEST_LABEL)


# Regime-flip sibling of broaden_best: the SAME 4h regime-quality gate and 15m RSI
# counter-trend entry, but the exit is that same 4h trend_strength read inverted --
# hold until the gate stops supporting the trade (|dev| falls back within 1 sigma
# or flips), capped at 2 days as a backstop. Tests "exit when the trend that
# justified the entry breaks" against broaden_best's fixed 2-day hold. Built by
# swapping only the exit on broaden_best so the gate/entry are provably identical.
# Parallel to -- not replacing -- broaden_best (no winner-bumping); not a member of
# broadened_cells() (that grid stays byte-stable), so it carries no DSR deflation.
REGIME_FLIP_LABEL = "4h:trend_strength|rsi_reversion|regime_flip@2d"


def regime_flip_cell() -> MtfCell:
    bb = broaden_best_cell()
    return MtfCell(
        label=REGIME_FLIP_LABEL, htf=bb.htf, bias_fn=bb.bias_fn,
        bias_params=dict(bb.bias_params), trigger_fn=bb.trigger_fn,
        trigger_params=dict(bb.trigger_params), exit_name="regime_flip",
        exit_params=_regime_flip(2), h=bb.h, test_bars=bb.test_bars,
        step_bars=bb.step_bars)
