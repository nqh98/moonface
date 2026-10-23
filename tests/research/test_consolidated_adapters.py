from moonface.research.consolidated import adapters as A
from moonface.research.consolidated.result import AdapterResult

import pytest

pytestmark = pytest.mark.slow


def test_register_and_contract():
    @A.register("fake")
    def _fake(ctx):
        return [AdapterResult(key="fake:x", lane="fake", unit="r_trade",
                              config={}, config_source="frozen_family",
                              exit_name="atr_trail", current_signal="FLAT",
                              records=[])]

    assert "fake" in A.ADAPTERS
    out = A.ADAPTERS["fake"](object())
    assert isinstance(out, list) and out[0].unit == "r_trade"
    assert out[0].current_signal in {"LONG", "SHORT", "FLAT"}
    del A.ADAPTERS["fake"]


def test_btc_classic_adapter_rows():
    from tests.helpers_consolidated import fake_ctx
    rows = A.ADAPTERS["btc_classic"](fake_ctx())
    keys = {r.key for r in rows}
    assert keys == {f"btc_classic:{k}" for k in
                    ("trend","breakout","momentum","channel","meanrev","funding_fade")}
    for r in rows:
        assert r.unit == "r_trade" and r.records is not None


def test_breadth_internal_adapter_keys():
    from tests.helpers_consolidated import fake_breadth_ctx
    rows = A.ADAPTERS["breadth_internal"](fake_breadth_ctx())
    assert {r.key.split(":")[1] for r in rows} == {
        "breadth_thrust", "net_new_highs", "breadth_divergence", "dispersion_regime"}
    for r in rows:
        assert r.unit == "r_trade"
        assert r.config_source == "frozen_family"


def test_donchian_adapter_row():
    from tests.helpers_consolidated import fake_ctx
    rows = A.ADAPTERS["donchian"](fake_ctx())
    assert len(rows) == 1
    r = rows[0]
    assert r.unit == "r_trade"
    assert r.r_stream is not None
    assert r.key == "donchian:deploy_base"
    assert r.config_source == "deployed"


def test_regime_adapters():
    from tests.helpers_consolidated import fake_ctx
    for lane in ("regime_overlay", "regime_selector"):
        rows = A.ADAPTERS[lane](fake_ctx())
        assert len(rows) == 1, f"{lane} should return 1 row"
        r = rows[0]
        assert r.unit == "r_trade"
        assert r.r_stream is not None
        assert r.config_source == "top_explore"
        assert r.current_signal in {"LONG", "SHORT", "FLAT"}


def test_practical_btcspec_adapters():
    from tests.helpers_consolidated import fake_ctx
    for lane in ("practical", "btcspec"):
        rows = A.ADAPTERS[lane](fake_ctx())
        assert len(rows) == 1, f"{lane} should return 1 row"
        r = rows[0]
        assert r.unit == "r_trade"
        assert r.r_stream is not None
        assert r.config_source == "top_explore"


def test_ls_tournament_adapter():
    from tests.helpers_consolidated import fake_ctx
    rows = A.ADAPTERS["ls_tournament"](fake_ctx())
    assert len(rows) == 1
    r = rows[0]
    assert r.unit == "r_trade"
    assert r.records is not None
    assert r.config_source == "top_explore"


def test_playbook_adapter():
    from tests.helpers_consolidated import fake_playbook_ctx
    rows = A.ADAPTERS["playbook"](fake_playbook_ctx())
    assert len(rows) == 1, "playbook adapter should return 1 row"
    r = rows[0]
    assert r.unit == "r_trade"
    assert r.r_stream is not None
    assert r.config_source == "top_explore"
    assert r.current_signal in {"LONG", "FLAT"}
    assert r.key.startswith("playbook:")
    assert r.exit_name in {"atr_trail", "chandelier", "donchian_trail"}


def test_engine_adapter():
    from tests.helpers_consolidated import fake_playbook_ctx
    rows = A.ADAPTERS["engine"](fake_playbook_ctx(n_days=25))
    assert len(rows) == 1, "engine adapter should return 1 row"
    r = rows[0]
    assert r.unit == "r_trade"
    assert r.key == "engine:confluence"
    assert r.config_source == "deployed"
    assert r.r_stream is not None
    assert r.current_signal in {"LONG", "SHORT", "FLAT"}


def test_excluded_contains_portfolio():
    from moonface.research.consolidated.adapters import EXCLUDED
    lanes = {e["lane"] for e in EXCLUDED}
    assert "portfolio" in lanes
    for e in EXCLUDED:
        assert e["reason"]
