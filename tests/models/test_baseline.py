import math

from moonface.core.models import Candle

_H4_MS = 4 * 3_600_000


def _candles(closes, highs=None, lows=None):
    """Build candles from close prices; highs/lows default to close."""
    out = []
    ts = 1_600_000_000_000
    for k, close in enumerate(closes):
        hi = close if highs is None else highs[k]
        lo = close if lows is None else lows[k]
        out.append(Candle(ts, close, hi, lo, close, 1000.0))
        ts += _H4_MS
    return out


class TestVoters:
    def test_trend_breakout_long_when_close_above_prior_high(self):
        from moonface.models.baseline import trend_breakout_vote
        # n=3; last close breaks above the max of the prior 3 highs
        candles = _candles([10, 11, 12, 13, 20])
        assert trend_breakout_vote(candles, n=3) == 1

    def test_trend_breakout_short_when_close_below_prior_low(self):
        from moonface.models.baseline import trend_breakout_vote
        candles = _candles([20, 19, 18, 17, 5])
        assert trend_breakout_vote(candles, n=3) == -1

    def test_trend_breakout_neutral_inside_channel(self):
        from moonface.models.baseline import trend_breakout_vote
        candles = _candles([10, 20, 5, 30, 15])
        assert trend_breakout_vote(candles, n=3) == 0

    def test_trend_confirm_sign_of_close_minus_sma(self):
        from moonface.models.baseline import trend_confirm_vote
        rising = _candles([1, 2, 3, 4, 100])
        assert trend_confirm_vote(rising, period=4) == 1
        falling = _candles([100, 99, 98, 97, 1])
        assert trend_confirm_vote(falling, period=4) == -1

    def test_funding_fade_short_on_crowded_long(self):
        from moonface.models.baseline import funding_fade_vote
        funding = [0.0] * 9 + [0.10]      # last value is a large positive spike
        assert funding_fade_vote(funding, window=10, z_thr=1.5) == -1

    def test_funding_fade_long_on_crowded_short(self):
        from moonface.models.baseline import funding_fade_vote
        funding = [0.0] * 9 + [-0.10]
        assert funding_fade_vote(funding, window=10, z_thr=1.5) == 1

    def test_funding_fade_abstains_without_data(self):
        from moonface.models.baseline import funding_fade_vote
        assert funding_fade_vote(None, window=10, z_thr=1.5) == 0
        assert funding_fade_vote([0.0] * 3, window=10, z_thr=1.5) == 0


class TestVolRatio:
    def test_none_without_enough_history(self):
        from moonface.models.baseline import vol_ratio
        assert vol_ratio(_candles([1, 2, 3]), window=5) is None

    def test_calm_then_spike_ratio_above_one(self):
        from moonface.models.baseline import vol_ratio
        closes = [100.0]
        for _ in range(60):
            closes.append(closes[-1] * 1.001)      # long calm baseline
        for _ in range(6):
            closes.append(closes[-1] * 1.05)       # recent vol spike
        r = vol_ratio(_candles(closes), window=10)
        assert r is not None and r > 1.5

    def test_steady_regime_ratio_near_one(self):
        from moonface.models.baseline import vol_ratio
        closes = [100.0 * (1.002 ** k) for k in range(80)]
        r = vol_ratio(_candles(closes), window=10)
        assert r is not None and 0.8 < r < 1.2


class TestAggregate:
    def test_unanimous_long_full_agreement(self):
        from moonface.models.baseline import aggregate
        decision, agreement = aggregate(
            {"a": 1, "b": 1, "c": 1}, {"a": 1.0, "b": 1.0, "c": 1.0}, 0.5)
        assert decision == "LONG"
        assert agreement == 1.0

    def test_split_below_floor_is_wait(self):
        from moonface.models.baseline import aggregate
        decision, agreement = aggregate(
            {"a": 1, "b": -1, "c": 0}, {"a": 1.0, "b": 1.0, "c": 1.0}, 0.5)
        assert decision == "WAIT"
        assert math.isclose(agreement, 0.0)

    def test_majority_short_above_floor(self):
        from moonface.models.baseline import aggregate
        # 2 votes against 1 with double weight on shorts
        decision, agreement = aggregate(
            {"a": -1, "b": -1, "c": 1}, {"a": 2.0, "b": 2.0, "c": 1.0}, 0.5)
        assert decision == "SHORT"
        assert math.isclose(agreement, 3.0 / 5.0)  # net=-3, total=5


class TestBaselineConfig:
    def test_missing_file_returns_enabled_default(self, tmp_path):
        from moonface.models.baseline import load_baseline_config
        cfg = load_baseline_config(tmp_path / "absent.json")
        assert cfg.enabled is True
        assert cfg.asset["symbol"] == "BTC/USDT:USDT"
        assert cfg.asset["timeframe"] == "4h"
        assert cfg.agreement_floor == 0.5

    def test_invalid_json_falls_back_to_default(self, tmp_path):
        from moonface.models.baseline import load_baseline_config
        p = tmp_path / "baseline.json"
        p.write_text("{not json")
        cfg = load_baseline_config(p)
        assert cfg.enabled is True

    def test_explicit_disable_is_honored(self, tmp_path):
        import json
        from moonface.models.baseline import load_baseline_config
        p = tmp_path / "baseline.json"
        p.write_text(json.dumps({"enabled": False}))
        cfg = load_baseline_config(p)
        assert cfg.enabled is False

    def test_overrides_merge_onto_defaults(self, tmp_path):
        import json
        from moonface.models.baseline import load_baseline_config
        p = tmp_path / "baseline.json"
        p.write_text(json.dumps({"donchian_n": 55, "agreement_floor": 0.9}))
        cfg = load_baseline_config(p)
        assert cfg.donchian_n == 55
        assert cfg.agreement_floor == 0.9
        assert cfg.ma_period == 50  # untouched default

    def test_hash_excludes_enabled_flag(self, tmp_path):
        import json
        from moonface.models.baseline import (baseline_hash,
                                              load_baseline_config)
        a = load_baseline_config(tmp_path / "absent.json")
        p = tmp_path / "baseline.json"
        p.write_text(json.dumps({"enabled": False}))
        b = load_baseline_config(p)
        # flipping only `enabled` must not change the journal identity
        assert baseline_hash(a) == baseline_hash(b)


class TestEvaluateBaseline:
    def _bundle(self, closes, funding=None):
        from moonface.core.bundle import DataBundle
        return DataBundle(candles=_candles(closes), funding=funding)

    def test_returns_wait_signal_with_baseline_tier_on_short_history(self):
        from moonface.models.baseline import BaselineConfig, evaluate_baseline
        sig = evaluate_baseline(BaselineConfig(), self._bundle([1, 2, 3]), 0)
        assert sig.decision == "WAIT"
        assert sig.tier == "baseline"
        assert sig.timeframe == "4h"

    def test_strong_uptrend_emits_long_with_label_and_risk_notes(self):
        from moonface.kernel.synth import make_candles
        from moonface.core.bundle import DataBundle
        from moonface.models.baseline import BaselineConfig, evaluate_baseline
        # steady drift up -> breakout + above-MA agree; funding abstains (None)
        candles = make_candles(n=200, drift=0.01, noise=0.001)
        sig = evaluate_baseline(BaselineConfig(), DataBundle(candles=candles), 0)
        assert sig.decision == "LONG"
        assert sig.tier == "baseline"
        assert 0.0 < sig.confidence <= 1.0
        assert sig.price == candles[-1].close
        assert sig.invalidation is not None and sig.invalidation < sig.price
        assert "no expectancy claim" in sig.risk_notes.lower()
        assert "not a validated edge" in sig.reason.lower()
        assert sig.fraction == BaselineConfig().risk_fraction

    def test_short_invalidation_sits_above_price(self):
        from moonface.kernel.synth import make_candles
        from moonface.core.bundle import DataBundle
        from moonface.models.baseline import BaselineConfig, evaluate_baseline
        candles = make_candles(n=200, drift=-0.01, noise=0.001)
        sig = evaluate_baseline(BaselineConfig(), DataBundle(candles=candles), 0)
        assert sig.decision == "SHORT"
        assert sig.invalidation > sig.price

    def test_confidence_never_exceeds_one(self):
        from moonface.kernel.synth import make_candles
        from moonface.core.bundle import DataBundle
        from moonface.models.baseline import BaselineConfig, evaluate_baseline
        candles = make_candles(n=200, drift=0.01, noise=0.001)
        sig = evaluate_baseline(BaselineConfig(), DataBundle(candles=candles), 0)
        assert sig.confidence <= 1.0