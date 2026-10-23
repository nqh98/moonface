"""Frozen, order-stable point-in-time feature set for the 4h path model.

Every feature at base bar i uses only candles[: i+1] (closed by bar i). HTF,
funding, positioning, and cross-sectional inputs are optional kwargs; when not
supplied those features are omitted from FEATURE_NAMES coverage by yielding None
for the whole row only if a *required* base feature is missing. Optional inputs
that are None for a given bar make that row None (dropped downstream)."""
from __future__ import annotations

from statistics import fmean, pstdev

from moonface.research.edge.evaluate import _risk
from moonface.core.models import Candle

# Order-stable frozen list. Base (price/vol) features are always present; the
# remaining features require their optional series and are still part of the
# frozen vector (a row missing any is dropped in build_dataset).
FEATURE_NAMES: tuple[str, ...] = (
    "ret_1", "ret_6", "ret_24",
    "rvol_24", "atr_frac",
    "ma100_dist", "donchian_pos_55",
    "htf_d1_ret_1", "htf_d1_rvol_14", "htf_w1_ret_1",
    "funding_level", "funding_slope_8",
    "oi_z", "taker_z",
    "xs_ret_rank", "xs_funding_rank",
)

_WARMUP = 100  # longest base lookback (ma100 / donchian via 55, rvol 24)


def _ret(candles: list[Candle], i: int, n: int) -> float | None:
    if i - n < 0:
        return None
    prev = candles[i - n].close
    if prev <= 0:
        return None
    return candles[i].close / prev - 1.0


def _rvol(candles: list[Candle], i: int, n: int) -> float | None:
    if i - n < 0:
        return None
    rets = []
    for k in range(i - n + 1, i + 1):
        p = candles[k - 1].close
        if p > 0:
            rets.append(candles[k].close / p - 1.0)
    if len(rets) < 2:
        return None
    return pstdev(rets)


def _ma_dist(candles: list[Candle], i: int, n: int) -> float | None:
    if i - n + 1 < 0:
        return None
    ma = fmean(c.close for c in candles[i - n + 1: i + 1])
    if ma <= 0:
        return None
    return candles[i].close / ma - 1.0


def _donchian_pos(candles: list[Candle], i: int, n: int) -> float | None:
    if i - n + 1 < 0:
        return None
    window = candles[i - n + 1: i + 1]
    hi = max(c.high for c in window)
    lo = min(c.low for c in window)
    if hi <= lo:
        return 0.5
    return (candles[i].close - lo) / (hi - lo)


def base_features(candles: list[Candle], i: int,
                  atr_period: int) -> dict[str, float] | None:
    """The always-present price/vol block. None until warmup satisfied."""
    if i < _WARMUP:
        return None
    unit = _risk(candles, i, 1.0, atr_period)
    close = candles[i].close
    parts = {
        "ret_1": _ret(candles, i, 1),
        "ret_6": _ret(candles, i, 6),
        "ret_24": _ret(candles, i, 24),
        "rvol_24": _rvol(candles, i, 24),
        "atr_frac": (unit / close) if (unit is not None and close > 0) else None,
        "ma100_dist": _ma_dist(candles, i, 100),
        "donchian_pos_55": _donchian_pos(candles, i, 55),
    }
    if any(v is None for v in parts.values()):
        return None
    return parts


def build_feature_rows(candles: list[Candle], atr_period: int
                       ) -> list[dict[str, float] | None]:
    """Base feature rows only (HTF/funding/positioning/cross-sectional are
    merged by build_dataset which has access to the aligned series). A row is
    None until warmup is satisfied. The keys of a non-None row are exactly the
    base block; build_dataset fills the remaining FEATURE_NAMES."""
    return [base_features(candles, i, atr_period) for i in range(len(candles))]


def to_vector(row: dict[str, float]) -> list[float]:
    """Project a complete feature dict onto FEATURE_NAMES order."""
    return [row[name] for name in FEATURE_NAMES]


def zscore(values: list[float | None], i: int, n: int) -> float | None:
    """Trailing z-score of values[i] over the n bars ending at i, inclusive.
    Nullable series: a None current value or a window with <2 non-None values
    (or zero variance) yields None."""
    if i - n + 1 < 0:
        return None
    if values[i] is None:
        return None
    window = [v for v in values[i - n + 1: i + 1] if v is not None]
    if len(window) < 2:
        return None
    mu = fmean(window)
    sd = pstdev(window)
    if sd <= 0:
        return None
    return (values[i] - mu) / sd
