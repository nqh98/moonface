"""Domain evaluators for the forced_error lane (spec 2026-07-08).

Two predatory trap setups, each vs its isolation control, on BTC/USDT:USDT 1h.
Dominance = treatment strictly beats its paired control on BOTH MAR and Sharpe.
The DSR trial count pools both setups (N_TRIALS = 8 = len(forced_error_specs)).
"""
from __future__ import annotations

from moonface.core.metrics import equity_summary, summarize_r
from moonface.research.ladder import (DRAWDOWN_BUDGET, LOCKBOX_MIN_MAR,
                                      SCREEN_FRACTION, r_stream)
from moonface.research.orderflow import dominates
from moonface.kernel.spec import HypothesisSpec

FORCED_ERROR_DOMAIN = "forced_error"

FRACTION = 0.01
SCREEN_MIN_TRADES = 30
LOCKBOX_MIN_TRADES = 20
N_TRIALS = 8

EXIT_NAME = "fixed_bracket"
EXIT_PARAMS = {"atr_period": 14, "k_stop": 2.0, "m_tp": 1.0}

# Frozen fixed parameters (grid varies only lookback x k; everything else fixed).
WINDOW = 180
DONCHIAN_N = 24            # Setup 1 resistance lookback (24 x 1h)
FUNDING_PCT = 0.2         # Setup 2: bottom-20th-percentile funding = deeply negative
FUNDING_WINDOW = 720      # 30d trailing window for the funding percentile

_BTC_OI = {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "1h",
           "metrics_field": "sum_open_interest"}
_BTC_OI_FUND = {**_BTC_OI, "funding_symbol": "BTC/USDT:USDT"}


def _spec(family: str, params: dict, asset: dict) -> HypothesisSpec:
    return HypothesisSpec(
        domain=FORCED_ERROR_DOMAIN, version=1, asset=asset,
        entry={"family": family, "params": params},
        exit={"name": EXIT_NAME, "params": EXIT_PARAMS},
        fraction=FRACTION)


def forced_error_specs() -> list[HypothesisSpec]:
    specs: list[HypothesisSpec] = []
    for lookback in (3, 6):
        for k in (1.5, 2.0):
            specs.append(_spec(
                "failed_breakout_harvest",
                {"donchian_n": DONCHIAN_N, "window": WINDOW,
                 "lookback": lookback, "k": k, "use_volume": True}, _BTC_OI))
    for lookback in (3, 6):
        for k in (1.5, 2.0):
            specs.append(_spec(
                "failed_fade_squeeze",
                {"window": WINDOW, "lookback": lookback, "k": k,
                 "funding_pct": FUNDING_PCT,
                 "funding_window": FUNDING_WINDOW}, _BTC_OI_FUND))
    return specs


def _paired(spec: HypothesisSpec, family: str, params: dict) -> HypothesisSpec:
    """A control/ablation for `spec`: swaps entry family+params but MUST carry
    the SAME exit and fraction as the treatment it is paired with."""
    return HypothesisSpec(
        domain=FORCED_ERROR_DOMAIN, version=1, asset=spec.asset,
        entry={"family": family, "params": params},
        exit=spec.exit, fraction=spec.fraction)


def control_for(spec: HypothesisSpec) -> HypothesisSpec:
    p = spec.entry["params"]
    if spec.entry["family"] == "failed_breakout_harvest":
        return _paired(spec, "failed_breakout_naive",
                       {"donchian_n": p["donchian_n"]})
    return _paired(spec, "funding_fade_long",
                   {"funding_pct": p["funding_pct"],
                    "funding_window": p["funding_window"]})


def ablation_for(spec: HypothesisSpec) -> HypothesisSpec:
    """Setup-1 OI-only reference (drops the volume gate). Reference baseline,
    NOT a counted trial. Raises for Setup 2."""
    if spec.entry["family"] != "failed_breakout_harvest":
        raise ValueError("ablation_for is defined for Setup 1 only")
    return _paired(spec, "failed_breakout_harvest",
                   {**spec.entry["params"], "use_volume": False})


def evaluate_dominant(spec: HypothesisSpec, control_spec: HypothesisSpec,
                      research, screen_fraction: float = SCREEN_FRACTION) -> dict:
    split = int(len(research.candles) * screen_fraction)
    ts = r_stream(spec, research)
    cs = r_stream(control_spec, research)
    t_screen = summarize_r([r for i, r, _ in ts if i < split])
    t_hold = equity_summary([(r, af) for i, r, af in ts if i >= split], FRACTION)
    t_full = equity_summary([(r, af) for _, r, af in ts], FRACTION)
    c_hold = equity_summary([(r, af) for i, r, af in cs if i >= split], FRACTION)
    return {
        "screen_trades": t_screen.trade_count,
        "screen_expectancy_r": t_screen.expectancy_r,
        "holdout_trades": t_hold.trade_count,
        "holdout_treatment_mar": t_hold.mar,
        "holdout_treatment_dd": t_hold.max_drawdown,
        "holdout_treatment_sharpe": t_hold.sharpe,
        "holdout_control_mar": c_hold.mar,
        "holdout_control_sharpe": c_hold.sharpe,
        "holdout_dominance": dominates(t_hold.mar, t_hold.sharpe,
                                       c_hold.mar, c_hold.sharpe),
        "research_sharpe": t_full.sharpe,
        "research_skew": t_full.skew,
        "research_kurtosis": t_full.kurtosis,
        "research_trades": t_full.trade_count,
    }


def lockbox_dominant(spec: HypothesisSpec, control_spec: HypothesisSpec,
                     full, fence_index: int) -> dict:
    ts = r_stream(spec, full)
    cs = r_stream(control_spec, full)
    t_tail = equity_summary([(r, af) for i, r, af in ts if i >= fence_index],
                            FRACTION)
    c_tail = equity_summary([(r, af) for i, r, af in cs if i >= fence_index],
                            FRACTION)
    return {
        "tail_trades": t_tail.trade_count,
        "tail_treatment_mar": t_tail.mar,
        "tail_treatment_dd": t_tail.max_drawdown,
        "tail_treatment_sharpe": t_tail.sharpe,
        "tail_control_mar": c_tail.mar,
        "tail_control_sharpe": c_tail.sharpe,
        "tail_dominance": dominates(t_tail.mar, t_tail.sharpe,
                                    c_tail.mar, c_tail.sharpe),
    }


def stage1_of(m: dict, min_trades: int = SCREEN_MIN_TRADES) -> bool:
    return m["screen_trades"] >= min_trades and m["screen_expectancy_r"] > 0.0


def stage2_of(m: dict) -> bool:
    return (m["holdout_treatment_mar"] > 0.0
            and m["holdout_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["holdout_dominance"])


def stage4_of(m: dict, min_trades: int = LOCKBOX_MIN_TRADES) -> bool:
    return (m["tail_treatment_mar"] >= LOCKBOX_MIN_MAR
            and m["tail_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["tail_trades"] >= min_trades
            and m["tail_dominance"])
