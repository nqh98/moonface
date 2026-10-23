# tests/test_funding_fade_ref.py
import ast
import pathlib
import unittest

from moonface.core.bundle import DataBundle
from moonface.research.funding_fade_ref import (BTC_REF_ASSET, btc_reference,
                                                format_reference, reference_rows)
from moonface.core.metrics import EquitySummary


class TestBtcReferenceAsset(unittest.TestCase):
    def test_asset_is_btc_with_own_funding(self):
        self.assertEqual(BTC_REF_ASSET["symbol"], "BTC/USDT:USDT")
        self.assertEqual(BTC_REF_ASSET["funding_symbol"], "BTC/USDT:USDT")

    def test_reference_rows_are_the_two_frozen_exits(self):
        rows = reference_rows()  # list[(exit_name, exit_params)]
        self.assertEqual([name for name, _ in rows],
                         ["fixed_bracket", "atr_trail"])


class TestBtcReferenceComputation(unittest.TestCase):
    def test_returns_an_equity_summary_per_exit(self):
        # Synthetic bundle from the repo's deterministic candle factory plus a
        # flat funding series (>= window-60 warmup). Flat funding => sd==0 =>
        # no funding_fade entries => empty EquitySummary; we assert SHAPE
        # (one summary per exit), not trade count, so this stays deterministic
        # and network-free.
        from moonface.kernel.synth import make_candles
        candles = make_candles(n=400)
        bundle = DataBundle(candles=candles, funding=[0.0] * len(candles))
        out = btc_reference(bundle)  # dict[exit_name -> EquitySummary]
        self.assertEqual(set(out), {"fixed_bracket", "atr_trail"})
        for summ in out.values():
            self.assertIsInstance(summ, EquitySummary)

    def test_format_reference_labels_in_sample_and_lists_metrics(self):
        summ = EquitySummary(trade_count=68, net_return=0.5, max_drawdown=-0.12,
                             mar=4.1, sharpe=0.2, skew=0.0, kurtosis=3.0)
        text = format_reference({"fixed_bracket": summ})
        self.assertIn("in-sample reference", text.lower())
        self.assertIn("not validation", text.lower())
        self.assertIn("fixed_bracket", text)
        self.assertIn("MAR", text)


class TestReferenceIsLockboxFree(unittest.TestCase):
    def test_module_imports_no_store_or_lockbox(self):
        src = pathlib.Path("src/moonface/research/funding_fade_ref.py").read_text()
        tree = ast.parse(src)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
        self.assertNotIn("moonface.kernel.store", imported)
        self.assertNotIn("moonface.kernel.lockbox", imported)
        self.assertNotIn("moonface.kernel.runner", imported)
