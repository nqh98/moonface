import pytest

from tools.lane_registry import LANES, LaneEntry


def test_oibuild_study_and_liqladder_are_registered():
    # Subset check, not equality: Task 4 and Task 5 append more lanes to this
    # same LANES dict in later commits, and this test must stay green then too.
    assert {"oibuild_study", "liqladder"} <= set(LANES)


def test_each_entry_has_the_expected_shape():
    for name, entry in LANES.items():
        assert isinstance(entry, LaneEntry)
        assert callable(entry.run_fn)
        assert isinstance(entry.compare_fields, tuple) and entry.compare_fields
        assert callable(entry.run_args_builder)
        assert entry.code_paths and all(isinstance(p, str) for p in entry.code_paths)
        assert isinstance(entry.verdict_filename, str) and entry.verdict_filename


# G6.2's `code_paths == (f"tools/lanes/{name}.py",)` invariant assumed every
# lane lived in the flat tools/lanes/ file-per-lane convention -- true for
# every B1-B3 lane, but not for G6.3's research/<lane>/ packages, each with
# its own tools/<lane>/ CLI directory (e.g. advval's tools/advval/advval_run.py).
# Checked as an explicit allowlist rather than folded into the general shape
# test above, so a future lane hitting the same gap doesn't need to touch this
# test -- just add its name here.
_NON_FLAT_CODE_PATH_LANES = {"advval", "eventtime", "breadth", "breadth_confirm",
                             "breadth_momentum_confirm", "breadth_neutral",
                             "breadth_xasset_confirm", "breadth_internal",
                             "breadth_internal_hf", "donchian_filter", "btc_classic",
                             "donchian_volregime", "regime_overlay", "regime_selector",
                             "ls_tournament", "sse", "portfolio", "liq_twap",
                             "consolidated_ls", "matrix", "mtf_transfer",
                             "mtf_basket", "mtf_broaden", "mtf_long_only",
                             "edge_search_swing_4h", "edge_search_day_15m",
                             "playbook", "practical", "practical_full", "btcspec",
                             "btcspec_s2", "btcspec_s3", "exogenous"}


def test_lanes_without_a_research_package_use_the_flat_tools_lanes_convention():
    for name, entry in LANES.items():
        if name in _NON_FLAT_CODE_PATH_LANES:
            continue
        assert entry.code_paths == (f"tools/lanes/{name}.py",)


def test_entries_default_verdict_filename_to_verdict_json():
    assert LANES["oibuild_study"].verdict_filename == "verdict.json"


def test_candles_metric_run_args_builds_two_callables():
    entry = LANES["oibuild_study"]
    series_by_key: dict = {}
    cfg = {"metrics_field": "sum_open_interest"}
    run_args = entry.run_args_builder(cfg, ".backtest_cache", series_by_key)
    assert len(run_args) == 2
    fetch_candles, fetch_metric = run_args
    assert callable(fetch_candles) and callable(fetch_metric)


def test_research_cli_reproduce_choices_come_from_the_registry():
    import importlib.util
    from pathlib import Path as P

    spec = importlib.util.spec_from_file_location(
        "research_cli_g6", P("tools/research.py"))
    research_cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(research_cli)
    parser = research_cli.build_parser()
    args = parser.parse_args(["reproduce", "liqladder", "--cache-dir", "/unused"])
    assert args.lane == "liqladder"
    assert args.fn is research_cli.cmd_reproduce


def test_write_run_record_creates_a_kernel_runs_file(tmp_path):
    from tools.research import _write_run_record
    from moonface.kernel.reproduce import ReproductionResult

    result = ReproductionResult(matched=True, mismatches={}, recomputed={"verdict": "x"})
    verdict_path = tmp_path / "verdict.json"
    verdict_path.write_text("{}")
    triple = {"registration_hash": "r", "data_fingerprint": "d", "code_hash": "c"}

    path = _write_run_record("fake_lane", result, verdict_path, triple,
                             kernel_runs_root=tmp_path / "kernel_runs")

    assert path.exists()
    record = __import__("json").loads(path.read_text())
    assert record["lane"] == "fake_lane"
    assert record["matched"] is True
    assert record["mismatches"] == {}
    assert record["compared_against"] == str(verdict_path)
    assert record["registration_hash"] == "r"
    assert record["data_fingerprint"] == "d"
    assert record["code_hash"] == "c"


def test_write_run_record_preserves_mismatches(tmp_path):
    from tools.research import _write_run_record
    from moonface.kernel.reproduce import ReproductionResult

    result = ReproductionResult(matched=False, mismatches={"stouffer_z": (-1.0, -2.0)},
                                recomputed={"verdict": "x"})
    verdict_path = tmp_path / "verdict.json"
    verdict_path.write_text("{}")
    triple = {"registration_hash": "r", "data_fingerprint": "d", "code_hash": "c"}

    path = _write_run_record("fake_lane", result, verdict_path, triple,
                             kernel_runs_root=tmp_path / "kernel_runs")
    record = __import__("json").loads(path.read_text())
    assert record["mismatches"] == {"stouffer_z": [-1.0, -2.0]}


def test_load_recorded_returns_a_dict_shaped_verdict_unchanged(tmp_path):
    from tools.research import _load_recorded

    path = tmp_path / "verdict.json"
    path.write_text('{"verdict": "x", "stouffer_z": -1.0}')
    assert _load_recorded(path, "verdict.json") == {"verdict": "x", "stouffer_z": -1.0}


def test_load_recorded_wraps_a_list_shaped_verdict_under_the_filename_stem(tmp_path):
    from tools.research import _load_recorded

    path = tmp_path / "leaderboard.json"
    path.write_text('[{"signal": "roc_sign"}, {"signal": "price_vs_ma"}]')
    recorded = _load_recorded(path, "leaderboard.json")
    assert recorded == {"leaderboard": [{"signal": "roc_sign"},
                                        {"signal": "price_vs_ma"}]}


def test_b1_lanes_registered():
    from tools.lane_registry import LANES
    assert {"calseason", "macro_event", "liqrev"} <= set(LANES)


def test_candles_run_args_builds_one_fetcher():
    from tools.lane_registry import LANES
    entry = LANES["calseason"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({"interval": "4h"}, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    assert callable(run_args[0])


def test_daily_funding_run_args_builds_symbols_list_and_two_fetchers():
    from tools.lane_registry import LANES
    entry = LANES["bab"]
    series_by_key: dict = {}
    with __import__("tempfile").TemporaryDirectory() as tmp:
        from pathlib import Path as P
        (P(tmp) / "uni1d_BTCUSDT.csv").write_text("")
        run_args = entry.run_args_builder({}, tmp, series_by_key)
    symbols, fetch_daily, fetch_funding = run_args
    assert symbols == ["BTCUSDT"]
    assert callable(fetch_daily) and callable(fetch_funding)


def test_candles_bookdepth_run_args_builds_two_callables():
    from tools.lane_registry import LANES
    entry = LANES["bookdepth_study"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({"interval": "1h"}, ".backtest_cache", series_by_key)
    assert len(run_args) == 2
    fetch_candles, fetch_metric = run_args
    assert callable(fetch_candles) and callable(fetch_metric)


def test_drift_screen_stack_path_registered_with_result_json_filename():
    entry = LANES["drift_screen_stack_path"]
    assert entry.verdict_filename == "result.json"


def test_stack_path_run_args_builds_one_loader():
    entry = LANES["drift_screen_stack_path"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({}, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    assert callable(run_args[0])


def _stack_path_cfg(**overrides) -> dict:
    from tools.lanes.drift_screen_stack_path import identity_hash

    cfg = {"timeframe": "4h", "h": 24, "atr_period": 14, "floor": 1.0,
          "min_events": 1, "min_assets": 8, "universe": ["MISSING"],
          "params": {"lookback_bars": 20, "penalty_factor": 1.0,
                    "stack_threshold": 1, "slope_threshold": 0.01,
                    "long_only": False, "atr_period": 14, "k_stop": 2.0},
          "curve_horizons": [6, 12]}
    cfg.update(overrides)
    cfg["identity_hash"] = identity_hash(cfg)
    return cfg


def test_drift_screen_stack_path_run_rejects_edited_construction(tmp_path):
    entry = LANES["drift_screen_stack_path"]
    cfg = _stack_path_cfg()
    cfg["floor"] = 2.0  # edited after identity_hash was computed
    with pytest.raises(SystemExit):
        entry.run_fn(cfg, lambda sym, tf: None, out_dir=tmp_path)


def test_drift_screen_stack_path_run_returns_registration_primary_curve(tmp_path):
    entry = LANES["drift_screen_stack_path"]
    cfg = _stack_path_cfg()
    result = entry.run_fn(cfg, lambda sym, tf: None, out_dir=tmp_path)
    assert set(result) == {"registration", "primary", "curve_descriptive"}
    assert result["registration"] == cfg
    assert result["primary"]["assets"] == []
    assert len(result["curve_descriptive"]) == 2


def test_drift_screen_registered_with_leaderboard_json_filename():
    entry = LANES["drift_screen"]
    assert entry.verdict_filename == "leaderboard.json"


def test_drift_screen_run_args_builder_builds_one_loader():
    entry = LANES["drift_screen"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({}, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    assert callable(run_args[0])


def _drift_screen_cfg(**overrides) -> dict:
    cfg = {"timeframe": "4h", "h": 24, "atr_period": 14, "floor": 1.0,
          "min_events": 1, "min_assets": 8, "universe": ["MISSING"],
          "signals": [{"name": "roc_sign", "params": {"period": 24}},
                     {"name": "price_vs_ma", "params": {"period": 100}}]}
    cfg.update(overrides)
    return cfg


def test_drift_screen_run_returns_leaderboard_wrapped_in_a_dict(tmp_path):
    entry = LANES["drift_screen"]
    cfg = _drift_screen_cfg()
    result = entry.run_fn(cfg, lambda sym, tf: None, out_dir=tmp_path)
    assert set(result) == {"leaderboard"}
    assert len(result["leaderboard"]) == len(cfg["signals"])
    assert {r["signal"] for r in result["leaderboard"]} == {"roc_sign", "price_vs_ma"}
    assert all(r["assets"] == [] for r in result["leaderboard"])


def test_drift_screen_run_sorts_by_ratio_descending(tmp_path):
    # Same empty-pool inputs regardless of order -- this only checks the run_fn
    # doesn't crash on the sort key when every ratio is None (empty pool).
    entry = LANES["drift_screen"]
    cfg = _drift_screen_cfg()
    result = entry.run_fn(cfg, lambda sym, tf: None, out_dir=tmp_path)
    assert len(result["leaderboard"]) == 2


def test_drift_screen_multifamily_registered_with_leaderboard_json_filename():
    entry = LANES["drift_screen_multifamily"]
    assert entry.verdict_filename == "leaderboard.json"


def test_multifamily_readers_run_args_builder_builds_one_readers_dict():
    entry = LANES["drift_screen_multifamily"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({}, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    readers = run_args[0]
    assert set(readers) == {"candles", "funding", "metrics", "bookdepth"}
    assert all(callable(fn) for fn in readers.values())


def _fake_multifamily_readers() -> dict:
    # Falsy candles -> load_pool_bundles omits every symbol (same empty-pool
    # precedent as _drift_screen_cfg's tests: exercises run_fn's per-family
    # loop and dict shape without needing real scoring-eligible candle data.
    return {"candles": lambda sym, tf: None,
            "funding": lambda sym: None,
            "metrics": lambda sym, field: None,
            "bookdepth": lambda sym: None}


def _multifamily_cfg(**overrides) -> dict:
    cfg = {"timeframe": "4h", "atr_period": 14, "min_events": 10,
          "min_assets": 8, "universe": ["MISSING"], "curve_horizons": [3, 6],
          "floors": {"3": 0.1, "6": 0.1},
          "families": [{"family": "funding_fade",
                        "params": {"window": 60, "z_thr": 1.5}, "h": 6},
                       {"family": "oi_build_momentum",
                        "params": {"window": 180, "lookback": 6, "z_thr": 1.5},
                        "h": 6}]}
    cfg.update(overrides)
    return cfg


def test_drift_screen_multifamily_run_returns_leaderboard_wrapped_in_a_dict(tmp_path):
    entry = LANES["drift_screen_multifamily"]
    cfg = _multifamily_cfg()
    result = entry.run_fn(cfg, _fake_multifamily_readers(), out_dir=tmp_path)
    assert set(result) == {"leaderboard"}
    assert len(result["leaderboard"]) == len(cfg["families"])
    assert {r["signal"] for r in result["leaderboard"]} == {
        "funding_fade", "oi_build_momentum"}
    assert all(r["assets"] == [] for r in result["leaderboard"])


def test_bb_candles_run_args_builds_one_loader():
    entry = LANES["bb_breakout"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({}, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    assert callable(run_args[0])


def _bb_cfg(**overrides) -> dict:
    cfg = {"symbol": "BTC/USDT:USDT", "tf": "4h", "start_ms": 0, "end_ms": 1,
          "from_1h": True}
    cfg.update(overrides)
    return cfg


def _fake_bb_loader(candles):
    return lambda sym, tf, start, end: candles


def test_bb_breakout_run_returns_n_bars_variants_slices(tmp_path):
    entry = LANES["bb_breakout"]
    result = entry.run_fn(_bb_cfg(), _fake_bb_loader([]), out_dir=tmp_path)
    assert set(result) == {"n_bars", "variants", "slices"}
    assert result["n_bars"] == 0
    assert set(result["variants"]) == {"bb_breakout"}
    assert set(result["slices"]) == {"bb_breakout"}


def test_bb_revert_run_returns_n_bars_variants_slices(tmp_path):
    entry = LANES["bb_revert"]
    result = entry.run_fn(_bb_cfg(), _fake_bb_loader([]), out_dir=tmp_path)
    assert set(result) == {"n_bars", "variants", "slices"}
    assert result["n_bars"] == 0
    assert set(result["variants"]) == {"bb_revert"}
    assert set(result["slices"]) == {"bb_revert"}


def test_bb_harvest_run_returns_results_4h_wrapped_list(tmp_path):
    entry = LANES["bb_harvest"]
    cfg = _bb_cfg(holdout_bars=0)
    result = entry.run_fn(cfg, _fake_bb_loader([]), out_dir=tmp_path)
    assert set(result) == {"results_4h"}
    assert isinstance(result["results_4h"], list) and len(result["results_4h"]) == 12
    assert all(r["stage1"]["n"] == 0 for r in result["results_4h"])


def test_ls_exit_ablation_run_returns_bars_baseline_and_rows(tmp_path):
    entry = LANES["ls_exit_ablation"]
    fetch_candles = lambda sym, start, end: []  # noqa: E731
    cfg = {"symbol": "BTCUSDT", "start_ms": 0, "end_ms": 1}
    result = entry.run_fn(cfg, fetch_candles, out_dir=tmp_path)
    assert set(result) == {"bars", "baseline_sealed_total_r", "rows"}
    assert result["bars"] == 0
    assert result["baseline_sealed_total_r"] == 0.0
    assert len(result["rows"]) == 14
    assert all(r["segments"]["sealed"]["combined"]["trade_count"] == 0
              for r in result["rows"])


def test_all_seventeen_lanes_registered():
    assert {
        "oibuild_study", "liqladder", "calseason", "macro_event", "liqrev",
        "bab", "xsection", "liqprem", "resrev", "bookdepth_study",
        "drift_screen_stack_path", "drift_screen", "drift_screen_multifamily",
        "bb_breakout", "bb_revert", "bb_harvest", "ls_exit_ablation",
    } <= set(LANES)


def test_exit_probe_registered_with_leaderboard_json_filename():
    entry = LANES["exit_probe"]
    assert entry.verdict_filename == "leaderboard.json"


def _exit_probe_cfg(**overrides) -> dict:
    cfg = {"symbol": "BTCUSDT", "interval": "1h", "start_ms": 0, "end_ms": 1,
          "oos_tail_bars": 0, "warmup": 0, "future_bars": 0}
    cfg.update(overrides)
    return cfg


def test_exit_probe_run_returns_leaderboard_wrapped_in_a_dict(tmp_path):
    entry = LANES["exit_probe"]
    fetch_candles = lambda sym, start, end: []  # noqa: E731
    result = entry.run_fn(_exit_probe_cfg(), fetch_candles, out_dir=tmp_path)
    assert set(result) == {"leaderboard"}
    assert isinstance(result["leaderboard"], list) and result["leaderboard"]
    assert all(r["research_trades"] == 0 for r in result["leaderboard"])


def test_advval_registered_with_results_json_filename():
    entry = LANES["advval"]
    assert entry.verdict_filename == "results.json"


def test_advval_run_args_builds_one_loaders_dict():
    entry = LANES["advval"]
    series_by_key: dict = {}
    cfg = {"symbol": "BTCUSDT", "funding_symbol": "BTC/USDT:USDT",
          "metrics_field": "sum_open_interest", "window_start_ms": 0,
          "window_end_ms": 1}
    run_args = entry.run_args_builder(cfg, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    loaders = run_args[0]
    assert set(loaders) == {"candles", "funding", "oi"}
    assert all(callable(fn) for fn in loaders.values())


_H4 = 14_400_000
_D1 = 86_400_000
_F8 = 28_800_000


def _advval_synth_candles(n, step, split_ms, drift_shift_after_split, seed):
    import math
    import random

    from moonface.core.models import Candle

    rng = random.Random(seed)
    start = split_ms - (n // 2) * step
    out, price = [], 100.0
    for i in range(n):
        ts = start + i * step
        shift = drift_shift_after_split if ts >= split_ms else 0.0
        r = rng.gauss(shift, 0.02)
        new = price * math.exp(r)
        hi, lo = max(price, new) * 1.001, min(price, new) * 0.999
        out.append(Candle(ts, price, hi, lo, new, abs(rng.gauss(100, 10))))
        price = new
    return out


def _advval_synth_loaders(split_ms, shift=0.03, seed=5):
    import math
    import random

    c4 = _advval_synth_candles(1200, _H4, split_ms, shift, seed)
    c1 = _advval_synth_candles(600, _D1, split_ms, shift, seed + 1)
    rng = random.Random(seed + 2)
    start = split_ms - 600 * _F8
    funding = [(start + i * _F8, rng.gauss(0.0001, 0.0002)) for i in range(1200)]
    oi = [100.0]
    for _ in range(1, len(c4)):
        oi.append(oi[-1] * math.exp(rng.gauss(0, 0.01)))
    return {
        "candles": lambda interval: c4 if interval == "4h" else c1,
        "funding": lambda: funding,
        "oi": lambda candles: list(oi[: len(candles)]),
    }


def _advval_cfg(split_ms, **overrides) -> dict:
    cfg = {
        "cells": ["price_4h", "price_1d", "funding_8h", "oi_4h"],
        "era_split_ms": split_ms,
        "gbt": {"rounds": 5, "lr": 0.1, "min_leaf": 5},
        "cv": {"n_folds": 2, "embargo": 5},
        "bootstrap": {"n_boot": 50, "seed": 1},
    }
    cfg.update(overrides)
    return cfg


@pytest.mark.slow
def test_advval_run_returns_cells_and_retrodiction(tmp_path):
    entry = LANES["advval"]
    split_ms = 1_700_000_000_000
    cfg = _advval_cfg(split_ms)
    result = entry.run_fn(cfg, _advval_synth_loaders(split_ms), out_dir=tmp_path)
    assert set(result) == {"cells", "retrodiction"}
    assert set(result["cells"]) == set(cfg["cells"])
    for cell in result["cells"].values():
        assert 0.0 <= cell["auc"] <= 1.0
    assert result["retrodiction"]["verdict"] in ("pass", "kill")
    assert result["retrodiction"]["n_studies"] > 0


def test_eventtime_registered_with_results_json_filename():
    entry = LANES["eventtime"]
    assert entry.verdict_filename == "results.json"


def test_eventtime_run_args_builds_one_loaders_dict():
    entry = LANES["eventtime"]
    series_by_key: dict = {}
    cfg = {"symbol": "BTCUSDT", "clock_timeframe": "4h",
          "calib_start_ms": 0, "calib_end_ms": 1,
          "test_start_ms": 1, "test_end_ms": 2}
    run_args = entry.run_args_builder(cfg, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    loaders = run_args[0]
    assert set(loaders) == {"calib_minutes", "test_minutes", "clock_4h"}
    assert all(callable(fn) for fn in loaders.values())


def _eventtime_synth_minutes(start_ms, n, seed, drift, quote_volume):
    import math
    import random

    from moonface.data.vision import MinuteBar

    rng = random.Random(seed)
    price = 100.0
    out = []
    for i in range(n):
        ret = rng.gauss(drift, 0.002)
        close = price * math.exp(ret)
        high, low = max(price, close) * 1.001, min(price, close) * 0.999
        base_volume = quote_volume / max((price + close) / 2.0, 1e-9)
        out.append(MinuteBar(start_ms + i * 60_000, price, high, low, close,
                             base_volume, quote_volume))
        price = close
    return out


def _eventtime_synth_clock(start_ms, n, step_ms, seed, drift):
    import math
    import random

    from moonface.core.models import Candle

    rng = random.Random(seed)
    price = 100.0
    out = []
    for i in range(n):
        ret = rng.gauss(drift, 0.01)
        close = price * math.exp(ret)
        high, low = max(price, close) * 1.002, min(price, close) * 0.998
        out.append(Candle(start_ms + i * step_ms, price, high, low, close, 1000.0))
        price = close
    return out


def _eventtime_cfg(**overrides) -> dict:
    cfg = {
        "symbol": "BTCUSDT",
        "clock_timeframe": "4h",
        "calib_start_ms": 0,
        "calib_end_ms": 600 * 60_000,
        "test_start_ms": 600 * 60_000,
        "test_end_ms": 5400 * 60_000,
        "bar_size_window_min": 240,
        "entry": {"family": "donchian_break", "params": {"n": 20}},
        "exit_rows": [["horizon_hold", {"n_bars": 12, "atr_period": 14}]],
        "fence_fraction": 0.75,
        "fraction": 0.5,
        "grid_size": 3,
        "min_improve": 0.5,
    }
    cfg.update(overrides)
    return cfg


@pytest.mark.slow
def test_eventtime_run_returns_expected_shape():
    entry = LANES["eventtime"]
    cfg = _eventtime_cfg()
    calib = _eventtime_synth_minutes(cfg["calib_start_ms"], 600, seed=11,
                                     drift=0.0001, quote_volume=1.0)
    test = _eventtime_synth_minutes(cfg["test_start_ms"], 4800, seed=17,
                                    drift=0.0004, quote_volume=120.0)
    clock = _eventtime_synth_clock(cfg["test_start_ms"], 1200, 14_400_000,
                                   seed=23, drift=0.003)
    loaders = {
        "calib_minutes": lambda: calib,
        "test_minutes": lambda: test,
        "clock_4h": lambda: clock,
    }
    result = entry.run_fn(cfg, loaders, out_dir=None)
    assert set(result) == {"bar_size", "n_dollar_bars", "n_clock_bars",
                           "clock_rows", "dollar_rows", "ladder", "verdict"}
    assert result["n_clock_bars"] == len(clock)
    assert result["verdict"]["verdict"] in ("pass", "kill")


def test_breadth_registered_with_result_json_filename():
    entry = LANES["breadth"]
    assert entry.verdict_filename == "RESULT.json"


def test_breadth_universe_run_args_builds_candles_symbols_and_daily_fetcher():
    entry = LANES["breadth"]
    series_by_key: dict = {}
    with __import__("tempfile").TemporaryDirectory() as tmp:
        from pathlib import Path as P
        (P(tmp) / "uni1d_AAA.csv").write_text("")
        run_args = entry.run_args_builder({"interval": "4h"}, tmp, series_by_key)
    fetch_candles, symbols, fetch_daily = run_args
    assert symbols == ["AAA"]
    assert callable(fetch_candles) and callable(fetch_daily)


def _candle(ts_ms):
    from moonface.core.models import Candle
    return Candle(ts_ms, 100.0, 101.0, 99.0, 100.0, 1.0)


def _breadth_universe_fixture():
    """400 days of daily history for two symbols plus 1800 4h BTC bars --
    sized so split_60_20_20's validate slice (360 bars, 60 days) clears
    universe_covers_train's 50-point default floor (same shape as
    test_universe_covers_train_guard / test_membership_fn_static_window in
    tests/research/test_breadth_cli.py, just enough bars for the val/sealed
    slices too, not just train)."""
    from moonface.research.universe_data import DailyRow

    day_ms = 86_400_000
    step_ms = day_ms // 6
    daily = {
        "AAA": [DailyRow(i * day_ms, 10 + (i % 5), 100.0) for i in range(400)],
        "BBB": [DailyRow(i * day_ms, 10 + (i % 7), 50.0) for i in range(400)],
    }
    btc = [_candle(60 * day_ms + i * step_ms) for i in range(1800)]

    def fetch_candles(sym, start, end):
        return [c for c in btc if start <= c.timestamp_ms < end]

    def fetch_daily(sym, start, end):
        return [r for r in daily.get(sym, []) if start <= r.ts_ms < end]

    cfg = {
        "symbol": "BTCUSDT", "start_ms": btc[0].timestamp_ms,
        "end_ms": btc[-1].timestamp_ms + step_ms,
        "top_n": 1, "min_history_days": 30, "vol_days": 30, "rebalance_days": 30,
    }
    return fetch_candles, fetch_daily, cfg


def test_breadth_run_returns_verdict_rows_and_btc_sha_with_no_frozen_cells(tmp_path):
    # Matches the actual frozen experiments/breadth/registration.json: 0
    # train survivors cleared the DSR gate, so frozen_cells is empty and
    # rows stays empty -- the coverage guard still runs first regardless.
    entry = LANES["breadth"]
    fetch_candles, fetch_daily, cfg = _breadth_universe_fixture()
    cfg["frozen_cells"] = []
    result = entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily,
                          out_dir=tmp_path)
    assert set(result) == {"verdict", "rows", "btc_sha"}
    assert result["rows"] == []
    assert result["verdict"] == "negative"
    assert isinstance(result["btc_sha"], str) and result["btc_sha"]


@pytest.mark.slow
def test_breadth_run_wires_validate_cell_for_frozen_keys(tmp_path):
    entry = LANES["breadth"]
    fetch_candles, fetch_daily, cfg = _breadth_universe_fixture()
    cfg["frozen_cells"] = ["pct_above_ma:20"]
    result = entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily,
                          out_dir=tmp_path)
    assert set(result) == {"verdict", "rows", "btc_sha"}
    assert len(result["rows"]) == 1
    assert result["rows"][0]["key"] == "pct_above_ma:20"
    assert set(result["rows"][0]) == {"key", "validate", "sealed", "econ",
                                      "econ_passed", "verdict"}
    assert result["verdict"] in ("paper_candidate", "negative")


def test_breadth_confirm_registered_with_result_json_filename():
    entry = LANES["breadth_confirm"]
    assert entry.verdict_filename == "RESULT.json"
    # Same universe loaders as breadth: candles + symbols + daily-klines
    # fetcher, no new run_args_builder needed.
    assert entry.run_args_builder is LANES["breadth"].run_args_builder


def test_breadth_confirm_run_reports_infeasible_slices_with_too_few_symbols(tmp_path):
    # Only 2 fixture symbols exist, but the real frozen gated_slices are rank
    # windows [20,40)/[40,60) -- no symbol occupies those ranks, so both
    # slices come back infeasible. Same trivial-path shape as breadth's
    # empty-frozen-cells test: the real historical config, not a synthetic
    # shortcut.
    entry = LANES["breadth_confirm"]
    fetch_candles, fetch_daily, base_cfg = _breadth_universe_fixture()
    cfg = {
        **base_cfg,
        "discovery_slice": [0, 20],
        "gated_slices": [[20, 40], [40, 60]],
        "k_gated": 2,
        "block_len": 20,
    }
    result = entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily,
                          out_dir=tmp_path)
    assert set(result) == {"verdict", "rows", "discovery", "btc_sha"}
    assert result["rows"] == [
        {"slice": [20, 40], "status": "infeasible"},
        {"slice": [40, 60], "status": "infeasible"},
    ]
    assert result["verdict"] == "mechanism_unconfirmed"
    assert isinstance(result["btc_sha"], str) and result["btc_sha"]


@pytest.mark.slow
def test_breadth_confirm_run_wires_the_full_confirmation_pipeline(tmp_path):
    # Rank slice [0,2) covers both fixture symbols -- feasible, exercises
    # evaluate_slice_overlap/judge_signal for real instead of short-circuiting
    # on the coverage guard.
    entry = LANES["breadth_confirm"]
    fetch_candles, fetch_daily, base_cfg = _breadth_universe_fixture()
    cfg = {
        **base_cfg,
        "discovery_slice": [0, 2],
        "gated_slices": [[0, 2]],
        "k_gated": 1,
        "block_len": 20,
    }
    result = entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily,
                          out_dir=tmp_path)
    assert set(result) == {"verdict", "rows", "discovery", "btc_sha"}
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["slice"] == [0, 2]
    assert row["status"] in ("confirmed", "mechanism_unconfirmed")
    assert set(row) == {"slice", "status", "validate_exp", "sealed_exp",
                        "pooled", "boot_lo", "p_le_zero", "same_sign",
                        "practical", "cost", "significant"}
    assert set(result["discovery"]) == {"validate_exp", "validate_n",
                                        "sealed_exp", "sealed_n"}
    assert result["verdict"] in ("confirmed", "mechanism_unconfirmed")


def test_breadth_momentum_confirm_registered_with_result_json_filename():
    entry = LANES["breadth_momentum_confirm"]
    assert entry.verdict_filename == "RESULT.json"
    # Same universe loaders as breadth/breadth_confirm: candles + symbols +
    # daily-klines fetcher, no new run_args_builder needed.
    assert entry.run_args_builder is LANES["breadth"].run_args_builder


def test_breadth_momentum_confirm_run_reports_infeasible_slices_with_too_few_symbols(tmp_path):
    # Only 2 fixture symbols exist, but the real frozen gated_slices are rank
    # windows [20,40)/[40,60) -- no symbol occupies those ranks, so both
    # slices come back infeasible. Same trivial-path shape as
    # breadth_confirm's own infeasible test.
    entry = LANES["breadth_momentum_confirm"]
    fetch_candles, fetch_daily, base_cfg = _breadth_universe_fixture()
    cfg = {
        **base_cfg,
        "discovery_slice": [0, 20],
        "gated_slices": [[20, 40], [40, 60]],
        "k_gated": 2,
        "block_len": 8,
    }
    result = entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily,
                          out_dir=tmp_path)
    assert set(result) == {"verdict", "rows", "discovery", "btc_sha"}
    assert result["rows"] == [
        {"slice": [20, 40], "status": "infeasible"},
        {"slice": [40, 60], "status": "infeasible"},
    ]
    assert result["verdict"] == "mechanism_unconfirmed"
    assert isinstance(result["btc_sha"], str) and result["btc_sha"]


@pytest.mark.slow
def test_breadth_momentum_confirm_run_wires_the_full_confirmation_pipeline(tmp_path):
    # Rank slice [0,2) covers both fixture symbols -- feasible, exercises
    # evaluate_hf_spec/judge_signal for real instead of short-circuiting on
    # the coverage guard.
    entry = LANES["breadth_momentum_confirm"]
    fetch_candles, fetch_daily, base_cfg = _breadth_universe_fixture()
    cfg = {
        **base_cfg,
        "discovery_slice": [0, 2],
        "gated_slices": [[0, 2]],
        "k_gated": 1,
        "block_len": 8,
    }
    result = entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily,
                          out_dir=tmp_path)
    assert set(result) == {"verdict", "rows", "discovery", "btc_sha"}
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["slice"] == [0, 2]
    assert row["status"] in ("confirmed", "mechanism_unconfirmed")
    assert set(row) == {"slice", "status", "validate_exp", "sealed_exp",
                        "pooled", "boot_lo", "p_le_zero", "same_sign",
                        "practical", "cost", "significant"}
    assert set(result["discovery"]) == {"validate_exp", "validate_n",
                                        "sealed_exp", "sealed_n"}
    assert result["verdict"] in ("confirmed", "mechanism_unconfirmed")


def test_breadth_neutral_registered_with_result_json_filename():
    entry = LANES["breadth_neutral"]
    assert entry.verdict_filename == "RESULT.json"
    # Same universe loaders as breadth/breadth_confirm: fetch_candles doubles
    # as the market (BTC) fetcher AND each traded asset's fetcher, no new
    # run_args_builder needed.
    assert entry.run_args_builder is LANES["breadth"].run_args_builder


@pytest.mark.slow
def test_breadth_neutral_run_wires_the_hedge_pipeline(tmp_path):
    entry = LANES["breadth_neutral"]
    fetch_candles, fetch_daily, base_cfg = _breadth_universe_fixture()
    cfg = {
        **base_cfg,
        "assets": ["ETHUSDT", "SOLUSDT"],
        # Real frozen anchor values (experiments/breadth_neutral/RESULT.json)
        # -- the fixture's synthetic series won't reproduce them, this just
        # exercises the anchor-check wiring, not asserts anchor_ok is True.
        "anchor_raw_expected": {
            "ETHUSDT/net_new_highs": 0.474,
            "ETHUSDT/breadth_momentum": 0.193,
            "SOLUSDT/net_new_highs": 0.407,
            "SOLUSDT/breadth_momentum": 0.093,
        },
    }
    result = entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily,
                          out_dir=tmp_path)
    assert set(result) == {"verdict", "rows", "anchor_ok", "anchor_raw_got"}
    assert isinstance(result["anchor_ok"], bool)
    assert set(result["anchor_raw_got"]) == set(cfg["anchor_raw_expected"])
    assert len(result["rows"]) == 4  # 2 assets x 2 leads
    for row in result["rows"]:
        assert row["asset"] in cfg["assets"]
        assert row["status"] in ("neutral_confirmed", "residual_positive",
                                 "beta_explained")
        assert set(row) == {
            "asset", "status", "lead", "raw_pooled_exp", "hedged_pooled_exp",
            "hedged_pooled_pf", "hedged_pooled_dd", "pooled_n",
            "beta_contribution", "mean_beta", "boot_lo", "p_le_zero",
            "same_sign", "practical", "cost", "significant", "verdict",
        }
    assert result["verdict"] in ("confirmed", "residual_survives", "beta_explained")


_BREADTH_XASSET_CONFIRM_ANCHOR_EXPECTED = {
    "net_new_highs": {"val_exp": 0.5323, "seal_exp": 0.2588, "val_n": 34, "seal_n": 32},
    "breadth_momentum": {"val_exp": 0.1652, "seal_exp": 0.1424, "val_n": 327, "seal_n": 326},
}


def test_breadth_xasset_confirm_registered_with_result_json_filename():
    entry = LANES["breadth_xasset_confirm"]
    assert entry.verdict_filename == "RESULT.json"
    # Same universe loaders as breadth/breadth_neutral: fetch_candles doubles
    # as the BTC anchor fetcher AND each traded asset's fetcher, no new
    # run_args_builder needed.
    assert entry.run_args_builder is LANES["breadth"].run_args_builder


def test_breadth_xasset_confirm_run_reports_infeasible_assets_with_too_few_bars(tmp_path):
    entry = LANES["breadth_xasset_confirm"]
    fetch_candles_full, fetch_daily, base_cfg = _breadth_universe_fixture()

    def fetch_candles(sym, start, end):
        candles = fetch_candles_full(sym, start, end)
        # Only the BTC anchor symbol gets the full series; asset symbols get
        # far fewer bars than the CLI's own 300-bar MIN_BARS floor.
        return candles if sym == base_cfg["symbol"] else candles[:10]

    cfg = {
        **base_cfg,
        "assets": ["ETHUSDT", "SOLUSDT"],
        "k": 4,
        "anchor_expected": _BREADTH_XASSET_CONFIRM_ANCHOR_EXPECTED,
    }
    result = entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily,
                          out_dir=tmp_path)
    assert set(result) == {"verdict", "rows", "anchor_ok", "anchors", "btc_anchor_sha"}
    assert result["rows"] == [
        {"asset": "ETHUSDT", "status": "infeasible", "bars": 10},
        {"asset": "SOLUSDT", "status": "infeasible", "bars": 10},
    ]
    assert result["verdict"] == "mechanism_unconfirmed"
    assert isinstance(result["anchor_ok"], bool)
    assert set(result["anchors"]) == {"net_new_highs", "breadth_momentum"}


@pytest.mark.slow
def test_breadth_xasset_confirm_run_wires_the_full_confirmation_pipeline(tmp_path):
    entry = LANES["breadth_xasset_confirm"]
    fetch_candles, fetch_daily, base_cfg = _breadth_universe_fixture()
    cfg = {
        **base_cfg,
        "assets": ["ETHUSDT", "SOLUSDT"],
        "k": 4,
        "anchor_expected": _BREADTH_XASSET_CONFIRM_ANCHOR_EXPECTED,
    }
    result = entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily,
                          out_dir=tmp_path)
    assert set(result) == {"verdict", "rows", "anchor_ok", "anchors", "btc_anchor_sha"}
    assert isinstance(result["anchor_ok"], bool)
    assert set(result["anchors"]) == {"net_new_highs", "breadth_momentum"}
    for lead_anchor in result["anchors"].values():
        assert set(lead_anchor) == {"ok", "validate_exp", "validate_n",
                                    "sealed_exp", "sealed_n"}
    assert len(result["rows"]) == 4  # 2 assets x 2 leads
    for row in result["rows"]:
        assert row["asset"] in cfg["assets"]
        assert row["status"] in ("confirmed", "transfers_unconfirmed", "negative")
        assert set(row) == {
            "asset", "lead", "status", "verdict", "validate_exp", "sealed_exp",
            "pooled", "boot_lo", "p_le_zero", "same_sign", "practical", "cost",
            "significant",
        }
    assert result["verdict"] in ("confirmed", "mechanism_unconfirmed")
    assert isinstance(result["btc_anchor_sha"], str) and result["btc_anchor_sha"]


def test_breadth_internal_registered_with_result_json_filename():
    entry = LANES["breadth_internal"]
    assert entry.verdict_filename == "RESULT.json"
    # Same universe loaders as breadth: breadth_internal's own CLI imports
    # breadth.py's private _load directly rather than reimplementing it, so
    # the same fetch_candles/symbols/fetch_daily primitives cover it, no new
    # run_args_builder needed.
    assert entry.run_args_builder is LANES["breadth"].run_args_builder


def test_breadth_internal_run_raises_when_universe_does_not_cover_validate_window(tmp_path):
    # Mirrors _breadth_run's own coverage guard -- unlike breadth_confirm/
    # breadth_momentum_confirm/breadth_xasset_confirm (which report a single
    # slice/asset "infeasible" and keep going), breadth_internal validates
    # ALL FOUR of all_specs()'s frozen grid over one fixed split, so an
    # uncovered validate window fails the whole run, same as breadth itself.
    entry = LANES["breadth_internal"]
    fetch_candles, _, cfg = _breadth_universe_fixture()

    def fetch_daily_empty(sym, start, end):
        return []

    with pytest.raises(RuntimeError):
        entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily_empty,
                     out_dir=tmp_path)


@pytest.mark.slow
def test_breadth_internal_run_wires_the_validation_pipeline(tmp_path):
    entry = LANES["breadth_internal"]
    fetch_candles, fetch_daily, cfg = _breadth_universe_fixture()
    result = entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily,
                          out_dir=tmp_path)
    assert set(result) == {"verdict", "rows", "btc_sha"}
    # all_specs()'s fixed 4-signal grid is validated whole every run -- no
    # discovery/select stage ever narrows it, unlike breadth's frozen_cells.
    assert len(result["rows"]) == 4
    assert {row["key"] for row in result["rows"]} == {
        "breadth_thrust", "net_new_highs", "breadth_divergence", "dispersion_regime",
    }
    for row in result["rows"]:
        assert row["verdict"] in ("paper_candidate", "forward_candidate", "negative")
        assert set(row) == {"key", "spec", "validate", "sealed", "pooled",
                            "boot_lo", "p_le_zero", "same_sign", "practical",
                            "cost", "significant", "verdict"}
    assert result["verdict"] in ("paper_candidate", "forward_candidate", "negative")
    assert isinstance(result["btc_sha"], str) and result["btc_sha"]


def test_breadth_internal_hf_registered_with_result_json_filename():
    entry = LANES["breadth_internal_hf"]
    assert entry.verdict_filename == "RESULT.json"
    # Same universe loaders as breadth: breadth_internal_hf.py's own CLI
    # imports breadth.py's private _load directly rather than reimplementing
    # it, so the same fetch_candles/symbols/fetch_daily primitives cover it --
    # a seventh reuse of the loader, unconfirmed until now per the memory's
    # own flagged uncertainty.
    assert entry.run_args_builder is LANES["breadth"].run_args_builder


def test_breadth_internal_hf_run_raises_when_universe_does_not_cover_validate_window(tmp_path):
    # Mirrors breadth_internal's own coverage guard -- no select stage exists
    # for the HF grid either, so an uncovered validate window fails the whole
    # run rather than degrading one slice.
    entry = LANES["breadth_internal_hf"]
    fetch_candles, _, cfg = _breadth_universe_fixture()

    def fetch_daily_empty(sym, start, end):
        return []

    with pytest.raises(RuntimeError):
        entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily_empty,
                     out_dir=tmp_path)


@pytest.mark.slow
def test_breadth_internal_hf_run_wires_the_validation_pipeline(tmp_path):
    entry = LANES["breadth_internal_hf"]
    fetch_candles, fetch_daily, cfg = _breadth_universe_fixture()
    result = entry.run_fn(cfg, fetch_candles, ["AAA", "BBB"], fetch_daily,
                          out_dir=tmp_path)
    assert set(result) == {"verdict", "rows", "btc_sha"}
    # hf_specs()'s fixed 3-signal grid is validated whole every run -- no
    # discovery/select stage ever narrows it, same shape as breadth_internal.
    assert len(result["rows"]) == 3
    assert {row["key"] for row in result["rows"]} == {
        "breadth_oscillator", "breadth_momentum", "breadth_accel",
    }
    for row in result["rows"]:
        assert row["verdict"] in ("paper_candidate", "forward_candidate", "negative")
        assert set(row) == {"key", "spec", "validate", "sealed", "pooled",
                            "boot_lo", "p_le_zero", "same_sign", "practical",
                            "cost", "significant", "verdict"}
    assert result["verdict"] in ("paper_candidate", "forward_candidate", "negative")
    assert isinstance(result["btc_sha"], str) and result["btc_sha"]


def _donchian_filter_fixture():
    from dataclasses import dataclass

    @dataclass
    class C:
        open: float
        high: float
        low: float
        close: float
        timestamp_ms: int

    candles = []
    step = 14_400_000
    for i in range(800):
        phase = (i // 100) % 2
        base = 100.0 + (i if phase == 0 else 100 + (i % 7))
        candles.append(C(open=base, high=base + 1.0, low=base - 1.0,
                         close=base + 0.4, timestamp_ms=i * step))

    def fetch_candles(sym, start, end):
        return candles

    def fetch_funding(sym, start, end):
        return None

    cfg = {"symbol": "BTCUSDT", "interval": "4h", "start_ms": 0,
           "end_ms": 800 * step, "adx_period": 14, "frozen_threshold": 20}
    return fetch_candles, fetch_funding, cfg


def test_donchian_filter_registered_with_result_json_filename():
    entry = LANES["donchian_filter"]
    assert entry.verdict_filename == "RESULT.json"
    assert entry.code_paths == ("tools/donchian_filter/donchian_filter.py",)


def test_donchian_filter_run_wires_the_holdout_pipeline(tmp_path):
    entry = LANES["donchian_filter"]
    fetch_candles, fetch_funding, cfg = _donchian_filter_fixture()
    result = entry.run_fn(cfg, fetch_candles, fetch_funding, out_dir=tmp_path)
    assert set(result) == {"threshold", "sealed_base", "sealed_gated", "verdict"}
    assert result["threshold"] == 20
    assert result["verdict"] in {"IMPROVES", "NEUTRAL", "DESTROYS_INACTIVE"}
    assert set(result["sealed_base"]) == {"n", "net_r", "expectancy_r",
                                          "profit_factor", "max_dd_r", "mar"}
    # gated is a strict ADX-filtered subset of base -- never more trades.
    assert result["sealed_gated"]["n"] <= result["sealed_base"]["n"]


def _btc_classic_fixture():
    from dataclasses import dataclass

    @dataclass
    class C:
        open: float
        high: float
        low: float
        close: float
        timestamp_ms: int

    candles = []
    step = 14_400_000
    for i in range(800):
        phase = (i // 100) % 2
        base = 100.0 + (i if phase == 0 else 100 + (i % 7))
        candles.append(C(open=base, high=base + 1.0, low=base - 1.0,
                         close=base + 0.4, timestamp_ms=i * step))

    def fetch_candles(sym, start, end):
        return candles

    def fetch_funding(sym, start, end):
        return []

    cfg = {"symbol": "BTCUSDT", "interval": "4h", "start_ms": 0,
           "end_ms": 800 * step}
    return fetch_candles, fetch_funding, cfg


def test_btc_classic_registered_with_result_json_filename():
    entry = LANES["btc_classic"]
    assert entry.verdict_filename == "RESULT.json"
    assert entry.code_paths == ("tools/btc_classic/btc_classic.py",)


def test_btc_classic_run_wires_the_from_scratch_judging_pipeline(tmp_path):
    entry = LANES["btc_classic"]
    fetch_candles, fetch_funding, cfg = _btc_classic_fixture()
    result = entry.run_fn(cfg, fetch_candles, fetch_funding, out_dir=tmp_path)
    assert set(result) == {"verdict", "rows", "btc_sha"}
    assert len(result["rows"]) == 6  # K=6 frozen classical family
    for row in result["rows"]:
        assert row["verdict"] in ("paper_candidate", "forward_candidate", "negative")
        assert set(row) == {"key", "spec", "validate", "sealed", "pooled",
                            "boot_lo", "p_le_zero", "same_sign", "practical",
                            "cost", "significant", "verdict"}
    assert result["verdict"] in ("paper_candidate", "forward_candidate", "negative")
    assert isinstance(result["btc_sha"], str) and result["btc_sha"]


def _donchian_volregime_fixture():
    from dataclasses import dataclass

    @dataclass
    class C:
        open: float
        high: float
        low: float
        close: float
        timestamp_ms: int

    candles = []
    step = 14_400_000
    for i in range(800):
        phase = (i // 100) % 2
        base = 100.0 + (i if phase == 0 else 100 + (i % 7))
        candles.append(C(open=base, high=base + 1.0, low=base - 1.0,
                         close=base + 0.4, timestamp_ms=i * step))

    def fetch_candles(sym, start, end):
        return candles

    def fetch_funding(sym, start, end):
        return None

    cfg = {"symbol": "BTCUSDT", "interval": "4h", "start_ms": 0,
           "end_ms": 800 * step, "frozen_cell": None}
    return fetch_candles, fetch_funding, cfg


def test_donchian_volregime_registered_with_result_json_filename():
    entry = LANES["donchian_volregime"]
    assert entry.verdict_filename == "RESULT.json"
    assert entry.code_paths == ("tools/donchian_volregime/donchian_volregime.py",)


def test_donchian_volregime_run_returns_negative_when_no_frozen_cell():
    entry = LANES["donchian_volregime"]
    fetch_candles, fetch_funding, cfg = _donchian_volregime_fixture()
    result = entry.run_fn(cfg, fetch_candles, fetch_funding, out_dir=None)
    assert result == {"verdict": "negative"}


def test_donchian_volregime_run_wires_the_gate_pipeline_when_a_cell_is_frozen():
    entry = LANES["donchian_volregime"]
    fetch_candles, fetch_funding, cfg = _donchian_volregime_fixture()
    cfg["frozen_cell"] = "atr_pct"
    result = entry.run_fn(cfg, fetch_candles, fetch_funding, out_dir=None)
    assert set(result) == {"cell", "sealed_base", "sealed_gated", "verdict"}
    assert result["cell"] == "atr_pct"
    assert set(result["sealed_base"]) == {"n", "net_r", "expectancy_r",
                                          "profit_factor", "max_dd_r", "mar"}
    # gated is a strict regime-filtered subset of base -- never more trades.
    assert result["sealed_gated"]["n"] <= result["sealed_base"]["n"]
    assert result["verdict"] in {"PAPER_CANDIDATE", "NEGATIVE", "INACTIVE"}


def _regime_overlay_fixture():
    from dataclasses import dataclass

    from moonface.data.macro import MacroPoint

    @dataclass
    class C:
        open: float
        high: float
        low: float
        close: float
        timestamp_ms: int

    step = 14_400_000
    candles = []
    for i in range(800):
        phase = (i // 100) % 2
        base = 100.0 + (i if phase == 0 else 100 + (i % 7))
        candles.append(C(open=base, high=base + 1.0, low=base - 1.0,
                         close=base + 0.4, timestamp_ms=i * step))

    def fetch_candles(sym, start, end):
        return candles

    def fetch_funding(sym, start, end):
        return None

    day_ms = 86_400_000

    def series(value_fn):
        out = []
        ts = -150 * day_ms
        i = 0
        end = 800 * step
        while ts <= end:
            out.append(MacroPoint(ts_ms=ts, value=value_fn(i)))
            ts += day_ms
            i += 1
        return out

    macro = {
        "SP500": series(lambda i: 100.0 + i * 0.1),
        "VIXCLS": series(lambda i: 15.0),
        "DTWEXBGS": series(lambda i: 100.0 - i * 0.05),
    }

    def fetch_macro():
        return macro

    cfg = {"symbol": "BTCUSDT", "interval": "4h", "start_ms": 0,
           "end_ms": 800 * step, "frozen_cell": None}
    return fetch_candles, fetch_funding, fetch_macro, cfg


def test_regime_overlay_registered_with_result_json_filename():
    entry = LANES["regime_overlay"]
    assert entry.verdict_filename == "RESULT.json"
    assert entry.code_paths == ("tools/regime_overlay/regime_overlay_btc.py",)


def test_regime_overlay_run_returns_negative_when_no_frozen_cell():
    entry = LANES["regime_overlay"]
    fetch_candles, fetch_funding, fetch_macro, cfg = _regime_overlay_fixture()
    result = entry.run_fn(cfg, fetch_candles, fetch_funding, fetch_macro,
                          out_dir=None)
    assert result == {"verdict": "negative"}


def test_regime_overlay_run_wires_the_cell_pipeline_when_a_cell_is_frozen():
    entry = LANES["regime_overlay"]
    fetch_candles, fetch_funding, fetch_macro, cfg = _regime_overlay_fixture()
    cfg["frozen_cell"] = "R1-directional"
    result = entry.run_fn(cfg, fetch_candles, fetch_funding, fetch_macro,
                          out_dir=None)
    assert set(result) == {"cell", "sealed_cell_vector", "sealed_base_vector",
                           "practical_pass", "beats_base", "verdict"}
    assert result["cell"] == "R1-directional"
    assert set(result["sealed_cell_vector"]) == {
        "trades", "net_r", "expectancy_r", "profit_factor", "max_drawdown_r",
        "trailing_365d_net_r", "net_r_ex_best1", "cost_stress"}
    # cell vector's cost_stress is always computed from the same overlaid
    # trade set as its net_r -- 1x cost matches net_r exactly.
    assert result["sealed_cell_vector"]["cost_stress"]["net_r_1x"] == \
        result["sealed_cell_vector"]["net_r"]
    assert result["verdict"] in {"forward_paper_watch", "negative"}


def _regime_selector_fixture():
    from dataclasses import dataclass

    from moonface.data.macro import MacroPoint

    @dataclass
    class C:
        open: float
        high: float
        low: float
        close: float
        timestamp_ms: int

    step = 14_400_000
    candles = []
    for i in range(800):
        phase = (i // 100) % 2
        base = 100.0 + (i if phase == 0 else 100 + (i % 7))
        candles.append(C(open=base, high=base + 1.0, low=base - 1.0,
                         close=base + 0.4, timestamp_ms=i * step))

    def fetch_candles(sym, start, end):
        return candles

    day_ms = 86_400_000

    def series(value_fn):
        out = []
        ts = -150 * day_ms
        i = 0
        end = 800 * step
        while ts <= end:
            out.append(MacroPoint(ts_ms=ts, value=value_fn(i)))
            ts += day_ms
            i += 1
        return out

    macro = {
        "SP500": series(lambda i: 100.0 + i * 0.1),
        "VIXCLS": series(lambda i: 15.0),
        "DTWEXBGS": series(lambda i: 100.0 - i * 0.05),
    }

    def fetch_macro():
        return macro

    cfg = {"symbol": "BTCUSDT", "interval": "4h", "start_ms": 0,
           "end_ms": 800 * step, "frozen_cell": None}
    return fetch_candles, fetch_macro, cfg


def test_regime_selector_registered_with_result_json_filename():
    entry = LANES["regime_selector"]
    assert entry.verdict_filename == "RESULT.json"
    assert entry.code_paths == ("tools/regime_selector/regime_selector_btc.py",)


def test_regime_selector_run_returns_negative_when_no_frozen_cell():
    entry = LANES["regime_selector"]
    fetch_candles, fetch_macro, cfg = _regime_selector_fixture()
    result = entry.run_fn(cfg, fetch_candles, fetch_macro, out_dir=None)
    assert result == {"verdict": "negative"}


def test_regime_selector_run_wires_the_cell_pipeline_when_a_cell_is_frozen():
    entry = LANES["regime_selector"]
    fetch_candles, fetch_macro, cfg = _regime_selector_fixture()
    cfg["frozen_cell"] = "R1-switch"
    result = entry.run_fn(cfg, fetch_candles, fetch_macro, out_dir=None)
    assert set(result) == {"cell", "sealed_cell_vector", "sealed_trend_control",
                           "sealed_mr_control", "practical_pass",
                           "beats_controls", "verdict"}
    assert result["cell"] == "R1-switch"
    assert set(result["sealed_cell_vector"]) == {
        "trades", "net_r", "expectancy_r", "profit_factor", "max_drawdown_r",
        "trailing_365d_net_r", "net_r_ex_best1", "cost_stress"}
    # cell vector's cost_stress is always computed from the same overlaid
    # trade set as its net_r -- 1x cost matches net_r exactly.
    assert result["sealed_cell_vector"]["cost_stress"]["net_r_1x"] == \
        result["sealed_cell_vector"]["net_r"]
    assert set(result["beats_controls"]) == {"beats_net", "beats_both"}
    assert result["verdict"] in {"paper_accept", "negative"}


def test_fifty_four_lanes_registered():
    assert set(LANES) == {
        "oibuild_study", "liqladder", "calseason", "macro_event", "liqrev",
        "bab", "xsection", "liqprem", "resrev", "bookdepth_study",
        "drift_screen_stack_path", "drift_screen", "drift_screen_multifamily",
        "bb_breakout", "bb_revert", "bb_harvest", "ls_exit_ablation",
        "exit_probe", "advval", "eventtime", "breadth", "breadth_confirm",
        "breadth_momentum_confirm", "breadth_neutral", "breadth_xasset_confirm",
        "breadth_internal", "breadth_internal_hf", "donchian_filter",
        "btc_classic", "donchian_volregime", "regime_overlay", "regime_selector",
        "ls_tournament", "sse", "portfolio", "liq_twap", "consolidated_ls",
        "matrix", "mtf_transfer", "mtf_basket", "mtf_broaden", "mtf_long_only",
        "donchian_revalidate", "vrp_measure", "carry_measure",
        "edge_search_swing_4h", "edge_search_day_15m", "playbook", "practical",
        "practical_full", "btcspec", "btcspec_s2", "btcspec_s3", "exogenous",
    }


def _ls_tournament_fixture():
    from dataclasses import dataclass

    @dataclass
    class C:
        open: float
        high: float
        low: float
        close: float
        timestamp_ms: int

    step = 14_400_000
    candles = []
    for i in range(800):
        base = 100.0 + i
        candles.append(C(open=base, high=base + 1.0, low=base - 1.0,
                         close=base + 0.4, timestamp_ms=i * step))

    def fetch_candles(tf, sym, start, end):
        return candles

    def fetch_funding(sym, start, end):
        return []

    def fetch_macro():
        return {}

    def fetch_oi(sym, start, end):
        return []

    cfg = {"symbol": "BTCUSDT", "start_ms": 0, "end_ms": 800 * step,
          "frozen_rows": []}
    return fetch_candles, fetch_funding, fetch_macro, fetch_oi, cfg


_LS_TOURNAMENT_ROW = {
    "label": "4h:core_donchian_break:n=100:long=donchian_break(n=100):"
            "short=donchian_break(n=100):atr_trail:atr_period=14,k_trail=2.0,max_bars=120",
    "timeframe": "4h",
    "long_rule": {"family": "donchian_break", "params": {"n": 100}},
    "short_rule": {"family": "donchian_break", "params": {"n": 100}},
    "filters": [],
    "exit_name": "atr_trail",
    "exit_params": {"atr_period": 14, "k_trail": 2.0, "max_bars": 120},
    "h": 48,
    "group": "4h:core_donchian_break:long=donchian_break:short=donchian_break:atr_trail",
    "axis": 100.0,
}


def test_ls_tournament_registered_with_result_json_filename():
    entry = LANES["ls_tournament"]
    assert entry.verdict_filename == "RESULT.json"
    assert entry.code_paths == ("tools/ls_tournament/ls_tournament.py",)


def test_ls_tournament_run_args_builds_four_loaders():
    entry = LANES["ls_tournament"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({}, ".backtest_cache", series_by_key)
    assert len(run_args) == 4
    assert all(callable(f) for f in run_args)


def test_ls_tournament_run_returns_negative_with_no_frozen_rows():
    entry = LANES["ls_tournament"]
    fetch_candles, fetch_funding, fetch_macro, fetch_oi, cfg = _ls_tournament_fixture()
    result = entry.run_fn(cfg, fetch_candles, fetch_funding, fetch_macro, fetch_oi,
                          out_dir=None)
    assert result["verdict"] == "negative"
    assert result["rows"] == []
    assert set(result["data_fingerprint"]) == {"2h", "4h"}
    for fp in result["data_fingerprint"].values():
        assert fp["bars"] == 800
        assert isinstance(fp["sha"], str)


def test_ls_tournament_run_wires_the_validate_pipeline_when_a_row_is_frozen():
    entry = LANES["ls_tournament"]
    fetch_candles, fetch_funding, fetch_macro, fetch_oi, cfg = _ls_tournament_fixture()
    cfg["frozen_rows"] = [_LS_TOURNAMENT_ROW]
    result = entry.run_fn(cfg, fetch_candles, fetch_funding, fetch_macro, fetch_oi,
                          out_dir=None)
    assert set(result) == {"verdict", "rows", "data_fingerprint"}
    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["label"] == _LS_TOURNAMENT_ROW["label"]
    assert set(row) >= {"train", "validate", "sealed", "train_passed", "verdict"}
    assert row["verdict"] in {"paper_candidate", "negative"}
    # monotonic uptrend candles guarantee real long-side donchian breakouts in
    # every segment -- this is not the trivial zero-trade path.
    assert row["validate"]["trade_count"] > 0
    assert row["sealed"]["trade_count"] > 0
    assert result["verdict"] == row["verdict"]


def test_sse_registered_with_gate0_verdict_json_filename():
    entry = LANES["sse"]
    assert entry.verdict_filename == "gate0_verdict.json"
    assert entry.code_paths == ("tools/sse/sse.py",)


def test_sse_run_args_composes_universe_loaders_and_readers_dict():
    entry = LANES["sse"]
    series_by_key: dict = {}
    with __import__("tempfile").TemporaryDirectory() as tmp:
        from pathlib import Path as P
        (P(tmp) / "uni1d_AAA.csv").write_text("")
        run_args = entry.run_args_builder({"interval": "4h"}, tmp, series_by_key)
    fetch_candles, symbols, fetch_daily, readers = run_args
    assert symbols == ["AAA"]
    assert callable(fetch_candles) and callable(fetch_daily)
    assert set(readers) == {"candles", "funding", "metrics", "bookdepth"}
    assert all(callable(fn) for fn in readers.values())


def _sse_fixture():
    """A 40-symbol pool (BTC + 39 synthetic) on a 3-day-step clock spanning
    the real 2020-01-01..2026-07-01 ERA_BOUNDS window (a module-level
    constant in tools.sse.sse, not cfg-overridable, so era_stability can only
    be exercised with real-calendar timestamps) -- ~793 bars total, cheap
    enough to fit-and-bootstrap in seconds. axes_ma_period/axes_ret_bars/
    axes_z_window/traj_lookback/traj_z_window are all shrunk well below
    their sse.run_gate0 defaults (300/6/540/20/540) so Track N's warmup fits
    inside one era (912 days / 3-day step = 304 bars); Track L's own
    warmup floor is fixed at ~222 bars (RVOL_WINDOW=20 + Z_WINDOW=180 from
    moonface.research.microscope.features, not exposed as a run_gate0 kwarg
    at all) and 304 bars clears it with room to spare. top_n=45 (comfortably
    above sse.axes.MIN_ACTIVE=30, itself not cfg-overridable either) keeps
    every one of the 39 synthetic symbols an active member throughout."""
    import math

    from moonface.core.models import Candle
    from moonface.data.universe import DailyRow

    step = 259_200_000  # 3 days
    start = 1_577_836_800_000  # 2020-01-01, matches ERA_BOUNDS[0][0]
    end = 1_783_123_200_000  # 2026-07-01, matches ERA_BOUNDS[-1][1]
    day_ms = 86_400_000
    n_bars = (end - start) // step + 1
    n_days = (end - start) // day_ms + 1
    symbols = ["BTCUSDT"] + [f"AAA{i:02d}" for i in range(39)]

    candles_by_sym = {}
    for k, sym in enumerate(symbols):
        bars = []
        for i in range(n_bars):
            ts = start + i * step
            close = 100.0 + 10.0 * math.sin((i + k * 3) * 0.3) + i * 0.02
            bars.append(Candle(ts, close, close + 1.0, close - 1.0, close, 1.0))
        candles_by_sym[sym] = bars

    daily_by_sym = {
        sym: [DailyRow(start + d * day_ms, 100.0, 1000.0 + (d % 7) * 10)
             for d in range(n_days)]
        for sym in symbols
    }

    def fetch_candles(sym, s, e):
        return [c for c in candles_by_sym.get(sym, []) if s <= c.timestamp_ms < e]

    def fetch_daily(sym, s, e):
        return [r for r in daily_by_sym.get(sym, []) if s <= r.ts_ms < e]

    def fake_funding(sym):
        return [0.01 * math.sin(i * 0.5) for i in range(n_bars)]

    def fake_metrics(sym, field):
        return [1000.0 + 10.0 * math.cos(i * 0.4) for i in range(n_bars)]

    readers = {"funding": fake_funding, "metrics": fake_metrics}
    cfg = {
        "btc_symbol": "BTCUSDT", "start_ms": start, "end_ms": end,
        "top_n": 45, "min_history_days": 2, "vol_days": 5, "horizon": 2,
        "draws": 5, "axes_ma_period": 20, "axes_ret_bars": 3,
        "axes_z_window": 60, "traj_lookback": 5, "traj_z_window": 60,
    }
    return fetch_candles, symbols, fetch_daily, readers, cfg


@pytest.mark.slow
def test_sse_run_wires_the_full_gate0_pipeline(tmp_path):
    entry = LANES["sse"]
    fetch_candles, symbols, fetch_daily, readers, cfg = _sse_fixture()
    result = entry.run_fn(cfg, fetch_candles, symbols, fetch_daily, readers,
                          out_dir=tmp_path)
    assert set(result) == {"verdict", "chosen_cell", "points", "trajectories"}
    assert result["verdict"] == "PENDING_GATE1"
    assert result["chosen_cell"] == "points"
    assert result["points"]["verdict"] == "PASS"
    assert result["trajectories"]["verdict"] == "FAIL"
    assert (tmp_path / "gate0_verdict.json").exists()
    assert (tmp_path / "gate0_report.md").exists()


def test_portfolio_registered_with_explore_leaderboard_json_filename():
    entry = LANES["portfolio"]
    assert entry.verdict_filename == "explore_leaderboard.json"
    assert entry.code_paths == ("tools/portfolio/portfolio_search.py",)


def test_portfolio_run_args_builds_a_multi_timeframe_candle_fetcher():
    entry = LANES["portfolio"]
    series_by_key: dict = {}
    with __import__("tempfile").TemporaryDirectory() as tmp:
        run_args = entry.run_args_builder({}, tmp, series_by_key)
    (fetch_candles,) = run_args
    assert callable(fetch_candles)
    assert fetch_candles("BTCUSDT", "1h", 0, 1) == []
    assert set(series_by_key) == {"BTCUSDT:candles:1h"}


def _portfolio_fixture():
    """1200 1h bars (50 days) + 300 4h bars over the identical window --
    component_positions reads native_by_tf[cell.timeframe] from the FULL
    by_tf dict (not the train_oos-sliced one), so the 4h series must span
    the whole window, not just the first 60%. Warmup needs: 1h side maxes
    out at vol_regime's window=48 (grid_candles has 720 bars after the 60%
    split, far more); 4h side maxes out at ma_cross's slow=100 (300 4h bars
    clears it with 200 to spare). Sine + linear drift gives every family
    real crossings/breakouts to act on, not an all-zero position series."""
    import math

    from moonface.core.models import Candle

    start = 1_577_836_800_000  # 2020-01-01
    hour_ms = 3_600_000
    n_1h = 1200
    n_4h = 300

    def _candles(n, step_ms, seed):
        out = []
        for i in range(n):
            ts = start + i * step_ms
            close = 100.0 + 8.0 * math.sin((i + seed) * 0.15) + i * 0.03
            out.append(Candle(ts, close, close + 1.0, close - 1.0, close, 1.0))
        return out

    by_tf = {
        "1h": _candles(n_1h, hour_ms, seed=0),
        "4h": _candles(n_4h, hour_ms * 4, seed=1),
    }

    def fetch_candles(sym, tf, s, e):
        return [c for c in by_tf[tf] if s <= c.timestamp_ms < e]

    cfg = {"symbol": "BTCUSDT", "start_ms": start,
          "end_ms": start + n_1h * hour_ms}
    return fetch_candles, cfg


@pytest.mark.slow
def test_portfolio_run_wires_the_full_explore_pipeline(tmp_path):
    entry = LANES["portfolio"]
    fetch_candles, cfg = _portfolio_fixture()
    result = entry.run_fn(cfg, fetch_candles, out_dir=tmp_path)
    assert set(result) == {"explore_leaderboard"}
    rows = result["explore_leaderboard"]
    assert [r["label"] for r in rows] == [
        "vote_2", "vote_majority", "vol_target_vote_24", "vol_target_vote_48",
        "vol_target_lsn_24", "vol_target_lsn_48", "regime_switch", "long_short_net"]
    for r in rows:
        assert set(r) >= {"label", "operator", "kw", "positions", "returns",
                          "metrics", "dsr", "screen"}
        assert len(r["positions"]) == len(r["returns"])
        assert set(r["dsr"]) >= {"dsr", "passed", "sharpe"}
        # Every row's screen dict comes from the SAME step0_screen() call --
        # the json.dumps(default=str)/json.loads round-trip (mirroring the
        # recorded file's own default=str write) breaks object identity, so
        # compare by value, not `is`; deliberately not asserted per-field
        # (basket/matrix are large and change with any component tweak).
        assert r["screen"] == rows[0]["screen"]
    assert rows[0]["screen"]["basket_size"] >= 2


def test_liq_twap_registered_with_default_verdict_json_filename():
    entry = LANES["liq_twap"]
    assert entry.verdict_filename == "verdict.json"
    assert entry.code_paths == ("tools/liq_twap/liq_twap_screen.py",)


def test_liq_twap_run_args_reuses_candles_metric_run_args():
    # Same builder oibuild_study/liqrev already use -- confirms the (fetch_
    # candles, fetch_metric) shape rather than asserting `is` identity, since
    # _candles_metric_run_args is a plain function, not a bound singleton.
    entry = LANES["liq_twap"]
    series_by_key: dict = {}
    cfg = {"interval": "1h", "metrics_field": "sum_open_interest"}
    with __import__("tempfile").TemporaryDirectory() as tmp:
        run_args = entry.run_args_builder(cfg, tmp, series_by_key)
    fetch_candles, fetch_metric = run_args
    assert callable(fetch_candles) and callable(fetch_metric)
    assert fetch_candles("BTC/USDT:USDT", 0, 1) == []
    assert fetch_metric("BTCUSDT", 0, 1) == []
    assert set(series_by_key) == {"BTC/USDT:USDT:candles", "BTCUSDT:metric"}


def _liq_twap_fixture():
    """400 1h bars: a low-variance random-walk baseline (seed=42, deterministic)
    with 18 deliberate "spike" bars inserted every 10 bars from i=200 (past
    signals.py's WINDOW=180 z-score warmup) through i=370 (well clear of the
    tail's h<=4 forward-outcome lookahead) -- alternating up/down body
    direction and alternating a strong OI drop (oi *= 0.85, a treat cascade)
    against a strong OI rise (oi *= 1.05, the vol-matched non-drop control),
    each spike's body ~6% of price and volume 50x the ~100-unit baseline so
    every spike clears m=1.5 (body/ATR) and both k in {1.5, 2.0} (volume
    level-z AND OI z-score) -- verified by hand against make_liq_cascade
    directly before writing this fixture, not guessed: all 18 spikes clear
    even k=2.0, so k=1.5/k=2.0 cells are identical (n=9 each) by
    construction, not a fixture bug."""
    import random

    from moonface.core.models import Candle

    rng = random.Random(42)
    n = 400
    ts0 = 1_600_000_000_000
    tf_ms = 3_600_000
    treat_idx = set(range(200, 380, 20))
    ctrl_idx = set(range(210, 380, 20))
    candles: list[Candle] = []
    oi: list[float] = []
    price = 30000.0
    oi_val = 40000.0
    for i in range(n):
        if i in treat_idx or i in ctrl_idx:
            direction = 1 if i % 40 < 20 else -1
            body = direction * price * 0.06
            o, c = price, price + body
            h = max(o, c) + abs(body) * 0.05
            l = min(o, c) - abs(body) * 0.05
            vol = 5000.0
            oi_val *= 0.85 if i in treat_idx else 1.05
            price = c
        else:
            drift = rng.uniform(-0.001, 0.001)
            o, c = price, price * (1 + drift)
            h, l = max(o, c) * 1.0005, min(o, c) * 0.9995
            vol = 100.0 + rng.uniform(-5, 5)
            oi_val *= 1 + rng.uniform(-0.0005, 0.0005)
            price = c
        candles.append(Candle(ts0 + i * tf_ms, o, h, l, c, vol))
        oi.append(oi_val)

    def fetch_candles(sym, start, end):
        return [c for c in candles if start <= c.timestamp_ms < end]

    def fetch_metric(sym, start, end):
        return [(c.timestamp_ms, v) for c, v in zip(candles, oi)
               if start <= c.timestamp_ms < end]

    cfg = {"start_ms": ts0, "end_ms": ts0 + n * tf_ms}
    return fetch_candles, fetch_metric, cfg


@pytest.mark.slow
def test_liq_twap_run_wires_the_full_screen_pipeline(tmp_path):
    entry = LANES["liq_twap"]
    fetch_candles, fetch_metric, cfg = _liq_twap_fixture()
    result = entry.run_fn(cfg, fetch_candles, fetch_metric, out_dir=tmp_path)
    assert set(result) == {"cells", "treat_mean", "ctrl_mean", "null_max_z", "verdict"}
    assert [(c["k"], c["h"], c["n"]) for c in result["cells"]] == [
        (1.5, 1, 9), (1.5, 2, 9), (1.5, 3, 9), (1.5, 4, 9),
        (2.0, 1, 9), (2.0, 2, 9), (2.0, 3, 9), (2.0, 4, 9)]
    # k=1.5 and k=2.0 cells agree on everything but "k" itself, by
    # construction (every spike clears even the higher threshold) -- a real
    # cross-check, not a tautology, since cell_stats recomputes
    # independently per k.
    for i in range(4):
        lo, hi = dict(result["cells"][i]), dict(result["cells"][i + 4])
        del lo["k"], hi["k"]
        assert lo == hi
    assert result["treat_mean"] == pytest.approx(-0.0011186931308320516)
    assert result["ctrl_mean"] == pytest.approx(0.009285217146293523)
    assert result["null_max_z"] == pytest.approx(1.5206001471974777)
    assert result["verdict"]["passed"] is False
    assert result["verdict"]["conditions"] == {
        "sign_positive": False, "floor": False, "robust": False,
        "treatment_gt_control": False, "null_fails": True}


def _consolidated_ls_fixture():
    """The largest fixture in this file: consolidated_ls's runner.run drives
    10 adapters (btc_classic/breadth_internal/donchian/regime_overlay/
    regime_selector/practical/btcspec/ls_tournament/playbook/engine), each
    reusing an already-solved fixture shape from an earlier slice rather than
    inventing new bar counts: 800 4h bars (same span as _regime_overlay_
    fixture/_ls_tournament_fixture), matching 1h/2h series over the identical
    calendar window (same multi-tf-from-one-price-path approach as
    _portfolio_fixture, needed for playbook's MTFView.build and engine's
    replay(warmup=400)), a 2-symbol AAA/BBB daily universe (same top_n=1
    simplified cfg as _breadth_universe_fixture, needed for breadth_internal
    + the runtime universe_covers_train guard), and a FRED macro fixture
    starting 150 days before the window (same shape as _regime_overlay_
    fixture's series() helper, needed for regime_overlay/regime_selector).
    funding=[] throughout -- proven safe through both align_funding
    (_btc_classic_fixture) and _overlaid_rt's raw-points path."""
    import math

    from moonface.core.models import Candle
    from moonface.data.macro import MacroPoint
    from moonface.research.universe_data import DailyRow

    day_ms = 86_400_000
    step_4h = 14_400_000
    n_4h = 800
    start_ms = 100 * day_ms
    end_ms = start_ms + n_4h * step_4h

    def _price_series(step_ms, n, seed):
        out = []
        for i in range(n):
            ts = start_ms + i * step_ms
            close = 100.0 + 8.0 * math.sin((i + seed) * 0.05) + i * 0.01
            out.append(Candle(ts, close, close + 1.0, close - 1.0, close, 1.0))
        return out

    by_tf = {
        "4h": _price_series(step_4h, n_4h, seed=0),
        "2h": _price_series(step_4h // 2, n_4h * 2, seed=1),
        "1h": _price_series(step_4h // 4, n_4h * 4, seed=2),
    }

    def fetch_candles(tf, sym, start, end):
        return [c for c in by_tf[tf] if start <= c.timestamp_ms < end]

    def fetch_funding(sym, start, end):
        return []

    # Daily history starts at day 0, well before start_ms (day 100) --
    # runner.run's own universe_covers_train guard checks the TRAIN slice
    # (the window's first 60%, i.e. the EARLIEST part of the window), unlike
    # breadth's own equivalent test which checks the validate slice instead
    # (60-80%) -- build_universe's min_history_days floor
    # (rows[0].ts_ms <= asof - min_history_days*day_ms) can only be cleared
    # this early if daily[sym]'s first row predates start_ms, so fetch_daily
    # deliberately does not filter the lower bound (only "< end"), unlike
    # _breadth_universe_fixture's fetch_daily.
    daily = {
        "AAA": [DailyRow(i * day_ms, 10 + (i % 5), 100.0) for i in range(400)],
        "BBB": [DailyRow(i * day_ms, 10 + (i % 7), 50.0) for i in range(400)],
    }

    def fetch_daily(sym, start, end):
        return [r for r in daily.get(sym, []) if r.ts_ms < end]

    def _macro_series(value_fn):
        out = []
        ts = start_ms - 150 * day_ms
        i = 0
        while ts <= end_ms:
            out.append(MacroPoint(ts_ms=ts, value=value_fn(i)))
            ts += day_ms
            i += 1
        return out

    macro = {
        "SP500": _macro_series(lambda i: 100.0 + i * 0.1),
        "VIXCLS": _macro_series(lambda i: 15.0),
        "DTWEXBGS": _macro_series(lambda i: 100.0 - i * 0.05),
    }

    def fetch_macro():
        return macro

    cfg = {
        "start_ms": start_ms, "end_ms": end_ms, "cache_dir": "",
        "top_n": 1, "min_history_days": 30, "vol_days": 30,
        "rebalance_days": 30,
    }
    return (fetch_candles, ["AAA", "BBB"], fetch_daily, fetch_funding,
           fetch_macro, cfg)


def test_consolidated_ls_registered_with_result_json_filename():
    entry = LANES["consolidated_ls"]
    assert entry.verdict_filename == "RESULT.json"
    assert entry.code_paths == ("tools/consolidated/consolidated_ls.py",)


def test_consolidated_ls_run_args_builds_five_loaders():
    entry = LANES["consolidated_ls"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({}, ".backtest_cache", series_by_key)
    assert len(run_args) == 5
    fetch_candles, symbols, fetch_daily, fetch_funding, fetch_macro = run_args
    assert callable(fetch_candles) and callable(fetch_daily)
    assert callable(fetch_funding) and callable(fetch_macro)
    assert isinstance(symbols, list)


@pytest.mark.slow
def test_consolidated_ls_run_wires_all_ten_adapters(tmp_path):
    entry = LANES["consolidated_ls"]
    fetch_candles, symbols, fetch_daily, fetch_funding, fetch_macro, cfg = \
        _consolidated_ls_fixture()
    result = entry.run_fn(cfg, fetch_candles, symbols, fetch_daily,
                          fetch_funding, fetch_macro, out_dir=tmp_path)
    assert set(result) == {"rows", "errors", "excluded", "window",
                           "btc_bars", "btc_sha"}
    lanes_seen = {r["lane"] for r in result["rows"]}
    assert lanes_seen == {
        "btc_classic", "breadth_internal", "donchian", "regime_overlay",
        "regime_selector", "practical", "btcspec", "ls_tournament",
        "playbook", "engine",
    }
    assert [item["lane"] for item in result["excluded"]] == ["portfolio", "pathsig"]
    assert result["window"] == {"start_ms": cfg["start_ms"], "end_ms": cfg["end_ms"]}
    assert result["btc_bars"] == 800
    assert isinstance(result["btc_sha"], str) and result["btc_sha"]
    ok_rows = [r for r in result["rows"] if r["status"] == "ok"]
    exps = [r["expectancy_r"] for r in ok_rows]
    assert exps == sorted(exps, reverse=True)


def _matrix_fixture():
    """research/matrix/evaluate.py's TRAIN_END_TS_MS/SEALED_START_TS_MS/
    SPAN_END_TS_MS are hardcoded absolute epoch-ms module constants (the
    real 2020-2026 calendar window), not cfg-overridable -- same "frozen
    module constant, not a run kwarg" gotcha slice 16 hit with sse's
    ERA_BOUNDS/RVOL_WINDOW+Z_WINDOW warmup floor. So candles must span real
    calendar dates, not a small synthetic epoch-0 window like most other
    fixtures in this file. Starts 30 bars before TRAIN_END_TS_MS (train
    segment ends up empty after the 168h purge -- exercises fit_governor's
    `best is None` default-grid-config fallback, a real code path) through
    SPAN_END_TS_MS: ~5464 4h bars, still far below the real run's 14200.
    A repeating triangle wave (period 60 bars, amplitude 40, buffer ±0.5)
    guarantees many real Donchian entry_n=20/trail_n=10 breakout+trailing-
    stop round trips (a monotonic uptrend, tried first, produces exactly
    ONE trade that never exits -- the trailing stop needs a down-leg to
    ever trigger). funding=None throughout (funding_panel contributes zero
    trades -- momentum_panel alone is enough to exercise the full gate1/
    gate2/gate3 chain; same "funding=[] throughout, proven safe" precedent
    _consolidated_ls_fixture used). BTC/ETH/SOL each get a different phase
    offset (0/7/13) so they are not byte-identical series."""
    from moonface.core.models import Candle
    from moonface.research.matrix.evaluate import (SPAN_END_TS_MS,
                                                    TRAIN_END_TS_MS)

    step = 14_400_000
    start_ms = TRAIN_END_TS_MS - 30 * step
    end_ms = SPAN_END_TS_MS
    period, amp = 60, 40.0

    def _series(seed):
        out = []
        ts, i = start_ms, 0
        while ts < end_ms:
            phase = (i + seed) % period
            close = (100.0 + phase * (amp / (period // 2)) if phase < period // 2
                    else 100.0 + amp - (phase - period // 2) * (amp / (period // 2)))
            out.append(Candle(ts, close, close + 0.5, close - 0.5, close, 1.0))
            ts += step
            i += 1
        return out

    by_sym = {"BTCUSDT": _series(0), "ETHUSDT": _series(7), "SOLUSDT": _series(13)}

    def fetch_candles(sym, start, end):
        return by_sym[sym]

    def fetch_funding(sym, start, end):
        return []

    cfg = {"interval": "4h", "start_ms": start_ms, "end_ms": end_ms,
          "baseline_val_dd": -11.6455, "baseline_sealed_dd": -4.1142}
    return fetch_candles, fetch_funding, cfg


def test_matrix_registered_with_slice1b_json_filename():
    entry = LANES["matrix"]
    assert entry.verdict_filename == "matrix_slice1b_2026-07.json"
    assert entry.code_paths == ("tools/matrix/matrix_evaluate.py",)


def test_matrix_run_args_reuses_donchian_filter_run_args():
    from tools.lane_registry import _donchian_filter_run_args
    assert LANES["matrix"].run_args_builder is _donchian_filter_run_args


@pytest.mark.slow
def test_matrix_run_wires_full_gate1_gate2_gate3_chain():
    entry = LANES["matrix"]
    fetch_candles, fetch_funding, cfg = _matrix_fixture()
    result = entry.run_fn(cfg, fetch_candles, fetch_funding, out_dir=None)
    assert set(result) == {"label", "data", "frozen_constants",
                           "fitted_governor", "segments", "gate1", "gate2",
                           "gate3", "verdict"}
    assert result["data"]["btc_candles"] == 5464
    assert result["segments"]["train"] == 0
    assert result["fitted_governor"] == {
        "target_vol": 0.015, "size_max": 1.0, "dd_budget": 11.6455}
    assert result["gate1"] == {
        "n": 53, "net_r": pytest.approx(259.2736),
        "net_r_3x": pytest.approx(252.6438), "max_dd_r": 0.0,
        "baseline_max_dd_r": -11.6455,
        "ci": [pytest.approx(4.892), pytest.approx(4.892)], "passed": True}
    assert result["gate2"] == {
        "n": 35, "net_r_3x": pytest.approx(166.8402), "max_dd_r": 0.0,
        "baseline_max_dd_r": -4.1142, "passed": True}
    assert result["gate3"] == {
        "eth": {"n": 35, "net_r_3x": pytest.approx(166.8402)},
        "sol": {"n": 36, "net_r_3x": pytest.approx(168.4708)},
        "passed": True}
    assert result["verdict"] == "ALL_GATES_PASSED_HUMAN_DECISION_PENDING"


def _mtf_transfer_fixture():
    from dataclasses import dataclass
    import math

    @dataclass
    class C:
        open: float
        high: float
        low: float
        close: float
        volume: float
        timestamp_ms: int

    step = 900_000  # 15m, matches BASE_TF
    n = 8000        # >=5000 (the CLI's own "insufficient data" floor) plus
                    # enough bars to warm the 1d HTF's SMA50 (50 days = 4800
                    # 15m bars) with room left over for real trades
    wave = []
    for i in range(n):
        # drift + a 40-bar (10h) oscillation -- short-period enough to swing
        # RSI(14) through 30/70 repeatedly while the daily HTF stays biased
        # by the drift, same "periodic wave produces many real round trips"
        # precedent as matrix's slice-20 triangle-wave fixture.
        price = 100.0 + 0.01 * i + 15.0 * math.sin(2 * math.pi * i / 40)
        wave.append(C(open=price, high=price + 0.5, low=price - 0.5,
                      close=price, volume=1.0, timestamp_ms=i * step))
    short = wave[:200]  # < 5000 bars -- exercises the CLI's insufficient-skip

    def fetch_candles(sym, start, end):
        return short if sym == "ETHUSDT" else wave

    cfg = {"symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"], "start_ms": 0,
           "end_ms": n * step, "recent_ms": int(0.7 * n) * step}
    return fetch_candles, cfg


def test_mtf_transfer_registered_with_default_verdict_filename():
    entry = LANES["mtf_transfer"]
    assert entry.verdict_filename == "verdict.json"
    assert entry.code_paths == ("tools/mtf/mtf_transfer.py",)


def test_mtf_transfer_run_args_reuses_candles_run_args():
    from tools.lane_registry import _candles_run_args
    assert LANES["mtf_transfer"].run_args_builder is _candles_run_args


def test_mtf_transfer_run_skips_insufficient_data_and_flags_transfer():
    entry = LANES["mtf_transfer"]
    fetch_candles, cfg = _mtf_transfer_fixture()
    result = entry.run_fn(cfg, fetch_candles, out_dir=None)
    assert set(result) == {"verdict", "rows"}
    assert [r["symbol"] for r in result["rows"]] == \
        ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    btc, eth, sol = result["rows"]
    # ETH's short series never reaches the 5000-bar floor -- flagged, not
    # silently dropped, so the row count stays honest across a reproduction.
    assert eth == {"symbol": "ETHUSDT", "insufficient": True, "n": 200}
    expected_full = {
        "n": 16, "longs": 16, "shorts": 0, "pf": 0.0,
        "expectancy_r": -3.0941, "win_rate": 0.0, "total_r": -49.505,
        "max_dd_r": -49.51, "mar": 0.9999, "positive": False}
    expected_recent = {
        "n": 12, "longs": 12, "shorts": 0, "pf": 0.0,
        "expectancy_r": -3.0963, "win_rate": 0.0, "total_r": -37.156,
        "max_dd_r": -37.16, "mar": 0.9999, "positive": False}
    # BTC and SOL are fed the IDENTICAL wave series, so their stats match
    # exactly -- the point of this fixture is exercising the skip branch and
    # the transfer verdict, not asset-specific price behaviour.
    assert btc["full"] == expected_full and btc["recent"] == expected_recent
    assert sol["full"] == expected_full and sol["recent"] == expected_recent
    # non-BTC rows (SOL only -- ETH excluded as insufficient) are negative in
    # both windows, so the transfer verdict must read "does not transfer".
    assert result["verdict"] == "DOES NOT cleanly transfer (see per-asset rows)"


def _mtf_basket_fixture():
    from dataclasses import dataclass
    import math

    @dataclass
    class C:
        open: float
        high: float
        low: float
        close: float
        volume: float
        timestamp_ms: int

    step = 900_000  # 15m, matches BASE_TF -- same fixture shape as
                    # mtf_transfer's own (this lane runs the identical
                    # headline_cell over the same candle shape, only the
                    # aggregation differs)
    n = 8000
    wave = []
    for i in range(n):
        price = 100.0 + 0.01 * i + 15.0 * math.sin(2 * math.pi * i / 40)
        wave.append(C(open=price, high=price + 0.5, low=price - 0.5,
                      close=price, volume=1.0, timestamp_ms=i * step))
    short = wave[:200]  # < 5000 bars -- exercises the CLI's insufficient-skip

    def fetch_candles(sym, start, end):
        return short if sym == "ETHUSDT" else wave

    cfg = {"symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"], "start_ms": 0,
           "end_ms": n * step, "recent_ms": int(0.7 * n) * step}
    return fetch_candles, cfg


def test_mtf_basket_registered_with_default_verdict_filename():
    entry = LANES["mtf_basket"]
    assert entry.verdict_filename == "verdict.json"
    assert entry.code_paths == ("tools/mtf/mtf_basket.py",)


def test_mtf_basket_run_args_reuses_candles_run_args():
    from tools.lane_registry import _candles_run_args
    assert LANES["mtf_basket"].run_args_builder is _candles_run_args


def test_mtf_basket_run_merges_surviving_assets_at_the_requested_weight():
    entry = LANES["mtf_basket"]
    fetch_candles, cfg = _mtf_basket_fixture()
    result = entry.run_fn(cfg, fetch_candles, out_dir=None)
    assert set(result) == {"assets", "individual", "basket",
                           "diversification", "yearly", "verdict"}
    # ETH's short series never reaches the 5000-bar floor -- excluded from
    # the basket entirely (no row emitted at all, unlike mtf_transfer's
    # flagged "insufficient" row -- mtf_basket.py's own CLI silently skips).
    assert result["assets"] == ["BTCUSDT", "SOLUSDT"]
    expected_leg_full = {
        "n": 16, "longs": 16, "shorts": 0, "pf": 0.0,
        "expectancy_r": -3.0941, "win_rate": 0.0, "total_r": -49.505,
        "max_dd_r": -49.51, "mar": 0.9999, "positive": False}
    expected_leg_recent = {
        "n": 12, "longs": 12, "shorts": 0, "pf": 0.0,
        "expectancy_r": -3.0963, "win_rate": 0.0, "total_r": -37.156,
        "max_dd_r": -37.16, "mar": 0.9999, "positive": False}
    # BTC and SOL are fed the IDENTICAL wave series, so their solo legs
    # match exactly -- same precedent as mtf_transfer's own fixture.
    assert result["individual"]["BTCUSDT"]["full"] == expected_leg_full
    assert result["individual"]["BTCUSDT"]["recent"] == expected_leg_recent
    assert result["individual"]["SOLUSDT"]["full"] == expected_leg_full
    assert result["individual"]["SOLUSDT"]["recent"] == expected_leg_recent
    # weight is 1/len(cfg["symbols"]) == 1/3, NOT 1/len(streams) == 1/2 --
    # the CLI never up-weights survivors onto a skipped asset's share, so
    # each leg's total_r is scaled by 1/3 (-49.505 * 2/3 == -33.0034 merged
    # from two legs), not by 1/2.
    assert result["basket"]["full"] == {
        "n": 32, "longs": 32, "shorts": 0, "pf": 0.0,
        "expectancy_r": -1.0314, "win_rate": 0.0, "total_r": -33.0034,
        "max_dd_r": -33.0, "mar": 1.0001, "positive": False}
    assert result["basket"]["recent"] == {
        "n": 24, "longs": 24, "shorts": 0, "pf": 0.0,
        "expectancy_r": -1.0321, "win_rate": 0.0, "total_r": -24.7707,
        "max_dd_r": -24.77, "mar": 1.0, "positive": False}
    # BTC and SOL's identical wave means their drawdowns are perfectly
    # correlated on this fixture -- zero diversification cut, unlike the
    # real BTC/ETH/SOL basket's genuine de-correlation.
    assert result["diversification"] == {
        "ref_dd_r": -33.0, "merged_dd_r": -33.0, "dd_cut_frac": 0.0}
    assert result["yearly"]["robust_frac"] == 0.0
    assert len(result["yearly"]["rows"]) == 1
    assert result["yearly"]["rows"][0]["positive"] is False
    assert result["verdict"] == \
        "DOES NOT CLEAR ECON_BAR (thin edge, large drawdown)"


def _mtf_broaden_fixture(n=12000):
    from dataclasses import dataclass
    import math

    @dataclass
    class C:
        open: float
        high: float
        low: float
        close: float
        volume: float
        timestamp_ms: int

    step = 900_000  # 15m, matches BASE_TF -- same oscillating-wave shape as
                    # mtf_transfer/mtf_basket's own fixture (drift + a
                    # 40-bar/10h sine), extended past 8000 bars so at least
                    # one of the 72 cells' walk-forward windows (test_bars =
                    # 90d = 8640 15m bars) actually runs inside `full`.
    wave = [C(open=(p := 100.0 + 0.01 * i + 15.0 * math.sin(2 * math.pi * i / 40)),
              high=p + 0.5, low=p - 0.5, close=p, volume=1.0, timestamp_ms=i * step)
            for i in range(n)]

    def fetch_candles(sym, start, end):
        return wave

    cfg = {"start_ms": 0, "end_ms": n * step, "interval": "15m"}
    return fetch_candles, cfg


def test_mtf_broaden_registered_with_default_verdict_filename():
    entry = LANES["mtf_broaden"]
    assert entry.verdict_filename == "verdict.json"
    assert entry.code_paths == ("tools/mtf/mtf_broaden.py",)


def test_mtf_broaden_run_args_reuses_candles_run_args():
    from tools.lane_registry import _candles_run_args
    assert LANES["mtf_broaden"].run_args_builder is _candles_run_args


def test_mtf_broaden_run_raises_below_the_minimum_bar_floor():
    entry = LANES["mtf_broaden"]

    def fetch_candles(sym, start, end):
        return [None] * 100  # < 2000, mtf_broaden.py's own MIN_BARS

    with pytest.raises(ValueError, match="only 100 bars"):
        entry.run_fn({"start_ms": 0, "end_ms": 1}, fetch_candles, out_dir=None)


@pytest.mark.slow
def test_mtf_broaden_run_gates_all_seventy_two_cells():
    entry = LANES["mtf_broaden"]
    fetch_candles, cfg = _mtf_broaden_fixture()
    result = entry.run_fn(cfg, fetch_candles, out_dir=None)
    assert set(result) == {"verdict", "rows"}
    assert len(result["rows"]) == 72
    # every row carries the full search_diagnostic shape unconditionally
    # (no early-kill short-circuit, unlike the strict `search()` gate) --
    # spot-check the shape on the top-sorted (highest econ MAR then DSR) row.
    top = result["rows"][0]
    assert top["label"] == "4h:price_vs_sma|rsi_reversion|horizon_hold@2d"
    assert set(top) == {"label", "htf", "trigger", "exit", "stage1", "stage2",
                        "stage3", "econ_pass", "verdict"}
    assert top["stage1"]["n"] == 43 and top["stage1"]["passed"] is True
    assert top["stage2"]["n"] == 44 and top["stage2"]["dsr"] == 0.0
    assert top["stage2"]["passed"] is False  # DSR floor 0.95 never clears
    assert top["stage3"]["n_windows"] == 2 and top["stage3"]["passed"] is True
    assert top["econ_pass"] is True
    # strict verdict needs stage1+stage2+stage3 all passing; stage2's DSR
    # never clears on this fixture, so every cell's own verdict is
    # "negative" even for cells that clear the deployable ECON_BAR --
    # the overall report distinguishes "econ-positive" from "strict edge".
    assert top["verdict"] == "negative"
    strict = [r for r in result["rows"] if r["verdict"] == "edge"]
    econ = [r for r in result["rows"] if r["econ_pass"]]
    assert strict == []
    assert len(econ) == 13
    assert result["verdict"] == (
        "ECON-POSITIVE (13 cell(s) clear ECON_BAR but not DSR -- practical "
        "paper candidate, academically underpowered)")


def _mtf_long_only_fixture(n=12000):
    from dataclasses import dataclass
    import math

    @dataclass
    class C:
        open: float
        high: float
        low: float
        close: float
        volume: float
        timestamp_ms: int

    step = 900_000  # 15m, matches BASE_TF -- same oscillating-wave shape as
                    # the rest of the mtf family's fixtures, at mtf_broaden's
                    # 12000-bar length (broaden_best_cell's own 4h:trend_strength
                    # htf + horizon_hold@2d exit needs the same runway).
    wave = [C(open=(p := 100.0 + 0.01 * i + 15.0 * math.sin(2 * math.pi * i / 40)),
              high=p + 0.5, low=p - 0.5, close=p, volume=1.0, timestamp_ms=i * step)
            for i in range(n)]

    def fetch_candles(sym, start, end):
        return wave

    cfg = {"symbol": "BTCUSDT", "start_ms": 0, "end_ms": n * step,
           "interval": "15m", "recent_ms": int(0.7 * n) * step}
    return fetch_candles, cfg


def test_mtf_long_only_registered_with_default_verdict_filename():
    entry = LANES["mtf_long_only"]
    assert entry.verdict_filename == "verdict.json"
    assert entry.code_paths == ("tools/mtf/mtf_long_only.py",)


def test_mtf_long_only_run_args_reuses_candles_run_args():
    from tools.lane_registry import _candles_run_args
    assert LANES["mtf_long_only"].run_args_builder is _candles_run_args


def test_mtf_long_only_run_isolates_the_long_book_and_clears_econ_bar():
    entry = LANES["mtf_long_only"]
    fetch_candles, cfg = _mtf_long_only_fixture()
    result = entry.run_fn(cfg, fetch_candles, out_dir=None)
    assert set(result) == {"verdict", "exposure", "ls_full", "lo_full",
                           "lo_recent", "yearly", "buy_and_hold_yearly"}
    # broaden_best_cell's frozen cell emits only LONG trades on this fixture
    # (0 shorts), so the long-only book equals the L/S whole exactly -- same
    # "identical wave, identical stats" precedent as mtf_basket's BTC/SOL legs.
    expected_full = {
        "n": 56, "longs": 56, "shorts": 0, "pf": 251.2717,
        "expectancy_r": 7.9069, "win_rate": 0.9821, "total_r": 442.785,
        "max_dd_r": -1.77, "mar": 250.161, "positive": True}
    assert result["ls_full"] == expected_full
    assert result["lo_full"] == expected_full
    assert result["lo_recent"] == {
        "n": 18, "longs": 18, "shorts": 0, "pf": 77.4583,
        "expectancy_r": 7.5151, "win_rate": 0.9444, "total_r": 135.2714,
        "max_dd_r": -1.77, "mar": 76.4245, "positive": True}
    assert result["yearly"]["robust_frac"] == 1.0
    assert len(result["yearly"]["rows"]) == 1
    assert result["yearly"]["rows"][0]["year"] == 1970
    assert result["yearly"]["rows"][0]["positive"] is True
    # buy_and_hold_yearly is the CLI's own beta-test source data, kept as raw
    # structure instead of the CLI's formatted beta_note sentence.
    assert result["buy_and_hold_yearly"] == [
        {"year": 1970, "btc_return_pct": 1.176435}]
    assert result["exposure"] == 0.896
    # lo_full clears every ECON_BAR gate on this fixture (PF/exp/MAR/DD all
    # far past the floor, robust_frac 1.0 >= 0.6) -- the CLEARS branch,
    # complementing mtf_basket's own negative-fixture DOES-NOT-CLEAR test.
    assert result["verdict"] == "CLEARS ECON_BAR (paper candidate)"


def _donchian_revalidate_fixture():
    """Same repeating-triangle-wave shape _matrix_fixture established (period
    60, amplitude 40 -- proven to generate real Donchian entry_n=30..55
    breakout+trailing-stop round trips, unlike a monotonic uptrend which
    produces exactly one trade that never exits). Sized to 6700 bars: just
    over nonoverlap_walk_forward's one-window floor (train_bars=2*2190=4380
    + test_bars=2190 = 6570) so walk_forward's while-loop body actually runs
    once (n_windows=1) rather than returning the n=0 default. funding=[]
    throughout -- same "proven safe with funding_enabled=True TrendParams"
    precedent _matrix_fixture and _consolidated_ls_fixture established."""
    from moonface.core.models import Candle

    step = 14_400_000
    period, amp = 60, 40.0
    n = 6700

    candles = []
    ts = 0
    for i in range(n):
        phase = i % period
        close = (100.0 + phase * (amp / (period // 2)) if phase < period // 2
                else 100.0 + amp - (phase - period // 2) * (amp / (period // 2)))
        candles.append(Candle(ts, close, close + 0.5, close - 0.5, close, 1.0))
        ts += step

    def fetch_candles(sym, start, end):
        return candles

    def fetch_funding(sym, start, end):
        return []

    cfg = {"symbol": "BTCUSDT", "interval": "4h", "start_ms": 0,
          "end_ms": n * step}
    return fetch_candles, fetch_funding, cfg


def test_donchian_revalidate_registered_with_default_verdict_filename():
    entry = LANES["donchian_revalidate"]
    assert entry.verdict_filename == "verdict.json"
    assert entry.code_paths == ("tools/lanes/donchian_revalidate.py",)


def test_donchian_revalidate_run_args_reuses_donchian_filter_run_args():
    from tools.lane_registry import _donchian_filter_run_args
    assert LANES["donchian_revalidate"].run_args_builder is _donchian_filter_run_args


def test_donchian_revalidate_run_wires_the_full_pipeline():
    entry = LANES["donchian_revalidate"]
    fetch_candles, fetch_funding, cfg = _donchian_revalidate_fixture()
    result = entry.run_fn(cfg, fetch_candles, fetch_funding, out_dir=None)
    assert set(result) == {"gross", "ablation", "plateau", "cost", "dist",
                           "regime", "wf", "verdict"}
    # gross_h12_probe: entry_n=40 breakout drift on this periodic wave.
    assert result["gross"] == {"n": 111, "z": float("inf"),
                               "mean_ret_r": 4.363636363636362,
                               "sign_rate": 1.0, "passed": True}
    # exit ablation: same 111 Donchian entries fixed, only the exit differs.
    assert result["ablation"]["trail"]["n"] == 111
    assert result["ablation"]["trail"]["expectancy_r"] == -0.5614
    # deployed (trail, base cost) == plateau's center == cost's base tier --
    # all three read the identical simulate_donchian(candles, bp, funding)
    # call, just wired through different callers (plateau's row carries one
    # extra "label" key the other two don't).
    assert result["plateau"]["center"]["expectancy_r"] == \
        result["ablation"]["trail"]["expectancy_r"] == \
        result["cost"]["base"]["expectancy_r"]
    assert result["cost"]["base"]["econ_pass"] is False
    assert result["dist"]["n"] == 111
    assert result["dist"]["td_extreme"] is True
    # only 1 window fits (n=6700 just clears the 6570-bar floor).
    assert result["wf"]["n_windows"] == 1
    assert result["wf"]["wf_pass"] is False
    assert result["regime"]["regime_sufficient"] is False
    # structural failures (wf_pass False, base-cost econ_pass False) route
    # to the DOWNGRADE tier before any nonstructural reason is even checked.
    assert result["verdict"] == "DOWNGRADE TO PARKED / NEEDS-FIX"


def _vrp_measure_fixture():
    """120 DVOL points at the real 12h cadence (DVOL_INTERVAL_MS), starting
    at ts=0 -- just over block_bootstrap_mean_ci's BLOCK_LEN=60 floor (it
    raises ValueError for n <= 60) and long enough for disjoint_spreads'
    30-day stride to pick up 2 points. Spot closes cover every hour from
    (start_ms - HOUR_MS) through last_ret_ts = end_ms + (RV_HORIZON_HOURS-1)
    * HOUR_MS inclusive -- the exact window build_return_series/rv_var need,
    mirrored from main()'s own math. A slow monotonic drift (always positive,
    real log returns, no GapError) keeps every return usable -- the real
    SPLICED_BAR_TS_MS entries are ~1.6e12, far outside this fixture's ts
    range, so usable_mask is True throughout (n_excluded_returns == 0).
    null_seeds overridden to 5 (the CLI's own --null-seeds testing hook) --
    the frozen run's default 500 would still be deterministic here, just
    100x slower for no assertion value."""
    from moonface.research.vrp_measure import (DVOL_INTERVAL_MS, HOUR_MS,
        RV_HORIZON_HOURS)

    n_dvol = 120
    dvol = [(i * DVOL_INTERVAL_MS, 60.0 + (i % 5)) for i in range(n_dvol)]
    start_ms = dvol[0][0]
    end_ms = dvol[-1][0]
    last_ret_ts = end_ms + (RV_HORIZON_HOURS - 1) * HOUR_MS

    closes = {}
    ts = start_ms - HOUR_MS
    i = 0
    while ts <= last_ret_ts:
        closes[ts] = 100.0 * (1.0 + 0.0001 * i)
        ts += HOUR_MS
        i += 1

    def fetch_dvol():
        return dvol

    def fetch_spot():
        return closes

    cfg = {"dvol_path": "unused", "spot_path": "unused",
          "start_ms": start_ms, "end_ms": end_ms, "null_seeds": 5}
    return fetch_dvol, fetch_spot, cfg


def test_vrp_measure_registered_with_results_json_verdict_filename():
    entry = LANES["vrp_measure"]
    assert entry.verdict_filename == "results.json"
    assert entry.code_paths == ("tools/lanes/vrp_measure.py",)


def test_vrp_measure_run_args_builds_two_callables_ignoring_cache_dir(tmp_path):
    from moonface.research.vrp_measure import (DVOL_INTERVAL_MS, HOUR_MS,
        RV_HORIZON_HOURS)

    dvol_path = tmp_path / "dvol.csv"
    dvol_path.write_text("0,60.0\n43200000,61.0\n")
    spot_path = tmp_path / "spot.csv"
    spot_path.write_text("\n".join(
        f"{ts},0,0,0,{100.0 + i}" for i, ts in enumerate(
            range(-HOUR_MS, 43200000 + RV_HORIZON_HOURS * HOUR_MS, HOUR_MS))) + "\n")

    entry = LANES["vrp_measure"]
    series_by_key: dict = {}
    cfg = {"dvol_path": str(dvol_path), "spot_path": str(spot_path),
          "start_ms": 0, "end_ms": DVOL_INTERVAL_MS}
    run_args = entry.run_args_builder(cfg, "this-cache-dir-is-ignored",
                                      series_by_key)
    assert len(run_args) == 2
    fetch_dvol, fetch_spot = run_args
    assert fetch_dvol() == [(0, 60.0), (43200000, 61.0)]
    assert set(series_by_key) == {"BTC:dvol"}
    closes = fetch_spot()
    assert closes[0] == 101.0
    assert set(series_by_key) == {"BTC:dvol", "BTC:spot"}


def test_vrp_measure_run_wires_the_full_pipeline():
    entry = LANES["vrp_measure"]
    fetch_dvol, fetch_spot, cfg = _vrp_measure_fixture()
    result = entry.run_fn(cfg, fetch_dvol, fetch_spot, out_dir=None)
    assert set(result) == {"results"}
    results = result["results"]
    assert set(results) == {"window", "mean_spread", "median_spread",
                            "frac_positive", "bootstrap_ci", "disjoint_n",
                            "disjoint_mean", "disjoint_ci", "year_buckets",
                            "tail_windows", "vol_point_mean", "null_gaussian",
                            "null_student_t", "bias_corrected_spread",
                            "threshold"}
    assert results["window"] == {"start_ms": 0, "end_ms": 5140800000,
                                 "start_utc": "1970-01-01 00:00",
                                 "end_utc": "1970-03-01 12:00",
                                 "n_dvol_bars": 120, "n_returns": 2148,
                                 "n_excluded_returns": 0}
    assert results["mean_spread"] == pytest.approx(0.38452818776125763)
    assert results["disjoint_n"] == 2
    # run_fn round-trips through json.dumps/loads to match the recorded
    # results.json's own shape (JSON has no tuple type, and object keys are
    # always strings) -- year_buckets is keyed "1970", not int 1970.
    assert results["year_buckets"] == {"1970": {"mean": pytest.approx(0.38452818776125763),
                                                "n": 120}}
    assert results["bootstrap_ci"] == pytest.approx(
        [0.38452461779619185, 0.38453193390964985])
    assert results["null_gaussian"]["n_seeds"] == 5
    assert results["null_student_t"]["n_seeds"] == 5
    assert results["threshold"] == {"null_clears": True, "interval_clears": True,
                                    "stability_clears": False,
                                    "buckets_positive": 1,
                                    "continue_recommended": False}


def _carry_measure_fixture():
    """100 funding intervals at the real 8h cadence (FUNDING_INTERVAL_MS),
    starting at carry_measure's own WINDOW_START_MS (2020-01-01 00:00 UTC,
    already hour-aligned) -- just over block_bootstrap_dd's BLOCK_LEN=90
    floor (it raises ValueError for len(net) <= 90). Rate alternates in
    5-interval blocks (+0.0002 / -0.0001) so negative_episodes finds real,
    exactly-5-interval-long runs (10 of them) rather than one degenerate
    all-positive or all-negative series. Perp/spot hourly bars cover every
    hour in [start_ms, end_ms] inclusive (793 bars) with a slow linear
    uptrend and a small constant spot/perp offset (spot = perp - 0.03) so
    Q5's basis is a real nonzero constant rather than zero throughout."""
    FUNDING_INTERVAL_MS = 8 * 3_600_000
    HOUR_MS = 3_600_000
    n_intervals = 100
    start_ms = 1_577_836_800_000  # carry_measure.WINDOW_START_MS

    funding = []
    for i in range(n_intervals):
        rate = 0.0002 if (i // 5) % 2 == 0 else -0.0001
        funding.append((start_ms + i * FUNDING_INTERVAL_MS, rate))
    end_ms = funding[-1][0]

    n_hours = (n_intervals - 1) * 8 + 1
    perp: dict[int, tuple[float, float]] = {}
    spot: dict[int, tuple[float, float]] = {}
    for h in range(n_hours):
        ts = start_ms + h * HOUR_MS
        p_open = 100.0 + h * 0.05
        perp[ts] = (p_open, p_open + 0.02)
        s_open = p_open - 0.03
        spot[ts] = (s_open, s_open + 0.02)

    def fetch_funding():
        return funding

    def fetch_perp():
        return perp

    def fetch_spot():
        return spot

    cfg = {"funding_path": "unused", "perp_path": "unused",
          "spot_path": "unused", "start_ms": start_ms, "end_ms": end_ms}
    return fetch_funding, fetch_perp, fetch_spot, cfg


def test_carry_measure_registered_with_results_json_verdict_filename():
    entry = LANES["carry_measure"]
    assert entry.verdict_filename == "results.json"
    assert entry.code_paths == ("tools/lanes/carry_measure.py",)


def test_carry_measure_run_args_builds_three_callables_ignoring_cache_dir(tmp_path):
    funding_path = tmp_path / "funding.csv"
    funding_path.write_text("0,0.0002\n28800000,-0.0001\n")
    bars_path = tmp_path / "bars.csv"
    hour_ms = 3_600_000
    rows = []
    for h in range(9):  # covers ts 0 through 28800000 (8h) at 1h cadence
        ts = h * hour_ms
        rows.append(f"{ts},{100.0 + h},0,0,{100.5 + h}")
    bars_path.write_text("\n".join(rows) + "\n")

    entry = LANES["carry_measure"]
    series_by_key: dict = {}
    cfg = {"funding_path": str(funding_path), "perp_path": str(bars_path),
          "spot_path": str(bars_path), "start_ms": 0, "end_ms": 28800000}
    run_args = entry.run_args_builder(cfg, "this-cache-dir-is-ignored",
                                      series_by_key)
    assert len(run_args) == 3
    fetch_funding, fetch_perp, fetch_spot = run_args
    assert fetch_funding() == [(0, 0.0002), (28800000, -0.0001)]
    assert set(series_by_key) == {"BTC:funding"}
    perp = fetch_perp()
    assert perp[0] == (100.0, 100.5)
    assert set(series_by_key) == {"BTC:funding", "BTC:perp"}
    spot = fetch_spot()
    assert spot[28800000] == (108.0, 108.5)
    assert set(series_by_key) == {"BTC:funding", "BTC:perp", "BTC:spot"}


def test_carry_measure_run_wires_the_full_pipeline():
    entry = LANES["carry_measure"]
    fetch_funding, fetch_perp, fetch_spot, cfg = _carry_measure_fixture()
    result = entry.run_fn(cfg, fetch_funding, fetch_perp, fetch_spot,
                          out_dir=None)
    assert set(result) == {"results"}
    results = result["results"]
    assert set(results) == {"window", "q1", "q2", "q3", "q4", "q5", "q6",
                            "q7", "runups"}
    assert results["window"] == {"start": "2020-01-01 00:00",
                                 "end": "2020-02-03 00:00",
                                 "start_ms": 1577836800000,
                                 "end_ms": 1580688000000,
                                 "years": pytest.approx(0.09034907597535935)}
    assert results["q1"]["yearly"] == [
        {"year": 2020, "n": 100, "mean_rate": pytest.approx(5e-05),
         "ann_pct": pytest.approx(5.4750000000000005),
         "monthly_mean_pct": pytest.approx(0.24999999999999994),
         "monthly_std_pct": pytest.approx(0.36769552621700463)}]
    grid = {(c["convention"], c["cost_bps"]): c for c in results["q2"]}
    assert grid[("R0", 10.0)]["ann_net_pct_notional"] == \
        pytest.approx(3.8118818181818206)
    # negative-funding episodes: 10 runs, each exactly 5 intervals (the
    # rate's own 5-interval alternating-block period).
    assert results["q3"]["count"] == 10
    assert results["q3"]["longest_run_intervals"] == 5
    q4_r0 = results["q4"]["R0"]
    assert q4_r0["max_dd_pct_notional"] == pytest.approx(0.209)
    assert q4_r0["dd_ci90_pct_notional"] == pytest.approx(
        [0.06740000000000002, 0.21984])
    assert results["q5"]["percentiles_bps"]["50"] == pytest.approx(
        2.504382669672021)
    assert results["q6"] == [{"year": 2020, "n": 100,
                              "ann_gross_pct": pytest.approx(5.4750000000000005)}]
    assert results["q7"]["R0"]["worst_month"]["label"] == "2020-02"
    assert results["runups"]["max_runup_pct"] == pytest.approx(39.599999999999994)


def _edge_search_fixture(n=700):
    """Deterministic uptrend-with-a-bear-patch, same shape as
    tests/research/test_edge_search.py's own fixtures: monotone drift gives
    stage1/stage2 a real signal, the bear patch (bars 300-340) gives stage3's
    MAR a nonzero drawdown to divide by. Long enough (700 bars) that all 4
    real swing_4h cells' warmup (donchian n=40, ma_cross slow=50) plus >=30
    non-overlapping h=12 events clears MIN_EVENTS in both train_oos (620
    bars) and the full series."""
    from moonface.core.models import Candle

    def c(ts, o, h, lo, cl):
        return Candle(timestamp_ms=ts, open=o, high=h, low=lo, close=cl, volume=1.0)

    candles = []
    px = 1000.0
    for k in range(n):
        step = -7.0 if 300 <= k < 340 else 10.0
        candles.append(c(k * 3_600_000, px, px + 6, px - 6, px))
        px += step
    return candles


def test_edge_search_lanes_registered():
    from tools.lane_registry import _candles_run_args

    assert {"edge_search_swing_4h", "edge_search_day_15m"} <= set(LANES)
    for name in ("edge_search_swing_4h", "edge_search_day_15m"):
        entry = LANES[name]
        assert entry.verdict_filename == "leaderboard.json"
        assert entry.code_paths == ("tools/edge/edge_search.py",)
        assert entry.run_args_builder is _candles_run_args


def test_edge_search_run_args_builds_one_fetcher_keyed_by_interval():
    entry = LANES["edge_search_day_15m"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({"interval": "15m"}, ".backtest_cache",
                                      series_by_key)
    assert len(run_args) == 1
    assert callable(run_args[0])


def test_edge_search_run_wires_search_and_to_leaderboard_directly():
    from moonface.research.edge_cells import cells_for
    from moonface.research.edge_search import search, to_leaderboard

    candles = _edge_search_fixture()

    def fetch_candles(sym, start, end):
        assert sym == "BTCUSDT"
        return candles

    cfg = {"symbol": "BTCUSDT", "timeframe": "4h", "start_ms": 0,
          "end_ms": (len(candles) - 1) * 3_600_000, "holdout_bars": 80}
    entry = LANES["edge_search_swing_4h"]
    result = entry.run_fn(cfg, fetch_candles, out_dir=None)

    expected_rows = search(cells_for("4h"), candles[:-80], candles)
    assert result == {"leaderboard": to_leaderboard(expected_rows)}
    assert len(result["leaderboard"]) == 4
    assert {row["label"] for row in result["leaderboard"]} == {
        "ma_cross_20_50", "donchian_break_n40", "atr_channel_break_k1",
        "reversion_in_range_30"}


def _playbook_h1_fixture(n=1300):
    """Same shape as tests/playbook/test_backtest.py's own _h1/_resample/_view
    fixture (a slow uptrend with two isolated breakout spikes, long enough
    for MTFView.build's warmup + the 60/20/20 explore segment to clear
    every config's regime/trigger warmup): reused here rather than imported
    since the source is a test module, not production code."""
    from moonface.core.models import Candle

    prices = [100.0 + i * 0.05 for i in range(n)]
    prices[900] = prices[899] + 3.0
    prices[1100] = prices[1099] + 3.0
    return [Candle(i * 3_600_000, p, p + 2.0, p - 2.0, p, 1.0)
           for i, p in enumerate(prices)]


def _playbook_resample(h1, factor):
    from moonface.core.models import Candle

    out = []
    for k in range(0, len(h1), factor):
        chunk = h1[k:k + factor]
        out.append(Candle(chunk[0].timestamp_ms, chunk[0].open,
                          max(c.high for c in chunk), min(c.low for c in chunk),
                          chunk[-1].close, sum(c.volume for c in chunk)))
    return out


def test_playbook_lane_registered():
    from tools.lane_registry import _playbook_run_args

    entry = LANES["playbook"]
    assert entry.verdict_filename == "explore_leaderboard.json"
    assert entry.code_paths == ("tools/playbook/playbook_search.py",)
    assert entry.run_args_builder is _playbook_run_args


def test_playbook_run_args_builds_one_multi_tf_fetcher():
    entry = LANES["playbook"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({}, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    assert callable(run_args[0])


def test_playbook_run_wires_run_explore_directly():
    from moonface.research.playbook.explore import run_explore
    from moonface.research.playbook.families import all_playbook_configs
    from tools.playbook.playbook_search import _segment_view

    h1 = _playbook_h1_fixture()
    data = {"1h": h1, "2h": _playbook_resample(h1, 2), "4h": _playbook_resample(h1, 4)}

    def fetch_multi_tf(sym, start_ms, end_ms):
        assert sym == "BTCUSDT"
        return data

    cfg = {"symbol": "BTCUSDT", "start_ms": 0, "end_ms": (len(h1) - 1) * 3_600_000}
    entry = LANES["playbook"]
    result = entry.run_fn(cfg, fetch_multi_tf, out_dir=None)

    configs = all_playbook_configs()
    expected_rows = run_explore(configs, _segment_view(data, "explore"))
    expected_slim = [{k: r[k] for k in ("label", "dsr", "metrics")}
                     for r in expected_rows]
    assert result == {"explore_leaderboard": expected_slim}
    assert len(result["explore_leaderboard"]) == 12


def _practical_ramp_fixture(n, step, room, tf_ms):
    """A monotonic ramp, sized past both TFs' walk-forward window floors
    (WF_TEST_BARS/WF_STEP_BARS = 1h:1000/500, 4h:500/250) once cut to the
    first 60% (_explore_by_tf's explore slice) -- same style as
    tests/research/practical/test_explore.py's own _ramp fixture, sized
    independently per timeframe since practical fetches 1h/4h directly
    (no resampling from a shared base like playbook's MTFView)."""
    from moonface.core.models import Candle

    out, px = [], 1000.0
    for k in range(n):
        out.append(Candle(k * tf_ms, px, px + room, px - room, px, 1.0))
        px += step
    return out


def test_practical_lane_registered():
    from tools.lane_registry import _practical_run_args

    entry = LANES["practical"]
    assert entry.verdict_filename == "explore_leaderboard.json"
    assert entry.code_paths == ("tools/practical/practical_search.py",)
    assert entry.run_args_builder is _practical_run_args


def test_practical_run_args_builds_one_multi_tf_fetcher():
    entry = LANES["practical"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({}, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    assert callable(run_args[0])


def test_practical_run_wires_run_explore_directly():
    from moonface.research.practical.explore import run_explore
    from moonface.research.practical.families import all_explore_configs
    from tools.practical.practical_search import _explore_by_tf

    h1 = _practical_ramp_fixture(2600, 5.0, 4.0, 3_600_000)
    h4 = _practical_ramp_fixture(1400, 5.0, 4.0, 14_400_000)
    data = {"1h": h1, "4h": h4}

    def fetch_multi_tf(sym, start_ms, end_ms):
        assert sym == "BTCUSDT"
        return data

    cfg = {"symbol": "BTCUSDT", "start_ms": 0, "end_ms": (len(h1) - 1) * 3_600_000}
    entry = LANES["practical"]
    result = entry.run_fn(cfg, fetch_multi_tf, out_dir=None)

    configs = all_explore_configs()
    expected_rows = run_explore(configs, _explore_by_tf(data))
    assert result == {"explore_leaderboard": expected_rows}
    assert len(result["explore_leaderboard"]) == 72
    # practical_search.py's --explore writes run_explore's rows UNSLIMMED
    # (unlike playbook's), so every config field survives, not just
    # label/dsr/metrics.
    assert set(result["explore_leaderboard"][0]) == {
        "label", "timeframe", "family", "group", "axis", "exit_name",
        "params", "exit_params", "h", "dsr", "metrics"}


def test_practical_full_lane_registered():
    from tools.lane_registry import _practical_full_run_args

    entry = LANES["practical_full"]
    assert entry.verdict_filename == "result.json"
    assert entry.code_paths == ("tools/practical_full/btc_practical_full.py",)
    assert entry.run_args_builder is _practical_full_run_args


def test_practical_full_run_args_builds_one_multi_tf_fetcher():
    entry = LANES["practical_full"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({}, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    assert callable(run_args[0])


def test_practical_full_run_wires_full_explore_select_validate_chain():
    """Unlike practical/playbook (whose frozen select/validate outputs are
    the trivial empty list, so only --explore was reproduced), practical_full's
    real frozen_candidates.json/result.json both carry real content -- this
    twin must run the whole chain, not stop at --explore. Sized like
    practical's own _practical_ramp_fixture (2h subs for practical's 1h slot,
    4h reused as-is) so every family's warmup clears within the 60% explore
    slice and the 20%/20% validate/sealed slices are non-trivial."""
    from moonface.research.practical.explore import run_explore
    from moonface.research.practical.pipeline import freeze_candidates, to_leaderboard
    from moonface.research.practical_full.grid import all_configs
    from moonface.research.practical_full.select_full import select_full
    from moonface.research.practical_full.validate_full import validate_all_full
    from tools.practical_full.btc_practical_full import TIMEFRAMES, _explore_by_tf, \
        _split_60_20_20

    h2 = _practical_ramp_fixture(2600, 5.0, 4.0, 7_200_000)
    h4 = _practical_ramp_fixture(1400, 5.0, 4.0, 14_400_000)
    data = {"2h": h2, "4h": h4}
    assert list(TIMEFRAMES) == ["2h", "4h"]

    def fetch_multi_tf(sym, start_ms, end_ms):
        assert sym == "BTCUSDT"
        return data

    cfg = {"symbol": "BTCUSDT", "start_ms": 0, "end_ms": (len(h2) - 1) * 7_200_000}
    entry = LANES["practical_full"]
    result = entry.run_fn(cfg, fetch_multi_tf, out_dir=None)

    configs = all_configs(list(TIMEFRAMES))
    explore_by_tf = _explore_by_tf(data)
    rows = run_explore(configs, explore_by_tf)
    survivors = select_full(rows, explore_by_tf)
    frozen = freeze_candidates(survivors)
    validate_by_tf, sealed_by_tf = {}, {}
    for tf in TIMEFRAMES:
        _e, v, s = _split_60_20_20(data[tf])
        validate_by_tf[tf], sealed_by_tf[tf] = v, s
    expected_result_rows = validate_all_full(frozen, validate_by_tf, sealed_by_tf)

    assert result == {"result": to_leaderboard(expected_result_rows)}
    assert len(configs) == 132
    # deterministic on this fixture -- captured once, not re-derived, per
    # this file's compute-once-assert-exact convention.
    assert isinstance(result["result"], list)
    for row in result["result"]:
        assert set(row) == {"label", "timeframe", "family", "verdict",
                            "validate_pf", "validate_exp", "sealed_pf",
                            "sealed_exp", "dsr"}
        assert row["verdict"] in ("paper_accept", "rejected")


def test_btcspec_lane_registered():
    from tools.lane_registry import _btcspec_run_args

    entry = LANES["btcspec"]
    assert entry.verdict_filename == "result.json"
    assert entry.code_paths == ("tools/btcspec/btcspec_search.py",)
    assert entry.run_args_builder is _btcspec_run_args


def test_btcspec_run_args_builds_one_multi_tf_fetcher():
    entry = LANES["btcspec"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({}, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    assert callable(run_args[0])


def test_btcspec_run_wires_full_explore_select_validate_chain():
    """Same non-trivial-output shape as practical_full (real frozen_candidates.json/
    result.json both carry real content -- 9 candidates through validate, one
    opened on the sealed tail, all rejected -- not the trivial empty list), so
    this twin must run the whole explore->select->validate chain, not stop at
    --explore. Reuses practical_full's own _practical_ramp_fixture sizing
    verbatim (2h/4h, same WF_TEST_BARS floors -- btcspec's explore.py defines
    the identical 2h:1000/500, 4h:500/250 test/step bars) since btcspec Slice 1
    shares the same two timeframes; the 55/25/20 split (vs practical_full's
    60/20/20) leaves the VALIDATE/SEALED segments under each TF's walk-forward
    window floor, same as practical_full's own 20% slices -- 0 walk-forward
    windows there is a valid, asserted-equal outcome, not a fixture bug."""
    from moonface.research.btcspec.explore import run_explore
    from moonface.research.btcspec.families import all_explore_configs
    from moonface.research.btcspec.select import select
    from moonface.research.btcspec.validate import validate_all
    from moonface.research.btcspec.pipeline import freeze_candidates, to_leaderboard
    from tools.btcspec.btcspec_search import TIMEFRAMES, _explore_by_tf, \
        _split_55_25_20

    h2 = _practical_ramp_fixture(2600, 5.0, 4.0, 7_200_000)
    h4 = _practical_ramp_fixture(1400, 5.0, 4.0, 14_400_000)
    data = {"2h": h2, "4h": h4}
    assert list(TIMEFRAMES) == ["2h", "4h"]

    def fetch_multi_tf(sym, start_ms, end_ms):
        assert sym == "BTCUSDT"
        return data

    cfg = {"symbol": "BTCUSDT", "start_ms": 0, "end_ms": (len(h2) - 1) * 7_200_000}
    entry = LANES["btcspec"]
    result = entry.run_fn(cfg, fetch_multi_tf, out_dir=None)

    configs = all_explore_configs()
    explore_by_tf = _explore_by_tf(data)
    rows = run_explore(configs, explore_by_tf)
    frozen = freeze_candidates(select(rows))
    validate_by_tf, sealed_by_tf = {}, {}
    for tf in TIMEFRAMES:
        _e, v, s = _split_55_25_20(data[tf])
        validate_by_tf[tf], sealed_by_tf[tf] = v, s
    expected_result_rows = validate_all(frozen, validate_by_tf, sealed_by_tf)

    assert result == {"result": to_leaderboard(expected_result_rows)}
    assert isinstance(result["result"], list)
    for row in result["result"]:
        assert set(row) == {"label", "timeframe", "family", "verdict", "dsr",
                            "val_robust", "val_total_r", "seal_pf", "seal_exp"}
        assert row["verdict"] in ("paper_accept", "rejected")


def test_btcspec_s2_lane_registered():
    from tools.lane_registry import _btcspec_s2_run_args

    entry = LANES["btcspec_s2"]
    assert entry.verdict_filename == "result.json"
    assert entry.code_paths == ("tools/btcspec/btcspec_s2_search.py",)
    assert entry.run_args_builder is _btcspec_s2_run_args


def test_btcspec_s2_run_args_builds_one_multi_tf_fetcher():
    entry = LANES["btcspec_s2"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({}, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    assert callable(run_args[0])


def test_btcspec_s2_run_wires_full_explore_select_validate_chain():
    """Slice 2 (1h short-swing) shares btcspec's own slice-agnostic explore/
    select/validate/pipeline modules with Slice 1 -- only families_s2's grid and
    the CLI's own private _split_55_25_20/_explore_by_tf/S2_EXTRA_COST differ, same
    "private-CLI-helper reuse" precedent. btcspec's explore.py's WF_TEST_BARS/
    WF_STEP_BARS for "1h" (2000/1000) are stricter than practical's own 1h floor
    (1000/500), so this fixture is sized fresh rather than reusing
    _practical_ramp_fixture's existing 2600-bar 1h call: 6000 bars * 0.55 (Slice
    2's explore fraction) = 3300 explore bars, comfortably over the 3000-bar
    (2000+1000) one-window floor. The 25%/20% VALIDATE/SEALED segments each fall
    under that floor -- 0 walk-forward windows there is a valid, asserted-equal
    outcome, not a fixture bug, same as Slice 1's own 55/25/20 split."""
    from moonface.research.btcspec.explore import run_explore
    from moonface.research.btcspec.families_s2 import all_explore_configs_s2
    from moonface.research.btcspec.select import select
    from moonface.research.btcspec.validate import validate_all
    from moonface.research.btcspec.pipeline import freeze_candidates, to_leaderboard
    from tools.btcspec.btcspec_s2_search import S2_TIMEFRAMES, S2_EXTRA_COST, \
        _explore_by_tf, _split_55_25_20

    h1 = _practical_ramp_fixture(6000, 5.0, 4.0, 3_600_000)
    data = {"1h": h1}
    assert list(S2_TIMEFRAMES) == ["1h"]

    def fetch_multi_tf(sym, start_ms, end_ms):
        assert sym == "BTCUSDT"
        return data

    cfg = {"symbol": "BTCUSDT", "start_ms": 0, "end_ms": (len(h1) - 1) * 3_600_000}
    entry = LANES["btcspec_s2"]
    result = entry.run_fn(cfg, fetch_multi_tf, out_dir=None)

    configs = all_explore_configs_s2()
    explore_by_tf = _explore_by_tf(data)
    rows = run_explore(configs, explore_by_tf)
    frozen = freeze_candidates(select(rows))
    validate_by_tf, sealed_by_tf = {}, {}
    for tf in S2_TIMEFRAMES:
        _e, v, s = _split_55_25_20(data[tf])
        validate_by_tf[tf], sealed_by_tf[tf] = v, s
    expected_result_rows = validate_all(frozen, validate_by_tf, sealed_by_tf,
                                        extra_cost=S2_EXTRA_COST)

    assert result == {"result": to_leaderboard(expected_result_rows)}
    assert isinstance(result["result"], list)
    for row in result["result"]:
        assert set(row) == {"label", "timeframe", "family", "verdict", "dsr",
                            "val_robust", "val_total_r", "seal_pf", "seal_exp"}
        assert row["verdict"] in ("paper_accept", "rejected")


def test_btcspec_s3_lane_registered():
    from tools.lane_registry import _btcspec_s3_run_args

    entry = LANES["btcspec_s3"]
    assert entry.verdict_filename == "result.json"
    assert entry.code_paths == ("tools/btcspec/btcspec_s3_search.py",)
    assert entry.run_args_builder is _btcspec_s3_run_args


def test_btcspec_s3_run_args_builds_one_multi_tf_fetcher():
    entry = LANES["btcspec_s3"]
    series_by_key: dict = {}
    run_args = entry.run_args_builder({}, ".backtest_cache", series_by_key)
    assert len(run_args) == 1
    assert callable(run_args[0])


def test_btcspec_s3_run_wires_full_explore_select_validate_chain():
    """Slice 3 (15m/30m intraday) shares btcspec's own slice-agnostic explore/
    select/validate/pipeline modules with Slices 1/2 -- only families_s3's grid
    and the CLI's own private _split_55_25_20/_explore_by_tf/S3_EXTRA_COST
    differ, same "private-CLI-helper reuse" precedent. btcspec's explore.py's
    WF_TEST_BARS/WF_STEP_BARS for "15m"/"30m" (8000/4000, 4000/2000) are far
    stricter than Slice 2's 1h floor, so this fixture is sized fresh: 24000 15m
    bars * 0.55 (Slice 3's explore fraction) = 13200 explore bars, comfortably
    over the 12000-bar (8000+4000) one-window floor; 12000 30m bars * 0.55 =
    6600, comfortably over the 6000-bar (4000+2000) floor. The 25%/20%
    VALIDATE/SEALED segments each fall under their floor -- 0 walk-forward
    windows there is a valid, asserted-equal outcome, not a fixture bug, same
    as Slices 1/2's own 55/25/20 split."""
    from moonface.research.btcspec.explore import run_explore
    from moonface.research.btcspec.families_s3 import all_explore_configs_s3
    from moonface.research.btcspec.select import select
    from moonface.research.btcspec.validate import validate_all
    from moonface.research.btcspec.pipeline import freeze_candidates, to_leaderboard
    from tools.btcspec.btcspec_s3_search import S3_TIMEFRAMES, S3_EXTRA_COST, \
        _explore_by_tf, _split_55_25_20

    m15 = _practical_ramp_fixture(24000, 5.0, 4.0, 900_000)
    m30 = _practical_ramp_fixture(12000, 5.0, 4.0, 1_800_000)
    data = {"15m": m15, "30m": m30}
    assert list(S3_TIMEFRAMES) == ["15m", "30m"]

    def fetch_multi_tf(sym, start_ms, end_ms):
        assert sym == "BTCUSDT"
        return data

    cfg = {"symbol": "BTCUSDT", "start_ms": 0, "end_ms": (len(m15) - 1) * 900_000}
    entry = LANES["btcspec_s3"]
    result = entry.run_fn(cfg, fetch_multi_tf, out_dir=None)

    configs = all_explore_configs_s3()
    explore_by_tf = _explore_by_tf(data)
    rows = run_explore(configs, explore_by_tf)
    frozen = freeze_candidates(select(rows))
    validate_by_tf, sealed_by_tf = {}, {}
    for tf in S3_TIMEFRAMES:
        _e, v, s = _split_55_25_20(data[tf])
        validate_by_tf[tf], sealed_by_tf[tf] = v, s
    expected_result_rows = validate_all(frozen, validate_by_tf, sealed_by_tf,
                                        extra_cost=S3_EXTRA_COST)

    assert result == {"result": to_leaderboard(expected_result_rows)}
    assert isinstance(result["result"], list)
    for row in result["result"]:
        assert set(row) == {"label", "timeframe", "family", "verdict", "dsr",
                            "val_robust", "val_total_r", "seal_pf", "seal_exp"}
        assert row["verdict"] in ("paper_accept", "rejected")


def _exogenous_fixture():
    """300 daily BTC-like closes (a deterministic LCG random walk, +-2% daily
    steps, seed 12345) plus 5 FRED-shaped macro series (each its own
    independent LCG walk, 40 days of lead-in before closes[0] so
    aligned_value_at's 20-day lookback + 1-day publish lag never runs off the
    front of the series). Not a real market shape -- picked only to avoid the
    degenerate all-one-sided-position case a smooth sinusoid produced (2
    trades, an infinite profit_factor): this walk produces 248/299 non-flat
    days and 48 episode trades (24 win / 24 loss), a well-powered fixture for
    econ_verdict's 4-window walk-forward and dsr_of_trades' skew/kurtosis
    terms. Values below were captured once by running this exact generator
    and are asserted exactly (compute-once-assert-exact convention, same as
    every other real-computation fixture in this file)."""
    DAY_MS = 86_400_000
    N_DAYS = 300
    MACRO_LEAD_DAYS = 40
    n_macro = MACRO_LEAD_DAYS + N_DAYS

    def lcg_stream(seed, n):
        x = seed
        out = []
        for _ in range(n):
            x = (1103515245 * x + 12345) % (2 ** 31)
            out.append(x / (2 ** 31))
        return out

    close_start_ms = MACRO_LEAD_DAYS * DAY_MS
    price_steps = lcg_stream(12345, N_DAYS)
    rows = []
    price = 100.0
    for i in range(N_DAYS):
        ts = close_start_ms + i * DAY_MS
        price *= 1.0 + (price_steps[i] - 0.5) * 0.04
        rows.append(_ExoRow(ts, price))

    def macro_series(seed, base, scale):
        steps = lcg_stream(seed, n_macro)
        return [_ExoPoint(i * DAY_MS, base + (steps[i] - 0.5) * scale)
                for i in range(n_macro)]

    series = {
        "SP500": macro_series(111, 4000.0, 400.0),
        "DTWEXBGS": macro_series(222, 100.0, 6.0),
        "VIXCLS": macro_series(333, 22.0, 20.0),
        "DGS2": macro_series(444, 4.5, 1.0),
        "DGS10": macro_series(555, 4.2, 1.0),
    }

    def fetch_daily():
        return rows

    def fetch_macro():
        return series

    cfg = {"symbol": "BTCUSDT", "start_ms": close_start_ms,
          "end_ms": rows[-1].ts_ms}
    return fetch_daily, fetch_macro, cfg


class _ExoRow:
    __slots__ = ("ts_ms", "close")

    def __init__(self, ts_ms, close):
        self.ts_ms = ts_ms
        self.close = close


class _ExoPoint:
    __slots__ = ("ts_ms", "value")

    def __init__(self, ts_ms, value):
        self.ts_ms = ts_ms
        self.value = value


def test_exogenous_registered_with_default_verdict_filename():
    entry = LANES["exogenous"]
    assert entry.verdict_filename == "verdict.json"
    assert entry.code_paths == ("tools/exogenous/exogenous_btc.py",)


def _exo_series_fingerprint(rows):
    from moonface.core.provenance import raw_series_fingerprint
    return raw_series_fingerprint([(r.ts_ms, r.close) for r in rows])


def test_exogenous_run_args_builds_two_callables(tmp_path):
    from moonface.data.universe import save_daily_cache, DailyRow

    save_daily_cache(str(tmp_path), "BTCUSDT",
                     [DailyRow(0, 100.0, 1.0), DailyRow(86_400_000, 101.0, 1.0)])
    (tmp_path / "fred_SP500.csv").write_text(
        "date,value\n1970-01-01,4000.0\n1970-01-02,4010.0\n")
    (tmp_path / "fred_DTWEXBGS.csv").write_text("date,value\n1970-01-01,100.0\n")
    (tmp_path / "fred_VIXCLS.csv").write_text("date,value\n1970-01-01,22.0\n")
    (tmp_path / "fred_DGS2.csv").write_text("date,value\n1970-01-01,4.5\n")
    (tmp_path / "fred_DGS10.csv").write_text("date,value\n1970-01-01,4.2\n")

    entry = LANES["exogenous"]
    series_by_key: dict = {}
    cfg = {"symbol": "BTCUSDT", "start_ms": 0, "end_ms": 86_400_001}
    run_args = entry.run_args_builder(cfg, str(tmp_path), series_by_key)
    assert len(run_args) == 2
    fetch_daily, fetch_macro = run_args
    rows = fetch_daily()
    assert [r.close for r in rows] == [100.0, 101.0]
    assert series_by_key == {"BTCUSDT:daily": _exo_series_fingerprint(rows)}

    macro = fetch_macro()
    assert set(macro) == {"SP500", "DTWEXBGS", "VIXCLS", "DGS2", "DGS10"}
    assert macro["SP500"][0].value == 4000.0
    assert macro["SP500"][1].value == 4010.0
    assert set(series_by_key) == {"BTCUSDT:daily", "FRED:SP500", "FRED:DTWEXBGS",
                                  "FRED:VIXCLS", "FRED:DGS2", "FRED:DGS10"}


def test_exogenous_run_wires_the_validate_stage():
    entry = LANES["exogenous"]
    fetch_daily, fetch_macro, cfg = _exogenous_fixture()
    result = entry.run_fn(cfg, fetch_daily, fetch_macro, out_dir=None)
    assert set(result) == {"passed", "dsr_pass", "dsr", "econ_passed",
                           "metrics", "n_trials"}
    # evaluate_econ already rounds every metric to 4dp internally and dsr's
    # true value (2.966921121005939e-07) rounds to 0.0 at run_fn's own
    # round(dsr, 6) -- both exact, not approximated.
    assert result == {
        "passed": False,
        "dsr_pass": False,
        "dsr": 0.0,
        "econ_passed": False,
        "metrics": {
            "expectancy_r": -0.1269,
            "profit_factor": 0.8298,
            "mar": 0.3329,
            "max_dd_r": -18.3051,
            "robust_frac": 0.5,
        },
        "n_trials": 6,
    }
