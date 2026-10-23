from __future__ import annotations

from dataclasses import dataclass
import os


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    """Data-source and deterministic analysis constants for the research
    engine. MoonFace is signal research only: there is no live bot, no LLM,
    and no notification layer."""

    exchange: str
    symbol: str
    sandbox: bool
    n_periods: int = 5
    atr_period: int = 14
    displacement_atr_mult: float = 1.5
    stop_atr_floor_mult: float = 1.0
    fib_zone_low: float = 0.618
    fib_zone_high: float = 0.786
    min_rr2: float = 1.5
    sweep_tol_atr_mult: float = 0.25
    lookback_bars: int = 30
    mitigation_lookback: int = 30
    confirmation_window: int = 48
    min_confluence_score: float = 1.0
    pinbar_wick_body_ratio: float = 2.0
    poi_tolerance: float = 0.0
    sweep_lookback: int = 30
    require_htf_bias: bool = True
    require_choch: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            exchange=os.getenv("MOONFACE_EXCHANGE", "binance").strip().lower(),
            symbol=os.getenv("MOONFACE_SYMBOL", "BTC/USDT:USDT").strip(),
            sandbox=_bool_env("MOONFACE_SANDBOX", False),
            n_periods=_int_env("MOONFACE_N_PERIODS", 5),
            atr_period=_int_env("MOONFACE_ATR_PERIOD", 14),
            displacement_atr_mult=_float_env("MOONFACE_DISPLACEMENT_ATR_MULT", 1.5),
            stop_atr_floor_mult=_float_env("MOONFACE_STOP_ATR_FLOOR_MULT", 1.0),
            fib_zone_low=_float_env("MOONFACE_FIB_ZONE_LOW", 0.618),
            fib_zone_high=_float_env("MOONFACE_FIB_ZONE_HIGH", 0.786),
            min_rr2=_float_env("MOONFACE_MIN_RR2", 1.5),
            sweep_tol_atr_mult=_float_env("MOONFACE_SWEEP_TOL_ATR_MULT", 0.25),
            lookback_bars=_int_env("MOONFACE_LOOKBACK_BARS", 30),
            mitigation_lookback=_int_env("MOONFACE_MITIGATION_LOOKBACK", 30),
            confirmation_window=_int_env("MOONFACE_CONFIRMATION_WINDOW", 48),
            min_confluence_score=_float_env("MOONFACE_MIN_CONFLUENCE_SCORE", 1.0),
            pinbar_wick_body_ratio=_float_env("MOONFACE_PINBAR_WICK_BODY_RATIO", 2.0),
            poi_tolerance=_float_env("MOONFACE_POI_TOLERANCE", 0.0),
            sweep_lookback=_int_env("MOONFACE_SWEEP_LOOKBACK", 30),
        )
