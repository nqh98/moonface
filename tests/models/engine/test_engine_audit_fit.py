"""Fitted upper bound (spec §5.4): leakage-safe chrono split, pre-enumerated
stdlib fitters, OOS Spearman verdict metric. Known-ordering data must yield a
CI-clean positive OOS rho; pure noise must span 0 (fixed seeds, deterministic).
"""
import random

from moonface.models.engine.audit import (chrono_split, fit_logistic,
                                          fit_nnls, fitted_upper_bound)

from tests.helpers_audit import _fixture, _mk_row, _mk_trade

import pytest

pytestmark = pytest.mark.slow


def _rows_list(rows_by_index):
    return [rows_by_index[i] for i in sorted(rows_by_index)]


def test_chrono_split_leakage_rules():
    panel, rows_by_index = _fixture()
    rows = _rows_list(rows_by_index)
    train, test, boundary, dropped = chrono_split(panel, rows)
    assert all(t.exit_index < boundary for t in train)
    assert all(t.entry_index >= boundary + 168 for t in test)
    assert dropped == len(panel) - len(train) - len(test)
    assert dropped > 0
    assert len(train) and len(test)


def test_fit_nnls_recovers_informative_weight():
    rng = random.Random(3)
    X, y = [], []
    for _ in range(2000):
        a, b = rng.gauss(0, 1), rng.gauss(0, 1)
        X.append([a, b])
        y.append(2.0 * a + rng.gauss(0, 0.1))
    w = fit_nnls(X, y)
    assert w[0] > 1.5
    assert w[1] < 0.2
    assert all(v >= 0 for v in w)
    assert fit_nnls(X, y) == w


def test_fit_logistic_nonnegative_and_ordered():
    rng = random.Random(4)
    X, y01 = [], []
    for _ in range(2000):
        a, b = rng.gauss(0, 1), rng.gauss(0, 1)
        X.append([a, b])
        y01.append(1.0 if a + rng.gauss(0, 0.5) > 0 else 0.0)
    w, _bias = fit_logistic(X, y01)
    assert w[0] > 0.2
    assert all(v >= 0 for v in w)


def test_fitted_upper_bound_known_ordering():
    panel, rows_by_index = _fixture(n=2400)
    fit = fitted_upper_bound(panel, _rows_list(rows_by_index),
                             rows_by_index, "trend")
    assert fit["status"] == "ok"
    for name in ("nnls_net_r", "logistic_win"):
        oos = fit["fitters"][name]["oos"]["pooled"]
        assert oos["rho_ci_95"][0] > 0
    assert fit["current"]["oos"]["pooled"]["rho_ci_95"][0] > 0


def test_fitted_upper_bound_pure_noise_spans_zero():
    rng = random.Random(3)
    rows_by_index, panel = {}, []
    for k in range(2400):
        i = k * 35
        m2 = rng.choice((0, 20))
        rows_by_index[i] = _mk_row(i, {"m1_macro": 20, "m2_breakout": m2})
        panel.append(_mk_trade(i, 20 + m2, round(rng.gauss(0, 1), 4)))
    fit = fitted_upper_bound(panel, _rows_list(rows_by_index),
                             rows_by_index, "trend")
    assert fit["status"] == "ok"
    for name in ("nnls_net_r", "logistic_win"):
        lo, hi = fit["fitters"][name]["oos"]["pooled"]["rho_ci_95"]
        assert lo <= 0 <= hi


def test_fitted_upper_bound_underpowered():
    panel, rows_by_index = _fixture(n=300)
    fit = fitted_upper_bound(panel, _rows_list(rows_by_index),
                             rows_by_index, "trend")
    assert fit["status"] == "UNDERPOWERED"
    assert "fitters" not in fit
