import os
import sys
import tempfile
from unittest import mock
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import macro_regime_model as m
from tests._synthetic import make_synthetic_fetcher, make_synthetic_raw


class TestEntropy(unittest.TestCase):
    def test_uniform_is_max_normalized_entropy(self):
        proba = np.full((5, 3), 1 / 3)
        np.testing.assert_allclose(m.normalized_entropy(proba), np.ones(5), atol=1e-9)

    def test_one_hot_is_zero_entropy(self):
        proba = np.zeros((4, 3))
        proba[:, 1] = 1.0
        np.testing.assert_allclose(m.regime_entropy(proba), np.zeros(4), atol=1e-9)
        np.testing.assert_allclose(m.normalized_entropy(proba), np.zeros(4), atol=1e-9)

    def test_entropy_nats_matches_formula(self):
        proba = np.array([[0.5, 0.5]])
        np.testing.assert_allclose(m.regime_entropy(proba), [np.log(2)], atol=1e-9)


class TestFeatures(unittest.TestCase):
    def test_columns_and_stationarity(self):
        raw = make_synthetic_raw(n=300, seed=1)
        feat = m.build_features(raw, window=20)
        for col in m.EXOG_FEATURES:
            self.assertIn(col, feat.columns)
        for carried in ("BTC_close", "BTC_logret", "BTC_Gold_Ratio_Return"):
            self.assertIn(carried, feat.columns)
        for level in ("DXY", "TNX", "GOLD", "BTC"):
            self.assertNotIn(level, feat.columns)
        self.assertFalse(feat.isna().any().any())

    def test_tnx_uses_first_difference_not_pct_return(self):
        raw = make_synthetic_raw(n=300, seed=1)
        feat = m.build_features(raw, window=20)
        expected = raw["TNX"].diff().reindex(feat.index)
        np.testing.assert_allclose(feat["tnx_dyield"].values, expected.values, atol=1e-9)


class TestCausalRegimeModel(unittest.TestCase):
    def setUp(self):
        raw = make_synthetic_raw(n=500, seed=2)
        self.feat = m.build_features(raw, window=20)
        self.train = self.feat.iloc[:300]
        self.test = self.feat.iloc[300:]

    def test_predict_before_fit_raises(self):
        model = m.CausalRegimeModel(n_components=3)
        with self.assertRaises(RuntimeError):
            model.predict_proba(self.test)

    def test_label_frame_shape_and_columns(self):
        model = m.CausalRegimeModel(n_components=3).fit(self.train)
        out = model.label(self.test)
        for k in range(3):
            self.assertIn(f"P_State_{k}", out.columns)
        for c in ("entropy", "entropy_norm", "regime_argmax", "BTC_close", "BTC_logret", "BTC_Gold_Ratio_Return"):
            self.assertIn(c, out.columns)
        p = out[[f"P_State_{k}" for k in range(3)]].to_numpy()
        np.testing.assert_allclose(p.sum(axis=1), np.ones(len(out)), atol=1e-6)

    def test_canonical_order_is_ascending_on_ordering_axis(self):
        model = m.CausalRegimeModel(n_components=3).fit(self.train)
        idx = model.features.index(m.ORDERING_FEATURE)
        ordered_means = model.gmm.means_[model._order, idx]
        self.assertTrue(np.all(np.diff(ordered_means) >= 0))

    def test_same_data_same_labels(self):
        a = m.CausalRegimeModel(n_components=3).fit(self.train).label(self.test)
        b = m.CausalRegimeModel(n_components=3).fit(self.train).label(self.test)
        np.testing.assert_array_equal(a["regime_argmax"].values, b["regime_argmax"].values)

    def test_no_fit_in_predict_path(self):
        model = m.CausalRegimeModel(n_components=3).fit(self.train)
        with mock.patch.object(type(model.scaler), "fit") as sfit, mock.patch.object(
            type(model.gmm), "fit"
        ) as gfit:
            model.predict_proba(self.test)
            model.label(self.test)
        sfit.assert_not_called()
        gfit.assert_not_called()


class TestWalkForward(unittest.TestCase):
    def setUp(self):
        raw = make_synthetic_raw(n=800, seed=3)
        self.feat = m.build_features(raw, window=20)

    def test_covers_rows_past_warmup(self):
        wf = m.WalkForwardRegimeLabeler(n_components=3, warmup=300, step=50)
        out = wf.run(self.feat)
        self.assertEqual(len(out), len(self.feat) - 300)
        self.assertEqual(list(out.index), list(self.feat.index[300:]))

    def test_too_few_rows_raises(self):
        wf = m.WalkForwardRegimeLabeler(n_components=3, warmup=len(self.feat) + 10, step=50)
        with self.assertRaises(ValueError):
            wf.run(self.feat)

    def test_causality_future_mutation_does_not_change_past_labels(self):
        wf = m.WalkForwardRegimeLabeler(n_components=3, warmup=300, step=50)
        base = wf.run(self.feat)
        mutated = self.feat.copy()
        mutated.iloc[-1, mutated.columns.get_loc("dxy_logret")] += 5.0
        after = wf.run(mutated)
        cutoff = self.feat.index[len(self.feat) - ((len(self.feat) - 300) % 50 or 50)]
        common = base.index[base.index < cutoff]
        np.testing.assert_array_equal(
            base.loc[common, "regime_argmax"].values,
            after.loc[common, "regime_argmax"].values,
        )


class TestDataLoader(unittest.TestCase):
    def test_align_shapes_and_columns(self):
        with tempfile.TemporaryDirectory() as d:
            loader = m.MacroDataLoader(cache_dir=d, fetcher=make_synthetic_fetcher(n=400, seed=4))
            raw = loader.load("2018-01-01")
            self.assertEqual(list(raw.columns), ["DXY", "TNX", "GOLD", "BTC"])
            self.assertFalse(raw[["DXY", "TNX", "GOLD"]].isna().any().any())
            self.assertEqual(len(raw), 400)

    def test_cache_roundtrip_avoids_second_fetch(self):
        calls = {"n": 0}
        base = make_synthetic_fetcher(n=300, seed=5)

        def counting_fetch(ticker, start, end):
            calls["n"] += 1
            return base(ticker, start, end)

        with tempfile.TemporaryDirectory() as d:
            m.MacroDataLoader(cache_dir=d, fetcher=counting_fetch).load("2018-01-01")
            first = calls["n"]
            m.MacroDataLoader(cache_dir=d, fetcher=counting_fetch).load("2018-01-01")
            self.assertEqual(first, 4)
            self.assertEqual(calls["n"], first)

    def test_empty_fetch_raises(self):
        def empty_fetch(ticker, start, end):
            return pd.Series([], dtype=float, name=ticker)

        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                m.MacroDataLoader(cache_dir=d, fetcher=empty_fetch).load("2018-01-01")


class TestOrchestratorAndCLI(unittest.TestCase):
    def test_build_regime_frame_split_mode(self):
        with tempfile.TemporaryDirectory() as d:
            frame = m.build_regime_frame(
                start="2018-01-01",
                n_components=3,
                window=20,
                mode="split",
                cache_dir=d,
                fetcher=make_synthetic_fetcher(n=500, seed=6),
            )
            for k in range(3):
                self.assertIn(f"P_State_{k}", frame.columns)
            self.assertIn("entropy_norm", frame.columns)
            self.assertGreater(len(frame), 0)

    def test_build_regime_frame_walkforward_mode(self):
        with tempfile.TemporaryDirectory() as d:
            frame = m.build_regime_frame(
                start="2018-01-01",
                n_components=3,
                window=20,
                mode="walkforward",
                warmup=300,
                step=50,
                cache_dir=d,
                fetcher=make_synthetic_fetcher(n=600, seed=7),
            )
            self.assertGreater(len(frame), 0)
            self.assertIn("regime_argmax", frame.columns)

    def test_summarize_mentions_every_state(self):
        with tempfile.TemporaryDirectory() as d:
            frame = m.build_regime_frame(
                start="2018-01-01",
                n_components=3,
                mode="split",
                cache_dir=d,
                fetcher=make_synthetic_fetcher(n=500, seed=6),
            )
            text = m.summarize(frame, 3)
            for k in range(3):
                self.assertIn(f"State {k}", text)

    def test_main_writes_csv(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "regimes.csv")
            orig = m._yf_fetch
            m._yf_fetch = make_synthetic_fetcher(n=500, seed=6)
            try:
                rc = m.main(
                    [
                        "--start",
                        "2018-01-01",
                        "--components",
                        "3",
                        "--mode",
                        "split",
                        "--cache-dir",
                        d,
                        "--out",
                        out,
                    ]
                )
            finally:
                m._yf_fetch = orig
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
