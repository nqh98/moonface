from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any


ENGINE_V3_VERSION: str = "v3"
_FROZEN_MATRIX_TEXT = (
    "TRENDING_UP|QUIET=PULLBACK;TRENDING_UP|NORMAL=BREAKOUT;"
    "TRENDING_UP|HIGH=BREAKOUT;RANGING|QUIET=REVERSION;"
    "RANGING|NORMAL=REVERSION;RANGING|HIGH=None;"
    "TRENDING_DOWN|QUIET=PULLBACK;TRENDING_DOWN|NORMAL=BREAKOUT;"
    "TRENDING_DOWN|HIGH=BREAKOUT"
)


def _default_asset() -> dict[str, str]:
    return {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "1h"}


@dataclass(frozen=True)
class EngineConfigV3:
    asset: dict[str, str] = field(default_factory=_default_asset)
    lookback_bars: int = 6000
    adx_period: int = 14
    adx_trend: float = 25.0
    ema_fast: int = 20
    ema_slow: int = 50
    atr_period: int = 14
    vol_baseline: int = 100
    vol_quiet_ratio: float = 0.7
    vol_high_ratio: float = 1.5
    vol_extreme_ratio: float = 2.5
    breakout_n: int = 20
    roc_n: int = 10
    ext_scale: float = 1.0
    roc_scale: float = 0.05
    pullback_ema: int = 20
    pullback_tol: float = 0.003
    adx_scale: float = 40.0
    band_period: int = 20
    band_k: float = 2.0
    rsi_period: int = 14
    stretch_scale: float = 1.5
    q_floor_breakout: float = 0.20
    q_floor_pullback: float = 0.25
    q_floor_reversion: float = 0.30
    enabled: bool = False
    base_fraction: float = 0.005
    max_fraction: float = 0.02


_CONFIG_FIELDS = {field.name for field in fields(EngineConfigV3)}
_DEFAULT_ASSET = _default_asset()


def _is_int(value: Any) -> bool:
    return type(value) is int


def _is_float(value: Any) -> bool:
    return (type(value) is float) or _is_int(value)


def _is_valid_override(name: str, value: Any) -> bool:
    if name == "enabled":
        return type(value) is bool
    if name == "asset":
        return isinstance(value, dict)
    if name in {
        "lookback_bars",
        "adx_period",
        "ema_fast",
        "ema_slow",
        "atr_period",
        "vol_baseline",
        "breakout_n",
        "roc_n",
        "pullback_ema",
        "band_period",
        "rsi_period",
    }:
        return _is_int(value)
    if name in {
        "adx_trend",
        "vol_quiet_ratio",
        "vol_high_ratio",
        "vol_extreme_ratio",
        "ext_scale",
        "roc_scale",
        "pullback_tol",
        "adx_scale",
        "band_k",
        "stretch_scale",
        "q_floor_breakout",
        "q_floor_pullback",
        "q_floor_reversion",
        "base_fraction",
        "max_fraction",
    }:
        return _is_float(value)
    return False


def _coerce_asset(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    asset = dict(_DEFAULT_ASSET)
    for key, item in value.items():
        if key not in asset or type(item) is not str:
            return None
        asset[key] = item
    return asset


def _coerce_overrides(raw: dict[str, Any]) -> dict[str, Any] | None:
    overrides: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in _CONFIG_FIELDS:
            continue
        if key == "asset":
            asset = _coerce_asset(value)
            if asset is None:
                return None
            overrides[key] = asset
            continue
        if not _is_valid_override(key, value):
            return None
        overrides[key] = value
    return overrides


def load_engine_config_v3(path) -> EngineConfigV3:
    try:
        raw = json.loads(Path(path).read_text())
        if not isinstance(raw, dict):
            return EngineConfigV3()
        overrides = _coerce_overrides(raw)
        if overrides is None:
            return EngineConfigV3()
        return EngineConfigV3(**overrides)
    except (OSError, ValueError, TypeError):
        return EngineConfigV3()


def engine_hash_v3(cfg: EngineConfigV3) -> str:
    payload: dict[str, Any] = {
        name: getattr(cfg, name)
        for name in sorted(_CONFIG_FIELDS)
        if name != "enabled"
    }
    payload["__engine_version__"] = ENGINE_V3_VERSION
    payload["__frozen_matrix_text__"] = _FROZEN_MATRIX_TEXT
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
