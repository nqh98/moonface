# src/moonface/signal/engine/engine.py
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.bundle import DataBundle
from moonface.models.evaluate import Signal
from moonface.models.engine.config import EngineConfig, engine_hash
from moonface.models.engine.confluence import (Decision, VETO_LONG_ONLY, decide)
from moonface.models.engine.discipline import (hard_breaker_tripped,
                                               in_cooldown, is_paused,
                                               tier_size_fraction)
from moonface.models.engine.macro import classify_macro
from moonface.models.engine.modules import revert_book, trend_book
from moonface.models.engine.modules.base import DerivSnapshot
from moonface.models.engine.position import (manage_position, open_position,
                                             reconstruct, StepResult)
from moonface.models.engine.regime import Regime, classify_regime

NO_CLAIM = "engine paper — disciplined heuristic, no validated-edge claim"


@dataclass(frozen=True)
class EngineResult:
    signal: Signal
    action: str
    entry_price: float | None
    stop: float | None
    extreme: float | None
    atr_at_entry: float | None
    atr_frac: float | None
    bars_held: int | None
    realized_r: float | None
    regime_trend: int
    regime_vol: str
    confidence: float
    decision: Decision | None
    profile: str | None
    target: float | None


def _conf(decision: Decision | None) -> float:
    return round(decision.score / 100.0, 4) if decision is not None else 0.0


def _result(step: StepResult, tf: str, regime: Regime,
            decision: Decision) -> EngineResult:
    label = ("LONG" if step.direction > 0 else
             "SHORT" if step.direction < 0 else "WAIT")
    # EXIT closes a position: it is a flat/WAIT instruction with a realized result
    out_decision = label if step.action in ("OPEN", "HOLD") else "WAIT"
    confidence = _conf(decision)
    risk_notes = NO_CLAIM if step.invalidation is None else (
        f"invalidation {step.invalidation:.2f}; {NO_CLAIM}")
    sig = Signal(out_decision, step.price, step.invalidation, step.fraction,
                 f"{step.reason} — {NO_CLAIM}", confidence=confidence,
                 timeframe=tf, risk_notes=risk_notes, tier="engine")
    return EngineResult(
        signal=sig, action=step.action, entry_price=step.entry_price,
        stop=step.stop, extreme=step.extreme, atr_at_entry=step.atr_at_entry,
        atr_frac=step.atr_frac, bars_held=step.bars_held,
        realized_r=step.realized_r, regime_trend=regime.trend,
        regime_vol=regime.vol_state, confidence=confidence, decision=decision,
        profile=step.profile, target=step.target)


def _wait(tf: str, reason: str, regime: Regime | None = None,
          decision: Decision | None = None) -> EngineResult:
    confidence = _conf(decision)
    sig = Signal("WAIT", None, None, None, f"{reason} — {NO_CLAIM}",
                 confidence=confidence, timeframe=tf,
                 risk_notes=NO_CLAIM, tier="engine")
    trend = regime.trend if regime is not None else 0
    vol = regime.vol_state if regime is not None else "normal"
    return EngineResult(sig, "WAIT", None, None, None, None, None, None, None,
                        trend, vol, confidence, decision, None, None)


def _reversal_direction(decision: Decision) -> int:
    if decision.veto == VETO_LONG_ONLY and decision.shadow_direction is not None:
        return decision.shadow_direction
    if decision.action == "SETUP":
        return decision.direction
    return 0


def evaluate_engine(cfg: EngineConfig, bundle: DataBundle,
                    entries: list[dict], now_ms: int,
                    deriv: DerivSnapshot | None = None) -> EngineResult:
    tf = cfg.asset["timeframe"]
    candles = bundle.candles
    version = engine_hash(cfg)

    if len(candles) < cfg.atr_period + 2:
        return _wait(tf, "insufficient history for the engine window")

    views = trend_book.build_views(candles)
    regime = classify_regime(views.h4, cfg)
    macro = classify_macro(views.w1, regime.vol_state, cfg)
    trend_scores = trend_book.score(views, macro, deriv, cfg)
    revert_scores = revert_book.score(views, macro, deriv, cfg)
    decision = decide(trend_scores, revert_scores, macro, cfg)

    pos = reconstruct(entries, version)
    if pos is not None:
        # manage; never open a 2nd position (v1 behaviour). Only an opposite
        # tiered SETUP or a long-only shadow reverses an open position.
        signal_dir = _reversal_direction(decision)
        step = manage_position(candles, cfg, pos, signal_dir,
                               decision.score / 100.0)
        return _result(step, tf, regime, decision)

    # flat: discipline gates new entries
    if is_paused(entries, cfg, version, now_ms):
        if hard_breaker_tripped(entries, cfg, version):
            pause_reason = ("drawdown kill-switch: hard circuit breaker tripped"
                            " (all-time) — human reset required")
        else:
            pause_reason = ("drawdown kill-switch: trailing-window pause —"
                            " auto-resumes as the drawdown ages out")
        return _wait(tf, pause_reason, regime, decision)
    if in_cooldown(entries, cfg, version):
        return _wait(tf, "post-loss cooldown", regime, decision)
    if decision.action != "SETUP":
        return _wait(tf, decision.detail, regime, decision)

    profile = "WT" if decision.archetype == "trend" else "CT"
    fraction = tier_size_fraction(decision.tier, profile, regime.vol_state, cfg)
    sweep_wick = None
    if profile == "CT":
        sw = revert_book.sweep_state(views.h1)
        if sw is not None and sw.direction == decision.direction:
            sweep_wick = sw.wick_extreme
    step = open_position(candles, cfg, decision.direction,
                         decision.score / 100.0, fraction, profile, sweep_wick)
    return _result(step, tf, regime, decision)
