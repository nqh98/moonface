# tests/test_universe_donchian_runner.py
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from moonface.core.models import Candle
from moonface.kernel.store import Store
from moonface.research.universe_data import DailyRow
from moonface.research import universe_donchian_runner as r


def _candles(start_ms, n, drift):
    """n 4h candles, close drifting by `drift` per bar (alt) or 0 (control)."""
    out = []
    ts = start_ms
    for i in range(n):
        out.append(Candle(ts, 100, 100, 100, 100 * (1 + drift) ** i, 1.0))
        ts += 4 * 3_600_000
    return out


class TestRunner(unittest.TestCase):
    def test_register_freezes_window_fence_and_grid(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            now = 1_609_459_200_000 + 400 * 86_400_000
            r.register(store, now)
            d = store.domain(r.UNIVERSE_DONCHIAN_DOMAIN, 1)
            self.assertEqual(d["status"], "active")
            self.assertEqual(d["config"], {"runner": "universe_donchian"})
            self.assertEqual(d["start_ms"], r.UNIVERSE_DONCHIAN_START_MS)
            self.assertEqual(len(store.rows(r.UNIVERSE_DONCHIAN_DOMAIN, 1)), 4)
            # fence = now - 0.2*(now - start)
            self.assertEqual(d["fence_ts"],
                             now - int((now - r.UNIVERSE_DONCHIAN_START_MS) * 0.2))
            r.register(store, now)   # idempotent
            self.assertEqual(len(store.rows(r.UNIVERSE_DONCHIAN_DOMAIN, 1)), 4)

    def test_register_is_idempotent_and_does_not_mutate_grid(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            now = 1_609_459_200_000 + 400 * 86_400_000
            r.register(store, now)
            original = store.domain(r.UNIVERSE_DONCHIAN_DOMAIN, 1)
            r.register(store, now + 100 * 86_400_000)
            self.assertEqual(store.domain(r.UNIVERSE_DONCHIAN_DOMAIN, 1)["end_ms"],
                             original["end_ms"])
            self.assertEqual(store.domain(r.UNIVERSE_DONCHIAN_DOMAIN, 1)["fence_ts"],
                             original["fence_ts"])
            self.assertEqual(len(store.rows(r.UNIVERSE_DONCHIAN_DOMAIN, 1)), 4)
            with self.assertRaises(Exception):
                # second insert_grid path is guarded by the domain-absent check;
                # re-calling register is a no-op, but a direct re-insert raises.
                from moonface.research.universe_donchian import universe_donchian_specs
                store.insert_grid(r.UNIVERSE_DONCHIAN_DOMAIN, 1, universe_donchian_specs())

    def test_run_domain_writes_verdict_and_sets_status(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            start = r.UNIVERSE_DONCHIAN_START_MS
            now = start + 500 * 86_400_000
            r.register(store, now)

            # Fakes: one alt (trending) + BTC (flat). Enough days + 4h bars.
            sym = "ALTSUSDT"
            days = 500
            daily = {sym: [DailyRow(start + i * 86_400_000, 100.0, 30e6)
                           for i in range(days)]}
            candles = {sym: _candles(start, days * 6, drift=0.0)}
            funding = {sym: []}

            with mock.patch.object(r, "list_um_perp_symbols", return_value=[sym]), \
                 mock.patch.object(r, "fetch_daily_klines",
                                   side_effect=lambda s, a, b, c: daily.get(s, [])), \
                 mock.patch.object(r, "fetch_perp_candles",
                                   side_effect=lambda s, iv, a, b, c: candles.get(s, [])), \
                 mock.patch.object(r, "fetch_funding_rates",
                                   side_effect=lambda s, a, b, c: funding.get(s, [])):
                verdict = r.run_domain(store, cache_dir=td,
                                       out_root=Path(td))
            self.assertIn(verdict, ("closed_positive", "closed_negative"))
            self.assertEqual(store.domain(r.UNIVERSE_DONCHIAN_DOMAIN, 1)["status"],
                             "closed_" + verdict.split("_")[1])
            vpath = Path(td) / "universe_donchian" / "verdict.md"
            self.assertTrue(vpath.exists())
            self.assertIn("Status:", vpath.read_text())

    def test_candidate_prefilter_includes_non_default_lookback_specs(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            start = r.UNIVERSE_DONCHIAN_START_MS
            now = start + 140 * 86_400_000
            r.register(store, now)

            sym = "SIXTYUSDT"
            rows = []
            for day in range(140):
                qv = 40e6 if 31 <= day <= 60 else 1e6
                rows.append(DailyRow(start + day * 86_400_000, 100.0, qv))

            seen_symbol_batches = []

            def fake_load(symbols, *_args):
                seen_symbol_batches.append(list(symbols))
                return {}, {}

            with mock.patch.object(r, "list_um_perp_symbols", return_value=[sym]), \
                 mock.patch.object(r, "fetch_daily_klines",
                                   side_effect=lambda s, a, b, c:
                                   rows if s == sym else []), \
                 mock.patch.object(r, "fetch_funding_rates", return_value=[]), \
                 mock.patch.object(r, "_load_engine_trades",
                                   side_effect=fake_load):
                r.run_domain(store, cache_dir=td, out_root=Path(td))

            self.assertIn(sym, seen_symbol_batches[0])

    def test_btc_reference_portfolio_receives_daily_funding(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            start = r.UNIVERSE_DONCHIAN_START_MS
            now = start + 500 * 86_400_000
            r.register(store, now)

            sym = "ALTSUSDT"
            days = 500
            daily = {sym: [DailyRow(start + i * 86_400_000, 100.0, 30e6)
                           for i in range(days)],
                     "BTCUSDT": [DailyRow(start + i * 86_400_000, 100.0, 30e6)
                                 for i in range(days)]}
            btc_positions = {"BTCUSDT": []}
            btc_closes = {"BTCUSDT": {start: 100.0}}
            funding = {"BTCUSDT": [(start, 0.001)]}
            funding_args = []

            def fake_load(symbols, *_args):
                if symbols == ["BTCUSDT"]:
                    return btc_positions, btc_closes
                return {}, {}

            def fake_sim(calendar, membership, book, positions, closes,
                         daily_funding, **_kwargs):
                if positions is btc_positions:
                    funding_args.append(daily_funding)
                return [0.0] * len(calendar)

            with mock.patch.object(r, "list_um_perp_symbols", return_value=[sym]), \
                 mock.patch.object(r, "fetch_daily_klines",
                                   side_effect=lambda s, a, b, c: daily.get(s, [])), \
                 mock.patch.object(r, "fetch_funding_rates",
                                   side_effect=lambda s, a, b, c: funding.get(s, [])), \
                 mock.patch.object(r, "_load_engine_trades",
                                   side_effect=fake_load), \
                 mock.patch.object(r, "simulate_portfolio",
                                   side_effect=fake_sim):
                r.run_domain(store, cache_dir=td, out_root=Path(td))

            self.assertEqual(funding_args, [{"BTCUSDT": {start: 0.001}}])

    def test_all_pass_spends_lockbox_once_and_promotes(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            start = r.UNIVERSE_DONCHIAN_START_MS
            now = start + 500 * 86_400_000
            r.register(store, now)

            sym = "ALTSUSDT"
            days = 500
            daily = {sym: [DailyRow(start + i * 86_400_000, 100.0, 30e6)
                           for i in range(days)],
                     "BTCUSDT": [DailyRow(start + i * 86_400_000, 100.0, 30e6)
                                 for i in range(days)]}
            m = {"screen_trades": 100, "screen_expectancy_r": 0.5,
                 "holdout_treatment_mar": 2.0, "holdout_treatment_dd": -0.1,
                 "holdout_treatment_sharpe": 1.0, "holdout_control_mar": 0.1,
                 "holdout_control_sharpe": 0.1, "holdout_dominance": True,
                 "research_sharpe": 2.0, "research_skew": 0.0,
                 "research_kurtosis": 3.0, "research_trades": 300}
            tail = {"tail_trades": 20, "tail_treatment_mar": 2.0,
                    "tail_treatment_dd": -0.1, "tail_treatment_sharpe": 1.0,
                    "tail_control_mar": 0.1, "tail_control_sharpe": 0.1,
                    "tail_dominance": True}
            original_touch = store.touch_lockbox

            with mock.patch.object(store, "touch_lockbox",
                                   side_effect=original_touch) as touch, \
                 mock.patch.object(r, "list_um_perp_symbols", return_value=[sym]), \
                 mock.patch.object(r, "fetch_daily_klines",
                                   side_effect=lambda s, a, b, c: daily.get(s, [])), \
                 mock.patch.object(r, "fetch_funding_rates", return_value=[]), \
                 mock.patch.object(r, "_load_engine_trades", return_value=({}, {})), \
                 mock.patch.object(r, "simulate_portfolio",
                                   side_effect=lambda cal, *_a, **_kw:
                                   [0.001 if i % 2 == 0 else 0.002
                                    for i, _ in enumerate(cal)]), \
                 mock.patch.object(r, "_screen_pooled_trades",
                                   return_value=[0.5] * 100) as pooled, \
                 mock.patch.object(r, "evaluate_dominant", return_value=m), \
                 mock.patch.object(r, "walk_forward",
                                   return_value={"folds": 1,
                                                 "aggregate_treatment_mar": 2.0,
                                                 "dominance": True}), \
                 mock.patch.object(r, "stage35_of", return_value=True), \
                 mock.patch.object(r, "deflated_sharpe", return_value=0.99), \
                 mock.patch.object(r, "lockbox_dominant", return_value=tail):
                verdict = r.run_domain(store, cache_dir=td, out_root=Path(td))

            d = store.domain(r.UNIVERSE_DONCHIAN_DOMAIN, 1)
            self.assertEqual(verdict, "closed_positive")
            self.assertEqual(d["status"], "closed_positive")
            self.assertTrue(d["lockbox_touched"])
            touch.assert_called_once_with(r.UNIVERSE_DONCHIAN_DOMAIN, 1)
            self.assertTrue(any(call.kwargs.get("tail_only") is True
                                for call in pooled.call_args_list))
            text = (Path(td) / "universe_donchian" / "verdict.md").read_text()
            self.assertIn("lockbox_pass", text)


if __name__ == "__main__":
    unittest.main()
