import unittest

from moonface.kernel.spec import (HypothesisSpec, canonical_json, spec_from_json,
                                    spec_hash)

ASSET = {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "4h"}


def make_spec(**overrides) -> HypothesisSpec:
    base = dict(
        domain="relaxed_budget_btc", version=1, asset=ASSET,
        entry={"family": "funding_fade", "params": {"window": 60, "z_thr": 1.5}},
        exit={"name": "horizon_hold", "params": {"n_bars": 24, "atr_period": 14}},
        fraction=0.01,
    )
    base.update(overrides)
    return HypothesisSpec(**base)


class TestHypothesisSpec(unittest.TestCase):
    def test_hash_is_stable_across_key_order(self):
        a = make_spec(entry={"family": "funding_fade", "params": {"window": 60, "z_thr": 1.5}})
        b = make_spec(entry={"params": {"z_thr": 1.5, "window": 60}, "family": "funding_fade"})
        self.assertEqual(spec_hash(a), spec_hash(b))

    def test_hash_changes_when_params_change(self):
        a = make_spec()
        b = make_spec(fraction=0.02)
        self.assertNotEqual(spec_hash(a), spec_hash(b))

    def test_json_roundtrip(self):
        a = make_spec()
        self.assertEqual(spec_from_json(canonical_json(a)), a)

    def test_hash_is_sha256_hex(self):
        h = spec_hash(make_spec())
        self.assertEqual(len(h), 64)
        int(h, 16)  # raises if not hex


if __name__ == "__main__":
    unittest.main()
