# src/moonface/signal/engine/config.py
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


ENGINE_VERSION = "2.2"


def _default_asset() -> dict:
    return {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "1h"}


@dataclass(frozen=True)
class EngineConfig:
    """Tunable parameters for the stateful confluence engine. Absent/invalid
    config file -> these defaults, which are DISABLED (enabled=False). The panel
    params (trend/donchian/pullback/momentum lengths) and the confluence weights
    are v2 frozen module constants, deliberately NOT tunable via this config."""

    enabled: bool = False
    asset: dict = field(default_factory=_default_asset)
    lookback_bars: int = 6000
    # regime (4h, resampled)
    regime_ma_fast: int = 20
    regime_ma_slow: int = 50
    vol_window: int = 30
    high_vol_ratio: float = 1.5
    extreme_vol_ratio: float = 2.5
    high_vol_damp: float = 0.5
    # position / risk
    atr_period: int = 14
    k_stop: float = 2.0
    k_trail: float = 3.0
    max_bars: int = 96
    base_fraction: float = 0.005
    max_fraction: float = 0.02
    # discipline — layered kill-switch
    # routine pause: peak-to-trough R drawdown over the trailing window
    # (drawdown_window_days) <= -drawdown_budget_r; auto-resumes as the cluster
    # ages out. <=0 disables the window and falls back to the all-time latch.
    drawdown_budget_r: float = 15.0
    drawdown_window_days: float = 90.0
    # hard catastrophe breaker: all-time R drawdown <= -hard_drawdown_budget_r;
    # a one-way latch requiring a human reset (never auto-resumes).
    hard_drawdown_budget_r: float = 30.0
    cooldown_bars: int = 6


_CONFIG_FIELDS = set(EngineConfig.__dataclass_fields__.keys())
_FROZEN_FIELDS_BY_MODULE = {
    "confluence": (
        "BASE_THRESHOLD",
        "TIER_A",
        "CT_SURCHARGE",
        "BREADTH_MIN",
        "_DIRECTION_LABEL",
        "_ARCHETYPE_LABEL",
        "_TREND_MAX",
        "_REVERT_MAX",
        "GATE",
        "EXCLUDED_MODULES",
        "VETO_LONG_ONLY",
        "VETO_M4_EXCLUDED",
        "VETO_NO_CT",
        "W_BREAKOUT",
        "W_MACRO",
        "W_MA_ALIGN",
        "W_PULLBACK",
        "W_ROC_STRONG",
        "W_DIVERGENCE",
        "W_FUND_CT",
        "W_OI_FLUSH",
        "W_RECLAIM",
        "W_STRETCH",
        "W_SWEEP",
    ),
    "discipline": ("_TIER_PROFILE_FRACTION",),
    "macro": ("MACRO_MA_WEEKS", "MACRO_CONFIRM_CLOSES"),
    "position": ("CT_STOP_ATR", "CT_TARGET_R", "CT_MAX_BARS", "COST_FRACTION"),
    "trend_book": (
        "W_MACRO",
        "W_BREAKOUT",
        "W_MA_ALIGN",
        "W_ROC_STRONG",
        "W_ROC_WEAK",
        "W_PULLBACK",
        "TREND_MA",
        "DONCHIAN_N",
        "PULLBACK_MA",
        "MOMENTUM_N",
    ),
    "revert_book": (
        "W_SWEEP",
        "W_RECLAIM",
        "W_DIVERGENCE",
        "W_FUND_CT",
        "W_OI_FLUSH",
        "W_STRETCH",
        "SWEEP_LOOKBACK",
        "EVENT_TTL_BARS",
        "PIVOT_K",
        "DIV_MAX_SPAN",
        "RSI_PERIOD",
        "OI_FLUSH_LOOKBACK",
        "TREND_MA",
        "_AR",
    ),
}


def load_engine_config(path) -> EngineConfig:
    try:
        raw = json.loads(Path(path).read_text())
        if not isinstance(raw, dict):
            return EngineConfig()
        overrides = {k: v for k, v in raw.items() if k in _CONFIG_FIELDS}
        return EngineConfig(**overrides)
    except (OSError, ValueError, TypeError):
        return EngineConfig()


def _frozen_constants_payload() -> dict:
    from moonface.models.engine import confluence, discipline, macro, position
    from moonface.models.engine.modules import revert_book, trend_book

    def _is_frozen_name(name: str) -> bool:
        return name.isupper() or (name.startswith("_") and name[1:].isupper())

    def _key_text(key) -> str:
        if isinstance(key, tuple):
            return "|".join(map(str, key))
        return str(key)

    def _jsonable(value):
        if isinstance(value, dict):
            return {
                _key_text(key): _jsonable(val)
                for key, val in sorted(value.items(), key=lambda item: _key_text(item[0]))
            }
        if isinstance(value, tuple):
            return [_jsonable(item) for item in value]
        if isinstance(value, list):
            return [_jsonable(item) for item in value]
        return value

    def _module_payload(module, field_names: tuple[str, ...]) -> dict:
        observed = sorted(name for name in vars(module) if _is_frozen_name(name))
        expected = sorted(field_names)
        if observed != expected:
            raise RuntimeError(
                f"frozen constant drift in {module.__name__}: "
                f"expected {expected}, observed {observed}"
            )
        frozen = {
            name: _jsonable(getattr(module, name))
            for name in field_names
        }
        return {name: frozen[name] for name in sorted(frozen)}

    return {
        "confluence": _module_payload(confluence, _FROZEN_FIELDS_BY_MODULE["confluence"]),
        "discipline": _module_payload(discipline, _FROZEN_FIELDS_BY_MODULE["discipline"]),
        "macro": _module_payload(macro, _FROZEN_FIELDS_BY_MODULE["macro"]),
        "position": _module_payload(position, _FROZEN_FIELDS_BY_MODULE["position"]),
        "trend_book": _module_payload(trend_book, _FROZEN_FIELDS_BY_MODULE["trend_book"]),
        "revert_book": _module_payload(revert_book, _FROZEN_FIELDS_BY_MODULE["revert_book"]),
    }


def engine_hash(cfg: EngineConfig) -> str:
    payload = {
        k: getattr(cfg, k) for k in sorted(_CONFIG_FIELDS) if k != "enabled"
    }
    payload["__frozen_constants__"] = _frozen_constants_payload()
    payload["__engine_version__"] = ENGINE_VERSION
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
