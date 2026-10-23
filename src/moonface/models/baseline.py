"""Baseline composite signal tier (spec 2026-06-15).

The falsification program (docs/findings/PROGRAM_CONCLUSION.md) found no OOS-valid
edge on free BTC data, so this tier makes NO expectancy claim. It emits an
honest, clearly-labelled HEURISTIC LONG/SHORT/WAIT by polling a few indicator
STATES and reporting how strongly they agree (`confidence`). It executes nothing
and sits below the live/paper/participation tiers in the CLI resolution ladder.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from statistics import fmean, pstdev

from moonface.core.models import Candle
from moonface.models.evaluate import Signal


def trend_breakout_vote(candles: list[Candle], n: int) -> int:
    """Donchian-channel STATE at the last bar (donchian_break logic, read as a
    state): close above the prior-n high -> +1, below the prior-n low -> -1,
    inside -> 0."""
    i = len(candles) - 1
    if i < n:
        return 0
    prior_high = max(c.high for c in candles[i - n:i])
    prior_low = min(c.low for c in candles[i - n:i])
    if candles[i].close > prior_high:
        return 1
    if candles[i].close < prior_low:
        return -1
    return 0


def trend_confirm_vote(candles: list[Candle], period: int) -> int:
    """Close vs SMA STATE: above -> +1, below -> -1, equal/short-history -> 0."""
    i = len(candles) - 1
    if i + 1 < period:
        return 0
    closes = [c.close for c in candles]
    ma = fmean(closes[i - period + 1:i + 1])
    if closes[i] == ma:
        return 0
    return 1 if closes[i] > ma else -1


def funding_fade_vote(funding: list[float | None] | None, window: int,
                      z_thr: float) -> int:
    """Rolling-z STATE of funding (funding_fade logic, read as a state): crowded
    long (z >= +z_thr) -> fade SHORT (-1), crowded short (z <= -z_thr) -> LONG
    (+1). Abstains (0) when funding data is missing or insufficient."""
    if funding is None or len(funding) < window:
        return 0
    recent = funding[-window:]
    if any(v is None for v in recent):
        return 0
    mean = fmean(recent)
    sd = pstdev(recent)
    if sd <= 0:
        return 0
    z = (recent[-1] - mean) / sd
    if z >= z_thr:
        return -1
    if z <= -z_thr:
        return 1
    return 0


def vol_ratio(candles: list[Candle], window: int) -> float | None:
    """Ratio of short-term realized vol (mean abs log-return over the last
    `window` bars) to the full-window baseline vol. ~1 in a steady regime, >1
    when volatility is spiking. None without >= 2*window bars."""
    if len(candles) < window * 2:
        return None
    closes = [c.close for c in candles]
    rets = [abs(math.log(closes[k] / closes[k - 1]))
            for k in range(1, len(closes))]
    long_vol = fmean(rets)
    short_vol = fmean(rets[-window:])
    if long_vol <= 0:
        return 1.0
    return short_vol / long_vol


def aggregate(votes: dict[str, int], weights: dict[str, float],
              agreement_floor: float) -> tuple[str, float]:
    """Weighted-vote decision. Returns (decision, agreement) where
    agreement = |net|/total in [0,1]. Below the floor (or a zero net) -> WAIT."""
    total = sum(weights[k] for k in votes)
    if total <= 0:
        return "WAIT", 0.0
    net = sum(weights[k] * votes[k] for k in votes)
    agreement = abs(net) / total
    if net == 0 or agreement < agreement_floor:
        return "WAIT", agreement
    return ("LONG" if net > 0 else "SHORT"), agreement


def _default_asset() -> dict:
    return {"exchange": "binance", "symbol": "BTC/USDT:USDT",
            "timeframe": "4h", "funding_symbol": "BTC/USDT:USDT"}


def _default_weights() -> dict:
    return {"trend_breakout": 1.0, "trend_confirm": 1.0, "funding_fade": 1.0}


@dataclass(frozen=True)
class BaselineConfig:
    """Tunable composite parameters. Absent/invalid file -> these defaults, so
    the baseline tier is ON unless the human writes `{"enabled": false}`."""

    enabled: bool = True
    asset: dict = field(default_factory=_default_asset)
    donchian_n: int = 20
    ma_period: int = 50
    funding_window: int = 60
    funding_z: float = 1.5
    vol_window: int = 30
    high_vol_ratio: float = 1.5         # damp confidence above this vol ratio
    extreme_vol_damp: float = 0.5       # multiplier applied in the loud regime
    wait_vol_ratio: float = 2.5         # force WAIT above this vol ratio
    weights: dict = field(default_factory=_default_weights)
    agreement_floor: float = 0.5
    atr_period: int = 14
    k_stop: float = 2.0
    risk_fraction: float = 0.0005       # suggested size; honest, tiny default


_CONFIG_FIELDS = {
    "enabled", "asset", "donchian_n", "ma_period", "funding_window",
    "funding_z", "vol_window", "high_vol_ratio", "extreme_vol_damp",
    "wait_vol_ratio", "weights", "agreement_floor", "atr_period", "k_stop",
    "risk_fraction",
}


def load_baseline_config(path) -> BaselineConfig:
    """Fail-safe, on-by-default loader: a missing or invalid file yields the
    default (enabled) composite; a valid file's recognised keys override the
    defaults. Never returns None — the baseline tier always resolves."""
    from pathlib import Path
    try:
        raw = json.loads(Path(path).read_text())
        if not isinstance(raw, dict):
            return BaselineConfig()
        overrides = {k: v for k, v in raw.items() if k in _CONFIG_FIELDS}
        return BaselineConfig(**overrides)
    except (OSError, ValueError, TypeError):
        return BaselineConfig()


def baseline_hash(cfg: BaselineConfig) -> str:
    """Journal identity of the signal-relevant content. `enabled` is excluded so
    silencing/unsilencing the tier does not start a new forward-record segment."""
    payload = {
        "asset": cfg.asset, "donchian_n": cfg.donchian_n,
        "ma_period": cfg.ma_period, "funding_window": cfg.funding_window,
        "funding_z": cfg.funding_z, "vol_window": cfg.vol_window,
        "high_vol_ratio": cfg.high_vol_ratio,
        "extreme_vol_damp": cfg.extreme_vol_damp,
        "wait_vol_ratio": cfg.wait_vol_ratio, "weights": cfg.weights,
        "agreement_floor": cfg.agreement_floor, "atr_period": cfg.atr_period,
        "k_stop": cfg.k_stop, "risk_fraction": cfg.risk_fraction,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_NO_CLAIM = "heuristic — NOT a validated edge, no expectancy claim"


def _regime_factor(ratio: float | None, cfg: BaselineConfig) -> tuple[float, bool]:
    """Returns (confidence multiplier, force_wait). High vol damps confidence;
    extreme vol forces WAIT."""
    if ratio is None:
        return 1.0, False
    if ratio >= cfg.wait_vol_ratio:
        return 0.0, True
    if ratio >= cfg.high_vol_ratio:
        return cfg.extreme_vol_damp, False
    return 1.0, False


def _wait(reason: str, confidence: float, tf: str) -> Signal:
    return Signal("WAIT", None, None, None, reason, confidence=round(confidence, 4),
                  timeframe=tf, risk_notes=_NO_CLAIM, tier="baseline")


def evaluate_baseline(cfg: BaselineConfig, bundle, now_ms: int) -> Signal:
    """Composite heuristic signal for the last closed candle. Reads OHLCV (+
    funding when present); never executes anything; always tier='baseline'."""
    from moonface.core.risk import risk_unit as _risk
    from moonface.models.evaluate import sentinel_extended

    candles = bundle.candles
    tf = cfg.asset["timeframe"]
    required = max(cfg.vol_window * 2, cfg.donchian_n + 1, cfg.ma_period,
                   cfg.atr_period + 2)
    if len(candles) < required:
        return _wait("insufficient history for the baseline window", 0.0, tf)

    votes = {
        "trend_breakout": trend_breakout_vote(candles, cfg.donchian_n),
        "trend_confirm": trend_confirm_vote(candles, cfg.ma_period),
        "funding_fade": funding_fade_vote(bundle.funding, cfg.funding_window,
                                          cfg.funding_z),
    }
    decision, agreement = aggregate(votes, cfg.weights, cfg.agreement_floor)
    damp, force_wait = _regime_factor(vol_ratio(candles, cfg.vol_window), cfg)
    confidence = agreement * damp

    agree_str = (f"votes trend_breakout={votes['trend_breakout']:+d}"
                 f" trend_confirm={votes['trend_confirm']:+d}"
                 f" funding_fade={votes['funding_fade']:+d}")
    if force_wait:
        return _wait(f"extreme volatility regime — standing flat; {agree_str}",
                     confidence, tf)
    if decision == "WAIT":
        return _wait(f"no directional agreement; {agree_str}", confidence, tf)

    last_index = len(candles) - 1
    unit = _risk(sentinel_extended(bundle).candles, last_index, cfg.k_stop,
                 cfg.atr_period)
    if unit is None:
        return _wait("ATR risk unit undefined on this window", confidence, tf)
    price = candles[last_index].close
    invalidation = price - unit if decision == "LONG" else price + unit
    atr = unit / cfg.k_stop
    risk_notes = (f"invalidation {invalidation:.2f} (1R=ATR{cfg.atr_period}"
                  f"~{atr:.0f}), suggested f={cfg.risk_fraction}; {_NO_CLAIM}")
    reason = (f"{decision} on {agree_str} (agreement {agreement:.2f}) —"
              f" {_NO_CLAIM}")
    return Signal(decision, price, round(invalidation, 2), cfg.risk_fraction,
                  reason, confidence=round(confidence, 4), timeframe=tf,
                  risk_notes=risk_notes, tier="baseline")