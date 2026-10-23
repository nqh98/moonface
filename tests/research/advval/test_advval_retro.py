import unittest

from moonface.research.advval.retrodiction import (
    CELLS,
    EXCLUDED,
    STUDIES,
    retrodiction_verdict,
)


class RegistryTest(unittest.TestCase):
    def test_table_shape(self):
        self.assertIsInstance(STUDIES, tuple)
        self.assertEqual(
            [(s.name, s.cell, s.outcome, s.basis) for s in STUDIES],
            [
                (
                    "xsection_mom_30",
                    "price_1d",
                    1,
                    "passed screen+holdout (MAR 3.19); sealed tail −91.6% DD",
                ),
                (
                    "xsection_mom_7",
                    "price_1d",
                    1,
                    "screen-positive; died in OOS holdout (−51% DD)",
                ),
                (
                    "xsection_carry_7",
                    "funding_8h",
                    1,
                    "screen-positive; died in OOS holdout (−35% DD)",
                ),
                (
                    "bab_60",
                    "price_1d",
                    1,
                    "IS anomaly (research MAR 1.93); holdout reverses (MAR −0.48)",
                ),
                (
                    "liqrev",
                    "oi_4h",
                    1,
                    "first half +0.42%/event; second half ≈0 (time decay)",
                ),
                (
                    "practical_full_reeval",
                    "price_4h",
                    1,
                    "3/132 passed battery; ALL reversed in recent sealed window",
                ),
                (
                    "ls_tournament",
                    "price_4h",
                    1,
                    "sole explore survivor reversed in sealed holdout",
                ),
                (
                    "bb_breakout_harvest",
                    "price_4h",
                    1,
                    "alive in-sample lead failed gross Z floor once OOS-aware",
                ),
                (
                    "resrev_1",
                    "price_1d",
                    0,
                    "gross pre-screen coin flip (Z −0.18); never IS-strong",
                ),
                (
                    "oibuild_study",
                    "oi_4h",
                    0,
                    "pooled −0.64%/event; sign test 8/16",
                ),
                (
                    "calseason",
                    "price_4h",
                    0,
                    "max |Z| 1.54 vs gate 3; never near gate",
                ),
                (
                    "system_search",
                    "price_4h",
                    0,
                    "0/72 pass stage 1; top DSR 0.401",
                ),
                (
                    "practical_discovery",
                    "price_4h",
                    0,
                    "0/72 survivors",
                ),
                (
                    "drift_basket",
                    "price_1d",
                    0,
                    "research net −0.64; stages 1–3 fail",
                ),
                (
                    "pathsig_rung0",
                    "price_4h",
                    0,
                    "DSR 0 on all 30 rows",
                ),
                (
                    "dual_timeframe",
                    "price_4h",
                    0,
                    "all 9 cells die at gross-drift stage 1",
                ),
                (
                    "multifamily_funding",
                    "funding_8h",
                    0,
                    "funding families mechanism_does_not_exist",
                ),
                (
                    "multifamily_oi",
                    "oi_4h",
                    0,
                    "OI families mechanism_does_not_exist",
                ),
            ],
        )
        self.assertEqual(
            EXCLUDED,
            (
                ("positioning_transfer", "asset-transfer failure, not time-OOS"),
                ("funding_fade_transfer", "asset-transfer failure, not time-OOS"),
                ("program_cycles_1_11", "drawdown-wall failure mode, predates the ladder"),
                ("breadth*", "cross-asset features unmeasured; confound closure"),
                ("macro_event", "exogenous data family unmeasured"),
                ("exogenous", "exogenous data family unmeasured"),
                ("bookdepth", "microstructure features unmeasured"),
                ("aggtrades", "microstructure features unmeasured"),
                ("taker_flow", "microstructure features unmeasured"),
                ("donchian_4h_paper", "withdrawn, not closed negative"),
                ("mtf_confluence", "still-open forward thread"),
                ("btc_specialized", "composite engines, no single feature family"),
                ("playbook", "composite engines, no single feature family"),
                ("confluence engine", "composite engines, no single feature family"),
            ),
        )
        self.assertIsInstance(EXCLUDED, tuple)

    def test_every_cell_has_both_outcomes_or_is_noted(self):
        for cell in CELLS:
            outs = {s.outcome for s in STUDIES if s.cell == cell}
            self.assertEqual(outs, {0, 1}, cell)


class VerdictTest(unittest.TestCase):
    def test_aligned_aucs_default_kill(self):
        aucs = {
            "price_4h": 0.1,
            "price_1d": 0.2,
            "funding_8h": 0.3,
            "oi_4h": 0.4,
        }
        v = retrodiction_verdict(aucs)
        self.assertEqual(v["verdict"], "kill")
        self.assertEqual(v["reason"], "rho_or_ci_not_positive")
        self.assertEqual(v["n_studies"], 18)
        self.assertAlmostEqual(v["rho"], 0.0457495710997814, places=15)
        self.assertAlmostEqual(v["ci_low"], -0.3504186988107663, places=15)
        self.assertAlmostEqual(v["ci_high"], 0.42975617985880515, places=15)

    def test_aligned_aucs_one_boot_pass(self):
        aucs = {
            "price_4h": 0.1,
            "price_1d": 0.2,
            "funding_8h": 0.3,
            "oi_4h": 0.4,
        }
        v = retrodiction_verdict(aucs, n_boot=1, seed=0)
        self.assertEqual(v["verdict"], "pass")
        self.assertEqual(v["reason"], "")
        self.assertEqual(v["n_studies"], 18)
        self.assertAlmostEqual(v["rho"], 0.0457495710997814, places=15)
        self.assertAlmostEqual(v["ci_low"], 0.1494239088042919, places=15)
        self.assertAlmostEqual(v["ci_high"], 0.1494239088042919, places=15)

    def test_anti_correlated_kills(self):
        aucs = {
            "price_4h": 0.5,
            "price_1d": 0.5,
            "funding_8h": 0.99,
            "oi_4h": 0.99,
        }
        v = retrodiction_verdict(aucs)
        self.assertEqual(v["verdict"], "kill")

    def test_degenerate_equal_aucs_kill(self):
        aucs = {c: 0.7 for c in CELLS}
        v = retrodiction_verdict(aucs)
        self.assertEqual(v["verdict"], "kill")
        self.assertEqual(v["reason"], "degenerate_spearman")

    def test_deterministic(self):
        aucs = {
            "price_4h": 0.8,
            "price_1d": 0.7,
            "funding_8h": 0.6,
            "oi_4h": 0.55,
        }
        a = retrodiction_verdict(aucs)
        b = retrodiction_verdict(aucs)
        self.assertEqual(a, b)

    def test_missing_cell_raises(self):
        with self.assertRaises(KeyError):
            retrodiction_verdict({"price_4h": 0.8})
