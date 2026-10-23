from __future__ import annotations

from dataclasses import dataclass

from moonface.core.models import Candle


FEATURE_COVERAGE_MIN = 0.8  # aligned feature series must be >=80% non-None


@dataclass(frozen=True)
class DataBundle:
    """Everything a hypothesis can see for one asset. funding/basis/feature/
    bookdepth are aligned 1:1 with candles (as-of joins, no lookahead) or None
    when not loaded. `feature` is a cross-asset close series (e.g. ETH for
    lead-lag) or a metrics series; `bookdepth` is the per-bar mean ±1% depth
    imbalance."""

    candles: list[Candle]
    funding: list[float | None] | None = None
    basis: list[float | None] | None = None
    feature: list[float | None] | None = None
    bookdepth: list[float | None] | None = None


def align_feature(candles: list[Candle],
                  feat_candles: list[Candle]) -> list[float | None]:
    """Exact close-time join: both series share the timeframe, so the feature
    candle closing at the same timestamp is fully closed — no lookahead."""
    closes = {c.timestamp_ms: c.close for c in feat_candles}
    return [closes.get(c.timestamp_ms) for c in candles]


def _check_coverage(feature: list[float | None], label: str) -> None:
    filled = sum(1 for v in feature if v is not None)
    if not feature or filled / len(feature) < FEATURE_COVERAGE_MIN:
        raise ValueError(
            f"feature {label} coverage {filled}/{len(feature)} below"
            f" {FEATURE_COVERAGE_MIN:.0%}; refusing to run with a gappy"
            " feature series")
