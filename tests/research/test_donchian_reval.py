import unittest

from moonface.core.models import Candle
from moonface.research.donchian_reval import (
    aggregate_econ_pass, cost_stress,
    gross_h12_probe, exit_ablation, ea_pass,
    local_param_plateau, ps_pass, param_diagnostic_grid, trade_distribution,
    regime_breakdown, revalidation_verdict)
from moonface.research.trend_sim import TrendParams, TrendTrade


def _trend(nbars=400, up=0.008, dn=0.03, run=22, pull=3):
    """Rising channel: 22-bar up-runs (+0.8%/bar) broken by 3-bar pullbacks
    (-3%/bar). The trailing exit rides each up-run to a large win while the
    fixed-horizon (12-bar) exit repeatedly cuts at a loss — the exit-driven
    edge the ablation is meant to expose."""
    cs = []
    price = 100.0
    for k in range(nbars):
        price *= (1 + up) if (k % (run + pull)) < run else (1 - dn)
        cs.append(Candle(timestamp_ms=1_000_000 + k * 14_400_000,
                         open=round(price / 1.003, 4), high=round(price * 1.006, 4),
                         low=round(price * 0.99, 4), close=round(price, 4), volume=10.0))
    return cs


_BP = TrendParams(entry_n=40, trail_n=20, atr_period=14, k_stop=2.0, long_only=True,
                  fee_rate=0.00045, slippage=0.0005, funding_enabled=False)


class GrossProbe(unittest.TestCase):
    def test_probe_reports_z_and_n(self):
        out = gross_h12_probe(_trend(), n=40, h=12, atr_period=14)
        self.assertIn("z", out)
        self.assertIn("n", out)
        self.assertIsInstance(out["passed"], bool)


class ExitAblation(unittest.TestCase):
    def test_three_arms_present(self):
        ab = exit_ablation(_trend(), None, _BP)
        self.assertEqual(set(ab), {"net_fixed_horizon_exit", "stop_only", "trail"})
        for row in ab.values():
            self.assertIn("expectancy_r", row)
            self.assertIn("mar", row)

    def test_trail_dominates_fixed_horizon_on_trender(self):
        ab = exit_ablation(_trend(), None, _BP)
        self.assertGreater(ab["trail"]["expectancy_r"], ab["net_fixed_horizon_exit"]["expectancy_r"])
        self.assertTrue(ea_pass(ab))

    def test_ea_fails_when_no_exit_edge(self):
        # identical rows -> trail does not dominate -> EA fails
        flat = {"expectancy_r": 0.1, "profit_factor": 1.5, "mar": 1.0,
                "max_dd_r": -5.0, "total_r": 5.0, "n": 50}
        ab = {"trail": dict(flat), "net_fixed_horizon_exit": dict(flat),
              "stop_only": dict(flat)}
        self.assertFalse(ea_pass(ab))


class ParamPlateau(unittest.TestCase):
    def test_plateau_has_center_and_star_neighbors(self):
        pl = local_param_plateau(_trend(600), None, _BP)
        self.assertIn("center", pl)
        # one-axis star: (3-1)+(3-1)+(3-1)+(2-1) = 7 neighbours
        self.assertEqual(len(pl["neighbors"]), 7)

    def test_ps_pass_on_broad_plateau(self):
        good = {"expectancy_r": 0.2, "profit_factor": 1.5}
        pl = {"center": {"expectancy_r": 0.2},
              "neighbors": [{"label": f"n{i}", **good} for i in range(7)]}
        self.assertTrue(ps_pass(pl))

    def test_ps_fails_on_spike(self):
        pl = {"center": {"expectancy_r": 1.0},
              "neighbors": [{"label": f"n{i}", "expectancy_r": -0.1,
                             "profit_factor": 0.8} for i in range(7)]}
        self.assertFalse(ps_pass(pl))

    def test_diagnostic_grid_is_full_cartesian(self):
        grid = param_diagnostic_grid(_trend(600), None, _BP)
        self.assertEqual(len(grid), 3 * 3 * 3 * 2)  # entry_n x trail_n x k_stop x atr


class CostStress(unittest.TestCase):
    def test_three_tiers(self):
        cs = cost_stress(_trend(600), None, _BP)
        self.assertEqual(set(cs), {"base", "moderate", "severe"})
        self.assertIn("econ_pass", cs["base"])
        self.assertIn("alive", cs["moderate"])

    def test_severe_is_not_better_than_base(self):
        cs = cost_stress(_trend(600), None, _BP)
        self.assertLessEqual(cs["severe"]["expectancy_r"], cs["base"]["expectancy_r"])

    def test_aggregate_econ_pass_logic(self):
        good = {"profit_factor": 1.5, "expectancy_r": 0.2, "mar": 1.0, "max_dd_r": -5.0}
        # all four gates pass
        self.assertTrue(aggregate_econ_pass(dict(good)))
        # pf == inf passes (winners-only book has no losses)
        self.assertTrue(aggregate_econ_pass({**good, "profit_factor": float("inf")}))
        # each of the four gates can fail the verdict independently
        self.assertFalse(aggregate_econ_pass({**good, "profit_factor": 1.1}))   # pf < 1.2
        self.assertFalse(aggregate_econ_pass({**good, "expectancy_r": 0.04}))   # exp < 0.05
        self.assertFalse(aggregate_econ_pass({**good, "mar": 0.4}))             # mar < 0.5
        self.assertFalse(aggregate_econ_pass({**good, "max_dd_r": -31.0}))      # |max_dd| > 30 (also pins the abs())


def _tt(r):
    return TrendTrade(side="BUY", entry_index=0, entry=1.0, exit_index=1, exit=1.0,
                      r_multiple=r, mae_r=-0.5, hold_bars=3)


class TradeDist(unittest.TestCase):
    def test_extreme_flag_on_single_dominant_trade(self):
        d = trade_distribution([_tt(10.0)] + [_tt(-0.2) for _ in range(20)])
        self.assertTrue(d["td_extreme"])  # one trade > 50% of net R

    def test_no_extreme_flag_on_balanced_book(self):
        d = trade_distribution([_tt(1.0) for _ in range(10)] + [_tt(-0.5) for _ in range(10)])
        self.assertFalse(d["td_extreme"])
        self.assertEqual(d["n"], 20)


class Regime(unittest.TestCase):
    def test_labels_present_and_pointintime(self):
        cs = _trend(600)
        from moonface.research.trend_sim import simulate_donchian
        trades = simulate_donchian(cs, _BP, None)
        rb = regime_breakdown(cs, trades)
        self.assertIn("trend", rb)
        self.assertIn("vol", rb)
        self.assertIn("rg_flag", rb)
        self.assertIn(set(rb["trend"]), [{"bull", "bear", "warmup"}])

    def test_rg_flag_logic(self):
        from moonface.research.donchian_reval import _rg_flag
        self.assertTrue(_rg_flag(bull_positive=95.0, total_positive=100.0,
                                 nonbull_total_r=-20.0, nonbull_expectancy=-0.3))
        self.assertFalse(_rg_flag(bull_positive=60.0, total_positive=100.0,
                                  nonbull_total_r=10.0, nonbull_expectancy=0.1))


def _passing_inputs():
    good = {"expectancy_r": 0.4, "profit_factor": 1.7, "mar": 4.0,
            "max_dd_r": -8.0, "total_r": 40.0, "n": 60}
    wf = {"n_windows": 4, "aggregate": dict(good), "robust_frac": 0.8, "wf_pass": True}
    ablation = {"trail": dict(good),
                "net_fixed_horizon_exit": {"expectancy_r": 0.05, "profit_factor": 1.1,
                                           "mar": 0.5, "max_dd_r": -10.0, "total_r": 5.0, "n": 60},
                "stop_only": dict(good)}
    plateau = {"center": {"expectancy_r": 0.4},
               "neighbors": [{"label": f"n{i}", "expectancy_r": 0.35,
                              "profit_factor": 1.5} for i in range(7)]}
    cost = {"base": {**good, "econ_pass": True},
            "moderate": {**good, "alive": True}, "severe": dict(good)}
    dist = {"td_extreme": False}
    regime = {"rg_flag": False, "regime_sufficient": True}
    return wf, ablation, plateau, cost, dist, regime


class VerdictTiers(unittest.TestCase):
    def test_reaffirm(self):
        v = revalidation_verdict(*_passing_inputs())
        self.assertEqual(v.tier, "REAFFIRM PAPER")

    def test_structural_downgrade_on_wf_fail(self):
        wf, ab, pl, co, di, rg = _passing_inputs()
        wf["wf_pass"] = False
        self.assertEqual(revalidation_verdict(wf, ab, pl, co, di, rg).tier,
                         "DOWNGRADE TO PARKED / NEEDS-FIX")

    def test_structural_downgrade_on_no_exit_edge(self):
        wf, ab, pl, co, di, rg = _passing_inputs()
        ab["net_fixed_horizon_exit"] = dict(ab["trail"])  # EA fails
        self.assertEqual(revalidation_verdict(wf, ab, pl, co, di, rg).tier,
                         "DOWNGRADE TO PARKED / NEEDS-FIX")

    def test_inconclusive_on_moderate_dead(self):
        wf, ab, pl, co, di, rg = _passing_inputs()
        co["moderate"]["alive"] = False
        self.assertEqual(revalidation_verdict(wf, ab, pl, co, di, rg).tier,
                         "INCONCLUSIVE / PAPER-SUSPENDED")


if __name__ == "__main__":
    unittest.main()
