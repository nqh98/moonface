import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from moonface.kernel.reproduce import (offline_fetch_metrics_history,
                                        offline_fetch_perp_candles)
from tools.lanes.liqladder import run_analysis as liqladder_run
from tools.lanes.oibuild_study import run_analysis as oibuild_study_run

CACHE_DIR = ".backtest_cache"


def _cache_available() -> bool:
    return Path(CACHE_DIR).is_dir() and any(Path(CACHE_DIR).iterdir())


pytestmark = pytest.mark.slow


@pytest.mark.skipif(not _cache_available(), reason="requires the live .backtest_cache/")
class TestOibuildStudyDeterminism:
    def test_two_runs_on_frozen_data_are_identical(self):
        cfg = json.loads(Path("experiments/oibuild_study/registration.json").read_text())

        def fetch_candles(sym, start, end):
            return offline_fetch_perp_candles(sym, "4h", start, end, CACHE_DIR)

        def fetch_metric(sym, start, end):
            field = cfg["metrics_field"]
            raw = offline_fetch_metrics_history(sym, start, end, CACHE_DIR)
            return [(ts, f[field]) for ts, f in raw if field in f]

        with TemporaryDirectory() as tmp_a, TemporaryDirectory() as tmp_b:
            out_a = oibuild_study_run(cfg, fetch_candles, fetch_metric, Path(tmp_a))
            out_b = oibuild_study_run(cfg, fetch_candles, fetch_metric, Path(tmp_b))

        for field in ("verdict", "stouffer_z", "pooled_mean", "p_sign",
                      "k_positive", "m_assets"):
            assert out_a[field] == out_b[field], field
        assert out_a["registration_hash"] == out_b["registration_hash"]
        assert out_a["data_fingerprint"] == out_b["data_fingerprint"]


@pytest.mark.skipif(not _cache_available(), reason="requires the live .backtest_cache/")
class TestLiqladderDeterminism:
    def test_two_runs_on_frozen_data_are_identical(self):
        cfg = json.loads(Path("experiments/liqladder/registration.json").read_text())

        def fetch_candles(sym, start, end):
            return offline_fetch_perp_candles(sym, cfg["interval"], start, end, CACHE_DIR)

        def fetch_metrics(sym, start, end):
            return offline_fetch_metrics_history(sym, start, end, CACHE_DIR)

        with TemporaryDirectory() as tmp_a, TemporaryDirectory() as tmp_b:
            out_a = liqladder_run(cfg, fetch_candles, fetch_metrics, Path(tmp_a))
            out_b = liqladder_run(cfg, fetch_candles, fetch_metrics, Path(tmp_b))

        for field in ("verdict", "stouffer_z", "pooled_mean", "k_positive", "m_assets"):
            assert out_a[field] == out_b[field], field
        assert out_a["registration_hash"] == out_b["registration_hash"]
        assert out_a["data_fingerprint"] == out_b["data_fingerprint"]
