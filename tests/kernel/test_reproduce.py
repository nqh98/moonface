import csv
from pathlib import Path
from tempfile import TemporaryDirectory

from moonface.kernel.reproduce import (offline_fetch_metrics_history,
                                        offline_fetch_perp_candles, reproduce)
from moonface.kernel.reproduce import (offline_fetch_daily_klines,
                                        offline_fetch_funding_rates,
                                        offline_list_um_perp_symbols)
from moonface.kernel.reproduce import offline_fetch_bookdepth_history
from moonface.kernel.reproduce import offline_fetch_funding_history_series


def _fake_run_ok(cfg: dict, out_dir: Path) -> dict:
    return {"verdict": "mechanism_does_not_exist", "stouffer_z": -1.024,
            "generated_utc": "2099-01-01T00:00:00Z"}


def _fake_run_mismatch(cfg: dict, out_dir: Path) -> dict:
    return {"verdict": "mechanism_does_not_exist", "stouffer_z": -9.999,
            "generated_utc": "2099-01-01T00:00:00Z"}


class TestReproduce:
    def test_matches_when_compared_fields_agree(self):
        recorded = {"verdict": "mechanism_does_not_exist", "stouffer_z": -1.024}
        with TemporaryDirectory() as tmp:
            result = reproduce(_fake_run_ok, {}, recorded,
                               compare_fields=("verdict", "stouffer_z"),
                               scratch_dir=Path(tmp))
        assert result.matched
        assert result.mismatches == {}

    def test_reports_a_mismatch_without_raising(self):
        recorded = {"verdict": "mechanism_does_not_exist", "stouffer_z": -1.024}
        with TemporaryDirectory() as tmp:
            result = reproduce(_fake_run_mismatch, {}, recorded,
                               compare_fields=("verdict", "stouffer_z"),
                               scratch_dir=Path(tmp))
        assert not result.matched
        assert result.mismatches == {"stouffer_z": (-1.024, -9.999)}

    def test_ignores_fields_not_in_compare_fields(self):
        recorded = {"verdict": "mechanism_does_not_exist", "stouffer_z": -1.024,
                   "generated_utc": "1970-01-01T00:00:00Z"}
        with TemporaryDirectory() as tmp:
            result = reproduce(_fake_run_ok, {}, recorded,
                               compare_fields=("verdict", "stouffer_z"),
                               scratch_dir=Path(tmp))
        assert result.matched  # generated_utc differs but is not compared

    def test_scratch_dir_is_passed_through_to_run_fn(self):
        seen = {}

        def run_fn(cfg, out_dir):
            seen["out_dir"] = out_dir
            return {"verdict": "x"}

        with TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            reproduce(run_fn, {}, {"verdict": "x"}, compare_fields=("verdict",),
                     scratch_dir=scratch)
        assert seen["out_dir"] == scratch

    def test_extra_args_and_kwargs_pass_through(self):
        seen = {}

        def run_fn(cfg, fetch_a, out_dir, fetch_b=None):
            seen["fetch_a"] = fetch_a
            seen["fetch_b"] = fetch_b
            return {"verdict": "x"}

        with TemporaryDirectory() as tmp:
            reproduce(run_fn, {}, {"verdict": "x"}, compare_fields=("verdict",),
                     scratch_dir=Path(tmp), run_args=("A",), run_kwargs={"fetch_b": "B"})
        assert seen == {"fetch_a": "A", "fetch_b": "B"}

    def test_missing_recorded_field_is_a_mismatch(self):
        recorded = {"verdict": "x"}
        with TemporaryDirectory() as tmp:
            result = reproduce(_fake_run_ok, {}, recorded,
                               compare_fields=("verdict", "stouffer_z"),
                               scratch_dir=Path(tmp))
        assert not result.matched
        assert "stouffer_z" in result.mismatches
        assert result.mismatches["stouffer_z"][0] is None


class TestOfflineFetchPerpCandles:
    def test_returns_empty_list_on_cache_miss_no_network_call(self):
        with TemporaryDirectory() as tmp:
            out = offline_fetch_perp_candles("NOPE", "4h", 0, 1_000_000, tmp)
        assert out == []

    def test_reads_and_filters_the_cached_window(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "BTCUSDT_4h.csv"
            with open(path, "w", newline="") as fh:
                w = csv.writer(fh)
                for ts in (0, 14_400_000, 28_800_000, 43_200_000):
                    w.writerow([ts, 1.0, 1.0, 1.0, 1.0, 0.0])
            out = offline_fetch_perp_candles("BTCUSDT", "4h", 14_400_000, 43_200_000, tmp)
        assert [c.timestamp_ms for c in out] == [14_400_000, 28_800_000]


class TestOfflineFetchMetricsHistory:
    def test_returns_empty_list_on_cache_miss_no_network_call(self):
        with TemporaryDirectory() as tmp:
            out = offline_fetch_metrics_history("NOPE", 0, 1_000_000, tmp)
        assert out == []

    def test_reads_and_filters_the_cached_window(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "metrics_BTCUSDT.csv"
            with open(path, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["ts_ms", "sum_open_interest"])
                w.writerow([0, "1.0"])
                w.writerow([86_400_000, "2.0"])
                w.writerow([172_800_000, "3.0"])
            out = offline_fetch_metrics_history("BTCUSDT", 86_400_000, 86_400_001, tmp)
        assert [ts for ts, _ in out] == [86_400_000]


class TestOfflineFetchDailyKlines:
    def test_returns_empty_list_on_cache_miss_no_network_call(self):
        with TemporaryDirectory() as tmp:
            out = offline_fetch_daily_klines("NOPE", 0, 1_000_000, tmp)
        assert out == []

    def test_reads_and_filters_the_cached_window(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "uni1d_BTCUSDT.csv"
            with open(path, "w", newline="") as fh:
                w = csv.writer(fh)
                for ts in (0, 86_400_000, 172_800_000, 259_200_000):
                    w.writerow([ts, 100.0, 1_000_000.0])
            out = offline_fetch_daily_klines("BTCUSDT", 86_400_000, 259_200_000, tmp)
        assert [r.ts_ms for r in out] == [86_400_000, 172_800_000]


class TestOfflineFetchFundingRates:
    def test_returns_empty_list_on_cache_miss_no_network_call(self):
        with TemporaryDirectory() as tmp:
            out = offline_fetch_funding_rates("NOPE", 0, 1_000_000, tmp)
        assert out == []

    def test_reads_and_filters_the_cached_window(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "unifunding_BTCUSDT.csv"
            with open(path, "w", newline="") as fh:
                w = csv.writer(fh)
                for ts, rate in ((0, 0.0001), (28_800_000, 0.0002), (57_600_000, -0.0001)):
                    w.writerow([ts, rate])
            out = offline_fetch_funding_rates("BTCUSDT", 28_800_000, 57_600_000, tmp)
        assert out == [(28_800_000, 0.0002)]


class TestOfflineFetchBookdepthHistory:
    def test_returns_empty_list_on_cache_miss_no_network_call(self):
        with TemporaryDirectory() as tmp:
            out = offline_fetch_bookdepth_history("NOPE", 0, 1_000_000, tmp)
        assert out == []

    def test_reads_and_filters_the_cached_window(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bookdepth_BTCUSDT.csv"
            with open(path, "w", newline="") as fh:
                w = csv.writer(fh)
                for ts in (0, 30_000, 60_000, 90_000):
                    w.writerow([ts, 100.0, 90.0])
            out = offline_fetch_bookdepth_history("BTCUSDT", 30_000, 90_000, tmp)
        assert [row[0] for row in out] == [30_000, 60_000]


class TestOfflineFetchFundingHistorySeries:
    """Distinct from TestOfflineFetchFundingRates: this reads
    moonface.data.series.FundingCache's cache format (funding_<safe>.csv,
    ccxt-style symbol e.g. "DOGE/USDT:USDT"), not data.universe's
    unifunding_<SYM>.csv plain-symbol format."""

    def test_returns_empty_list_on_cache_miss_no_network_call(self):
        with TemporaryDirectory() as tmp:
            out = offline_fetch_funding_history_series(
                "NOPE/USDT:USDT", 0, 1_000_000, tmp)
        assert out == []

    def test_reads_and_filters_the_cached_window(self):
        from moonface.data.series import FundingCache

        with TemporaryDirectory() as tmp:
            FundingCache(tmp).save("DOGE/USDT:USDT",
                                   [(0, 0.0001), (28_800_000, 0.0002),
                                    (57_600_000, -0.0001)])
            out = offline_fetch_funding_history_series(
                "DOGE/USDT:USDT", 28_800_000, 57_600_000, tmp)
        assert out == [(28_800_000, 0.0002)]


class TestOfflineListUmPerpSymbols:
    def test_returns_empty_list_when_no_daily_cache_present(self):
        with TemporaryDirectory() as tmp:
            assert offline_list_um_perp_symbols(tmp) == []

    def test_returns_sorted_symbols_from_daily_cache_filenames(self):
        with TemporaryDirectory() as tmp:
            for sym in ("ETHUSDT", "BTCUSDT", "SOLUSDT"):
                (Path(tmp) / f"uni1d_{sym}.csv").write_text("")
            out = offline_list_um_perp_symbols(tmp)
        assert out == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
