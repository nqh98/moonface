# src/moonface/research/orderflow.py
"""Entry-pair dominance evaluators for the orderflow_microstructure domain
(spec 2026-07-02). Pure functions over ladder.r_stream — no store/lockbox
imports (those live in orderflow_runner).

Unlike voltarget.py (treatment vs control SIZING on the same entries), the
orderflow control is a different ENTRY (donchian_break) at the same sizing,
timeframe, exit, and cost. Dominance = treatment strictly beats the paired
donchian control on BOTH MAR and Sharpe."""
from __future__ import annotations

from moonface.core.metrics import equity_summary, summarize_r
from moonface.research.ladder import (DRAWDOWN_BUDGET, LOCKBOX_MIN_MAR,
                                      SCREEN_FRACTION, r_stream)
from moonface.kernel.spec import HypothesisSpec

ORDERFLOW_DOMAIN = "orderflow_microstructure"

ORDERFLOW_FRACTION = 0.01            # fixed-fractional sizing for both arms
SCREEN_MIN_TRADES_INTRADAY = 100     # intraday floor (ladder.SCREEN_MIN_TRADES=30 untouched)
LOCKBOX_MIN_TRADES_INTRADAY = 20     # intraday floor (ladder.LOCKBOX_MIN_TRADES=10 untouched)
N_TRIALS = 10                        # DSR multiple-comparison correction

# Frozen construction (spec §2).
EXIT_NAME = "fixed_bracket"
EXIT_PARAMS = {"atr_period": 14, "k_stop": 2.0, "m_tp": 1.0}
ORDERFLOW_EXIT = (EXIT_NAME, EXIT_PARAMS)

_BTC = {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "15m"}
_BTC_OI = {**_BTC, "metrics_field": "sum_open_interest"}
_BTC_TAKER = {**_BTC, "metrics_field": "sum_taker_long_short_vol_ratio"}


def _spec(family: str, params: dict, asset: dict) -> HypothesisSpec:
    return HypothesisSpec(
        domain=ORDERFLOW_DOMAIN, version=1, asset=asset,
        entry={"family": family, "params": params},
        exit={"name": EXIT_NAME, "params": EXIT_PARAMS},
        fraction=ORDERFLOW_FRACTION)


def orderflow_specs() -> list[HypothesisSpec]:
    """The 10 pre-registered treatment specs (spec §2)."""
    specs: list[HypothesisSpec] = []
    for window in (48, 96):
        for z_thr in (2.0, 2.5):
            specs.append(_spec("oi_flush_reversal",
                               {"window": window, "lookback": 6, "z_thr": z_thr},
                               _BTC_OI))
            specs.append(_spec("taker_flow_momentum",
                               {"window": window, "z_thr": z_thr}, _BTC_TAKER))
    for swing_n in (48, 96):
        specs.append(_spec("liquidity_sweep_reclaim", {"swing_n": swing_n}, _BTC))
    return specs


def control_for(spec: HypothesisSpec) -> HypothesisSpec:
    """The donchian_break control paired to a treatment spec by lookback horizon:
    window/swing_n >= 96 -> donchian n=96, else n=48. Same exit/fraction/asset-class."""
    p = spec.entry["params"]
    horizon = p.get("window", p.get("swing_n", 48))
    n = 96 if horizon >= 96 else 48
    return HypothesisSpec(
        domain=ORDERFLOW_DOMAIN, version=1, asset=_BTC,
        entry={"family": "donchian_break", "params": {"n": n, "long_only": False}},
        exit={"name": EXIT_NAME, "params": EXIT_PARAMS},
        fraction=ORDERFLOW_FRACTION)


def dominates(t_mar: float, t_sharpe: float,
              c_mar: float, c_sharpe: float) -> bool:
    """Strict: treatment beats control on BOTH MAR and Sharpe."""
    return t_mar > c_mar and t_sharpe > c_sharpe


def evaluate_dominant(spec: HypothesisSpec, control_spec: HypothesisSpec,
                      research, screen_fraction: float = SCREEN_FRACTION) -> dict:
    """One pass over the research window for the treatment spec AND its paired
    control. Dominance is computed on the holdout; research_* fields feed DSR."""
    split = int(len(research.candles) * screen_fraction)
    ts = r_stream(spec, research)
    cs = r_stream(control_spec, research)
    t_screen = summarize_r([r for i, r, _ in ts if i < split])
    t_hold = equity_summary([(r, af) for i, r, af in ts if i >= split],
                            ORDERFLOW_FRACTION)
    t_full = equity_summary([(r, af) for _, r, af in ts], ORDERFLOW_FRACTION)
    c_hold = equity_summary([(r, af) for i, r, af in cs if i >= split],
                            ORDERFLOW_FRACTION)
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
    """One-touch tail (entry_index >= fence_index) for treatment and control."""
    ts = r_stream(spec, full)
    cs = r_stream(control_spec, full)
    t_tail = equity_summary([(r, af) for i, r, af in ts if i >= fence_index],
                            ORDERFLOW_FRACTION)
    c_tail = equity_summary([(r, af) for i, r, af in cs if i >= fence_index],
                            ORDERFLOW_FRACTION)
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


def stage1_of(m: dict, min_trades: int = SCREEN_MIN_TRADES_INTRADAY) -> bool:
    return m["screen_trades"] >= min_trades and m["screen_expectancy_r"] > 0.0


def stage2_of(m: dict) -> bool:
    return (m["holdout_treatment_mar"] > 0.0
            and m["holdout_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["holdout_dominance"])


def stage4_of(m: dict, min_trades: int = LOCKBOX_MIN_TRADES_INTRADAY) -> bool:
    return (m["tail_treatment_mar"] >= LOCKBOX_MIN_MAR
            and m["tail_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["tail_trades"] >= min_trades
            and m["tail_dominance"])
