from __future__ import annotations

from dataclasses import dataclass

import pytest

from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig
from moonface.models.engine.deriv import (
    DerivSnapshot,
    FUND_CROWDED,
    FUND_HIGH,
    FUND_LOW,
    OI_FLUSH,
    fetch_deriv_snapshot,
    funding_points_ct,
    funding_points_trend,
    oi_flush_points,
)
from moonface.models.engine.macro import MacroState
from moonface.models.engine.modules.base import DerivSnapshot as BaseDerivSnapshot
from moonface.models.engine.modules.base import TfViews
from moonface.models.engine.modules.revert_book import score as revert_score
from moonface.models.engine.modules.trend_book import score as trend_score

H = 3_600_000
D = 24 * H
W = 7 * D


def _cfg() -> EngineConfig:
    return EngineConfig(atr_period=14)


def _candles(closes: list[float], step_ms: int, spread: float = 1.0) -> list[Candle]:
    out: list[Candle] = []
    prev = closes[0]
    for i, close in enumerate(closes):
        open_ = prev if i else close
        high = max(open_, close) + spread
        low = min(open_, close) - spread
        out.append(Candle(i * step_ms, open_, high, low, close, 1.0))
        prev = close
    return out


def _views() -> TfViews:
    rising_h1 = _candles([100.0 + i for i in range(80)], H)
    rising_h4 = _candles([100.0 + i for i in range(80)], 4 * H)
    rising_d1 = _candles([100.0 + i for i in range(80)], D)
    rising_w1 = _candles([100.0 + i for i in range(80)], W)
    return TfViews(h1=rising_h1, h4=rising_h4, d1=rising_d1, w1=rising_w1)


@dataclass(frozen=True)
class _LegacyOiOnly:
    oi_change_pct: float | None = None
    oi_change_z: float | None = None


@pytest.mark.parametrize(
    ("rates", "expected_pct"),
    [
        ([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 0.0], FUND_LOW),
        ([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 9.0, 7.0], FUND_CROWDED),
        ([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 9.0, 8.0], FUND_HIGH),
    ],
)
def test_fetch_deriv_snapshot_computes_percentile_edges(monkeypatch, rates, expected_pct):
    def fake_funding(_symbol, _start_ms, _end_ms, _cache_dir):
        return [(i, rate) for i, rate in enumerate(rates)]

    monkeypatch.setattr("moonface.models.engine.deriv.fetch_funding_rates", fake_funding)
    monkeypatch.setattr(
        "moonface.models.engine.deriv._fetch_open_interest_points",
        lambda *_args, **_kwargs: [],
    )

    snap = fetch_deriv_snapshot("BTCUSDT", now_ms=30 * D)

    assert snap == DerivSnapshot(funding_pct=expected_pct, oi_change_6h=None)


def test_funding_helpers_use_exact_band_edges_and_direction_symmetry():
    low = DerivSnapshot(funding_pct=FUND_LOW, oi_change_6h=None)
    crowded = DerivSnapshot(funding_pct=FUND_CROWDED, oi_change_6h=None)
    high = DerivSnapshot(funding_pct=FUND_HIGH, oi_change_6h=None)

    low_points, low_evidence = funding_points_trend(low, 1)
    assert low_points == 15
    assert "<= 10.00" in low_evidence
    assert funding_points_trend(low, -1)[0] == 0
    assert funding_points_ct(low, 1)[0] == 15
    assert funding_points_ct(low, -1)[0] == 0

    crowded_points, crowded_evidence = funding_points_trend(crowded, 1)
    assert crowded_points == 0
    assert ">= 80.00" in crowded_evidence
    assert funding_points_trend(crowded, -1)[0] == 5
    assert funding_points_ct(crowded, -1)[0] == 0

    high_points, high_evidence = funding_points_trend(high, -1)
    assert high_points == 15
    assert ">= 90.00" in high_evidence
    assert funding_points_trend(high, 1)[0] == 0
    assert funding_points_ct(high, -1)[0] == 15
    assert funding_points_ct(high, 1)[0] == 0


def test_none_snapshot_fields_score_zero_and_keep_upstream_data_not_ok():
    snap = DerivSnapshot(funding_pct=None, oi_change_6h=None)

    assert funding_points_trend(snap, 1)[0] == 0
    assert funding_points_ct(snap, -1)[0] == 0
    assert oi_flush_points(snap)[0] == 0

    views = _views()
    macro = MacroState("BULL", True, "normal")
    trend = {item.module: item for item in trend_score(views, macro, snap, _cfg())}
    revert = {item.module: item for item in revert_score(views, macro, snap, _cfg())}

    assert trend["m5_funding"].data_ok is False
    assert revert["m4_fund_ct"].data_ok is False
    assert revert["m5_oi_flush"].data_ok is False


def test_oi_flush_points_accepts_fractional_change_aliases():
    snap = DerivSnapshot(funding_pct=None, oi_change_6h=OI_FLUSH)
    legacy = _LegacyOiOnly(oi_change_pct=OI_FLUSH)

    assert oi_flush_points(snap)[0] == 10
    assert oi_flush_points(legacy)[0] == 10


def test_fetch_deriv_snapshot_never_raises_and_returns_all_none_on_failure(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("moonface.models.engine.deriv.fetch_funding_rates", boom)
    monkeypatch.setattr(
        "moonface.models.engine.deriv._fetch_open_interest_points",
        lambda *_args, **_kwargs: [(0, 100.0), (6 * H, 97.0)],
    )

    snap = fetch_deriv_snapshot("BTCUSDT", now_ms=30 * D)

    assert snap == DerivSnapshot(funding_pct=None, oi_change_6h=None)


def test_base_module_reexports_canonical_deriv_snapshot():
    assert BaseDerivSnapshot is DerivSnapshot
