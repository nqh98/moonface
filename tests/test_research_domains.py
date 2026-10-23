# tests/test_research_domains.py
import os
import tempfile
import unittest

from moonface.research.domains import (FUNDING_FADE_TRANSFER_ASSETS,
                                       FUNDING_FADE_TRANSFER_ENTRY,
                                       FUNDING_FADE_TRANSFER_EXITS,
                                       funding_fade_transfer_grid,
                                       RETIRED_SUBDOMAINS, multi_asset_grid,
                                       register_v1,
                                       relaxed_budget_grid,
                                       relaxed_budget_v2_grid)
from moonface.kernel.spec import spec_hash
from moonface.kernel.store import Store

NOW_MS = 1_780_000_000_000


class TestGrids(unittest.TestCase):
    def test_relaxed_budget_grid_size(self):
        # (4 fade + 1 flip + 4 basis) entries x 10 exit specs x 3 fractions
        self.assertEqual(len(relaxed_budget_grid()), 270)

    def test_multi_asset_grid_size(self):
        # 19 price-entry param specs x 10 exit specs x 1 fraction x 2 assets
        self.assertEqual(len(multi_asset_grid()), 380)

    def test_grids_are_deterministic(self):
        a = [spec_hash(s) for s in relaxed_budget_grid()]
        b = [spec_hash(s) for s in relaxed_budget_grid()]
        self.assertEqual(a, b)

    def test_no_duplicate_hypotheses(self):
        hashes = [spec_hash(s) for s in (
            relaxed_budget_grid() + relaxed_budget_v2_grid() + multi_asset_grid()
            + funding_fade_transfer_grid()
        )]
        self.assertEqual(len(hashes), len(set(hashes)))

    def test_relaxed_grid_carries_positioning_data_needs(self):
        for s in relaxed_budget_grid():
            self.assertIn("funding_symbol", s.asset)
            self.assertIn("spot_symbol", s.asset)

    def test_relaxed_budget_v2_grid_size(self):
        # 2 BTC entries x 3 selected exits x 1 sizing fraction
        self.assertEqual(len(relaxed_budget_v2_grid()), 6)

    def test_relaxed_budget_v2_grid_is_deterministic(self):
        a = [spec_hash(s) for s in relaxed_budget_v2_grid()]
        b = [spec_hash(s) for s in relaxed_budget_v2_grid()]
        self.assertEqual(a, b)

    def test_relaxed_budget_v2_specs_are_btc_version_2(self):
        specs = relaxed_budget_v2_grid()
        self.assertEqual({s.domain for s in specs}, {"relaxed_budget_btc"})
        self.assertEqual({s.version for s in specs}, {2})
        self.assertEqual({s.asset["symbol"] for s in specs}, {"BTC/USDT:USDT"})
        self.assertEqual({s.fraction for s in specs}, {0.01})

    def test_relaxed_budget_v2_uses_only_confirmatory_families(self):
        entries = {(s.entry["family"],
                    tuple(sorted(s.entry["params"].items())))
                   for s in relaxed_budget_v2_grid()}
        self.assertEqual(entries, {
            ("basis_discount_reversion", (("pct", 5), ("window", 180))),
            ("funding_fade", (("window", 180), ("z_thr", 2.0))),
        })

    def test_relaxed_budget_v2_uses_only_selected_exits(self):
        exits = {(s.exit["name"],
                  tuple(sorted(s.exit["params"].items())))
                 for s in relaxed_budget_v2_grid()}
        self.assertEqual(exits, {
            ("fixed_bracket", (("atr_period", 14), ("k_stop", 1.0),
                               ("m_tp", 4.0))),
            ("fixed_bracket", (("atr_period", 14), ("k_stop", 2.0),
                               ("m_tp", 4.0))),
            ("atr_trail", (("atr_period", 14), ("k_trail", 3.0),
                           ("max_bars", 48))),
        })

    def test_relaxed_budget_v2_grid_carries_positioning_data_needs(self):
        for s in relaxed_budget_v2_grid():
            self.assertIn("funding_symbol", s.asset)
            self.assertIn("spot_symbol", s.asset)


class TestRegisterV1(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(os.path.join(self.tmp.name, "r.db"))

    def test_registers_existing_domains_and_btc_v2(self):
        register_v1(self.store, NOW_MS)
        pairs = [(d["name"], d["version"]) for d in self.store.domains_in_order()]
        self.assertEqual(pairs, [
            ("relaxed_budget_btc", 1),
            ("multi_asset_transfer", 1),
            ("relaxed_budget_btc", 2),
            ("new_families.lead_lag", 1),
            ("positioning_btc", 1),
            ("positioning_transfer", 1),
            ("funding_fade_transfer", 1),
            *[(name, 1) for name in RETIRED_SUBDOMAINS],
        ])

    def test_registers_funding_fade_transfer_with_four_pending_rows(self):
        register_v1(self.store, NOW_MS)
        d = self.store.domain("funding_fade_transfer", 1)
        self.assertIsNotNone(d)
        self.assertEqual(d["status"], "active")
        self.assertEqual(d["grid_size"], 4)
        self.assertEqual(self.store.counts("funding_fade_transfer", 1),
                         {"pending": 4})

    def test_idempotent(self):
        register_v1(self.store, NOW_MS)
        self.assertEqual(register_v1(self.store, NOW_MS), [])
        self.assertEqual(len(self.store.domains_in_order()), 9)  # 7 active + 2 shelved

    def test_registers_btc_v2_with_six_pending_rows(self):
        register_v1(self.store, NOW_MS)
        d = self.store.domain("relaxed_budget_btc", 2)
        self.assertIsNotNone(d)
        self.assertEqual(d["status"], "active")
        self.assertEqual(d["grid_size"], 6)
        self.assertEqual(self.store.counts("relaxed_budget_btc", 2), {"pending": 6})

    def test_registering_btc_v2_does_not_mutate_v1(self):
        register_v1(self.store, NOW_MS)
        v1_before = self.store.domain("relaxed_budget_btc", 1)
        rows_before = len(self.store.rows("relaxed_budget_btc", 1))
        self.assertEqual(register_v1(self.store, NOW_MS), [])
        v1_after = self.store.domain("relaxed_budget_btc", 1)
        rows_after = len(self.store.rows("relaxed_budget_btc", 1))
        self.assertEqual(v1_after, v1_before)
        self.assertEqual(rows_after, rows_before)

    def test_blocked_subdomains_have_no_grid(self):
        register_v1(self.store, NOW_MS)
        for name in RETIRED_SUBDOMAINS:
            d = self.store.domain(name, 1)
            self.assertEqual(d["status"], "shelved")
            self.assertEqual(d["grid_size"], 0)

    def test_fence_is_final_20_percent_of_window(self):
        register_v1(self.store, NOW_MS)
        d = self.store.domain("relaxed_budget_btc", 1)
        window = d["end_ms"] - d["start_ms"]
        self.assertAlmostEqual((d["end_ms"] - d["fence_ts"]) / window, 0.2, places=3)

    def test_register_v1_fresh_store_activates_lead_lag(self):
        register_v1(self.store, NOW_MS)
        d = self.store.domain("new_families.lead_lag", 1)
        self.assertEqual(d["status"], "active")
        self.assertEqual(d["grid_size"], 6)
        for name in ("new_families.vol_regime", "new_families.seasonality"):
            self.assertEqual(self.store.domain(name, 1)["status"], "shelved")


def test_lead_lag_grid_is_exactly_six_and_deterministic():
    from moonface.research.domains import lead_lag_grid
    g1, g2 = lead_lag_grid(), lead_lag_grid()
    assert len(g1) == 6
    assert [s.entry for s in g1] == [s.entry for s in g2]
    assert all(s.domain == "new_families.lead_lag" and s.version == 1 for s in g1)
    assert all(s.asset["feature_symbol"] == "ETH/USDT:USDT" for s in g1)
    assert all(s.entry["family"] == "eth_lead_momentum" for s in g1)
    assert all(s.fraction == 0.01 for s in g1)
    lookbacks = {s.entry["params"]["lookback"] for s in g1}
    assert lookbacks == {12, 24}


def test_register_v1_fresh_store_activates_lead_lag(tmp_path):
    from moonface.research.domains import register_v1
    from moonface.kernel.store import Store
    store = Store(str(tmp_path / "r.db"))
    register_v1(store, now_ms=1_750_000_000_000)
    d = store.domain("new_families.lead_lag", 1)
    assert d["status"] == "active" and d["grid_size"] == 6
    for name in ("new_families.vol_regime", "new_families.seasonality"):
        assert store.domain(name, 1)["status"] == "shelved"


def test_reconcile_lifts_existing_blocked_placeholder(tmp_path):
    from moonface.research.domains import (lead_lag_grid,
                                           reconcile_new_families)
    from moonface.kernel.store import Store
    store = Store(str(tmp_path / "r.db"))
    now = 1_750_000_000_000
    for name in ("new_families.vol_regime", "new_families.lead_lag",
                 "new_families.seasonality"):
        store.register_domain(name, 1, "blocked", {"assets": []},
                              now - 1000, now, now - 200)
    changed = reconcile_new_families(store)
    assert set(changed) == {"new_families.lead_lag", "new_families.vol_regime",
                            "new_families.seasonality"}
    d = store.domain("new_families.lead_lag", 1)
    assert d["status"] == "active" and d["grid_size"] == len(lead_lag_grid())
    # frozen window untouched
    assert d["start_ms"] == now - 1000 and d["fence_ts"] == now - 200
    assert store.domain("new_families.vol_regime", 1)["status"] == "shelved"
    # idempotent
    assert reconcile_new_families(store) == []


def test_positioning_grid_is_80_deterministic_and_field_consistent(tmp_path):
    from moonface.research.domains import positioning_grid
    g1, g2 = positioning_grid(), positioning_grid()
    assert len(g1) == 80  # 8 frozen entries x 10 exits x 1 fraction
    assert [spec_hash(s) for s in g1] == [spec_hash(s) for s in g2]
    assert all(s.domain == "positioning_btc" and s.version == 1 for s in g1)
    assert all(s.fraction == 0.01 for s in g1)
    field_by_family = {
        "oi_flush_reversal": "sum_open_interest",
        "oi_build_momentum": "sum_open_interest",
        "toptrader_follow": "sum_toptrader_long_short_ratio",
        "taker_flow_momentum": "sum_taker_long_short_vol_ratio",
    }
    for s in g1:
        assert s.asset["symbol"] == "BTC/USDT:USDT"
        assert s.asset["metrics_field"] == field_by_family[s.entry["family"]]


def test_register_v1_includes_positioning_domain(tmp_path):
    from moonface.research.domains import register_v1
    store = Store(str(tmp_path / "r.db"))
    register_v1(store, now_ms=1_750_000_000_000)
    d = store.domain("positioning_btc", 1)
    assert d is not None
    assert d["status"] == "active" and d["grid_size"] == 80


def test_positioning_transfer_grid_is_40_oi_build_only():
    from moonface.research.domains import positioning_transfer_grid
    g1, g2 = positioning_transfer_grid(), positioning_transfer_grid()
    assert len(g1) == 40  # 2 assets x 2 frozen oi_build entries x 10 exits
    assert [spec_hash(s) for s in g1] == [spec_hash(s) for s in g2]
    assert all(s.domain == "positioning_transfer" and s.version == 1 for s in g1)
    assert all(s.entry["family"] == "oi_build_momentum" for s in g1)
    assert all(s.asset["metrics_field"] == "sum_open_interest" for s in g1)
    assert {s.asset["symbol"] for s in g1} == {"ETH/USDT:USDT", "SOL/USDT:USDT"}
    assert all(s.asset["timeframe"] == "4h" for s in g1)
    assert all(s.fraction == 0.01 for s in g1)
    assert {tuple(sorted(s.entry["params"].items())) for s in g1} == {
        (("lookback", 6), ("window", 180), ("z_thr", 1.5)),
        (("lookback", 24), ("window", 180), ("z_thr", 1.5)),
    }


def test_register_v1_includes_positioning_transfer(tmp_path):
    from moonface.research.domains import register_v1
    store = Store(str(tmp_path / "r.db"))
    register_v1(store, now_ms=1_750_000_000_000)
    d = store.domain("positioning_transfer", 1)
    assert d is not None
    assert d["status"] == "active" and d["grid_size"] == 40


def _reregister_fixture(tmp_path, status="closed_negative"):
    """A v1 domain with a 2-spec frozen grid in the given terminal status."""
    import json

    from moonface.kernel.spec import HypothesisSpec

    store = Store(str(tmp_path / "r.db"))
    now = 1_750_000_000_000
    specs = [HypothesisSpec(
        domain="dom_x", version=1,
        asset={"exchange": "binance", "symbol": "ETH/USDT:USDT",
               "timeframe": "4h"},
        entry={"family": "donchian_break", "params": {"n": n}},
        exit={"name": "fixed_bracket",
              "params": {"atr_period": 14, "k_stop": 1.0, "m_tp": 4.0}},
        fraction=0.01) for n in (20, 55)]
    store.register_domain("dom_x", 1, "active",
                          {"assets": [json.loads('{"symbol": "ETH/USDT:USDT"}')]},
                          now - 9000, now, now - 3000)
    store.insert_grid("dom_x", 1, specs)
    store.set_domain_status("dom_x", 1, status)
    return store, specs


def test_reregister_creates_next_version_with_frozen_grid(tmp_path):
    import json

    from moonface.research.domains import reregister_domain
    store, specs = _reregister_fixture(tmp_path)
    new_version = reregister_domain(store, "dom_x", 1)
    assert new_version == 2
    v1, v2 = store.domain("dom_x", 1), store.domain("dom_x", 2)
    assert v2["status"] == "active" and v2["grid_size"] == 2
    # frozen window, fence, and config carried over verbatim
    for key in ("start_ms", "end_ms", "fence_ts", "config"):
        assert v2[key] == v1[key]
    # v1 stays exactly as it was
    assert v1["status"] == "closed_negative"
    assert {r["status"] for r in store.rows("dom_x", 1)} == {"pending"}
    # v2 rows are the same hypotheses, re-versioned and pending
    v2_rows = store.rows("dom_x", 2)
    assert all(r["status"] == "pending" for r in v2_rows)
    v2_entries = [json.loads(r["spec_json"])["entry"] for r in v2_rows]
    assert v2_entries == [s.entry for s in specs]
    assert all(json.loads(r["spec_json"])["version"] == 2 for r in v2_rows)


def test_reregister_refuses_contaminated_lockbox_tail(tmp_path):
    import pytest

    from moonface.research.domains import reregister_domain
    store, specs = _reregister_fixture(tmp_path)
    h = spec_hash(specs[0])
    for step in ("screened", "oos_pass", "corrected_survivor", "lockbox_fail"):
        store.advance(h, step, {})
    with pytest.raises(ValueError, match="lockbox"):
        reregister_domain(store, "dom_x", 1)


def test_reregister_refuses_unclosed_source(tmp_path):
    import pytest

    from moonface.research.domains import reregister_domain
    store, _ = _reregister_fixture(tmp_path, status="awaiting_gate")
    with pytest.raises(ValueError, match="closed"):
        reregister_domain(store, "dom_x", 1)


def test_reregister_refuses_when_later_version_exists(tmp_path):
    import pytest

    from moonface.research.domains import reregister_domain
    store, _ = _reregister_fixture(tmp_path)
    assert reregister_domain(store, "dom_x", 1) == 2
    with pytest.raises(ValueError, match="version"):
        reregister_domain(store, "dom_x", 1)


class TestFundingFadeTransferConstants(unittest.TestCase):
    def test_assets_are_eth_and_sol_with_own_funding(self):
        symbols = {a["symbol"] for a in FUNDING_FADE_TRANSFER_ASSETS}
        self.assertEqual(symbols, {"ETH/USDT:USDT", "SOL/USDT:USDT"})
        # no BTC: the contaminated asset never enters the gated/lockbox path
        self.assertNotIn("BTC/USDT:USDT", symbols)
        for a in FUNDING_FADE_TRANSFER_ASSETS:
            # funding_fade needs each asset's OWN perp funding series
            self.assertEqual(a["funding_symbol"], a["symbol"])
            self.assertEqual(a["timeframe"], "4h")

    def test_entry_is_the_single_frozen_winner(self):
        fam, params = FUNDING_FADE_TRANSFER_ENTRY
        self.assertEqual(fam, "funding_fade")
        self.assertEqual(params, {"window": 60, "z_thr": 1.5})

    def test_exits_are_the_two_bounded_survivors(self):
        self.assertEqual(FUNDING_FADE_TRANSFER_EXITS, [
            ("fixed_bracket", {"atr_period": 14, "k_stop": 2.0, "m_tp": 4.0}),
            ("atr_trail", {"atr_period": 14, "k_trail": 3.0, "max_bars": 48}),
        ])


class TestFundingFadeTransferGrid(unittest.TestCase):
    def test_grid_size(self):
        # 2 assets x 1 entry x 2 exits x 1 fraction
        self.assertEqual(len(funding_fade_transfer_grid()), 4)

    def test_specs_are_domain_v1_fraction_001(self):
        specs = funding_fade_transfer_grid()
        self.assertEqual({s.domain for s in specs}, {"funding_fade_transfer"})
        self.assertEqual({s.version for s in specs}, {1})
        self.assertEqual({s.fraction for s in specs}, {0.01})

    def test_every_spec_uses_the_frozen_entry(self):
        for s in funding_fade_transfer_grid():
            self.assertEqual(s.entry,
                             {"family": "funding_fade",
                              "params": {"window": 60, "z_thr": 1.5}})

    def test_every_spec_carries_own_funding_symbol(self):
        for s in funding_fade_transfer_grid():
            self.assertEqual(s.asset["funding_symbol"], s.asset["symbol"])

    def test_grid_is_deterministic_and_unique(self):
        a = [spec_hash(s) for s in funding_fade_transfer_grid()]
        b = [spec_hash(s) for s in funding_fade_transfer_grid()]
        self.assertEqual(a, b)
        self.assertEqual(len(a), len(set(a)))


if __name__ == "__main__":
    unittest.main()
