"""Scoring pass of the read-only v2 calibration diagnostic.

Parity claim (spec §2c): the pass calls the SAME frozen functions
evaluate_engine calls, in the same order, on the same rolling window — so its
Decision must equal evaluate_engine's Decision bar-for-bar while flat."""
import random

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.models.engine.calibration import (_TREND_MODULES, BarRow,
                                                BookState, scoring_pass)
from moonface.models.engine.config import EngineConfig, engine_hash
from moonface.models.engine.confluence import EXCLUDED_MODULES
from moonface.models.engine.deriv import DerivSnapshot
from moonface.models.engine.engine import evaluate_engine
from moonface.models.engine.modules import trend_book
from moonface.models.engine.modules.base import ModuleScore

H = 3_600_000

V2_FROZEN_HASH = "10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf"
V21_FROZEN_HASH = "4e35561fe6b7d639712e10f8b87d78b5cf0a6d629d9ccc2cac8d605909305a6a"
V22_FROZEN_HASH = "b4924f8eadd603db8dc8a7c63a35971f56ac0b46a81c07674f45555686ec85b5"


def _walk_series(n, seed=7, start=100.0):
    rng = random.Random(seed)
    out, price = [], start
    for i in range(n):
        drift = rng.uniform(-1.0, 1.5)
        o = price
        c = max(1.0, price + drift)
        hi = max(o, c) + rng.uniform(0.0, 0.8)
        lo = min(o, c) - rng.uniform(0.0, 0.8)
        out.append(Candle(i * H, o, hi, lo, c, 10.0))
        price = c
    return out


def _cfg(**kw):
    base = dict(lookback_bars=400)
    base.update(kw)
    return EngineConfig(**base)


def test_engine_hash_matches_v22_identity():
    # v2.2 journals under the new frozen identity, not the superseded v2/v2.1 ones.
    h = engine_hash(EngineConfig())
    assert h != V2_FROZEN_HASH
    assert h != V21_FROZEN_HASH
    assert h == V22_FROZEN_HASH


def test_scoring_pass_row_shape_and_indices():
    candles = _walk_series(420)
    rows = scoring_pass(_cfg(), candles, warmup=380)
    assert len(rows) == 420 - 380
    first = rows[0]
    assert isinstance(first, BarRow)
    assert first.index == 380
    assert first.ts_ms == candles[380].timestamp_ms
    assert isinstance(first.trend, BookState)
    assert isinstance(first.revert, BookState)
    # all 12 module names present in the signed-points map
    assert len(first.module_points) == 12
    assert "m1_macro" in first.module_points
    assert "m6_stretch" in first.module_points


def test_scoring_pass_decision_parity_with_evaluate_engine():
    candles = _walk_series(430, seed=11)
    cfg = _cfg()
    warmup = 380
    rows = scoring_pass(cfg, candles, warmup)
    window = cfg.lookback_bars
    for row in rows:
        j = row.index
        lo = max(0, j + 1 - window)
        sub = DataBundle(candles=candles[lo:j + 1])
        res = evaluate_engine(cfg, sub, entries=[],
                              now_ms=candles[j].timestamp_ms)
        assert res.decision is not None
        assert row.decision_action == res.decision.action
        assert row.decision_direction == res.decision.direction
        assert row.decision_score == res.decision.score
        assert row.vol_state == res.regime_vol
        assert row.regime_trend == res.regime_trend


def test_book_state_policy_only_when_directional():
    candles = _walk_series(420, seed=3)
    rows = scoring_pass(_cfg(), candles, warmup=380)
    for row in rows:
        for state in (row.trend, row.revert):
            if state.direction == 0:
                assert state.policy is None
            else:
                assert state.policy in ("ALLOW", "ALLOW_CT", "REJECT")


def test_sweep_wick_only_when_revert_directional():
    candles = _walk_series(420, seed=5)
    rows = scoring_pass(_cfg(), candles, warmup=380)
    for row in rows:
        if row.sweep_wick is not None:
            assert row.revert.direction != 0


def test_scoring_pass_deriv_seam_defaults_match_base_output():
    candles = _walk_series(430, seed=17)
    cfg = _cfg()
    warmup = 380
    base_rows = scoring_pass(cfg, candles, warmup)
    assert scoring_pass(cfg, candles, warmup, None) == base_rows
    assert scoring_pass(cfg, candles, warmup, {}) == base_rows


def test_scoring_pass_threads_deriv_snapshot_to_trend_score(monkeypatch):
    candles = _walk_series(430, seed=19)
    cfg = _cfg()
    warmup = 380
    snapshot = DerivSnapshot(funding_pct=50.0)
    seen = []

    original_score = trend_book.score

    def wrapped_score(views, macro, deriv, cfg):
        seen.append(deriv)
        return original_score(views, macro, deriv, cfg)

    monkeypatch.setattr(trend_book, "score", wrapped_score)

    rows = scoring_pass(cfg, candles, warmup,
                        {warmup: snapshot, warmup + 1: snapshot})

    assert len(rows) == 430 - warmup
    assert seen[0] is snapshot
    assert seen[1] is snapshot
    assert all(item is None for item in seen[2:])


def test_book_state_excludes_m4_pullback(monkeypatch):
    # Force m4_pullback to a nonzero score on every bar: the BarRow trend
    # BookState must mirror the live engine and leave it uncounted, while
    # module_points still journals it.
    candles = _walk_series(430, seed=29)
    cfg = _cfg()
    original = trend_book.score

    def forced(views, macro, deriv, c):
        out = []
        for m in original(views, macro, deriv, c):
            if m.module == "m4_pullback":
                m = ModuleScore(module="m4_pullback", direction=1, points=15,
                                archetype=m.archetype, data_ok=True,
                                evidence=("forced",))
            out.append(m)
        return out

    monkeypatch.setattr(trend_book, "score", forced)
    rows = scoring_pass(cfg, candles, warmup=380)
    counted = [m for m in _TREND_MODULES if m not in EXCLUDED_MODULES]
    assert counted == ["m1_macro", "m2_breakout", "m2_ma_align",
                       "m3_roc", "m5_funding"]
    for row in rows:
        assert row.module_points["m4_pullback"] == 15
        signed = sum(row.module_points[m] for m in counted)
        assert row.trend.score == abs(signed)
