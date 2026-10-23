# tests/test_research_cli.py
import argparse
import os
import tempfile
import unittest
from pathlib import Path

from tools.research import (build_parser, cmd_gate, cmd_init, cmd_reregister,
                            cmd_retry_errors)

from moonface.kernel.store import Store


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "research.db")

    def args(self, **kw) -> argparse.Namespace:
        base = dict(db=self.db, out_root=self.tmp.name)
        base.update(kw)
        return argparse.Namespace(**base)

    def test_init_registers_v1_domains_and_btc_v2(self):
        cmd_init(self.args())
        pairs = [(d["name"], d["version"]) for d in Store(self.db).domains_in_order()]
        self.assertEqual(len(pairs), 9)
        self.assertIn(("positioning_transfer", 1), pairs)
        self.assertIn(("relaxed_budget_btc", 1), pairs)
        self.assertIn(("relaxed_budget_btc", 2), pairs)
        self.assertIn(("positioning_btc", 1), pairs)
        self.assertIn(("funding_fade_transfer", 1), pairs)

    def test_init_is_idempotent(self):
        cmd_init(self.args())
        cmd_init(self.args())  # must not raise
        self.assertEqual(len(Store(self.db).domains_in_order()), 9)

    def test_gate_requires_awaiting_status(self):
        cmd_init(self.args())
        with self.assertRaises(SystemExit):
            cmd_gate(self.args(domain="relaxed_budget_btc", version=1,
                               open_lockbox=True))

    def _advance_one_to(self, store, name, target):
        h = store.rows(name, 1, status="pending")[0]["spec_hash"]
        chain = ["screened", "oos_pass", "corrected_survivor"]
        for step in chain[: chain.index(target) + 1]:
            store.advance(h, step, {})

    def test_gate_flips_awaiting_to_lockbox_open(self):
        cmd_init(self.args())
        store = Store(self.db)
        self._advance_one_to(store, "relaxed_budget_btc", "corrected_survivor")
        store.set_domain_status("relaxed_budget_btc", 1, "awaiting_gate")
        cmd_gate(self.args(domain="relaxed_budget_btc", version=1,
                           open_lockbox=True))
        self.assertEqual(Store(self.db).domain("relaxed_budget_btc", 1)["status"],
                         "lockbox_open")

    def test_gate_refuses_without_corrected_survivors(self):
        # An error boundary parks domains at awaiting_gate with zero corrected
        # survivors; arming the lockbox then burns the one-touch on nothing
        # (multi_asset_transfer v1, 2026-06-11). The gate must refuse.
        cmd_init(self.args())
        store = Store(self.db)
        store.set_domain_status("relaxed_budget_btc", 1, "awaiting_gate")
        with self.assertRaises(SystemExit) as ctx:
            cmd_gate(self.args(domain="relaxed_budget_btc", version=1,
                               open_lockbox=True))
        self.assertIn("survivor", str(ctx.exception))
        self.assertEqual(Store(self.db).domain("relaxed_budget_btc", 1)["status"],
                         "awaiting_gate")

    def test_gate_without_flag_refuses(self):
        cmd_init(self.args())
        store = Store(self.db)
        store.set_domain_status("relaxed_budget_btc", 1, "awaiting_gate")
        with self.assertRaises(SystemExit):
            cmd_gate(self.args(domain="relaxed_budget_btc", version=1,
                               open_lockbox=False))

    def test_reregister_cli_creates_new_version(self):
        cmd_init(self.args())
        store = Store(self.db)
        store.set_domain_status("multi_asset_transfer", 1, "closed_negative")
        cmd_reregister(self.args(domain="multi_asset_transfer", from_version=1))
        d = Store(self.db).domain("multi_asset_transfer", 2)
        self.assertIsNotNone(d)
        self.assertEqual(d["status"], "active")
        self.assertEqual(d["grid_size"], 380)

    def test_reregister_cli_maps_refusal_to_exit(self):
        cmd_init(self.args())  # relaxed_budget_btc v1 is 'active', not closed
        with self.assertRaises(SystemExit):
            cmd_reregister(self.args(domain="relaxed_budget_btc", from_version=1))

    def test_parser_wires_subcommands(self):
        p = build_parser()
        args = p.parse_args(["run", "--budget", "5", "--domain", "x"])
        self.assertEqual(args.budget, 5)
        self.assertEqual(args.domain, "x")
        args = p.parse_args(["gate", "d", "--open-lockbox"])
        self.assertTrue(args.open_lockbox)
        args = p.parse_args(["reregister", "d", "--from-version", "2"])
        self.assertEqual(args.from_version, 2)


if __name__ == "__main__":
    unittest.main()


class TestRetryErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "research.db")

    def args(self, **kw) -> argparse.Namespace:
        base = dict(db=self.db, out_root=self.tmp.name)
        base.update(kw)
        return argparse.Namespace(**base)

    def _store_with_errors(self):
        cmd_init(self.args())
        store = Store(self.db)
        for row in store.rows("positioning_btc", 1)[:3]:
            for _ in range(3):
                store.record_error(row["spec_hash"], "ValueError('bug')")
        store.set_domain_status("positioning_btc", 1, "awaiting_gate")
        return store

    def test_retry_errors_resets_rows_and_reactivates(self):
        self._store_with_errors()
        cmd_retry_errors(self.args(domain="positioning_btc", version=1))
        store = Store(self.db)
        counts = store.counts("positioning_btc", 1)
        self.assertNotIn("error", counts)
        self.assertEqual(counts["pending"], 80)
        self.assertEqual(store.domain("positioning_btc", 1)["status"], "active")
        row = store.rows("positioning_btc", 1)[0]
        self.assertEqual(row["attempts"], 0)

    def test_retry_errors_refuses_closed_domain(self):
        store = self._store_with_errors()
        store.set_domain_status("positioning_btc", 1, "closed_negative")
        with self.assertRaises(SystemExit):
            cmd_retry_errors(self.args(domain="positioning_btc", version=1))


class TestFundingRefCommand(unittest.TestCase):
    def test_funding_ref_prints_in_sample_reference(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        from moonface.core.bundle import DataBundle
        from moonface.kernel.synth import make_candles
        import tools.research as cli

        candles = make_candles(n=400)
        bundle = DataBundle(candles=candles, funding=[0.0] * len(candles))
        # the CLI wires handlers via set_defaults(fn=...) and main() calls
        # args.fn(args); the test invokes the same way.
        args = cli.build_parser().parse_args(
            ["funding-ref", "--cache-dir", "/unused"])
        with patch("tools.research.load_bundle", return_value=bundle):
            buf = io.StringIO()
            with redirect_stdout(buf):
                args.fn(args)
        out = buf.getvalue()
        self.assertIn("IN-SAMPLE REFERENCE", out.upper())
        self.assertIn("fixed_bracket", out)
        self.assertIn("atr_trail", out)


class TestOrderflowCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "research.db")

    def test_parser_wires_orderflow_subcommand(self):
        import tools.research as cli
        args = cli.build_parser().parse_args(["orderflow", "--cache-dir", "/unused"])
        self.assertTrue(callable(args.fn))

    def test_cmd_orderflow_registers_runs_and_prints_verdict(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        import tools.research as cli

        args = cli.build_parser().parse_args(
            ["--db", self.db, "--out-root", self.tmp.name,
             "orderflow", "--cache-dir", "/unused"])
        with patch("tools.research.register_orderflow") as reg, \
             patch("tools.research.run_orderflow",
                   return_value="closed_negative") as run, \
             patch("tools.research.Store"):
            buf = io.StringIO()
            with redirect_stdout(buf):
                args.fn(args)
        reg.assert_called_once()
        run.assert_called_once()
        self.assertIn("closed_negative", buf.getvalue())


class TestUniverseDonchianCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "research.db")

    def test_parser_wires_universe_donchian_subcommand(self):
        import tools.research as cli

        args = cli.build_parser().parse_args(["universe-donchian"])
        self.assertIs(args.fn, cli.cmd_universe_donchian)
        self.assertEqual(args.cache_dir, ".backtest_cache")

    def test_cmd_universe_donchian_registers_runs_and_prints_verdict(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        import tools.research as cli

        args = cli.build_parser().parse_args(
            ["--db", self.db, "--out-root", self.tmp.name,
             "universe-donchian", "--cache-dir", "/unused"])
        with patch("tools.research.register_universe_donchian") as reg, \
             patch("tools.research.run_universe_donchian",
                   return_value="closed_positive") as run, \
             patch("tools.research.Store") as store_cls:
            buf = io.StringIO()
            with redirect_stdout(buf):
                args.fn(args)
        store_cls.assert_called_once_with(self.db)
        store = store_cls.return_value
        reg.assert_called_once()
        self.assertIs(reg.call_args.args[0], store)
        self.assertIsInstance(reg.call_args.args[1], int)
        run.assert_called_once_with(store, "/unused", Path(self.tmp.name))
        out = buf.getvalue()
        self.assertIn("closed_positive", out)
        self.assertIn("universe_donchian/verdict.md", out)
