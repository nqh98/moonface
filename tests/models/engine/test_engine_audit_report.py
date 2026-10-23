"""Verdict precedence and end-to-end audit report shape."""
import json

from moonface.models.engine.audit import (AUDIT_LABEL, book_verdict,
                                          build_audit_report)
from moonface.models.engine.config import EngineConfig, engine_hash

from tests.helpers_audit import _walk_series

import pytest

pytestmark = pytest.mark.slow


def _fit(cur_lo, fit_lo_a, fit_lo_b):
    def oos(lo):
        return {"oos": {"pooled": {"n": 1000, "spearman_rho": lo + 0.02,
                                   "rho_ci_95": [lo, lo + 0.05],
                                   "status": "ok"}}}
    return {"status": "ok",
            "fitters": {"nnls_net_r": oos(fit_lo_a),
                        "logistic_win": oos(fit_lo_b)},
            "current": oos(cur_lo)}


def test_verdict_precedence():
    assert book_verdict({"status": "UNDERPOWERED"}) == "UNDERPOWERED"
    assert book_verdict(_fit(-0.1, -0.1, -0.1)) == "NO_SIGNAL_IN_ANY_WEIGHTING"
    assert book_verdict(_fit(0.01, 0.05, -0.1)) == "CURRENT_WEIGHTS_ADEQUATE"
    assert book_verdict(_fit(0.01, -0.1, -0.1)) == "CURRENT_WEIGHTS_ADEQUATE"
    assert book_verdict(_fit(-0.1, 0.01, -0.1)) == "WEIGHTS_MISCALIBRATED"


def test_build_audit_report_shape_on_synthetic_series():
    cfg = EngineConfig(lookback_bars=400)
    candles = _walk_series(700)
    report = build_audit_report(cfg, candles, warmup=380)
    assert report["engine_hash"] == engine_hash(cfg)
    assert report["label"] == AUDIT_LABEL
    assert report["stage"] == 1
    assert report["deriv"] is None
    assert set(report["books"]) == {"trend", "mean_revert"}
    trend = report["books"]["trend"]
    for key in ("panel_counts", "baseline", "loo", "conditional",
                "fitted_upper_bound", "verdict"):
        assert key in trend
    assert len(trend["loo"]) == 6
    assert report["data"]["scored_bars"] == 700 - 380
    assert trend["verdict"] == "UNDERPOWERED"
    json.dumps(report)


def test_build_audit_report_records_stage_and_deriv_metadata():
    cfg = EngineConfig(lookback_bars=400)
    candles = _walk_series(700)
    deriv_meta = {"funding_coverage": 1.0, "coverage_floor": 0.9}
    report = build_audit_report(cfg, candles, warmup=380,
                                stage=2, deriv_meta=deriv_meta)
    assert report["stage"] == 2
    assert report["deriv"] == deriv_meta
