"""Entry-pair dominance evaluators for the price_oi_divergence domain.

The treatment is the z-gap divergence SHORT; the control is the same entry with
the OI gate removed. Dominance = treatment strictly beats its paired control on
BOTH MAR and Sharpe.
"""
from __future__ import annotations

from moonface.core.metrics import equity_summary, summarize_r
from moonface.research.ladder import (DRAWDOWN_BUDGET, LOCKBOX_MIN_MAR,
                                      SCREEN_FRACTION, r_stream)
from moonface.research.orderflow import dominates
from moonface.kernel.spec import HypothesisSpec

DIVERGENCE_DOMAIN = "price_oi_divergence"

DIVERGENCE_FRACTION = 0.01
SCREEN_MIN_TRADES = 30
LOCKBOX_MIN_TRADES = 20
N_TRIALS = 4

EXIT_NAME = "fixed_bracket"
EXIT_PARAMS = {"atr_period": 14, "k_stop": 2.0, "m_tp": 1.0}
DIVERGENCE_EXIT = (EXIT_NAME, EXIT_PARAMS)

_BTC_OI = {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "1h",
           "metrics_field": "sum_open_interest"}


def _spec(family: str, params: dict) -> HypothesisSpec:
    return HypothesisSpec(
        domain=DIVERGENCE_DOMAIN, version=1, asset=_BTC_OI,
        entry={"family": family, "params": params},
        exit={"name": EXIT_NAME, "params": EXIT_PARAMS},
        fraction=DIVERGENCE_FRACTION)


def divergence_specs() -> list[HypothesisSpec]:
    specs: list[HypothesisSpec] = []
    for lookback in (3, 6):
        for k in (1.5, 2.0):
            specs.append(_spec("price_oi_divergence",
                               {"window": 180, "lookback": lookback, "k": k}))
    return specs


def control_for(spec: HypothesisSpec) -> HypothesisSpec:
    return HypothesisSpec(
        domain=DIVERGENCE_DOMAIN, version=1, asset=spec.asset,
        entry={"family": "price_extension_short",
               "params": dict(spec.entry["params"])},
        exit=spec.exit, fraction=spec.fraction)


def evaluate_dominant(spec: HypothesisSpec, control_spec: HypothesisSpec,
                      research, screen_fraction: float = SCREEN_FRACTION) -> dict:
    split = int(len(research.candles) * screen_fraction)
    ts = r_stream(spec, research)
    cs = r_stream(control_spec, research)
    t_screen = summarize_r([r for i, r, _ in ts if i < split])
    t_hold = equity_summary([(r, af) for i, r, af in ts if i >= split],
                            DIVERGENCE_FRACTION)
    t_full = equity_summary([(r, af) for _, r, af in ts], DIVERGENCE_FRACTION)
    c_hold = equity_summary([(r, af) for i, r, af in cs if i >= split],
                            DIVERGENCE_FRACTION)
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
                            DIVERGENCE_FRACTION)
    c_tail = equity_summary([(r, af) for i, r, af in cs if i >= fence_index],
                            DIVERGENCE_FRACTION)
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
