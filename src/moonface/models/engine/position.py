# src/moonface/signal/engine/position.py
from __future__ import annotations

from dataclasses import dataclass

from moonface.core.metrics import COST_FRACTION
from moonface.core.models import Candle
from moonface.core.risk import atr
from moonface.models.engine.config import EngineConfig
from moonface.models.engine.discipline import engine_entries

# CT (counter-trend) risk profile — frozen module-level constants, deliberately
# NOT in EngineConfig (anti-overfitting: these are not tunable).
CT_STOP_ATR = 1.5     # CT stop sits 1.5xATR beyond the sweep wick
CT_TARGET_R = 2.0     # CT fixed target at 2R (R measured in ATR units, see _gross_r)
CT_MAX_BARS = 24      # CT time stop


@dataclass(frozen=True)
class PositionState:
    direction: int
    entry_price: float
    stop: float
    extreme: float
    atr_at_entry: float
    fraction: float
    bars_held: int
    profile: str = "WT"
    target: float | None = None


@dataclass(frozen=True)
class StepResult:
    action: str
    direction: int
    price: float | None
    invalidation: float | None
    fraction: float | None
    entry_price: float | None
    stop: float | None
    extreme: float | None
    atr_at_entry: float | None
    atr_frac: float | None
    bars_held: int | None
    realized_r: float | None
    reason: str
    profile: str = "WT"
    target: float | None = None


def reconstruct(entries: list[dict], version: str) -> PositionState | None:
    mine = engine_entries(entries, version)
    if not mine:
        return None
    last = mine[-1]
    if last.get("action") not in ("OPEN", "HOLD"):
        return None
    direction = 1 if last.get("decision") == "LONG" else -1
    target = last.get("target")
    return PositionState(
        direction=direction,
        entry_price=float(last["entry_price"]),
        stop=float(last["stop"]),
        extreme=float(last["extreme"]),
        atr_at_entry=float(last["atr_at_entry"]),
        fraction=float(last["fraction"]),
        bars_held=int(last["bars_held"]),
        profile=last.get("profile", "WT"),
        target=float(target) if target is not None else None,
    )


def open_position(candles: list[Candle], cfg: EngineConfig, direction: int,
                  confidence: float, fraction: float, profile: str = "WT",
                  sweep_wick: float | None = None) -> StepResult:
    entry = candles[-1].close
    a = atr(candles, cfg.atr_period)
    side = "LONG" if direction > 0 else "SHORT"
    atr_frac = a / entry if entry > 0 else 0.0

    if profile == "CT":
        if sweep_wick is not None:
            stop = (sweep_wick - CT_STOP_ATR * a if direction > 0
                    else sweep_wick + CT_STOP_ATR * a)
        else:
            stop = entry - CT_STOP_ATR * a if direction > 0 else entry + CT_STOP_ATR * a
        target = entry + CT_TARGET_R * a if direction > 0 else entry - CT_TARGET_R * a
        reason = (f"OPEN {side} CT @ {entry:.2f}, stop {stop:.2f}, "
                 f"target {target:.2f} (conf {confidence:.2f})")
    else:
        stop = entry - cfg.k_stop * a if direction > 0 else entry + cfg.k_stop * a
        target = None
        reason = f"OPEN {side} @ {entry:.2f}, stop {stop:.2f} (conf {confidence:.2f})"

    return StepResult(
        action="OPEN", direction=direction, price=entry, invalidation=stop,
        fraction=fraction, entry_price=entry, stop=stop, extreme=entry,
        atr_at_entry=a, atr_frac=atr_frac, bars_held=0, realized_r=None,
        reason=reason, profile=profile, target=target)


def _gross_r(pos: PositionState, exit_price: float) -> float:
    sign = 1.0 if pos.direction > 0 else -1.0
    return sign * (exit_price - pos.entry_price) / pos.atr_at_entry


def _net_r(pos: PositionState, exit_price: float) -> float:
    atr_frac = pos.atr_at_entry / pos.entry_price if pos.entry_price > 0 else 0.0
    cost = COST_FRACTION / atr_frac if atr_frac > 0 else 0.0
    return round(_gross_r(pos, exit_price) - cost, 4)


def _exit(pos: PositionState, exit_price: float, reason: str) -> StepResult:
    atr_frac = pos.atr_at_entry / pos.entry_price if pos.entry_price > 0 else 0.0
    return StepResult(
        action="EXIT", direction=0, price=exit_price, invalidation=None,
        fraction=pos.fraction, entry_price=pos.entry_price, stop=pos.stop,
        extreme=pos.extreme, atr_at_entry=pos.atr_at_entry, atr_frac=atr_frac,
        bars_held=pos.bars_held, realized_r=_net_r(pos, exit_price),
        reason=reason, profile=pos.profile, target=pos.target)


def _manage_ct(bar: Candle, cfg: EngineConfig, pos: PositionState,
               signal_direction: int, confidence: float, side: str) -> StepResult:
    """CT (counter-trend) management: fixed wick-based stop, fixed 2R target,
    24-bar time stop, NO trail, NO adds. Separate branch from the WT ratchet
    logic; the fixed stop/target are never revised while the position is open.
    """
    # 1) prior-stop fill check FIRST (pessimistic), stop is FIXED (no ratchet)
    if pos.direction > 0 and bar.low <= pos.stop:
        return _exit(pos, pos.stop, f"{side} CT stop {pos.stop:.2f} hit")
    if pos.direction < 0 and bar.high >= pos.stop:
        return _exit(pos, pos.stop, f"{side} CT stop {pos.stop:.2f} hit")

    # 2) target fill check SECOND (only reached if the stop did not fill). A
    # malformed journal entry may lack a target; guard so it degrades to a
    # no-target HOLD rather than raising on the comparison / format.
    if pos.target is not None:
        if pos.direction > 0 and bar.high >= pos.target:
            return _exit(pos, pos.target, f"{side} CT target {pos.target:.2f} hit")
        if pos.direction < 0 and bar.low <= pos.target:
            return _exit(pos, pos.target, f"{side} CT target {pos.target:.2f} hit")

    bars_held = pos.bars_held + 1

    # 3) CT time stop
    if bars_held >= CT_MAX_BARS:
        held = PositionState(pos.direction, pos.entry_price, pos.stop, pos.extreme,
                             pos.atr_at_entry, pos.fraction, bars_held,
                             pos.profile, pos.target)
        return _exit(held, bar.close, f"{side} CT max_bars {CT_MAX_BARS} reached")

    # 4) reversal: an opposite tiered SETUP closes the position (v2 has no
    # confidence float; any opposite signal_direction reverses)
    if signal_direction != 0 and signal_direction != pos.direction:
        held = PositionState(pos.direction, pos.entry_price, pos.stop, pos.extreme,
                             pos.atr_at_entry, pos.fraction, bars_held,
                             pos.profile, pos.target)
        return _exit(held, bar.close, f"{side} CT exit on opposite-signal reversal")

    # 5) otherwise HOLD with the SAME fixed stop/target (no ratchet, no adds)
    atr_frac = pos.atr_at_entry / pos.entry_price if pos.entry_price > 0 else 0.0
    target_note = (f"target {pos.target:.2f}" if pos.target is not None
                   else "no target")
    return StepResult(
        action="HOLD", direction=pos.direction, price=bar.close,
        invalidation=pos.stop, fraction=pos.fraction, entry_price=pos.entry_price,
        stop=pos.stop, extreme=pos.extreme, atr_at_entry=pos.atr_at_entry,
        atr_frac=atr_frac, bars_held=bars_held, realized_r=None,
        reason=f"HOLD {side} CT, stop {pos.stop:.2f} {target_note} "
              f"(bar {bars_held})",
        profile="CT", target=pos.target)


def manage_position(candles: list[Candle], cfg: EngineConfig,
                    pos: PositionState, signal_direction: int,
                    confidence: float) -> StepResult:
    """Mirror foundation.exits.atr_trail order: the stop in force during this
    candle is the one set after the previous bar; check it first, then ratchet
    for next bar."""
    bar = candles[-1]
    side = "LONG" if pos.direction > 0 else "SHORT"

    if pos.profile == "CT":
        return _manage_ct(bar, cfg, pos, signal_direction, confidence, side)

    # 1) prior-stop fill check (pessimistic)
    if pos.direction > 0 and bar.low <= pos.stop:
        return _exit(pos, pos.stop, f"{side} stop {pos.stop:.2f} hit")
    if pos.direction < 0 and bar.high >= pos.stop:
        return _exit(pos, pos.stop, f"{side} stop {pos.stop:.2f} hit")

    # 2) ratchet trail from the running extreme using entry ATR
    trail = cfg.k_trail * pos.atr_at_entry
    if pos.direction > 0:
        extreme = max(pos.extreme, bar.high)
        stop = max(pos.stop, extreme - trail)
    else:
        extreme = min(pos.extreme, bar.low)
        stop = min(pos.stop, extreme + trail)
    bars_held = pos.bars_held + 1

    # 3) max-bars time stop
    if bars_held >= cfg.max_bars:
        return _exit(PositionState(pos.direction, pos.entry_price, stop, extreme,
                                   pos.atr_at_entry, pos.fraction, bars_held),
                     bar.close, f"{side} max_bars {cfg.max_bars} reached")

    # 4) reversal: an opposite tiered SETUP closes the position (v2 has no
    # confidence float; any opposite signal_direction reverses)
    if signal_direction != 0 and signal_direction != pos.direction:
        return _exit(PositionState(pos.direction, pos.entry_price, stop, extreme,
                                   pos.atr_at_entry, pos.fraction, bars_held),
                     bar.close, f"{side} exit on opposite-signal reversal")

    # 5) otherwise HOLD with the updated trail
    atr_frac = pos.atr_at_entry / pos.entry_price if pos.entry_price > 0 else 0.0
    return StepResult(
        action="HOLD", direction=pos.direction, price=bar.close,
        invalidation=stop, fraction=pos.fraction, entry_price=pos.entry_price,
        stop=stop, extreme=extreme, atr_at_entry=pos.atr_at_entry,
        atr_frac=atr_frac, bars_held=bars_held, realized_r=None,
        reason=f"HOLD {side}, trail stop {stop:.2f} (bar {bars_held})")
