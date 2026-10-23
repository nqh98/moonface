import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile
import unittest
import zipfile

try:
    from moonface.research.forced_flow.coinm_archive import ArchiveError, load_coinm_bars
    from moonface.research.forced_flow import coinm_runner
    from moonface.research.forced_flow.iid_guard import NullBatteryResult, NullResult, PipelineResult
except ModuleNotFoundError:
    ArchiveError = None
    load_coinm_bars = None
    coinm_runner = None
    NullBatteryResult = None
    NullResult = None
    PipelineResult = None


WINDOW_START = datetime(2023, 6, 25, tzinfo=UTC)
WINDOW_END = datetime(2024, 10, 14, 23, tzinfo=UTC)


def _write_zip(path: Path, member: str, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, "\n".join(rows) + "\n")


def _kline_row(timestamp: datetime) -> str:
    open_time = int(timestamp.timestamp() * 1000)
    close_time = open_time + 3_599_999
    return f"{open_time},100,101,99,100,1,{close_time},1,1,1,1,0"


def _write_complete_kline_fixtures(
    root: Path, *, omit: set[datetime] | None = None
) -> None:
    omitted = omit or set()
    rows_by_month: dict[str, list[str]] = {}
    current = WINDOW_START
    while current <= WINDOW_END:
        if current not in omitted:
            rows_by_month.setdefault(current.strftime("%Y-%m"), []).append(_kline_row(current))
        current += timedelta(hours=1)
    for month, rows in rows_by_month.items():
        _write_zip(
            root / "klines" / f"BTCUSD_PERP-1h-{month}.zip",
            f"BTCUSD_PERP-1h-{month}.csv",
            rows,
        )


def _write_liquidation_fixture(
    root: Path,
    *,
    malformed: bool = False,
    zero_row_days: tuple[datetime, ...] = (),
) -> None:
    rows = ["time,side,order_type,average_price,last_fill_quantity,accumulated_fill_quantity"]
    if malformed:
        rows.append(f"{int(WINDOW_START.timestamp() * 1000)},HOLD,MARKET,100,1,1")
    else:
        row = f"{int(WINDOW_START.timestamp() * 1000)},BUY,MARKET,100,1,1"
        rows.extend((row, row))
    _write_zip(
        root / "liquidations" / "BTCUSD_PERP-liquidationSnapshot-2023-06-25.zip",
        "BTCUSD_PERP-liquidationSnapshot-2023-06-25.csv",
        rows,
    )
    for timestamp in zero_row_days:
        _write_zip(
            root
            / "liquidations"
            / f"BTCUSD_PERP-liquidationSnapshot-{timestamp:%Y-%m-%d}.zip",
            f"BTCUSD_PERP-liquidationSnapshot-{timestamp:%Y-%m-%d}.csv",
            [rows[0]],
        )


class TestCoinMArchive(unittest.TestCase):
    def test_exact_duplicates_are_deduped_and_zero_row_days_are_observed(self):
        self.assertIsNotNone(load_coinm_bars)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_complete_kline_fixtures(root)
            _write_liquidation_fixture(root, zero_row_days=(WINDOW_START + timedelta(days=1),))

            bars = load_coinm_bars(root)

        self.assertEqual(len(bars.timestamps), 48)
        self.assertEqual(bars.timestamps[0], WINDOW_START)
        self.assertEqual(bars.liq_counts[0], 1)
        self.assertEqual(bars.liq_imbalances[0], 1.0)
        self.assertEqual(bars.liq_counts[24], 0)
        self.assertEqual(bars.liq_imbalances[24], 0.0)
        self.assertEqual(bars.timestamps[-1], WINDOW_START + timedelta(days=1, hours=23))

    def test_single_kline_gap_is_dropped_and_splits_segments(self):
        self.assertIsNotNone(ArchiveError)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_complete_kline_fixtures(root, omit={WINDOW_START + timedelta(hours=13)})
            _write_liquidation_fixture(root)

            bars = load_coinm_bars(root)

        self.assertEqual(len(bars.timestamps), 23)
        self.assertEqual(bars.timestamps[12], WINDOW_START + timedelta(hours=12))
        self.assertEqual(bars.timestamps[13], WINDOW_START + timedelta(hours=14))
        self.assertEqual([(segment.start, segment.stop) for segment in bars.segments], [(0, 13), (13, 23)])

    def test_initial_dropped_liquidation_day_marks_first_segment_after_a_gap(self):
        self.assertIsNotNone(load_coinm_bars)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_complete_kline_fixtures(root)
            zero_day = WINDOW_START + timedelta(days=1)
            _write_zip(
                root / "liquidations" / f"BTCUSD_PERP-liquidationSnapshot-{zero_day:%Y-%m-%d}.zip",
                f"BTCUSD_PERP-liquidationSnapshot-{zero_day:%Y-%m-%d}.csv",
                ["time,side,order_type,average_price,last_fill_quantity,accumulated_fill_quantity"],
            )

            bars = load_coinm_bars(root)

        self.assertEqual(bars.timestamps[0], zero_day)
        self.assertTrue(bars.segments[0].starts_after_gap)

    def test_excessive_kline_gaps_stop_before_a_run(self):
        self.assertIsNotNone(ArchiveError)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_complete_kline_fixtures(
                root,
                omit={WINDOW_START + timedelta(hours=hour) for hour in range(115)},
            )

            with self.assertRaisesRegex(ArchiveError, "kline gaps exceed 1%"):
                load_coinm_bars(root)

    def test_malformed_required_liquidation_row_raises(self):
        self.assertIsNotNone(ArchiveError)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_complete_kline_fixtures(root)
            _write_liquidation_fixture(root, malformed=True)

            with self.assertRaisesRegex(ArchiveError, "side"):
                load_coinm_bars(root)

    def test_non_hour_aligned_kline_row_raises(self):
        self.assertIsNotNone(ArchiveError)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_complete_kline_fixtures(root)
            _write_zip(
                root / "klines" / "BTCUSD_PERP-1h-2023-06.zip",
                "BTCUSD_PERP-1h-2023-06.csv",
                [_kline_row(WINDOW_START + timedelta(minutes=30))],
            )

            with self.assertRaisesRegex(ArchiveError, "kline open time.*hour-aligned"):
                load_coinm_bars(root)

    def test_canonical_kline_header_is_accepted_as_metadata(self):
        self.assertIsNotNone(load_coinm_bars)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_complete_kline_fixtures(root)
            _write_liquidation_fixture(root)
            june_rows = [
                "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_base,taker_quote,ignore"
            ]
            current = WINDOW_START
            while current.month == 6:
                june_rows.append(_kline_row(current))
                current += timedelta(hours=1)
            _write_zip(
                root / "klines" / "BTCUSD_PERP-1h-2023-06.zip",
                "BTCUSD_PERP-1h-2023-06.csv",
                june_rows,
            )

            bars = load_coinm_bars(root)

        self.assertEqual(bars.closes[0], 100.0)


class TestCoinMRunner(unittest.TestCase):
    def test_runner_uses_the_repository_terminal_verdict_directory(self):
        self.assertIsNotNone(coinm_runner)
        self.assertEqual(
            coinm_runner.VERDICT_DIR,
            Path(__file__).resolve().parents[2] / "experiments" / "forced_flow",
        )

    def test_runner_writes_terminal_underpowered_verdict_once(self):
        self.assertIsNotNone(coinm_runner)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "archive"
            _write_complete_kline_fixtures(root)
            _write_liquidation_fixture(root)
            output_dir = Path(temp_dir) / "verdicts"
            original_output_dir = coinm_runner.VERDICT_DIR
            coinm_runner.VERDICT_DIR = output_dir
            try:
                verdict = coinm_runner.run_once(root)
                payload = json.loads((output_dir / "verdict.json").read_text(encoding="utf-8"))
                markdown = (output_dir / "PILOT_VERDICT.md").read_text(encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    coinm_runner.run_once(root)
            finally:
                coinm_runner.VERDICT_DIR = original_output_dir

        self.assertEqual(verdict.verdict, "UNDERPOWERED_KILL")
        self.assertEqual(payload["verdict"], "UNDERPOWERED_KILL")
        self.assertEqual(payload["episode_count"], 0)
        self.assertEqual(payload["qualifying_bucket_count"], 0)
        self.assertIsNone(payload["observed_spread"])
        self.assertIsNone(payload["label_shuffle_p975"])
        self.assertIsNone(payload["circular_shift_p975"])
        self.assertFalse(payload["iid_guard_passed"])
        self.assertIn("UNDERPOWERED_KILL", markdown)

    def test_iid_guard_precedence_is_suspect_harness(self):
        self.assertIsNotNone(coinm_runner)
        self.assertIsNotNone(NullBatteryResult)
        pipeline = PipelineResult((), (), 0.1)
        passing = NullResult(0.1, 0.05, True, ())
        failing = NullResult(0.1, 0.2, False, ())
        battery = NullBatteryResult(pipeline, passing, passing, passing)

        self.assertEqual(coinm_runner._select_verdict(battery), "SUSPECT_HARNESS")
        self.assertEqual(
            coinm_runner._select_verdict(NullBatteryResult(pipeline, failing, failing, failing)),
            "UNDERPOWERED_KILL",
        )
        self.assertEqual(
            coinm_runner._select_verdict(
                NullBatteryResult(PipelineResult((), (object(), object()), 0.1), failing, passing, failing)
            ),
            "KILL",
        )
        self.assertEqual(
            coinm_runner._select_verdict(
                NullBatteryResult(PipelineResult((), (object(), object()), 0.1), passing, passing, failing)
            ),
            "WEAK SUPPORT",
        )

    def test_discard_majority_precedence_is_suspect_harness_and_is_exposed(self):
        self.assertIsNotNone(coinm_runner)
        self.assertIsNotNone(NullBatteryResult)
        pipeline = PipelineResult((), (), None)
        discarded = NullResult(None, None, False, (), discarded_draws=501)
        battery = NullBatteryResult(pipeline, discarded, discarded, discarded)

        verdict = coinm_runner._build_verdict(battery, ())

        self.assertEqual(verdict.verdict, "SUSPECT_HARNESS")
        self.assertEqual(verdict.label_shuffle_discarded_draws, 501)
        self.assertEqual(verdict.circular_shift_discarded_draws, 501)
        self.assertEqual(verdict.iid_return_discarded_draws, 501)


if __name__ == "__main__":
    unittest.main()
