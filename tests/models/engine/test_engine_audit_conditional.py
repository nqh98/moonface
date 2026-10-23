"""Per-module conditional ordering vs trade net R (spec §5.3) — unlike the
calibration IC table, which used fixed-horizon drift and stays SECONDARY."""
from moonface.models.engine.audit import conditional_ordering

from tests.helpers_audit import _fixture

import pytest

pytestmark = pytest.mark.slow


def test_conditional_ordering_informative_vs_noise():
    panel, rows_by_index = _fixture()
    table = conditional_ordering(panel, rows_by_index, "trend")
    m2 = table["m2_breakout"]["pooled"]
    assert m2["status"] == "ok"
    assert m2["rho_ci_95"][0] > 0
    m4 = table["m4_pullback"]["pooled"]
    assert m4["rho_ci_95"][0] < 0 < m4["rho_ci_95"][1]
    assert table["m1_macro"]["pooled"]["spearman_rho"] is None


def test_conditional_ordering_reports_all_splits():
    panel, rows_by_index = _fixture()
    table = conditional_ordering(panel, rows_by_index, "trend")
    assert set(table["m2_breakout"]) == {"pooled", "LONG", "SHORT"}
    assert table["m2_breakout"]["SHORT"]["n"] == 0
    assert table["m2_breakout"]["SHORT"]["status"] == "UNDERPOWERED"
