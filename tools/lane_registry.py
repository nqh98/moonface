#!/usr/bin/env python
"""LANES: every lane wired into `tools/research.py reproduce --lane <name>`.

Adding a lane after G6.1 is: confirm its run function's dependency-injection
shape, pick (or write) a run_args_builder that matches it, define
compare_fields (the substantive numeric/structural output fields -- never a
status/winner/reason/generated_utc narrative field; the parent restructure
spec's invariant is that a verdict/conclusion is never treated as
authoritative), and add one LANES entry. No new cmd_reproduce_* function --
tools/research.py's cmd_reproduce is lane-agnostic (see design spec
docs/research-log/specs/2026-08-25-g6-lane-kernel-conversion-design.md)."""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict, dataclass, replace
from typing import Callable

from moonface.core.bundle import DataBundle
from moonface.core.exits import EXIT_REGISTRY
from moonface.core.provenance import raw_series_fingerprint
from moonface.core.stats import series_fingerprint
from moonface.data.series import align_funding, align_metric
from moonface.features.orderbook_features import imbalance_points
from moonface.kernel.reproduce import (offline_fetch_bookdepth_history,
                                       offline_fetch_daily_klines,
                                       offline_fetch_fred_series,
                                       offline_fetch_funding_history_series,
                                       offline_fetch_funding_rates,
                                       offline_fetch_metrics_history,
                                       offline_fetch_perp_candles,
                                       offline_fetch_vision_1m,
                                       offline_list_um_perp_symbols)
from moonface.research.bb_harvest import run as bb_harvest_run
from moonface.research.breadth.gates import validate_cell
from moonface.research.breadth.grid import all_cells
from moonface.research.drift_screen import (horizon_curve, screen_family,
                                            screen_signal)
from moonface.research.edge.exit_score import ENTRY_SPECS_BY_TF, run_exit_battery
from moonface.research.ls_tournament.exit_ablation import run_ablation
from moonface.research.edge.ob_imbalance_signals import bar_mean_imbalance
from moonface.research.advval.retrodiction import retrodiction_verdict
from moonface.research.multifamily_loader import load_pool_bundles
from tools.advval.advval_run import compute_cell_aucs
from moonface.research.breadth.evaluate import summarize
from moonface.research.breadth_confirm.evaluate import evaluate_slice_overlap
from moonface.research.breadth_confirm.grid import net_new_highs_spec
from moonface.research.breadth_confirm.momentum_grid import breadth_momentum_spec
from moonface.research.breadth_confirm.neutral import (aligned_returns,
                                                        entries_provider,
                                                        hedge_entries,
                                                        rolling_betas)
from moonface.research.breadth_confirm.universe_slice import slice_membership_fn
from moonface.research.breadth_confirm.xasset_grid import lead_specs
from moonface.research.breadth_internal.evaluate import evaluate_spec
from moonface.research.breadth_internal.grid import all_specs
from moonface.research.breadth_internal.hf_evaluate import evaluate_hf_spec
from moonface.research.breadth_internal.hf_grid import BLOCK_LEN, hf_specs
from moonface.research.btc_classic.evaluate import evaluate_spec as btc_classic_evaluate_spec
from moonface.research.btc_classic.grid import all_specs as btc_classic_all_specs
from moonface.research.donchian_filter.adx import adx_series
from moonface.research.donchian_filter.evaluate import (base_trades, gate,
                                                        slice_metrics)
from moonface.research.donchian_filter.select import holdout_verdict
from moonface.research.donchian_volregime.evaluate import (
    base_trades as dvr_base_trades, cell_flags as dvr_cell_flags,
    gate as dvr_gate)
from moonface.research.donchian_volregime.select import sealed_verdict as dvr_sealed_verdict
from moonface.research.regime_overlay.evaluate import (base_vector,
                                                        beats_base,
                                                        cell_vector,
                                                        practical_pass)
from moonface.research.regime_overlay.grid import CELLS as REGIME_OVERLAY_CELLS
from moonface.research.regime_overlay.grid import FRED_SERIES as REGIME_OVERLAY_FRED_SERIES
from moonface.research.regime_overlay.regime import REGIME_DEFS
from moonface.research.regime_selector.evaluate import (
    beats_controls, cell_vector as rs_cell_vector,
    control_vector as rs_control_vector)
from moonface.research.regime_selector.grid import CELLS as REGIME_SELECTOR_CELLS
from moonface.research.regime_selector.grid import FRED_SERIES as REGIME_SELECTOR_FRED_SERIES
from moonface.research.regime_selector.grid import REGIME_IDS as REGIME_SELECTOR_REGIME_IDS
from moonface.research.ls_tournament.grid import TIMEFRAMES as LS_TOURNAMENT_TIMEFRAMES
from moonface.research.ls_tournament.validate import validate_all as ls_tournament_validate_all
from moonface.research.portfolio.components import center_components
from moonface.research.portfolio.components import TIMEFRAMES as PORTFOLIO_TIMEFRAMES
from moonface.research.portfolio.correlation import step0_screen
from moonface.research.portfolio.pipeline import run_explore
from moonface.research.portfolio.streams import (asset_bar_r, component_positions,
                                                 position_returns)
from moonface.research.sse.universe import monthly_membership as sse_monthly_membership
from moonface.research.liq_twap.runner import run_screen as liq_twap_run_screen
from moonface.research.liq_twap.runner import BTC_ASSET as LIQ_TWAP_BTC_ASSET
from moonface.kernel.econ import ECON_BAR
from moonface.research.matrix.evaluate import build_matrix_report
from moonface.research.mtf.attribute import period_stats as mtf_period_stats
from moonface.research.mtf.attribute import trade_stream as mtf_trade_stream
from moonface.research.mtf.basket import diversification as mtf_diversification
from moonface.research.mtf.basket import merge_streams as mtf_merge_streams
from moonface.research.mtf.basket import yearly_robustness as mtf_yearly_robustness
from moonface.research.mtf.basket import _year as mtf_year
from moonface.research.mtf.evaluate import search_diagnostic as mtf_search_diagnostic
from moonface.research.mtf.grid import broaden_best_cell as mtf_broaden_best_cell
from moonface.research.mtf.grid import broadened_cells as mtf_broadened_cells
from moonface.research.mtf.grid import headline_cell as mtf_headline_cell
from moonface.research.trend_sim import TrendParams, simulate_donchian
from moonface.research.donchian_reval import (cost_stress, exit_ablation,
    gross_h12_probe, local_param_plateau, nonoverlap_walk_forward,
    regime_breakdown, revalidation_verdict, trade_distribution)
from moonface.research.consolidated.adapters import ADAPTERS, EXCLUDED
from moonface.research.consolidated.result import metric_block
from moonface.research.consolidated.runner import RunContext
from moonface.research.vrp_measure import (HOUR_MS, N_NULL_SEEDS,
    RV_HORIZON_HOURS, assemble_results, build_return_series, load_dvol,
    load_spot_closes)
from moonface.research.carry_measure import (
    assemble_results as carry_measure_assemble_results,
    load_bars_1h as carry_measure_load_bars_1h,
    load_funding as carry_measure_load_funding)
from moonface.research.edge_cells import cells_for as edge_cells_for
from moonface.research.edge_search import search as edge_search_search
from moonface.research.edge_search import to_leaderboard as edge_to_leaderboard
from moonface.kernel.power_harness import judge_signal
from tools.breadth.breadth import SYMBOL, membership_fn, split_60_20_20, universe_covers_train
from tools.engine.swing_donchian import _BASE as SWING_DONCHIAN_BASE
from tools.eventtime.eventtime_run import compute as eventtime_compute
from tools.engine.smc_decompose import aggregate_4h, score_variant, slice_events
from tools.lanes.bab import run_pipeline as bab_run
from tools.lanes.bb_breakout import GRID as BB_BREAKOUT_GRID
from tools.lanes.bb_revert import GRID as BB_REVERT_GRID
from tools.lanes.calseason import run_analysis as calseason_run
from tools.lanes.drift_screen_stack_path import (
    identity_hash as stack_path_identity_hash, stack_path_generator)
from tools.lanes.liqladder import run_analysis as liqladder_run
from tools.lanes.liqprem import run_pipeline as liqprem_run
from tools.lanes.liqrev import run_analysis as liqrev_run
from tools.lanes.macro_event import run_analysis as macro_event_run
from tools.lanes.oibuild_study import run_analysis as oibuild_study_run
from tools.lanes.resrev import run_pipeline as resrev_run
from tools.lanes.xsection import run_pipeline as xsection_run
from tools.playbook.playbook_search import TIMEFRAMES as PLAYBOOK_TIMEFRAMES
from tools.playbook.playbook_search import _segment_view as playbook_segment_view
from tools.sse.sse import run_gate0 as sse_run_gate0
from moonface.research.playbook.explore import run_explore as playbook_run_explore
from moonface.research.playbook.families import all_playbook_configs as playbook_all_configs
from tools.practical.practical_search import TIMEFRAMES as PRACTICAL_TIMEFRAMES
from tools.practical.practical_search import _explore_by_tf as practical_explore_by_tf
from moonface.research.practical.explore import run_explore as practical_run_explore
from moonface.research.practical.families import all_explore_configs as practical_all_configs
from tools.practical_full.btc_practical_full import TIMEFRAMES as PRACTICAL_FULL_TIMEFRAMES
from tools.practical_full.btc_practical_full import _split_60_20_20 as practical_full_split
from tools.practical_full.btc_practical_full import _explore_by_tf as practical_full_explore_by_tf
from moonface.research.practical_full.grid import all_configs as practical_full_all_configs
from moonface.research.practical_full.select_full import select_full
from moonface.research.practical_full.validate_full import validate_all_full
from moonface.research.practical.pipeline import freeze_candidates, to_leaderboard
from tools.btcspec.btcspec_search import TIMEFRAMES as BTCSPEC_TIMEFRAMES
from tools.btcspec.btcspec_search import _split_55_25_20 as btcspec_split
from tools.btcspec.btcspec_search import _explore_by_tf as btcspec_explore_by_tf
from moonface.research.btcspec.explore import run_explore as btcspec_run_explore
from moonface.research.btcspec.families import all_explore_configs as btcspec_all_configs
from moonface.research.btcspec.select import select as btcspec_select
from moonface.research.btcspec.validate import validate_all as btcspec_validate_all
from moonface.research.btcspec.pipeline import freeze_candidates as btcspec_freeze_candidates
from moonface.research.btcspec.pipeline import to_leaderboard as btcspec_to_leaderboard
from tools.btcspec.btcspec_s2_search import S2_TIMEFRAMES as BTCSPEC_S2_TIMEFRAMES
from tools.btcspec.btcspec_s2_search import S2_EXTRA_COST as BTCSPEC_S2_EXTRA_COST
from tools.btcspec.btcspec_s2_search import _split_55_25_20 as btcspec_s2_split
from tools.btcspec.btcspec_s2_search import _explore_by_tf as btcspec_s2_explore_by_tf
from moonface.research.btcspec.families_s2 import all_explore_configs_s2 as btcspec_s2_all_configs
from tools.btcspec.btcspec_s3_search import S3_TIMEFRAMES as BTCSPEC_S3_TIMEFRAMES
from tools.btcspec.btcspec_s3_search import S3_EXTRA_COST as BTCSPEC_S3_EXTRA_COST
from tools.btcspec.btcspec_s3_search import _split_55_25_20 as btcspec_s3_split
from tools.btcspec.btcspec_s3_search import _explore_by_tf as btcspec_s3_explore_by_tf
from moonface.research.btcspec.families_s3 import all_explore_configs_s3 as btcspec_s3_all_configs
from moonface.research.exogenous.backtest import daily_returns as exogenous_daily_returns
from moonface.research.exogenous.backtest import episode_trades as exogenous_episode_trades
from moonface.research.exogenous.conditioning import state_positions as exogenous_state_positions
from moonface.research.exogenous.evaluate import dsr_of_trades as exogenous_dsr_of_trades
from moonface.research.exogenous.evaluate import econ_verdict as exogenous_econ_verdict
from moonface.research.exogenous.grid import N_TRIALS as EXOGENOUS_N_TRIALS


@dataclass(frozen=True)
class LaneEntry:
    run_fn: Callable[..., dict]
    compare_fields: tuple[str, ...]
    run_args_builder: Callable[[dict, str, dict], tuple]
    code_paths: tuple[str, ...]
    verdict_filename: str = "verdict.json"


def _candles_metric_run_args(cfg: dict, cache_dir: str,
                             series_by_key: dict) -> tuple:
    interval = cfg.get("interval", "4h")
    field = cfg["metrics_field"]

    def fetch_candles(sym, start, end):
        candles = offline_fetch_perp_candles(sym, interval, start, end, cache_dir)
        series_by_key[f"{sym}:candles"] = series_fingerprint(candles)
        return candles

    def fetch_metric(sym, start, end):
        raw = offline_fetch_metrics_history(sym, start, end, cache_dir)
        points = [(ts, f[field]) for ts, f in raw if field in f]
        series_by_key[f"{sym}:metric"] = raw_series_fingerprint(points)
        return points

    return (fetch_candles, fetch_metric)


def _candles_raw_metrics_run_args(cfg: dict, cache_dir: str,
                                  series_by_key: dict) -> tuple:
    """liqladder.run_analysis's fetch_metrics contract differs from
    oibuild_study/liqrev's fetch_metric: it needs raw, unfiltered metric rows
    ([(ts, {field: value, ...})]) because it extracts two fields itself
    (cfg["oi_field"] and cfg["ratio_field"]), not one field pre-filtered by
    the fetch closure. Reusing _candles_metric_run_args here raised
    KeyError('metrics_field') -- liqladder's registration.json has no such
    key -- discovered while manually verifying Task 2 behavior preservation."""
    interval = cfg.get("interval", "4h")

    def fetch_candles(sym, start, end):
        candles = offline_fetch_perp_candles(sym, interval, start, end, cache_dir)
        series_by_key[f"{sym}:candles"] = series_fingerprint(candles)
        return candles

    def fetch_metrics(sym, start, end):
        raw = offline_fetch_metrics_history(sym, start, end, cache_dir)
        series_by_key[f"{sym}:metric"] = raw_series_fingerprint(raw)
        return raw

    return (fetch_candles, fetch_metrics)


def _candles_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    interval = cfg.get("interval", "4h")

    def fetch_candles(sym, start, end):
        candles = offline_fetch_perp_candles(sym, interval, start, end, cache_dir)
        series_by_key[f"{sym}:candles"] = series_fingerprint(candles)
        return candles

    return (fetch_candles,)


def _candles_bookdepth_run_args(cfg: dict, cache_dir: str,
                                series_by_key: dict) -> tuple:
    interval = cfg.get("interval", "4h")

    def fetch_candles(sym, start, end):
        candles = offline_fetch_perp_candles(sym, interval, start, end, cache_dir)
        series_by_key[f"{sym}:candles"] = series_fingerprint(candles)
        return candles

    def fetch_metric(sym, start, end):
        points = imbalance_points(
            offline_fetch_bookdepth_history(sym, start, end, cache_dir))
        series_by_key[f"{sym}:metric"] = raw_series_fingerprint(points)
        return points

    return (fetch_candles, fetch_metric)


def _ohlcv_loader_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    """A bare OhlcvCache.load(sym, tf) loader -- shared by drift_screen_stack_path
    and drift_screen, both of which call their loader with (sym, tf) rather than
    the (sym, start, end) window shape offline_fetch_perp_candles/_candles_run_args
    use."""
    from moonface.data.ohlcv import OhlcvCache

    cache = OhlcvCache(cache_dir)

    def load(sym, tf):
        candles = cache.load(sym, tf)
        if candles:
            series_by_key[f"{sym}:candles"] = series_fingerprint(candles)
        return candles

    return (load,)


def _drift_screen_stack_path_run(cfg: dict, load, out_dir) -> dict:
    """Kernel-callable twin of tools.lanes.drift_screen_stack_path.cmd_run:
    same pool-build/screen/curve logic, but cfg and the candle loader are
    injected (reproduce()'s contract) instead of read from out_dir/
    registration.json and a hardcoded OhlcvCache. cmd_run itself is
    untouched -- this lane has no run_analysis/run_pipeline function to
    reuse (unlike bookdepth_study), so its equivalent lives here instead."""
    if stack_path_identity_hash(cfg) != cfg["identity_hash"]:
        sys.exit("identity_hash mismatch: the frozen construction was edited")

    pool: dict = {}
    for sym in cfg["universe"]:
        candles = load(sym, cfg["timeframe"])
        if candles:
            pool[sym] = candles

    primary = screen_signal(
        "stack_path", stack_path_generator, cfg["params"], pool,
        h=cfg["h"], atr_period=cfg["atr_period"], floor=cfg["floor"],
        min_events=cfg["min_events"], min_assets=cfg["min_assets"])

    curve = []
    for h in cfg["curve_horizons"]:
        r = screen_signal(
            "stack_path", stack_path_generator, cfg["params"], pool,
            h=h, atr_period=cfg["atr_period"], floor=cfg["floor"],
            min_events=cfg["min_events"], min_assets=cfg["min_assets"])
        v = r["verdict"]
        curve.append({"h": h, "m_assets": v["m_assets"],
                      "pooled_ret_r": v["pooled_ret_r"],
                      "pooled_abs_mae_r": v["pooled_abs_mae_r"],
                      "ratio": v["ratio"], "p_sign": v["p_sign"],
                      "stouffer_z": v["stouffer_z"],
                      "n_events": sum(a["n"] for a in r["assets"])})

    return {"registration": cfg, "primary": primary, "curve_descriptive": curve}


def _drift_screen_run(cfg: dict, loader, out_dir) -> dict:
    """Kernel-callable twin of tools.lanes.drift_screen.cmd_run: same
    pool-build/screen-every-signal/sort logic, but cfg and the candle loader are
    injected instead of read from out_dir/registration.json and a hardcoded
    OhlcvCache -- cmd_run itself is untouched. Unlike drift_screen_stack_path,
    drift_screen's cmd_run already accepted an injectable loader; the only gap
    was cfg being read from disk and the result never returned (only written to
    leaderboard.json). resolve_signal is imported from the lane file itself
    (drift_screen_stack_path's precedent), so drift_screen.py is not modified.
    The result is wrapped under "leaderboard" (a bare list otherwise, which
    reproduce()'s field-by-field dict comparison can't index into) -- see
    tools/research.py's _load_recorded, which wraps the recorded leaderboard.json
    the same way."""
    from tools.lanes.drift_screen import resolve_signal

    pool: dict = {}
    for sym in cfg["universe"]:
        candles = loader(sym, cfg["timeframe"])
        if candles:
            pool[sym] = candles

    results = []
    for sig in cfg["signals"]:
        results.append(screen_signal(
            sig["name"], resolve_signal(sig["name"]), sig["params"], pool,
            h=cfg["h"], atr_period=cfg["atr_period"], floor=cfg["floor"],
            min_events=cfg["min_events"], min_assets=cfg["min_assets"]))
    results.sort(key=lambda r: -1.0 if r["verdict"]["ratio"] is None
                 else r["verdict"]["ratio"], reverse=True)
    return {"leaderboard": results}


_FAR_FUTURE_MS = 4_102_444_800_000  # 2100-01-01: an "everything cached" upper bound


def _multifamily_readers_run_args(cfg: dict, cache_dir: str,
                                  series_by_key: dict) -> tuple:
    """Offline cache-only readers matching multifamily_loader.load_pool_bundles'
    call shape (candles(sym, tf), funding(sym), metrics(sym, field),
    bookdepth(sym)) -- unwindowed (the full cached series for each symbol),
    same precedent as _ohlcv_loader_run_args: a closed lane's cache already
    holds exactly what the frozen run fetched, and a synthetic "now"-based
    window (cmd_run's default when no readers are injected) would make the
    harness itself non-deterministic across repeated invocations. funding uses
    offline_fetch_funding_history_series (data.series.FundingCache's
    ccxt-symbol cache), distinct from _daily_funding_run_args' offline_fetch_
    funding_rates (data.universe's plain-symbol cache) -- multifamily_loader.
    default_readers wires the former, not the latter."""
    from moonface.data.ohlcv import OhlcvCache

    ohlcv = OhlcvCache(cache_dir)

    def candles(sym, tf):
        bars = ohlcv.load(sym, tf)
        if bars:
            series_by_key[f"{sym}:candles"] = series_fingerprint(bars)
        return bars or []

    def funding(sym):
        funding_symbol = f"{sym[:-4]}/USDT:USDT"
        points = offline_fetch_funding_history_series(
            funding_symbol, 0, _FAR_FUTURE_MS, cache_dir)
        if not points:
            return None
        series_by_key[f"{sym}:funding"] = raw_series_fingerprint(points)
        return align_funding(ohlcv.load(sym, "4h") or [], points)

    def metrics(sym, field):
        raw = offline_fetch_metrics_history(sym, 0, _FAR_FUTURE_MS, cache_dir)
        points = [(ts, f[field]) for ts, f in raw if field in f]
        if not points:
            return None
        series_by_key[f"{sym}:metric:{field}"] = raw_series_fingerprint(points)
        return align_metric(ohlcv.load(sym, "4h") or [], points)

    def bookdepth(sym):
        rows = offline_fetch_bookdepth_history(sym, 0, _FAR_FUTURE_MS, cache_dir)
        points = imbalance_points(rows)
        if not points:
            return None
        series_by_key[f"{sym}:bookdepth"] = raw_series_fingerprint(points)
        return bar_mean_imbalance(ohlcv.load(sym, "4h") or [], points)

    readers = {"candles": candles, "funding": funding,
              "metrics": metrics, "bookdepth": bookdepth}
    return (readers,)


def _drift_screen_multifamily_run(cfg: dict, readers: dict, out_dir) -> dict:
    """Kernel-callable twin of tools.lanes.drift_screen_multifamily.cmd_run:
    same per-metrics-field pool build / per-family screen+curve loop, but cfg
    and readers are injected instead of read from out_dir/registration.json
    and multifamily_loader.default_readers' live-network-capable fetchers.
    cmd_run itself is untouched. Result wrapped under "leaderboard" -- same
    list-shaped-verdict precedent as _drift_screen_run."""
    from tools.lanes.drift_screen_multifamily import DEFAULT_FIELD, METRICS_FIELD

    symbols = cfg["universe"]
    pools: dict[str, dict] = {}

    def pool_for(field):
        if field not in pools:
            pools[field] = load_pool_bundles(symbols, metrics_field=field, **readers)
        return pools[field]

    results = []
    for spec in cfg["families"]:
        fam, params, h = spec["family"], spec["params"], spec["h"]
        field = METRICS_FIELD.get(fam, DEFAULT_FIELD)
        pool = pool_for(field)
        floor = cfg["floors"][str(h)]
        res = screen_family(fam, params, pool, h=h, atr_period=cfg["atr_period"],
                            floor=floor, min_events=cfg["min_events"],
                            min_assets=cfg["min_assets"])
        res["curve"] = horizon_curve(fam, params, pool, horizons=cfg["curve_horizons"],
                                     atr_period=cfg["atr_period"],
                                     min_events=cfg["min_events"],
                                     min_assets=cfg["min_assets"])
        results.append(res)

    results.sort(key=lambda r: -1.0 if r["verdict"]["ratio"] is None
                 else r["verdict"]["ratio"], reverse=True)
    return {"leaderboard": results}


def _bb_candles_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    """A (sym, tf, start, end) candle loader matching tools.engine.smc_decompose.
    _load_candles' contract: 4h with cfg["from_1h"] True (the frozen default for
    all three bb_* lanes) aggregates from the 1h cache via aggregate_4h, exactly
    as _load_candles does, so this is offline_fetch_perp_candles + aggregate_4h,
    not a new aggregation path."""

    def load(sym, tf, start, end):
        if tf == "4h" and cfg.get("from_1h", True):
            candles = aggregate_4h(offline_fetch_perp_candles(sym, "1h", start, end, cache_dir))
        else:
            candles = offline_fetch_perp_candles(sym, tf, start, end, cache_dir)
        if candles:
            series_by_key[f"{sym}:candles"] = series_fingerprint(candles)
        return candles

    return (load,)


def _bb_variant_run(cfg: dict, load, out_dir, grid: dict) -> dict:
    """Shared kernel-callable twin of tools.lanes.bb_breakout.cmd_run and
    tools.lanes.bb_revert.cmd_run's identical GRID/score_variant/slice_events
    logic (only the GRID dict differs between the two lanes, injected by each
    lane's own thin run_fn below) -- cfg and the candle loader are injected
    instead of read from out_dir/registration.json and a hardcoded
    fetch_perp_candles/aggregate_4h call, same precedent as _drift_screen_run.
    Neither lane file is modified."""
    candles = load(cfg["symbol"], cfg["tf"], cfg["start_ms"], cfg["end_ms"])
    variants = {name: [score_variant(candles, gen, params) for params in param_grid]
               for name, (param_grid, gen) in grid.items()}
    return {
        "n_bars": len(candles),
        "variants": variants,
        "slices": {name: [{"params": r["params"], "slices": slice_events(r["events"])}
                          for r in rows]
                   for name, rows in variants.items()},
    }


def _bb_breakout_run(cfg: dict, load, out_dir) -> dict:
    return _bb_variant_run(cfg, load, out_dir, BB_BREAKOUT_GRID)


def _bb_revert_run(cfg: dict, load, out_dir) -> dict:
    return _bb_variant_run(cfg, load, out_dir, BB_REVERT_GRID)


def _bb_harvest_run(cfg: dict, load, out_dir) -> dict:
    """Kernel-callable twin of tools.lanes.bb_harvest.main: reuses
    moonface.research.bb_harvest.run (already pure -- candles in, rows out)
    directly, only the candle load + train/OOS holdout split are injected.
    experiments/bb_harvest/results_4h.json is a bare list (not a dict), so
    -- same precedent as drift_screen/drift_screen_multifamily's "leaderboard"
    wrapping -- the key here must match verdict_filename's stem ("results_4h")
    for reproduce()'s dict comparison to find it."""
    full = load(cfg["symbol"], cfg["tf"], cfg["start_ms"], cfg["end_ms"])
    train_oos = full[:-cfg["holdout_bars"]]
    return {"results_4h": bb_harvest_run(train_oos, full)}


def _donchian_filter_run_args(cfg: dict, cache_dir: str,
                              series_by_key: dict) -> tuple:
    """Single-symbol candles+funding, the same two offline fetchers
    _daily_funding_run_args already uses (fetch_perp_candles/fetch_funding_rates
    via moonface.research.universe_data, a re-export shim over moonface.data.
    universe -- confirmed by reading donchian_filter.data.load) but called
    directly rather than per-universe-symbol, since donchian_filter is a
    fixed-BTC lane with no universe loop."""
    interval = cfg.get("interval", "4h")

    def fetch_candles(sym, start, end):
        candles = offline_fetch_perp_candles(sym, interval, start, end, cache_dir)
        series_by_key[f"{sym}:candles"] = series_fingerprint(candles)
        return candles

    def fetch_funding(sym, start, end):
        points = offline_fetch_funding_rates(sym, start, end, cache_dir)
        series_by_key[f"{sym}:funding"] = raw_series_fingerprint(points)
        return points

    return (fetch_candles, fetch_funding)


def _regime_overlay_run_args(cfg: dict, cache_dir: str,
                             series_by_key: dict) -> tuple:
    """Same two candle/funding offline fetchers as _donchian_filter_run_args,
    plus a third fetch_macro() over the frozen FRED_SERIES ids (SP500/
    VIXCLS/DTWEXBGS) via offline_fetch_fred_series. Unwindowed (no start_ms/
    end_ms) -- matches regime_overlay.data.load_macro's own call shape
    (fetch(sid, cache_dir), no window args at all), same "full cached series"
    precedent as drift_screen_multifamily's readers."""
    interval = cfg.get("interval", "4h")

    def fetch_candles(sym, start, end):
        candles = offline_fetch_perp_candles(sym, interval, start, end, cache_dir)
        series_by_key[f"{sym}:candles"] = series_fingerprint(candles)
        return candles

    def fetch_funding(sym, start, end):
        points = offline_fetch_funding_rates(sym, start, end, cache_dir)
        series_by_key[f"{sym}:funding"] = raw_series_fingerprint(points)
        return points

    def fetch_macro():
        macro = {sid: offline_fetch_fred_series(sid, cache_dir)
                 for sid in REGIME_OVERLAY_FRED_SERIES}
        for sid, points in macro.items():
            series_by_key[f"fred:{sid}"] = raw_series_fingerprint(
                [(p.ts_ms, p.value) for p in points])
        return macro

    return (fetch_candles, fetch_funding, fetch_macro)


def _regime_selector_run_args(cfg: dict, cache_dir: str,
                              series_by_key: dict) -> tuple:
    """Two fetchers only -- unlike _regime_overlay_run_args's three, this
    lane has no fetch_funding: its evaluate/selector chain (cell_vector/
    control_vector -> selector_rt/control_rt, confirmed by reading
    selector.py) never consumes funding at all. Candle fetcher shared with
    _donchian_filter_run_args/_regime_overlay_run_args; macro fetcher reuses
    offline_fetch_fred_series unwindowed -- resolves the uncertainty
    regime_overlay's slice flagged: yes, regime_selector.data.load_macro
    calls fetch_fred_series the identical unwindowed way (confirmed by
    reading data.py)."""
    interval = cfg.get("interval", "4h")

    def fetch_candles(sym, start, end):
        candles = offline_fetch_perp_candles(sym, interval, start, end, cache_dir)
        series_by_key[f"{sym}:candles"] = series_fingerprint(candles)
        return candles

    def fetch_macro():
        macro = {sid: offline_fetch_fred_series(sid, cache_dir)
                 for sid in REGIME_SELECTOR_FRED_SERIES}
        for sid, points in macro.items():
            series_by_key[f"fred:{sid}"] = raw_series_fingerprint(
                [(p.ts_ms, p.value) for p in points])
        return macro

    return (fetch_candles, fetch_macro)


def _ls_tournament_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    """Four fetchers -- the most this 6-lane group needs. Unlike every other
    lane here (single fixed interval from cfg), ls_tournament.py's own
    _load_timeframes fetches BOTH grid.TIMEFRAMES ("2h" and "4h") over the
    same window, so fetch_candles takes tf as a call argument rather than
    reading cfg["interval"]. fetch_funding/fetch_macro mirror
    _donchian_filter_run_args/_regime_selector_run_args exactly (macro reuses
    REGIME_SELECTOR_FRED_SERIES -- ls_tournament.py's own load_macro import
    comes from regime_selector.data, which reads regime_selector.grid.
    FRED_SERIES internally, confirmed by reading data.py). fetch_oi is new:
    offline_fetch_metrics_history filtered to "sum_open_interest", the same
    inline extraction ls_tournament.py's own _load_context performs
    (raw = fetch_metrics_history(...); oi_points = [(ts, f["sum_open_interest"])
    for ts, f in raw if "sum_open_interest" in f])."""

    def fetch_candles(tf, sym, start, end):
        candles = offline_fetch_perp_candles(sym, tf, start, end, cache_dir)
        series_by_key[f"{sym}:candles:{tf}"] = series_fingerprint(candles)
        return candles

    def fetch_funding(sym, start, end):
        points = offline_fetch_funding_rates(sym, start, end, cache_dir)
        series_by_key[f"{sym}:funding"] = raw_series_fingerprint(points)
        return points

    def fetch_macro():
        macro = {sid: offline_fetch_fred_series(sid, cache_dir)
                 for sid in REGIME_SELECTOR_FRED_SERIES}
        for sid, points in macro.items():
            series_by_key[f"fred:{sid}"] = raw_series_fingerprint(
                [(p.ts_ms, p.value) for p in points])
        return macro

    def fetch_oi(sym, start, end):
        raw = offline_fetch_metrics_history(sym, start, end, cache_dir)
        points = [(ts, f["sum_open_interest"]) for ts, f in raw if "sum_open_interest" in f]
        series_by_key[f"{sym}:oi"] = raw_series_fingerprint(points)
        return points

    return (fetch_candles, fetch_funding, fetch_macro, fetch_oi)


def _sse_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    """Composes two already-solved loader shapes rather than inventing a
    fifth: tools.sse.sse.load_gate0_inputs needs the same top-volume-universe
    primitives _breadth_universe_run_args already wires (offline_
    list_um_perp_symbols/offline_fetch_perp_candles/offline_fetch_daily_klines)
    PLUS a BTC-only funding/OI reader pair, which is exactly
    _multifamily_readers_run_args' readers["funding"]/readers["metrics"]
    shape -- confirmed by reading load_gate0_inputs: it calls
    readers["funding"](sym)/readers["metrics"](sym, "sum_open_interest") for
    BTCUSDT only, the same two calls default_readers' dict supports. No new
    kernel primitive needed."""
    fetch_candles, symbols, fetch_daily = _breadth_universe_run_args(
        cfg, cache_dir, series_by_key)
    (readers,) = _multifamily_readers_run_args(cfg, cache_dir, series_by_key)
    return (fetch_candles, symbols, fetch_daily, readers)


def _daily_funding_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    symbols = offline_list_um_perp_symbols(cache_dir)

    def fetch_daily(sym, start, end):
        rows = offline_fetch_daily_klines(sym, start, end, cache_dir)
        series_by_key[f"{sym}:daily"] = raw_series_fingerprint(
            [(r.ts_ms, r.close) for r in rows])
        return rows

    def fetch_funding(sym, start, end):
        points = offline_fetch_funding_rates(sym, start, end, cache_dir)
        series_by_key[f"{sym}:funding"] = raw_series_fingerprint(points)
        return points

    return (symbols, fetch_daily, fetch_funding)


def _ls_exit_ablation_split(candles: list) -> dict:
    """Mirrors tools.lanes.ls_exit_ablation._split_60_20_20 exactly (not
    imported: that module is a CLI script with sys.path surgery at import
    time, same reason bb_harvest's tiny glue is reimplemented rather than
    imported from its CLI wrapper)."""
    n = len(candles)
    a, b = int(0.6 * n), int(0.8 * n)
    return {"train": candles[:a], "validate": candles[a:b], "sealed": candles[b:]}


def _ls_exit_ablation_run(cfg: dict, fetch_candles, out_dir) -> dict:
    """Kernel-callable twin of tools.lanes.ls_exit_ablation.run: reuses
    moonface.research.ls_tournament.exit_ablation.run_ablation directly
    (already pure -- segments in, {baseline_sealed_total_r, rows} out), only
    the candle fetch + 60/20/20 split are injected. xcheck_ok/asof/data_sha
    are the CLI wrapper's own bookkeeping, not run_ablation's output, so
    they're outside compare_fields -- bars is the one CLI-added field worth
    comparing (a cache-growth canary, same role as bb_variant's n_bars)."""
    candles = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    segments = _ls_exit_ablation_split(candles)
    return {"bars": len(candles), **run_ablation(segments)}


def _exit_probe_run(cfg: dict, fetch_candles, out_dir) -> dict:
    """Kernel-callable twin of tools.lanes.exit_probe.run_exit_probe: reuses
    moonface.research.edge.exit_score.run_exit_battery directly (already
    pure -- candles+entry_specs in, sorted ExitRow list out), only the candle
    fetch is injected. cfg["interval"] doubles as both the OhlcvCache
    timeframe key (matching _candles_run_args' own convention) and the
    ENTRY_SPECS_BY_TF lookup key, since the two must always agree for a given
    frozen run. leaderboard.json is a bare JSON list (same as drift_screen),
    so the recorded verdict wraps under the "leaderboard" key -- compare_fields
    is that one key, not a hand-picked subset of ExitRow fields.

    funding_probe/positioning_exit_probe/basis_probe were investigated
    alongside exit_probe (same timestamped-run-dir family, same
    now()-years()-back CLI shape) but found BLOCKED, not converted: their
    frozen runs read the perp/spot symbol in ccxt form ("BTC/USDT:USDT" /
    "BTC/USDT"), and .backtest_cache/'s OhlcvCache file for that exact key
    (BTC_USDT:USDT_4h.csv) now holds only a ~113-day recent slice (681 rows,
    2026-03..2026-07) -- some other, later lane's short-window fetch appears
    to have replaced the multi-year history a 2026-06 run would have needed;
    the spot key (BTC_USDT_4h.csv) has no 4h file at all. This is a data-
    availability blocker, not a design-scoping one (contrast the 4 lanes'
    original "which stamped run" question, which turned out to be moot --
    each of these has exactly one stamped dir): reproduce raises
    ValueError from split_research_tail on an under-length candle series.
    Do not re-attempt without either backfilling that cache key's full
    history or accepting a live-network fetch (which the harness's offline-
    only invariant forbids doing silently inside reproduce)."""
    candles = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    entry_specs = ENTRY_SPECS_BY_TF[cfg.get("interval", "1h")]
    rows = run_exit_battery(candles, entry_specs, EXIT_REGISTRY,
                            oos_tail_bars=cfg["oos_tail_bars"], warmup=cfg["warmup"],
                            future_bars=cfg["future_bars"])
    return {"leaderboard": [asdict(r) for r in rows]}


def _advval_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    """Loaders dict matching tools.advval.advval_run.default_loaders' call
    shape (candles(interval), funding(), oi(candles_4h)) -- the first G6.3
    lane (a research/<lane>/ package with its own tools/<lane>/<lane>_run.py
    CLI, not a tools/lanes/<name>.py file; compute_cell_aucs is already
    exactly as injectable as any G6.2 run_analysis). Cache-only substitutes
    for default_loaders' live-fallback fetchers: offline_fetch_perp_candles,
    offline_fetch_funding_history_series (FundingCache's ccxt-symbol
    convention, cfg["funding_symbol"] -- same reader as
    _multifamily_readers_run_args' funding, distinct from
    _daily_funding_run_args' plain-symbol data.universe cache), and
    offline_fetch_metrics_history filtered to cfg["metrics_field"]."""
    field = cfg["metrics_field"]

    def candles(interval: str):
        bars = offline_fetch_perp_candles(
            cfg["symbol"], interval, cfg["window_start_ms"], cfg["window_end_ms"],
            cache_dir)
        series_by_key[f"{cfg['symbol']}:candles:{interval}"] = series_fingerprint(bars)
        return bars

    def funding():
        points = offline_fetch_funding_history_series(
            cfg["funding_symbol"], cfg["window_start_ms"], cfg["window_end_ms"],
            cache_dir)
        series_by_key[f"{cfg['funding_symbol']}:funding"] = raw_series_fingerprint(points)
        return points

    def oi(candles_4h):
        raw = offline_fetch_metrics_history(
            cfg["symbol"], cfg["window_start_ms"], cfg["window_end_ms"], cache_dir)
        points = [(ts, fields[field]) for ts, fields in raw if field in fields]
        series_by_key[f"{cfg['symbol']}:metric:{field}"] = raw_series_fingerprint(points)
        return align_metric(candles_4h, points)

    return ({"candles": candles, "funding": funding, "oi": oi},)


def _advval_run(cfg: dict, loaders: dict, out_dir) -> dict:
    """Kernel-callable twin of tools.advval.advval_run.cmd_run: reuses
    compute_cell_aucs/retrodiction_verdict directly (already pure -- cfg +
    loaders in, {cells, retrodiction} out), skipping cmd_run's one-touch
    out_dir guard and RESULT.md/results.json writes -- reproduce() only ever
    runs against a scratch out_dir, never the frozen experiments/advval/ one."""
    cells = compute_cell_aucs(cfg, loaders)
    retro = retrodiction_verdict(
        {name: cells[name]["auc"] for name in cfg["cells"]},
        n_boot=cfg["bootstrap"]["n_boot"], seed=cfg["bootstrap"]["seed"])
    return {"cells": cells, "retrodiction": retro}


def _eventtime_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    """Loaders dict matching tools.eventtime.eventtime_run.default_loaders'
    call shape (calib_minutes(), test_minutes(), clock_4h()). Cache-only
    substitutes for default_loaders' live-fallback fetchers:
    offline_fetch_vision_1m (new -- eventtime is the first lane needing
    minute-level Vision klines) and offline_fetch_perp_candles. MinuteBar
    series are fingerprinted via raw_series_fingerprint over (ts_ms, close)
    pairs -- core.stats.series_fingerprint expects Candle's
    .timestamp_ms/.close attrs, which MinuteBar doesn't have."""

    def calib_minutes():
        bars = offline_fetch_vision_1m(
            cfg["symbol"], cfg["calib_start_ms"], cfg["calib_end_ms"], cache_dir)
        series_by_key[f"{cfg['symbol']}:vision1m:calib"] = raw_series_fingerprint(
            [(b.ts_ms, b.close) for b in bars])
        return bars

    def test_minutes():
        bars = offline_fetch_vision_1m(
            cfg["symbol"], cfg["test_start_ms"], cfg["test_end_ms"], cache_dir)
        series_by_key[f"{cfg['symbol']}:vision1m:test"] = raw_series_fingerprint(
            [(b.ts_ms, b.close) for b in bars])
        return bars

    def clock_4h():
        bars = offline_fetch_perp_candles(
            cfg["symbol"], cfg["clock_timeframe"], cfg["test_start_ms"],
            cfg["test_end_ms"], cache_dir)
        series_by_key[f"{cfg['symbol']}:candles:{cfg['clock_timeframe']}"] = (
            series_fingerprint(bars))
        return bars

    return ({"calib_minutes": calib_minutes, "test_minutes": test_minutes,
             "clock_4h": clock_4h},)


def _eventtime_run(cfg: dict, loaders: dict, out_dir) -> dict:
    """Kernel-callable twin of tools.eventtime.eventtime_run.cmd_run:
    compute() is already pure (cfg + loaders in, dict out, no out_dir
    writes) and its return shape already matches results.json exactly, so
    it's reused directly -- skipping cmd_run's one-touch
    registration.json/results.json guards."""
    return eventtime_compute(cfg, loaders)


def _breadth_universe_run_args(cfg: dict, cache_dir: str,
                               series_by_key: dict) -> tuple:
    """Same offline_fetch_perp_candles/offline_list_um_perp_symbols/
    offline_fetch_daily_klines primitives _daily_funding_run_args already
    uses for bab/xsection/liqprem/resrev -- no new kernel primitive needed.
    Breadth's membership universe needs BTC candles plus every symbol's
    daily klines, no funding rate, so this is a new 3-tuple shape
    (fetch_candles, symbols, fetch_daily) rather than reusing that function
    directly."""
    interval = cfg.get("interval", "4h")
    symbols = offline_list_um_perp_symbols(cache_dir)

    def fetch_candles(sym, start, end):
        candles = offline_fetch_perp_candles(sym, interval, start, end, cache_dir)
        series_by_key[f"{sym}:candles"] = series_fingerprint(candles)
        return candles

    def fetch_daily(sym, start, end):
        rows = offline_fetch_daily_klines(sym, start, end, cache_dir)
        series_by_key[f"{sym}:daily"] = raw_series_fingerprint(
            [(r.ts_ms, r.close) for r in rows])
        return rows

    return (fetch_candles, symbols, fetch_daily)


def _breadth_sha(candles) -> str:
    """Mirrors tools.breadth.breadth._sha exactly -- not imported since it's
    a leading-underscore module-private helper, same reason
    _ls_exit_ablation_split reimplements rather than imports
    tools.lanes.ls_exit_ablation's private split helper."""
    return hashlib.sha256(
        ",".join(f"{c.timestamp_ms}:{c.close}" for c in candles).encode()
    ).hexdigest()[:16]


def _breadth_run(cfg: dict, fetch_candles, symbols, fetch_daily, out_dir) -> dict:
    """Kernel-callable twin of tools.breadth.breadth._validate: the
    register/explore/select stages are frozen data already recorded in
    frozen_candidates.json -- injected here as cfg["frozen_cells"] rather
    than re-run (re-running select would re-derive the DSR-gated survivor
    set instead of reproducing the frozen one). Only the validate stage
    (moonface.research.breadth.gates.validate_cell, already pure) is
    recomputed, against the same membership_fn/split_60_20_20/
    universe_covers_train helpers tools/breadth/breadth.py itself uses --
    imported directly (public, no CLI side effects), not reimplemented."""
    btc = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    daily: dict = {}
    for sym in symbols:
        rows = fetch_daily(sym, cfg["start_ms"], cfg["end_ms"])
        if rows:
            daily[sym] = rows

    is_member = membership_fn(
        daily, cfg["top_n"], cfg["min_history_days"], cfg["vol_days"],
        cfg["rebalance_days"])
    _, val, seal = split_60_20_20(btc)
    if not universe_covers_train(daily, is_member, val):
        raise RuntimeError(
            "breadth: universe daily history does not cover the validate "
            "window -- the frozen run's own feasibility guard would have "
            "failed too, so this isn't a reproduction mismatch to record")

    frozen_keys = set(cfg["frozen_cells"])
    cells = [cell for cell in all_cells() if cell.key in frozen_keys]
    rows = [validate_cell(daily, val, seal, cell, is_member) for cell in cells]
    verdict = ("paper_candidate"
              if any(row["verdict"] == "paper_candidate" for row in rows)
              else "negative")
    return {"verdict": verdict, "rows": rows, "btc_sha": _breadth_sha(btc)}


def _breadth_confirm_run(cfg: dict, fetch_candles, symbols, fetch_daily,
                         out_dir) -> dict:
    """Kernel-callable twin of tools.breadth_confirm.breadth_confirm._validate.
    Reuses breadth's own universe loaders (_breadth_universe_run_args, shared
    via the breadth LANES entry -- no new run_args_builder, same primitives).
    net_new_highs_spec/slice_membership_fn/evaluate_spec/evaluate_slice_overlap/
    judge_signal are all public and pure, imported directly rather than
    reimplemented -- same precedent as breadth's validate_cell reuse.
    discovery_xcheck_ok is deliberately NOT recomputed here: RESULT.json's own
    "discovery" field already holds the frozen validate/sealed expectancy+n,
    so the harness's own field-by-field compare_fields does that x-check,
    without mirroring the CLI's private _XCHECK constant."""
    btc = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    daily: dict = {}
    for sym in symbols:
        rows = fetch_daily(sym, cfg["start_ms"], cfg["end_ms"])
        if rows:
            daily[sym] = rows

    _, val, seal = split_60_20_20(btc)
    spec = net_new_highs_spec()

    disc_member = slice_membership_fn(
        daily, *cfg["discovery_slice"], cfg["min_history_days"], cfg["vol_days"],
        cfg["rebalance_days"])
    disc_validate = evaluate_spec(daily, val, spec, is_member=disc_member)
    disc_sealed = evaluate_spec(daily, seal, spec, is_member=disc_member)

    rows = []
    for lo, hi in cfg["gated_slices"]:
        is_member = slice_membership_fn(
            daily, lo, hi, cfg["min_history_days"], cfg["vol_days"],
            cfg["rebalance_days"])
        if not universe_covers_train(daily, is_member, val):
            rows.append({"slice": [lo, hi], "status": "infeasible"})
            continue
        validate = evaluate_slice_overlap(daily, val, spec, is_member=is_member)
        sealed = evaluate_slice_overlap(daily, seal, spec, is_member=is_member)
        judge = judge_signal(
            validate["metrics"], sealed["metrics"],
            validate["records"] + sealed["records"], cfg["k_gated"],
            block=True, block_len=cfg["block_len"])
        status = ("confirmed" if judge["verdict"] == "paper_candidate"
                  else "mechanism_unconfirmed")
        rows.append({
            "slice": [lo, hi], "status": status,
            "validate_exp": validate["metrics"]["expectancy_r"],
            "sealed_exp": sealed["metrics"]["expectancy_r"],
            "pooled": judge["pooled"], "boot_lo": judge["boot_lo"],
            "p_le_zero": judge["p_le_zero"], "same_sign": judge["same_sign"],
            "practical": judge["practical"], "cost": judge["cost"],
            "significant": judge["significant"],
        })

    verdict = ("confirmed" if any(r["status"] == "confirmed" for r in rows)
              else "mechanism_unconfirmed")
    return {
        "verdict": verdict,
        "rows": rows,
        "discovery": {
            "validate_exp": disc_validate["metrics"]["expectancy_r"],
            "validate_n": disc_validate["metrics"]["trade_count"],
            "sealed_exp": disc_sealed["metrics"]["expectancy_r"],
            "sealed_n": disc_sealed["metrics"]["trade_count"],
        },
        "btc_sha": _breadth_sha(btc),
    }


def _breadth_momentum_confirm_run(cfg: dict, fetch_candles, symbols, fetch_daily,
                                  out_dir) -> dict:
    """Kernel-callable twin of tools.breadth.breadth_momentum_confirm._validate.
    Reuses breadth's own universe loaders (_breadth_universe_run_args, shared
    via the breadth LANES entry -- same as breadth_confirm, no new
    run_args_builder). Differs from breadth_confirm only in which frozen spec
    is confirmed (breadth_momentum_spec, not net_new_highs_spec) and which
    evaluator computes metrics: evaluate_hf_spec plays both roles
    breadth_confirm splits across evaluate_spec (discovery, non-overlapping)
    and evaluate_slice_overlap (gated slices) -- the HF grid's own
    overlapping-entries state machine needs no separate overlap-aware
    evaluator the way the daily non-overlapping net_new_highs signal does."""
    btc = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    daily: dict = {}
    for sym in symbols:
        rows = fetch_daily(sym, cfg["start_ms"], cfg["end_ms"])
        if rows:
            daily[sym] = rows

    _, val, seal = split_60_20_20(btc)
    spec = breadth_momentum_spec()

    disc_member = slice_membership_fn(
        daily, *cfg["discovery_slice"], cfg["min_history_days"], cfg["vol_days"],
        cfg["rebalance_days"])
    disc_validate = evaluate_hf_spec(daily, val, spec, is_member=disc_member)
    disc_sealed = evaluate_hf_spec(daily, seal, spec, is_member=disc_member)

    rows = []
    for lo, hi in cfg["gated_slices"]:
        is_member = slice_membership_fn(
            daily, lo, hi, cfg["min_history_days"], cfg["vol_days"],
            cfg["rebalance_days"])
        if not universe_covers_train(daily, is_member, val):
            rows.append({"slice": [lo, hi], "status": "infeasible"})
            continue
        validate = evaluate_hf_spec(daily, val, spec, is_member=is_member)
        sealed = evaluate_hf_spec(daily, seal, spec, is_member=is_member)
        judge = judge_signal(
            validate["metrics"], sealed["metrics"],
            validate["records"] + sealed["records"], cfg["k_gated"],
            block=True, block_len=cfg["block_len"])
        status = ("confirmed" if judge["verdict"] == "paper_candidate"
                  else "mechanism_unconfirmed")
        rows.append({
            "slice": [lo, hi], "status": status,
            "validate_exp": validate["metrics"]["expectancy_r"],
            "sealed_exp": sealed["metrics"]["expectancy_r"],
            "pooled": judge["pooled"], "boot_lo": judge["boot_lo"],
            "p_le_zero": judge["p_le_zero"], "same_sign": judge["same_sign"],
            "practical": judge["practical"], "cost": judge["cost"],
            "significant": judge["significant"],
        })

    verdict = ("confirmed" if any(r["status"] == "confirmed" for r in rows)
              else "mechanism_unconfirmed")
    return {
        "verdict": verdict,
        "rows": rows,
        "discovery": {
            "validate_exp": disc_validate["metrics"]["expectancy_r"],
            "validate_n": disc_validate["metrics"]["trade_count"],
            "sealed_exp": disc_sealed["metrics"]["expectancy_r"],
            "sealed_n": disc_sealed["metrics"]["trade_count"],
        },
        "btc_sha": _breadth_sha(btc),
    }


# Mirrors tools.breadth.breadth_neutral.LEAD_BLOCK exactly -- same
# private-constant-copy precedent as _breadth_sha mirroring breadth's _sha.
_BREADTH_NEUTRAL_LEAD_BLOCK = {"net_new_highs": (False, 1), "breadth_momentum": (True, 8)}


def _breadth_neutral_run(cfg: dict, fetch_candles, symbols, fetch_daily,
                         out_dir) -> dict:
    """Kernel-callable twin of tools.breadth.breadth_neutral._validate. Reuses
    breadth's own universe loaders (_breadth_universe_run_args, shared via the
    breadth LANES entry -- fetch_candles already fetches any symbol, so the
    same primitive covers the market (BTC) series and both traded assets, no
    new run_args_builder). lead_specs/entries_provider/hedge_entries/
    rolling_betas/aligned_returns (moonface.research.breadth_confirm.neutral,
    .xasset_grid) and judge_signal/summarize are all public and pure, imported
    directly rather than reimplemented. The frozen beta=0 raw-anchor
    expectations are injected via cfg["anchor_raw_expected"] (measured from
    RESULT.json, not re-derived or mirrored as a private ANCHOR_RAW constant)
    -- same frozen-data-as-cfg precedent as breadth's frozen_cells."""
    btc = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    daily: dict = {}
    for sym in symbols:
        rows = fetch_daily(sym, cfg["start_ms"], cfg["end_ms"])
        if rows:
            daily[sym] = rows
    is_member = membership_fn(
        daily, cfg["top_n"], cfg["min_history_days"], cfg["vol_days"],
        cfg["rebalance_days"])

    k = len(cfg["assets"]) * len(lead_specs())

    def evaluate(asset_full, beta):
        beta_lookup = None
        if beta is None:
            beta_lookup = rolling_betas(aligned_returns(asset_full, btc))
        _, val, seal = split_60_20_20(asset_full)
        out = []
        for spec in lead_specs():
            block, block_len = _BREADTH_NEUTRAL_LEAD_BLOCK[spec.key]
            provider = entries_provider(spec.key)
            rv = hedge_entries(
                val, btc, provider(daily, val, spec, is_member=is_member),
                spec.exit_name, dict(spec.exit_params),
                beta=beta, beta_lookup=beta_lookup)
            rs = hedge_entries(
                seal, btc, provider(daily, seal, spec, is_member=is_member),
                spec.exit_name, dict(spec.exit_params),
                beta=beta, beta_lookup=beta_lookup)
            hedged = rv["hedged"] + rs["hedged"]
            raw = rv["raw"] + rs["raw"]
            judge = judge_signal(
                summarize(rv["hedged"]), summarize(rs["hedged"]), hedged, k,
                block=block, block_len=block_len)
            betas = rv["betas"] + rs["betas"]
            out.append({
                "lead": spec.key,
                "raw_pooled_exp": summarize(raw)["expectancy_r"],
                "hedged_pooled_exp": judge["pooled"]["expectancy_r"],
                "hedged_pooled_pf": judge["pooled"]["profit_factor"],
                "hedged_pooled_dd": judge["pooled"]["max_drawdown_r"],
                "pooled_n": judge["pooled"]["trade_count"],
                "beta_contribution": round(
                    summarize(raw)["expectancy_r"] - judge["pooled"]["expectancy_r"], 4),
                "mean_beta": round(sum(betas) / len(betas), 3) if betas else None,
                "boot_lo": judge["boot_lo"],
                "p_le_zero": judge["p_le_zero"],
                "same_sign": judge["same_sign"],
                "practical": judge["practical"],
                "cost": judge["cost"],
                "significant": judge["significant"],
                "verdict": judge["verdict"],
            })
        return out

    def status(row: dict) -> str:
        if row["verdict"] == "paper_candidate":
            return "neutral_confirmed"
        if row["hedged_pooled_exp"] > 0 and row["same_sign"]:
            return "residual_positive"
        return "beta_explained"

    anchor_rows: dict = {}
    for symbol in cfg["assets"]:
        asset = fetch_candles(symbol, cfg["start_ms"], cfg["end_ms"])
        for row in evaluate(asset, beta=0.0):
            anchor_rows[f"{symbol}/{row['lead']}"] = row["raw_pooled_exp"]
    anchor_ok = all(
        abs(anchor_rows[key] - v) <= 0.01
        for key, v in cfg["anchor_raw_expected"].items())

    rows = []
    for symbol in cfg["assets"]:
        asset = fetch_candles(symbol, cfg["start_ms"], cfg["end_ms"])
        for row in evaluate(asset, beta=None):
            rows.append({"asset": symbol, "status": status(row), **row})

    if any(r["status"] == "neutral_confirmed" for r in rows):
        verdict = "confirmed"
    elif any(r["status"] == "residual_positive" for r in rows):
        verdict = "residual_survives"
    else:
        verdict = "beta_explained"

    return {
        "verdict": verdict,
        "rows": rows,
        "anchor_ok": anchor_ok,
        "anchor_raw_got": anchor_rows,
    }


# Mirrors tools.breadth.breadth_xasset_confirm.LEAD_EVAL exactly -- same
# private-constant-copy precedent as _BREADTH_NEUTRAL_LEAD_BLOCK.
_BREADTH_XASSET_CONFIRM_LEAD_EVAL = {
    "net_new_highs": (evaluate_spec, False, 1),
    "breadth_momentum": (evaluate_hf_spec, True, 8),
}
# Same MIN_BARS floor as the CLI's own module constant.
_BREADTH_XASSET_CONFIRM_MIN_BARS = 300


def _breadth_xasset_confirm_anchor_ok(validate: dict, sealed: dict, expected: dict) -> bool:
    """Mirrors tools.breadth.breadth_xasset_confirm._anchor_ok exactly -- not
    imported since it's a leading-underscore module-private helper, same
    precedent as _breadth_sha mirroring breadth's _sha. expected is injected
    via cfg["anchor_expected"] (frozen data measured from RESULT.json's own
    "anchors" field, not mirrored as a private ANCHOR constant) -- same
    frozen-data-as-cfg precedent as breadth_neutral's anchor_raw_expected."""
    tol = 0.01
    pairs = [
        (validate["metrics"]["expectancy_r"], expected["val_exp"], True),
        (sealed["metrics"]["expectancy_r"], expected["seal_exp"], True),
        (validate["metrics"]["trade_count"], expected["val_n"], False),
        (sealed["metrics"]["trade_count"], expected["seal_n"], False),
    ]
    for got, exp, is_float in pairs:
        if is_float:
            if abs(got - exp) > tol:
                return False
        elif got != exp:
            return False
    return True


def _breadth_xasset_confirm_run(cfg: dict, fetch_candles, symbols, fetch_daily,
                                out_dir) -> dict:
    """Kernel-callable twin of tools.breadth.breadth_xasset_confirm._validate.
    Reuses breadth's own universe loaders (_breadth_universe_run_args, shared
    via the breadth LANES entry -- fetch_candles already fetches any symbol,
    so the same primitive covers the BTC anchor series and both traded
    assets, no new run_args_builder -- same reuse as breadth_neutral).
    lead_specs/evaluate_spec/evaluate_hf_spec/judge_signal are all public and
    pure, imported directly rather than reimplemented. The BTC discovery is
    anchor-x-checked per lead (cfg["anchor_expected"], frozen data) and never
    re-gated, matching the CLI's own never-re-gate-BTC contract."""
    btc = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    daily: dict = {}
    for sym in symbols:
        rows = fetch_daily(sym, cfg["start_ms"], cfg["end_ms"])
        if rows:
            daily[sym] = rows
    is_member = membership_fn(
        daily, cfg["top_n"], cfg["min_history_days"], cfg["vol_days"],
        cfg["rebalance_days"])

    _, btc_val, btc_seal = split_60_20_20(btc)
    anchors = {}
    for spec in lead_specs():
        evaluator, _, _ = _BREADTH_XASSET_CONFIRM_LEAD_EVAL[spec.key]
        av = evaluator(daily, btc_val, spec, is_member=is_member)
        as_ = evaluator(daily, btc_seal, spec, is_member=is_member)
        anchors[spec.key] = {
            "ok": _breadth_xasset_confirm_anchor_ok(
                av, as_, cfg["anchor_expected"][spec.key]),
            "validate_exp": av["metrics"]["expectancy_r"],
            "validate_n": av["metrics"]["trade_count"],
            "sealed_exp": as_["metrics"]["expectancy_r"],
            "sealed_n": as_["metrics"]["trade_count"],
        }
    anchor_ok = all(a["ok"] for a in anchors.values())

    rows = []
    for symbol in cfg["assets"]:
        asset = fetch_candles(symbol, cfg["start_ms"], cfg["end_ms"])
        if len(asset) < _BREADTH_XASSET_CONFIRM_MIN_BARS:
            rows.append({"asset": symbol, "status": "infeasible", "bars": len(asset)})
            continue
        _, val, seal = split_60_20_20(asset)
        if not universe_covers_train(daily, is_member, val):
            rows.append({"asset": symbol, "status": "infeasible_universe"})
            continue
        for spec in lead_specs():
            evaluator, block, block_len = _BREADTH_XASSET_CONFIRM_LEAD_EVAL[spec.key]
            v = evaluator(daily, val, spec, is_member=is_member)
            s = evaluator(daily, seal, spec, is_member=is_member)
            judge = judge_signal(
                v["metrics"], s["metrics"], v["records"] + s["records"], cfg["k"],
                block=block, block_len=block_len)
            status = "confirmed" if judge["verdict"] == "paper_candidate" else (
                "transfers_unconfirmed" if judge["verdict"] == "forward_candidate"
                else "negative")
            rows.append({
                "asset": symbol, "lead": spec.key, "status": status,
                "verdict": judge["verdict"],
                "validate_exp": v["metrics"]["expectancy_r"],
                "sealed_exp": s["metrics"]["expectancy_r"],
                "pooled": judge["pooled"], "boot_lo": judge["boot_lo"],
                "p_le_zero": judge["p_le_zero"], "same_sign": judge["same_sign"],
                "practical": judge["practical"], "cost": judge["cost"],
                "significant": judge["significant"],
            })

    verdict = ("confirmed" if any(r.get("status") == "confirmed" for r in rows)
              else "mechanism_unconfirmed")
    return {
        "verdict": verdict,
        "rows": rows,
        "anchor_ok": anchor_ok,
        "anchors": anchors,
        "btc_anchor_sha": _breadth_sha(btc),
    }


def _breadth_internal_spec_doc(spec) -> dict:
    """Mirrors tools.breadth_internal.breadth_internal._spec_doc exactly --
    same private-helper-mirror precedent as _breadth_sha mirroring _sha."""
    return {
        "key": spec.key,
        "builder": spec.builder,
        "params": dict(spec.params),
        "exit_name": spec.exit_name,
        "exit_params": dict(spec.exit_params),
        "h": spec.h,
    }


def _breadth_internal_run(cfg: dict, fetch_candles, symbols, fetch_daily,
                          out_dir) -> dict:
    """Kernel-callable twin of tools.breadth_internal.breadth_internal._validate.
    Reuses breadth's own universe loaders (_breadth_universe_run_args, shared
    via the breadth LANES entry) -- breadth_internal.py's own CLI imports
    breadth.py's private _load directly, so this is the same primitives, a
    sixth reuse of the loader. Unlike breadth_confirm/breadth_momentum_confirm/
    breadth_xasset_confirm (which gate ONE frozen spec across multiple
    universe slices/assets), breadth_internal validates ALL FOUR of
    all_specs()'s frozen grid over one fixed validate/sealed split -- the
    register/explore stages never narrow the grid (no select stage exists),
    so there's no frozen survivor list to inject as cfg data, unlike
    breadth's frozen_cells. s1_xcheck_ok is deliberately NOT recomputed here:
    rows already carries breadth_thrust's own validate/sealed metrics, so the
    harness's own field-by-field compare_fields does that x-check without
    mirroring the CLI's private _S1_XCHECK constant."""
    btc = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    daily: dict = {}
    for sym in symbols:
        rows = fetch_daily(sym, cfg["start_ms"], cfg["end_ms"])
        if rows:
            daily[sym] = rows

    is_member = membership_fn(
        daily, cfg["top_n"], cfg["min_history_days"], cfg["vol_days"],
        cfg["rebalance_days"])
    _, val, seal = split_60_20_20(btc)
    if not universe_covers_train(daily, is_member, val):
        raise RuntimeError(
            "breadth_internal: universe daily history does not cover the "
            "validate window -- the frozen run's own feasibility guard "
            "would have failed too, so this isn't a reproduction mismatch "
            "to record")

    specs = all_specs()
    result_rows = []
    for spec in specs:
        validate = evaluate_spec(daily, val, spec, is_member=is_member)
        sealed = evaluate_spec(daily, seal, spec, is_member=is_member)
        judge = judge_signal(
            validate["metrics"], sealed["metrics"],
            validate["records"] + sealed["records"], len(specs))
        result_rows.append({
            "key": spec.key,
            "spec": _breadth_internal_spec_doc(spec),
            "validate": validate,
            "sealed": sealed,
            "pooled": judge["pooled"],
            "boot_lo": judge["boot_lo"],
            "p_le_zero": judge["p_le_zero"],
            "same_sign": judge["same_sign"],
            "practical": judge["practical"],
            "cost": judge["cost"],
            "significant": judge["significant"],
            "verdict": judge["verdict"],
        })

    if any(row["verdict"] == "paper_candidate" for row in result_rows):
        verdict = "paper_candidate"
    elif any(row["verdict"] == "forward_candidate" for row in result_rows):
        verdict = "forward_candidate"
    else:
        verdict = "negative"

    return {"verdict": verdict, "rows": result_rows, "btc_sha": _breadth_sha(btc)}


def _breadth_internal_hf_run(cfg: dict, fetch_candles, symbols, fetch_daily,
                             out_dir) -> dict:
    """Kernel-callable twin of tools.breadth_internal.breadth_internal_hf._validate,
    Lane 2 of the breadth_internal pairing (HF grid, evaluate_hf_spec, moving-
    block bootstrap) that breadth_momentum_confirm transfers its lead from.
    Reuses breadth's own universe loaders (_breadth_universe_run_args, shared
    via the breadth LANES entry) -- breadth_internal_hf.py's own CLI imports
    breadth.py's private _load directly, same primitives, a seventh reuse of
    the loader (confirms the memory's flagged uncertainty). Like
    breadth_internal, hf_specs()'s fixed 3-signal grid is validated whole
    every run -- no select stage narrows it. overlap_xcheck_ok/block_xcheck_ok
    are deliberately NOT recomputed here, same "let compare_fields do the
    x-check" simplification as breadth_internal's s1_xcheck_ok: rows already
    carries each spec's own validate/sealed metrics."""
    btc = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    daily: dict = {}
    for sym in symbols:
        rows = fetch_daily(sym, cfg["start_ms"], cfg["end_ms"])
        if rows:
            daily[sym] = rows

    is_member = membership_fn(
        daily, cfg["top_n"], cfg["min_history_days"], cfg["vol_days"],
        cfg["rebalance_days"])
    _, val, seal = split_60_20_20(btc)
    if not universe_covers_train(daily, is_member, val):
        raise RuntimeError(
            "breadth_internal_hf: universe daily history does not cover the "
            "validate window -- the frozen run's own feasibility guard "
            "would have failed too, so this isn't a reproduction mismatch "
            "to record")

    specs = hf_specs()
    result_rows = []
    for spec in specs:
        validate = evaluate_hf_spec(daily, val, spec, is_member)
        sealed = evaluate_hf_spec(daily, seal, spec, is_member)
        judge = judge_signal(
            validate["metrics"], sealed["metrics"],
            validate["records"] + sealed["records"], len(specs),
            block=True, block_len=BLOCK_LEN)
        result_rows.append({
            "key": spec.key,
            "spec": _breadth_internal_spec_doc(spec),
            "validate": validate,
            "sealed": sealed,
            "pooled": judge["pooled"],
            "boot_lo": judge["boot_lo"],
            "p_le_zero": judge["p_le_zero"],
            "same_sign": judge["same_sign"],
            "practical": judge["practical"],
            "cost": judge["cost"],
            "significant": judge["significant"],
            "verdict": judge["verdict"],
        })

    if any(row["verdict"] == "paper_candidate" for row in result_rows):
        verdict = "paper_candidate"
    elif any(row["verdict"] == "forward_candidate" for row in result_rows):
        verdict = "forward_candidate"
    else:
        verdict = "negative"

    return {"verdict": verdict, "rows": result_rows, "btc_sha": _breadth_sha(btc)}


def _donchian_filter_run(cfg: dict, fetch_candles, fetch_funding, out_dir) -> dict:
    """Kernel-callable twin of tools.donchian_filter.donchian_filter._validate:
    reuses evaluate.base_trades/gate/slice_metrics, adx.adx_series, and
    select.holdout_verdict directly (all pure, no file I/O) -- only the
    sealed-window candle/funding fetch is injected. The frozen ADX threshold
    (cfg["frozen_threshold"]) is injected as data rather than re-derived --
    the register/explore/select stages (train-window grid search over
    G.THRESHOLDS) are not re-run, matching this tier's "reproduce the frozen
    result, don't re-derive the selection" contract."""
    candles = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    funding = fetch_funding(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    base = base_trades(candles, funding)
    adx = adx_series(candles, cfg["adx_period"])
    base_m = slice_metrics(base)
    gated_m = slice_metrics(gate(base, adx, cfg["frozen_threshold"]))
    return {
        "threshold": cfg["frozen_threshold"],
        "sealed_base": base_m,
        "sealed_gated": gated_m,
        "verdict": holdout_verdict(base_m, gated_m),
    }


def _donchian_volregime_run(cfg: dict, fetch_candles, fetch_funding, out_dir) -> dict:
    """Kernel-callable twin of tools.donchian_volregime.donchian_volregime._validate:
    reuses evaluate.base_trades/cell_flags/gate (dvr_-aliased -- bare names collide
    with donchian_filter's own base_trades/gate, already imported above) plus the
    shared slice_metrics (byte-identical, re-exported from donchian_filter.evaluate
    by donchian_volregime.evaluate itself) and select.sealed_verdict directly --
    only the sealed-window candle/funding fetch is injected. The frozen cell id
    (cfg["frozen_cell"], None in the actual frozen state -- no train qualifier
    cleared select_cell's bar, per frozen_candidate.json) is injected as data
    rather than re-derived, matching donchian_filter/btc_classic's "reproduce the
    frozen result, don't re-derive the selection" contract."""
    if cfg["frozen_cell"] is None:
        return {"verdict": "negative"}
    candles = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    funding = fetch_funding(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    base = dvr_base_trades(candles, funding)
    base_m = slice_metrics(base)
    gated_m = slice_metrics(dvr_gate(base, dvr_cell_flags(candles, cfg["frozen_cell"])))
    return {
        "cell": cfg["frozen_cell"],
        "sealed_base": base_m,
        "sealed_gated": gated_m,
        "verdict": dvr_sealed_verdict(base_m, gated_m),
    }


_REGIME_OVERLAY_REG_BY_ID = {r.id: r for r in REGIME_DEFS}


def _regime_overlay_run(cfg: dict, fetch_candles, fetch_funding, fetch_macro,
                        out_dir) -> dict:
    """Kernel-callable twin of tools.regime_overlay.regime_overlay_btc._validate:
    reuses evaluate.cell_vector/base_vector/practical_pass/beats_base directly
    (all pure) -- only the sealed-window candle/funding fetch plus the
    unwindowed macro fetch are injected. The frozen cell id (cfg["frozen_cell"],
    None in the actual frozen state -- no train+validate survivor, per
    frozen_candidate.json) is injected as data rather than re-derived, same
    "reproduce the frozen result, don't re-derive the selection" contract as
    donchian_filter/btc_classic/donchian_volregime. base_params is the CLI's
    own base_params() (_BASE with entry_n=40/trail_n=20), reconstructed here
    rather than importing the CLI module (kernel-callable code stays outside
    tools/, per this module's own import-boundary convention)."""
    if cfg["frozen_cell"] is None:
        return {"verdict": "negative"}
    cell = next(c for c in REGIME_OVERLAY_CELLS if c.cell_id == cfg["frozen_cell"])
    candles = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    funding = fetch_funding(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    macro = fetch_macro()
    bp = replace(SWING_DONCHIAN_BASE, entry_n=40, trail_n=20)
    cv = cell_vector(candles, funding, bp, _REGIME_OVERLAY_REG_BY_ID[cell.regime_id],
                     macro, cell.mode, cfg["start_ms"], cfg["end_ms"])
    bv = base_vector(candles, funding, bp, cfg["start_ms"], cfg["end_ms"])
    pp = practical_pass(cv)
    vb = beats_base(cv, bv)
    verdict = ("forward_paper_watch" if pp["all_pass"] and vb["beats_recent"]
               else "negative")
    return {"cell": cell.cell_id, "sealed_cell_vector": cv,
            "sealed_base_vector": bv, "practical_pass": pp,
            "beats_base": vb, "verdict": verdict}


def _regime_selector_run(cfg: dict, fetch_candles, fetch_macro, out_dir) -> dict:
    """Kernel-callable twin of tools.regime_selector.regime_selector_btc.
    _validate: reuses regime_selector.evaluate.cell_vector/control_vector
    (rs_-aliased -- bare names collide with regime_overlay's own cell_vector,
    already imported above) plus the shared practical_pass (byte-identical:
    regime_selector.evaluate imports it straight from regime_overlay.evaluate,
    confirmed by reading the module) and its own beats_controls directly (all
    pure) -- only the sealed-window candle fetch plus the unwindowed macro
    fetch are injected, no funding (this lane's chain never touches funding).
    The frozen cell id (cfg["frozen_cell"], None in the actual frozen state --
    no validate survivor, per frozen_candidate.json) is injected as data
    rather than re-derived, same "reproduce the frozen result, don't
    re-derive the selection" contract as donchian_filter/btc_classic/
    donchian_volregime/regime_overlay. Controls reuse _REGIME_OVERLAY_REG_BY_ID
    (identical REGIME_DEFS the CLI's own _REG builds from) keyed by the first
    of this lane's own REGIME_IDS, same "arbitrary regime def, always_* ignore
    it" shape as the CLI's _controls helper. beats_controls is called with
    recent=False, matching the CLI's own sealed-validate call."""
    if cfg["frozen_cell"] is None:
        return {"verdict": "negative"}
    cell = next(c for c in REGIME_SELECTOR_CELLS if c.cell_id == cfg["frozen_cell"])
    candles = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    macro = fetch_macro()
    reg = _REGIME_OVERLAY_REG_BY_ID[cell.regime_id]
    cv = rs_cell_vector(candles, macro, reg, cell.riskoff_action,
                        cfg["start_ms"], cfg["end_ms"])
    any_reg = _REGIME_OVERLAY_REG_BY_ID[REGIME_SELECTOR_REGIME_IDS[0]]
    trend_c = rs_control_vector(candles, macro, any_reg, "always_trend",
                                cfg["start_ms"], cfg["end_ms"])
    mr_c = rs_control_vector(candles, macro, any_reg, "always_mr",
                             cfg["start_ms"], cfg["end_ms"])
    pp = practical_pass(cv)
    vb = beats_controls(cv, trend_c, mr_c, recent=False)
    verdict = ("paper_accept" if pp["all_pass"] and vb["beats_both"] else "negative")
    return {"cell": cell.cell_id, "sealed_cell_vector": cv,
            "sealed_trend_control": trend_c, "sealed_mr_control": mr_c,
            "practical_pass": pp, "beats_controls": vb, "verdict": verdict}


def _ls_tournament_run(cfg: dict, fetch_candles, fetch_funding, fetch_macro,
                       fetch_oi, out_dir) -> dict:
    """Kernel-callable twin of tools.ls_tournament.ls_tournament._validate:
    the register/explore/select stages are not re-run -- frozen_candidates.
    json's already-frozen rows are injected via cfg["frozen_rows"] (the full
    row dicts, not lookup keys against a code-level CELLS registry like every
    other lane in this group -- there is no such registry here), same
    "reproduce the frozen result, don't re-derive the selection" contract as
    donchian_filter/btc_classic/donchian_volregime/regime_overlay/
    regime_selector -- only validate_all is reproduced.

    Unlike the rest of this group (whose cfg["start_ms"]/["end_ms"] is just
    the frozen sealed slice), this lane's own _validate recomputes the FULL
    60/20/20 split from one combined per-timeframe fetch, so cfg["start_ms"]/
    ["end_ms"] here must be the tournament's full window (confirmed by
    reading ls_tournament.py's _split_60_20_20 call shape) -- registration.
    json backfills PREREGISTRATION.json's own args (train[0] to sealed[1]),
    not VALIDATE_END/SEALED_END like the rest of the group.

    Both grid.TIMEFRAMES ("2h"/"4h") are fetched even though the one real
    frozen row is "4h" only -- matching _load_timeframes' own unconditional
    fetch of every timeframe. funding/macro/oi context is loaded ONCE
    unwindowed-by-segment and the same ctx dict is reused across train/
    validate/sealed, mirroring the CLI's own _load_context call: every
    filter that reads context (_apply_funding_extreme/_apply_oi_momentum/
    _apply_macro_regime in explore.py) aligns by timestamp, not by index
    slice, so passing the full-window series into every segment is correct,
    not a leak -- confirmed by reading explore.py. The one real frozen row
    has filters=() anyway, so context is fetched but never consulted.

    data_fingerprint's per-tf {bars, sha} reuses the already-imported
    _breadth_sha, byte-identical to the CLI's own private _sha (both
    hashlib.sha256(",".join(f"{c.timestamp_ms}:{c.close}" ...)) -- confirmed
    by reading both formulas)."""
    data = {tf: fetch_candles(tf, cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
            for tf in LS_TOURNAMENT_TIMEFRAMES}
    funding = fetch_funding(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    macro = fetch_macro()
    oi_points = fetch_oi(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    ctx = {"funding": funding, "macro": macro, "oi_points": oi_points}

    train_by_tf, validate_by_tf, sealed_by_tf = {}, {}, {}
    for tf in LS_TOURNAMENT_TIMEFRAMES:
        n = len(data[tf])
        a, b = int(0.6 * n), int(0.8 * n)
        train_by_tf[tf] = data[tf][:a]
        validate_by_tf[tf] = data[tf][a:b]
        sealed_by_tf[tf] = data[tf][b:]

    context_by_tf = {tf: ctx for tf in LS_TOURNAMENT_TIMEFRAMES}
    rows = ls_tournament_validate_all(
        cfg["frozen_rows"], train_by_tf, validate_by_tf, sealed_by_tf,
        context_validate_by_tf=context_by_tf,
        context_sealed_by_tf=context_by_tf,
        context_train_by_tf=context_by_tf,
    )
    verdict = ("paper_candidate" if any(r["verdict"] == "paper_candidate" for r in rows)
               else "negative")
    data_fingerprint = {tf: {"bars": len(data[tf]),
                             "sha": _breadth_sha(data[tf]) if data[tf] else None}
                        for tf in LS_TOURNAMENT_TIMEFRAMES}
    return {"verdict": verdict, "rows": rows, "data_fingerprint": data_fingerprint}


_SSE_CLOCK_STEP_MS = 14_400_000  # 4h, matches tools.sse.sse's own literal


def _sse_run(cfg: dict, fetch_candles, symbols, fetch_daily, readers,
            out_dir) -> dict:
    """Kernel-callable twin of tools.sse.sse.main's gate0 path --
    load_gate0_inputs' own symbol-discovery optimization is reproduced
    faithfully, not skipped: a preliminary monthly_membership pass over a
    synthetic 4h-step timestamp axis (same range(start_ms, end_ms, 14_400_000)
    load_gate0_inputs itself builds) picks the union of symbols any month's
    top-volume ranking ever selects, and only THAT union's candles are
    fetched into pool -- fetching all ~787 cached-daily symbols' full candle
    histories instead (a simpler but unfaithful "superset" shortcut) measured
    at ~5 minutes end to end against the real cache; the union is ~1-2
    orders of magnitude smaller. sse.run_gate0 itself recomputes membership a
    second time internally, from BTC's own real candle timestamps rather
    than this synthetic axis -- confirmed by reading run_gate0, this
    preliminary pass changes only which symbols get fetched, never the real
    membership computation. BTC alone gets funding/OI attached, matching
    load_gate0_inputs' own `if sym == "BTCUSDT"` branch exactly. run_gate0's
    own write_gate0_artifacts(out_dir, result) side effect is exactly what
    the harness's scratch_dir is for (same precedent noted in
    kernel.reproduce.reproduce's own docstring re: oibuild_study/liqladder).
    Every random draw inside gate0_result/fit_kmeans is seeded (seed=1 fixed
    in clusters.py, seed=1 default threaded through gate.py's bootstrap
    calls), so this lane is fully deterministic given identical pool/daily
    inputs -- no float-drift tolerance needed beyond ordinary cache growth."""
    start_ms, end_ms = cfg["start_ms"], cfg["end_ms"]
    btc_symbol = cfg.get("btc_symbol", "BTCUSDT")
    top_n = cfg.get("top_n", 50)
    min_history_days = cfg.get("min_history_days", 90)
    vol_days = cfg.get("vol_days", 30)

    daily: dict = {}
    for sym in symbols:
        rows = fetch_daily(sym, start_ms, end_ms)
        if rows:
            daily[sym] = rows

    prelim_timestamps = list(range(start_ms, end_ms, _SSE_CLOCK_STEP_MS))
    members = sse_monthly_membership(
        daily, prelim_timestamps, top_n=top_n,
        min_history_days=min_history_days, vol_days=vol_days)
    union = sorted({sym for bucket in members.members for sym in bucket}
                   | {btc_symbol})

    pool: dict = {}
    for sym in union:
        candles = fetch_candles(sym, start_ms, end_ms)
        if not candles:
            continue
        if sym == btc_symbol:
            pool[sym] = DataBundle(
                candles=candles,
                funding=readers["funding"](sym),
                feature=readers["metrics"](sym, "sum_open_interest"))
        else:
            pool[sym] = DataBundle(candles=candles)
    return sse_run_gate0(
        pool, daily, out_dir,
        top_n=cfg.get("top_n", 50),
        min_history_days=cfg.get("min_history_days", 90),
        vol_days=cfg.get("vol_days", 30),
        horizon=cfg.get("horizon", 24),
        draws=cfg.get("draws", 1000),
        btc_symbol=btc_symbol,
        axes_ma_period=cfg.get("axes_ma_period", 300),
        axes_ret_bars=cfg.get("axes_ret_bars", 6),
        axes_z_window=cfg.get("axes_z_window", 540),
        traj_lookback=cfg.get("traj_lookback", 20),
        traj_z_window=cfg.get("traj_z_window", 540),
    )


def _portfolio_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    """Bare (sym, tf, start, end) candle fetcher -- tools/portfolio/
    portfolio_search.py's own private _load fetches BOTH
    components.TIMEFRAMES ("1h"/"4h") for one fixed symbol (BTCUSDT), so
    fetch_candles takes tf as a call argument, same shape
    _ls_tournament_run_args established for its own two-timeframe fetch (sym
    is passed at call time too, unlike that lane's cfg-only interval, since
    nothing here needs a second symbol)."""

    def fetch_candles(sym, tf, start, end):
        candles = offline_fetch_perp_candles(sym, tf, start, end, cache_dir)
        series_by_key[f"{sym}:candles:{tf}"] = series_fingerprint(candles)
        return candles

    return (fetch_candles,)


def _portfolio_run(cfg: dict, fetch_candles, out_dir) -> dict:
    """Kernel-callable twin of tools.portfolio.portfolio_search.main's
    --explore path ONLY -- this lane's one real frozen run
    (experiments/portfolio/run1/RESULT.md) states plainly "stages run:
    --register -> --explore. --select/--validate NOT run (zero DSR survivors
    => nothing to freeze, nothing to validate)", so select/freeze_candidates/
    validate_all/render_result are never reached and stay unimported here.
    _load/_build_positions_and_bar_r/_split_all/_split_60_20_20 are
    portfolio_search.py private (leading-underscore) helpers -- reimplemented
    inline here from public center_components/component_positions/
    asset_bar_r/position_returns/step0_screen/run_explore instead, same
    reimplement-not-import precedent as _ls_exit_ablation_split. The
    --explore branch's own comp_metrics_list (summarize_portfolio over each
    component's returns) is computed by the CLI but never read before
    explore_leaderboard.json is written -- dead code with zero effect on the
    returned rows, skipped here rather than reproduced faithfully-but-uselessly."""
    symbol, start_ms, end_ms = cfg["symbol"], cfg["start_ms"], cfg["end_ms"]
    by_tf = {tf: fetch_candles(symbol, tf, start_ms, end_ms)
             for tf in PORTFOLIO_TIMEFRAMES}
    train_oos_by_tf = {tf: candles[:int(0.6 * len(candles))]
                       for tf, candles in by_tf.items()}

    comps = center_components()
    grid_candles = train_oos_by_tf["1h"]
    bar_r = asset_bar_r(grid_candles)
    positions_by_comp = [component_positions(by_tf, cell, grid_candles)[:len(grid_candles)]
                         for cell in comps]
    comp_returns_list = [position_returns(positions_by_comp[i], bar_r, grid_candles)
                         for i in range(len(comps))]
    screen = step0_screen(comps, comp_returns_list)
    rows = run_explore(positions_by_comp, bar_r, grid_candles)
    for r in rows:
        r["screen"] = screen
    # screen["basket"] is list[SystemCell] (a dataclass, not JSON-native) --
    # portfolio_search.py's own --explore branch already writes
    # explore_leaderboard.json with json.dumps(rows, default=str), so the
    # recorded file's basket entries are already SystemCell's str() repr,
    # not live objects. Round-tripping through the identical default=str
    # here (rather than only at _write_run_record time) keeps this
    # function's return value byte-comparable to the recorded JSON, the
    # same contract every other lane's run_fn gets for free by returning
    # plain dicts/floats/strings only.
    return {"explore_leaderboard": json.loads(json.dumps(rows, default=str))}


def _liq_twap_run(cfg: dict, fetch_candles, fetch_metric, out_dir) -> dict:
    """Kernel-callable twin of tools.liq_twap.liq_twap_screen.cmd_run.
    moonface.data.bundle.load_bundle's own candle fetch uses BTC_ASSET's
    "BTC/USDT:USDT" symbol string verbatim -- data.ohlcv.OhlcvCache.path only
    strips "/" (not ":"), so this resolves to .backtest_cache/
    BTC_USDT:USDT_1h.csv, a DIFFERENT cache file than every other lane's
    "BTCUSDT_1h.csv" (both exist in the cache, confirmed by reading
    OhlcvCache.path and listing .backtest_cache/ directly -- not the same
    series). _candles_metric_run_args's fetch_candles is symbol-agnostic
    (offline_fetch_perp_candles just wraps OhlcvCache.load), so reusing it
    verbatim here with candle_symbol == BTC_ASSET["symbol"] resolves to the
    identical cache file load_bundle's cache-hit path would read -- same
    window-filter semantics, confirmed by reading both. The OI metric fetch
    instead needs load_bundle's own archive_symbol transform
    (symbol.split(":")[0].replace("/", "") == "BTCUSDT"), the same
    metrics_BTCUSDT.csv file every other BTC-OI lane already reads --
    fetch_metric is called with that transformed symbol, not candle_symbol.
    load_bundle's own _check_coverage guard (>=80% non-None) is not
    reimplemented: it never fires on the real frozen window (measured
    coverage 51773/51773 == 100%, verified 2026-09-01 against real cache),
    so it is a validation-only guard with zero effect on the returned
    numbers here, same "skip a dead guard" precedent as sse's
    s1_xcheck_ok. run_screen/DataBundle are both public research-module
    functions, imported directly rather than reimplementing screen.py's
    event/effect-Z machinery inline."""
    start_ms, end_ms = cfg["start_ms"], cfg["end_ms"]
    candle_symbol = LIQ_TWAP_BTC_ASSET["symbol"]
    metric_symbol = candle_symbol.split(":")[0].replace("/", "")
    candles = fetch_candles(candle_symbol, start_ms, end_ms)
    points = fetch_metric(metric_symbol, start_ms, end_ms)
    feature = align_metric(candles, points)
    return liq_twap_run_screen(DataBundle(candles=candles, feature=feature))


def _btc_classic_spec_doc(spec) -> dict:
    """Mirrors tools.btc_classic.btc_classic._spec_doc exactly -- not imported,
    same leading-underscore-CLI-private-helper precedent as _breadth_sha."""
    return {
        "key": spec.key,
        "kind": spec.kind,
        "builder": spec.builder,
        "params": dict(spec.params),
        "exit_name": spec.exit_name,
        "exit_params": dict(spec.exit_params),
    }


def _btc_classic_run(cfg: dict, fetch_candles, fetch_funding, out_dir) -> dict:
    """Kernel-callable twin of tools.btc_classic.btc_classic._validate: reuses
    already-pure moonface.research.btc_classic.evaluate.evaluate_spec/grid.
    all_specs and power_harness.judge_signal directly -- only the candle/
    funding fetch and the 60/20/20 parallel split are injected. Funding is
    aligned to per-bar floats via align_funding (same as the CLI's own
    _load) -- NOT the raw funding-point shape _donchian_filter_run consumes,
    despite reusing _donchian_filter_run_args verbatim as the loader: that
    builder's fetch_funding already returns raw points, alignment happens
    here, in the run_fn, not the loader."""
    candles = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    points = fetch_funding(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    funding = align_funding(candles, points)
    n = len(candles)
    a, b = int(0.6 * n), int(0.8 * n)
    va_c, va_f = candles[a:b], funding[a:b]
    se_c, se_f = candles[b:], funding[b:]
    specs = btc_classic_all_specs()
    rows = []
    for spec in specs:
        validate = btc_classic_evaluate_spec(va_c, va_f, spec)
        sealed = btc_classic_evaluate_spec(se_c, se_f, spec)
        judge = judge_signal(validate["metrics"], sealed["metrics"],
                             validate["records"] + sealed["records"], len(specs))
        rows.append({
            "key": spec.key,
            "spec": _btc_classic_spec_doc(spec),
            "validate": validate,
            "sealed": sealed,
            "pooled": judge["pooled"],
            "boot_lo": judge["boot_lo"],
            "p_le_zero": judge["p_le_zero"],
            "same_sign": judge["same_sign"],
            "practical": judge["practical"],
            "cost": judge["cost"],
            "significant": judge["significant"],
            "verdict": judge["verdict"],
        })
    if any(r["verdict"] == "paper_candidate" for r in rows):
        verdict = "paper_candidate"
    elif any(r["verdict"] == "forward_candidate" for r in rows):
        verdict = "forward_candidate"
    else:
        verdict = "negative"
    return {"verdict": verdict, "rows": rows, "btc_sha": _breadth_sha(candles)}


def _consolidated_ls_run_args(cfg: dict, cache_dir: str,
                              series_by_key: dict) -> tuple:
    """Composes two already-solved loader shapes rather than inventing new
    ones -- confirmed by reading moonface.research.consolidated.runner.
    _build_context directly: it needs breadth's own daily/is_member universe
    (_daily_funding_run_args' (symbols, fetch_daily, fetch_funding) 3-tuple,
    same primitives sse/breadth reuse) PLUS BTC candles at THREE intervals
    (1h/2h/4h, not one) and a FRED macro fetch. fetch_candles takes tf as a
    call arg, same _ls_tournament_run_args precedent (needed for exactly the
    same reason: one lane, more than one interval). fetch_macro reuses
    REGIME_OVERLAY_FRED_SERIES -- runner.py imports
    regime_overlay.data.load_macro directly (not its own copy), so this is
    the same FRED_SERIES set, not a new one."""
    symbols, fetch_daily, fetch_funding = _daily_funding_run_args(
        cfg, cache_dir, series_by_key)

    def fetch_candles(tf, sym, start, end):
        candles = offline_fetch_perp_candles(sym, tf, start, end, cache_dir)
        series_by_key[f"{sym}:candles:{tf}"] = series_fingerprint(candles)
        return candles

    def fetch_macro():
        macro = {sid: offline_fetch_fred_series(sid, cache_dir)
                 for sid in REGIME_OVERLAY_FRED_SERIES}
        for sid, points in macro.items():
            series_by_key[f"fred:{sid}"] = raw_series_fingerprint(
                [(p.ts_ms, p.value) for p in points])
        return macro

    return (fetch_candles, symbols, fetch_daily, fetch_funding, fetch_macro)


def _consolidated_ls_run(cfg: dict, fetch_candles, symbols, fetch_daily,
                         fetch_funding, fetch_macro, out_dir) -> dict:
    """Kernel-callable twin of moonface.research.consolidated.runner.run.
    Its own _build_context (leading-underscore, not injectable -- same
    reimplement-not-import precedent as every other CLI-private helper in
    this module) is reimplemented here field-for-field using the injected
    fetchers instead of tools.breadth.breadth._load/fetch_perp_candles/
    fetch_funding_rates/regime_overlay.data.load_macro's own live-capable
    calls. RunContext and ADAPTERS/EXCLUDED are both public (no leading
    underscore), so run()'s own adapter-loop + sort + result-dict body is
    reused verbatim below rather than duplicated blind -- only the I/O
    (_build_context) needed replacing."""
    start_ms, end_ms = cfg["start_ms"], cfg["end_ms"]
    btc_4h = fetch_candles("4h", SYMBOL, start_ms, end_ms)
    btc_1h = fetch_candles("1h", SYMBOL, start_ms, end_ms)
    btc_2h = fetch_candles("2h", SYMBOL, start_ms, end_ms)
    funding = fetch_funding(SYMBOL, start_ms, end_ms)
    macro = fetch_macro()
    daily: dict = {}
    for sym in symbols:
        rows = fetch_daily(sym, start_ms, end_ms)
        if rows:
            daily[sym] = rows
    is_member = membership_fn(
        daily, cfg["top_n"], cfg["min_history_days"], cfg["vol_days"],
        cfg["rebalance_days"])
    train = btc_4h[: int(0.6 * len(btc_4h))]
    if not universe_covers_train(daily, is_member, train):
        raise RuntimeError(
            "consolidated_ls: universe daily history does not cover the "
            "train window -- the frozen run's own feasibility guard would "
            "have failed too, so this isn't a reproduction mismatch to "
            "record")

    ctx = RunContext(btc_4h=btc_4h, btc_1h=btc_1h, btc_2h=btc_2h,
                     funding=funding, daily=daily, is_member=is_member,
                     macro=macro, start_ms=start_ms, end_ms=end_ms,
                     cache_dir=cfg.get("cache_dir", ""))

    rows: list[dict] = []
    for lane, fn in ADAPTERS.items():
        try:
            results = fn(ctx)
        except Exception as exc:  # noqa: BLE001
            rows.append({
                "key": None, "lane": lane, "config": None,
                "config_source": None, "exit_name": None,
                "current_signal": None, "status": "error", "error": str(exc),
                "expectancy_r": None, "pf": None, "max_dd_r": None, "n": None,
                "total_r": None, "mar": None,
            })
            continue
        for res in results:
            row = {
                "key": res.key, "lane": res.lane, "config": res.config,
                "config_source": res.config_source, "exit_name": res.exit_name,
                "current_signal": res.current_signal, "status": "ok",
            }
            row.update(metric_block(res))
            rows.append(row)

    rows.sort(key=lambda r: (
        r.get("expectancy_r") is None,
        -(r.get("expectancy_r") or 0.0),
        -(r.get("n") or 0),
        -(r.get("total_r") or 0.0),
    ))

    return {
        "rows": rows,
        "errors": [r for r in rows if r["status"] == "error"],
        "excluded": list(EXCLUDED),
        "window": {"start_ms": start_ms, "end_ms": end_ms},
        "btc_bars": len(btc_4h),
        "btc_sha": _breadth_sha(btc_4h) if btc_4h else "",
    }


BREADTH_CONFIRM_COMPARE_FIELDS = ("verdict", "rows", "discovery", "btc_sha")
BREADTH_MOMENTUM_CONFIRM_COMPARE_FIELDS = ("verdict", "rows", "discovery", "btc_sha")

LS_EXIT_ABLATION_COMPARE_FIELDS = ("bars", "baseline_sealed_total_r", "rows")

OIBUILD_STUDY_COMPARE_FIELDS = ("verdict", "stouffer_z", "pooled_mean", "p_sign",
                                "k_positive", "m_assets")
LIQLADDER_COMPARE_FIELDS = ("verdict", "stouffer_z", "pooled_mean", "k_positive",
                            "m_assets")
LIQREV_COMPARE_FIELDS = ("verdict", "stouffer_z", "pooled_mean", "k_positive",
                         "m_assets")
CALSEASON_COMPARE_FIELDS = ("assets", "skipped", "cells", "halves")
MACRO_EVENT_COMPARE_FIELDS = ("cells", "candles")
BAB_COMPARE_FIELDS = ("universe_symbols", "funding_symbols", "constructions")
XSECTION_COMPARE_FIELDS = ("universe_symbols", "funding_symbols", "constructions")
RESREV_COMPARE_FIELDS = ("universe_symbols", "funding_symbols", "constructions")
LIQPREM_COMPARE_FIELDS = ("universe_symbols", "viability_members",
                          "funding_symbols", "constructions")
DRIFT_SCREEN_STACK_PATH_COMPARE_FIELDS = ("primary", "curve_descriptive")
DRIFT_SCREEN_COMPARE_FIELDS = ("leaderboard",)
DRIFT_SCREEN_MULTIFAMILY_COMPARE_FIELDS = ("leaderboard",)
BB_VARIANT_COMPARE_FIELDS = ("n_bars", "variants", "slices")
BB_HARVEST_COMPARE_FIELDS = ("results_4h",)
EXIT_PROBE_COMPARE_FIELDS = ("leaderboard",)
ADVVAL_COMPARE_FIELDS = ("cells", "retrodiction")
EVENTTIME_COMPARE_FIELDS = ("bar_size", "n_dollar_bars", "n_clock_bars",
                           "clock_rows", "dollar_rows", "ladder", "verdict")
BREADTH_COMPARE_FIELDS = ("verdict", "rows", "btc_sha")
BREADTH_NEUTRAL_COMPARE_FIELDS = ("verdict", "rows", "anchor_ok", "anchor_raw_got")
BREADTH_XASSET_CONFIRM_COMPARE_FIELDS = ("verdict", "rows", "anchor_ok", "anchors",
                                         "btc_anchor_sha")
BREADTH_INTERNAL_COMPARE_FIELDS = ("verdict", "rows", "btc_sha")
BREADTH_INTERNAL_HF_COMPARE_FIELDS = ("verdict", "rows", "btc_sha")
DONCHIAN_FILTER_COMPARE_FIELDS = ("threshold", "sealed_base", "sealed_gated", "verdict")
# RESULT.json's actual field set in the frozen state (frozen_cell is None, so
# only "reason"/"verdict" are ever written -- "reason" is a narrative field,
# excluded per the standing never-compare-narrative-fields rule).
DONCHIAN_VOLREGIME_COMPARE_FIELDS = ("verdict",)
BTC_CLASSIC_COMPARE_FIELDS = ("verdict", "rows", "btc_sha")
# Same trivial-frozen-state shape as DONCHIAN_VOLREGIME_COMPARE_FIELDS --
# frozen_candidate.json's "frozen" is null (no train+validate survivor), so
# RESULT.json's real field set is just "reason"/"verdict" ("reason" excluded,
# narrative field).
REGIME_OVERLAY_COMPARE_FIELDS = ("verdict",)
# Same trivial-frozen-state shape as DONCHIAN_VOLREGIME_COMPARE_FIELDS/
# REGIME_OVERLAY_COMPARE_FIELDS -- frozen_candidate.json's "frozen" is null
# (no validate survivor), so RESULT.json's real field set is just
# "reason"/"verdict" ("reason" excluded, narrative field).
REGIME_SELECTOR_COMPARE_FIELDS = ("verdict",)
# Not a trivial-frozen-state lane like the rest of this group -- one real
# frozen candidate (frozen_candidates.json has 1 row, not []), so rows/
# data_fingerprint both carry substantive per-run structure worth comparing.
# data_fingerprint plays the same cache-growth-canary role as btc_sha does
# for the breadth family.
LS_TOURNAMENT_COMPARE_FIELDS = ("verdict", "rows", "data_fingerprint")
# gate0_verdict.json's full top-level shape: verdict/chosen_cell plus the
# points/trajectories sub-dicts (each carrying track_n_spread/track_l_spread/
# label_shuffle/circular_shift/era_stability -- substantive numeric/structural
# fields, not narrative text) -- compare the whole record, same precedent as
# LS_TOURNAMENT_COMPARE_FIELDS's "rows".
SSE_COMPARE_FIELDS = ("verdict", "chosen_cell", "points", "trajectories")

# explore_leaderboard.json is a bare list (one row per FROZEN_PORTFOLIOS
# entry, each carrying positions/returns/metrics/dsr plus the shared
# step0_screen "screen" dict) -- _load_recorded wraps it as
# {"explore_leaderboard": [...]} since verdict_filename's stem is
# "explore_leaderboard", same list-shaped-verdict-file precedent as
# DRIFT_SCREEN_COMPARE_FIELDS's "leaderboard".
PORTFOLIO_COMPARE_FIELDS = ("explore_leaderboard",)

# Full run_screen() record -- no trivial-frozen-state shortcut exists for
# this lane (it always computes the 5-condition screen for real), so the
# whole return dict is substantive: cells/treat_mean/ctrl_mean/null_max_z
# are the numeric substrate, "verdict" is included alongside them (not
# alone) as a structural cross-check on top of them, same "compare the full
# top-level record" precedent as SSE_COMPARE_FIELDS.
LIQ_TWAP_COMPARE_FIELDS = ("cells", "treat_mean", "ctrl_mean", "null_max_z", "verdict")

# render_json's own top-level shape minus its two static labels
# ("evidence_class"/"sealed_holdouts", constant literals never computed by
# run(), same "never a status/reason narrative field" exclusion as every
# other lane's asof/generated_utc omission) and "asof" itself (date.today(),
# time-based) -- rows/errors/excluded/window/btc_bars/btc_sha is exactly
# run()'s own return dict, confirmed by reading report.render_json directly.
CONSOLIDATED_LS_COMPARE_FIELDS = ("window", "btc_bars", "btc_sha", "rows",
                                  "errors", "excluded")


def _matrix_run(cfg: dict, fetch_candles, fetch_funding, out_dir) -> dict:
    """Kernel-callable twin of tools.matrix.matrix_evaluate.main: reuses
    already-pure moonface.research.matrix.evaluate.build_matrix_report
    directly -- only the BTC/ETH/SOL candle+funding fetch is injected.
    Reuses _donchian_filter_run_args verbatim as the loader (same bare
    (fetch_candles, fetch_funding) shape, sym passed at call time) but,
    same precedent as _btc_classic_run, funding is aligned to per-bar
    floats via align_funding here in the run_fn, not the loader -- called
    once per symbol since this lane needs three FIXED symbols (BTC for
    fit+validation+sealed, ETH/SOL transfer-only), not a universe loop.
    "matrix" scopes to matrix_evaluate.py alone, not the other 3 files in
    tools/matrix/ (matrix_baselines.py/matrix_regime.py/matrix_router.py
    are separate prerequisite/diagnostic CLIs feeding this one's
    --baseline-val-dd/--baseline-sealed-dd args, each with its own
    unrelated output shape -- G6.3 slice 18/19's flagged "ambiguous lane
    boundary" resolved by picking the one CLI that actually produces a
    verdict via a frozen registration, same "lane = what was actually
    run and gated" precedent as portfolio's register+explore-only scope).
    Confirmed current research/matrix/evaluate.py matches the SUPERSEDING
    Slice-1b registration (MIN_VAL_TRADES=40/govern_scope=per_segment_reset/
    retain_zero_size=True in frozen_constants), not the original flawed
    Slice-1 run -- experiments/matrix/registration.json and the verdict
    symlink both point at matrix_slice1b_2026-07.json, not matrix_slice1_
    2026-07.json (MATRIX_SLICE1B_REGISTRATION.md states it "Supersedes
    MATRIX_SLICE1_REGISTRATION.md")."""
    cfg_donchian = TrendParams(entry_n=20, trail_n=10, atr_period=14,
                               k_stop=2.0, long_only=True, fee_rate=0.0,
                               slippage=0.0, funding_enabled=False)

    def _load(sym):
        candles = fetch_candles(sym, cfg["start_ms"], cfg["end_ms"])
        points = fetch_funding(sym, cfg["start_ms"], cfg["end_ms"])
        return candles, align_funding(candles, points)

    btc, f_btc = _load("BTCUSDT")
    eth, f_eth = _load("ETHUSDT")
    sol, f_sol = _load("SOLUSDT")
    return build_matrix_report(btc, eth, sol, f_btc, f_eth, f_sol,
                               cfg_donchian, cfg["baseline_val_dd"],
                               cfg["baseline_sealed_dd"])


# build_matrix_report's own top-level shape minus "label" (a constant
# descriptive literal, same "never a status/reason narrative field"
# exclusion every other lane applies to its own static fields) --
# frozen_constants is KEPT (unlike consolidated_ls's excluded
# evidence_class/sealed_holdouts) because, unlike those two, nothing here
# is copied verbatim from cfg -- every frozen_constants value is a
# module-level literal in research/matrix/evaluate.py itself, so comparing
# it catches an accidental future edit to those constants, not just cache
# growth. "data" (btc_candles count + fingerprint) plays the same
# cache-growth-canary role btc_sha plays for the breadth family.
MATRIX_COMPARE_FIELDS = ("data", "frozen_constants", "fitted_governor",
                         "segments", "gate1", "gate2", "gate3", "verdict")


def _mtf_transfer_run(cfg: dict, fetch_candles, out_dir) -> dict:
    """Kernel-callable twin of tools.mtf.mtf_transfer.main: reuses
    already-pure moonface.research.mtf.attribute.trade_stream/period_stats
    and grid.headline_cell directly -- only the candle fetch is injected.
    Mirrors the CLI's own per-symbol insufficient-data skip (len(candles) <
    5000, a bare `continue` with no row emitted in the CLI's own markdown
    table) as a `rows` entry carrying `insufficient: True` instead, so the
    row count stays honest across a reproduction rather than silently
    shrinking. First lane in the `mtf` family: `tools/mtf/` has 10 separate
    CLI files, none of which write any JSON at all (only markdown reports),
    and several genuinely distinct frozen forward registrations (transfer,
    basket, long_only, broaden) rather than one lane's four feeder files
    like `matrix` -- so, unlike `matrix`, this is not "the one real lane in
    the directory": it is the first of a family, converted one member at a
    time the same way the `breadth*` family was."""
    cell = mtf_headline_cell()
    rows = []
    for sym in cfg["symbols"]:
        candles = fetch_candles(sym, cfg["start_ms"], cfg["end_ms"])
        if len(candles) < 5000:
            rows.append({"symbol": sym, "insufficient": True, "n": len(candles)})
            continue
        trades = mtf_trade_stream(candles, cell)
        full = mtf_period_stats(trades)
        recent = mtf_period_stats(trades, start_ms=cfg["recent_ms"])
        rows.append({"symbol": sym, "full": full, "recent": recent})
    non_control = [r for r in rows
                  if r["symbol"] != "BTCUSDT" and "full" in r]
    transferred = bool(non_control) and all(
        r["full"]["positive"] and r["recent"]["positive"] for r in non_control)
    verdict = ("TRANSFERS (sign holds + recent-positive on every non-BTC asset)"
               if transferred else
               "DOES NOT cleanly transfer (see per-asset rows)")
    return {"verdict": verdict, "rows": rows}


# render_diagnostic/render_json's own top-level shape has no JSON counterpart
# here (the CLI only ever wrote TRANSFER.md) -- both fields are the CLI's
# full per-symbol/per-period record, same "no trivial shortcut exists"
# shape as liq_twap's LIQ_TWAP_COMPARE_FIELDS.
MTF_TRANSFER_COMPARE_FIELDS = ("verdict", "rows")

_MTF_BASKET_CELLS = {"headline": mtf_headline_cell,
                     "broaden_best": mtf_broaden_best_cell}


def _mtf_basket_run(cfg: dict, fetch_candles, out_dir) -> dict:
    """Kernel-callable twin of tools.mtf.mtf_basket.main: reuses already-pure
    mtf.attribute.trade_stream/period_stats (same as mtf_transfer) plus
    mtf.basket.merge_streams/diversification/yearly_robustness and
    mtf.grid.headline_cell/broaden_best_cell directly -- only the candle
    fetch is injected. Second member of the `mtf` family (after
    mtf_transfer): this lane's own frozen forward registration
    (BASKET_FORWARD_REGISTRATION.md) only ever ran the `headline` cell, so
    cfg["cell"] is expected to be "headline", but the CLI's own
    `--cell broaden_best` option is wired too since it costs nothing extra
    and keeps this twin faithful to the whole CLI, not just the frozen path.
    Weight is 1/len(cfg["symbols"]) -- the CLI's own denominator is the
    REQUESTED symbol count, not the count that actually clears the
    insufficient-data floor, mirrored here exactly (an asset skipped for
    thin cache does not get up-weighted onto the survivors)."""
    cell = _MTF_BASKET_CELLS[cfg.get("cell", "headline")]()
    weight = 1.0 / len(cfg["symbols"])
    streams: dict = {}
    individual: dict = {}
    for sym in cfg["symbols"]:
        candles = fetch_candles(sym, cfg["start_ms"], cfg["end_ms"])
        if len(candles) < 5000:
            continue
        streams[sym] = mtf_trade_stream(candles, cell)
        individual[sym] = {
            "full": mtf_period_stats(streams[sym]),
            "recent": mtf_period_stats(streams[sym], start_ms=cfg["recent_ms"])}

    merged = mtf_merge_streams(streams, weight)
    full = mtf_period_stats(merged)
    recent = mtf_period_stats(merged, start_ms=cfg["recent_ms"])
    yearly, robust = mtf_yearly_robustness(merged)
    div = mtf_diversification(streams, weight)

    b = ECON_BAR
    clears = (full["pf"] >= b.profit_factor
             and full["expectancy_r"] >= b.expectancy_r
             and full["mar"] >= b.mar_floor
             and abs(full["max_dd_r"]) <= b.max_dd_r
             and robust >= b.robust_frac)
    verdict = ("CLEARS ECON_BAR (paper candidate)" if clears
               else "DOES NOT CLEAR ECON_BAR (thin edge, large drawdown)")

    return {"assets": sorted(streams), "individual": individual,
            "basket": {"full": full, "recent": recent},
            "diversification": div,
            "yearly": {"rows": yearly, "robust_frac": robust},
            "verdict": verdict}


# The CLI (mtf_basket.py) only ever wrote BASKET.md -- no JSON counterpart,
# same freeze-provenance shape as mtf_transfer. All 5 fields are computed
# results (no cfg echo like "cell"/"asof"/"data_sha"), same "no
# status/reason-only field, no trivial shortcut" rule every lane applies.
MTF_BASKET_COMPARE_FIELDS = ("assets", "individual", "basket",
                             "diversification", "yearly", "verdict")

# MIN_BARS is mtf_broaden.py's own module constant (2000), never exposed as a
# cfg-overridable kwarg -- same "frozen module constant, not a run kwarg"
# class as matrix's TRAIN_END_TS_MS / sse's RVOL_WINDOW gotchas, mirrored
# here as a literal rather than importing the CLI __main__ module.
_MTF_BROADEN_MIN_BARS = 2000


def _mtf_broaden_run(cfg: dict, fetch_candles, out_dir) -> dict:
    """Kernel-callable twin of tools.mtf.mtf_broaden.main: reuses already-pure
    moonface.research.mtf.evaluate.search_diagnostic directly over
    mtf.grid.broadened_cells() -- only the candle fetch is injected. Third
    member of the `mtf` family: resolves the question slice 22 flagged
    ("may be a pure feeder with no frozen verdict of its own"). It is NOT a
    feeder like matrix_baselines/matrix_regime (those compute no gate, no
    verdict at all) -- this CLI's own search_diagnostic gates all 72 cells
    through stage1/stage2/stage3 and assigns each a real "edge"/"negative"
    verdict, the same gated shape matrix_evaluate's gate1/gate2/gate3 chain
    has. Its own frozen forward registration (BROADEN_FORWARD_REGISTRATION.md)
    happens to RESOLVE via a different code path (mtf_transfer-style
    trade_stream/period_stats over the single winning broaden_best_cell,
    not this CLI's 72-cell search) -- but that governs how the *registration*
    resolves, not whether this CLI is itself a real, comparable, gated lane.
    It earns its own LANES entry. Single fixed BTCUSDT symbol (no --symbol
    flag on this CLI, unlike mtf_long_only.py), so cfg carries no "symbols"
    list, only the shared start_ms/end_ms/interval="15m" triple every mtf
    lane's registration.json already carries."""
    candles = fetch_candles("BTCUSDT", cfg["start_ms"], cfg["end_ms"])
    if len(candles) < _MTF_BROADEN_MIN_BARS:
        raise ValueError(
            f"only {len(candles)} bars (<{_MTF_BROADEN_MIN_BARS}); aborting")
    cells = mtf_broadened_cells()
    cut = int(0.8 * len(candles))
    rows = mtf_search_diagnostic(cells, candles[:cut], candles)
    strict = [r for r in rows if r["verdict"] == "edge"]
    econ = [r for r in rows if r["econ_pass"]]
    if strict:
        verdict = "EDGE (clears DSR + ECON_BAR -- paper candidate)"
    elif econ:
        verdict = (f"ECON-POSITIVE ({len(econ)} cell(s) clear ECON_BAR but "
                   "not DSR -- practical paper candidate, academically "
                   "underpowered)")
    else:
        verdict = "NEGATIVE (no cell clears the deployable ECON_BAR)"
    return {"verdict": verdict, "rows": rows}


# render_diagnostic's own top-level shape minus "asof"/"data_sha"/"base_tf"
# (time-based / constant-literal fields, same exclusion rule every lane
# applies) and "n_cells" (a constant of broadened_cells(), not data-derived).
# No trivial-shortcut shape exists (same as mtf_transfer/mtf_basket -- the
# CLI never wrote a JSON verdict).
MTF_BROADEN_COMPARE_FIELDS = ("verdict", "rows")


def _yearly_btc_return(candles) -> list[dict]:
    """Mirrors tools.mtf.mtf_long_only._yearly_btc_return exactly: passive
    buy-and-hold % per calendar year (first vs last close in the fetched
    window). A short CLI-local helper (not part of moonface.research.mtf.*),
    so reimplemented here rather than importing the CLI __main__ module --
    same "mirror, don't import" precedent as mtf_broaden's MIN_BARS. Returned
    as a sorted list of {"year", "btc_return_pct"} rows rather than the CLI's
    own formatted beta_note sentence -- the CLI's prose is fully derivable
    from this plus yearly_robustness's own per-year rows, so keeping it as
    raw data (not a narrative field) lets the beta test stay comparable."""
    first: dict[int, float] = {}
    last: dict[int, float] = {}
    for c in candles:
        y = mtf_year(c.timestamp_ms)
        first.setdefault(y, c.close)
        last[y] = c.close
    return [{"year": y, "btc_return_pct": round(last[y] / first[y] - 1.0, 6)}
            for y in sorted(first)]


def _mtf_long_only_run(cfg: dict, fetch_candles, out_dir) -> dict:
    """Kernel-callable twin of tools.mtf.mtf_long_only.main: reuses
    already-pure mtf.attribute.trade_stream/period_stats (same as
    mtf_transfer/mtf_basket) plus mtf.grid.broaden_best_cell and
    mtf.basket.yearly_robustness directly -- only the candle fetch is
    injected. Fourth and last member of the mtf family (mtf_transfer,
    mtf_basket, mtf_broaden already converted) -- closes the family. Single
    fixed symbol via cfg["symbol"] (this CLI's own --symbol flag defaults to
    BTCUSDT, unlike mtf_transfer/mtf_basket's "symbols" list), so cfg has no
    "symbols" list. lo_recent is descriptive only -- like mtf_transfer's own
    "recent" field, it never gates the verdict (only lo_full + robust do,
    mirroring the CLI's own `clears` check exactly)."""
    cell = mtf_broaden_best_cell()
    candles = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    stream = mtf_trade_stream(candles, cell)
    longs = [t for t in stream if t[1] == "LONG"]
    ls_full = mtf_period_stats(stream)
    lo_full = mtf_period_stats(longs)
    lo_recent = mtf_period_stats(longs, start_ms=cfg["recent_ms"])
    yr_rows, robust = mtf_yearly_robustness(longs)
    buy_and_hold = _yearly_btc_return(candles)
    exposure = min(1.0, len(longs) * cell.h / len(candles)) if candles else 0.0

    b = ECON_BAR
    clears = (lo_full["pf"] >= b.profit_factor
             and lo_full["expectancy_r"] >= b.expectancy_r
             and lo_full["mar"] >= b.mar_floor
             and abs(lo_full["max_dd_r"]) <= b.max_dd_r
             and robust >= b.robust_frac)
    verdict = ("CLEARS ECON_BAR (paper candidate)" if clears
               else "DOES NOT CLEAR ECON_BAR (DD cap over 30R — sizing failure)")

    return {"verdict": verdict, "exposure": round(exposure, 4),
            "ls_full": ls_full, "lo_full": lo_full, "lo_recent": lo_recent,
            "yearly": {"rows": yr_rows, "robust_frac": robust},
            "buy_and_hold_yearly": buy_and_hold}


# The CLI (mtf_long_only.py) only ever wrote LONG_ONLY.md -- no JSON
# counterpart, same freeze-provenance shape as the rest of the mtf family.
# "exposure" is a real data-derived scalar (len(longs) * cell.h / len(candles)),
# not a constant -- kept, unlike broaden's excluded "n_cells". No
# status/reason-only narrative field (the CLI's own beta_note sentence is
# replaced by "buy_and_hold_yearly", its raw structured source).
MTF_LONG_ONLY_COMPARE_FIELDS = ("verdict", "exposure", "ls_full", "lo_full",
                                "lo_recent", "yearly", "buy_and_hold_yearly")


def _donchian_revalidate_run(cfg: dict, fetch_candles, fetch_funding,
                             out_dir) -> dict:
    """Kernel-callable twin of tools.lanes.donchian_revalidate.main: reuses
    moonface.research.donchian_reval's pure analysis functions directly
    (already pure -- candles/funding in, dict out) -- only the candle/funding
    fetch is injected. DEPLOYED reconstructs the CLI's own base_params
    (replace(_BASE, entry_n=40, trail_n=20)) via the already-imported
    SWING_DONCHIAN_BASE, the same reconstruction _regime_overlay_run already
    established -- byte-identical params, confirmed by reading both call
    sites. The CLI's own _YEAR_BARS["4h"]=2190 (its only supported
    --interval choice) is mirrored as a literal."""
    candles = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    funding = fetch_funding(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    bp = replace(SWING_DONCHIAN_BASE, entry_n=40, trail_n=20)
    gross = gross_h12_probe(candles, n=40)
    ablation = exit_ablation(candles, funding, bp)
    plateau = local_param_plateau(candles, funding, bp)
    cost = cost_stress(candles, funding, bp)
    deployed_trades = simulate_donchian(candles, bp, funding)
    dist = trade_distribution(deployed_trades)
    regime = regime_breakdown(candles, deployed_trades)
    wf = nonoverlap_walk_forward(candles, funding, 2190)
    verdict = revalidation_verdict(wf, ablation, plateau, cost, dist, regime)
    return {"gross": gross, "ablation": ablation, "plateau": plateau,
            "cost": cost, "dist": dist, "regime": regime, "wf": wf,
            "verdict": verdict.tier}


# The CLI (tools/lanes/donchian_revalidate.py) only ever wrote a markdown
# report (render_result), no JSON counterpart -- same freeze-provenance
# shape as liq_twap/the mtf family. verdict.reasons is a narrative
# explanation of verdict.tier, itself fully derived from the already-
# compared wf/ablation/plateau/cost/dist/regime fields -- excluded per the
# "no narrative reason field" rule; only verdict.tier is kept, a plain
# string matching every other lane's verdict shape.
DONCHIAN_REVALIDATE_COMPARE_FIELDS = ("gross", "ablation", "plateau", "cost",
                                      "dist", "regime", "wf", "verdict")


def _vrp_measure_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    """vrp_measure.py's own main() never reads through a cache_dir/symbol
    fetcher shape -- it reads two pinned CSVs by direct path
    (cfg["dvol_path"]/cfg["spot_path"], real registration.json values:
    cache/exogenous/dvol_BTC_43200_full.csv, .backtest_cache/BTC_USDT_1h.csv),
    the same "pinned inputs, frozen window" contract SPEC.md section 3
    describes. cache_dir is accepted (required by run_args_builder's shape)
    but unused -- this lane has no cache-dir concept at all. Mirrors main()'s
    own window math exactly: fetch_spot reads [start_ms - HOUR_MS, last_ret_ts]
    where last_ret_ts extends RV_HORIZON_HOURS-1 hours past end_ms, so
    build_return_series (called in the run_fn) has every close it needs."""

    def fetch_dvol():
        points = load_dvol(cfg["dvol_path"], cfg["start_ms"], cfg["end_ms"])
        series_by_key["BTC:dvol"] = raw_series_fingerprint(points)
        return points

    def fetch_spot():
        last_ret_ts = cfg["end_ms"] + (RV_HORIZON_HOURS - 1) * HOUR_MS
        closes = load_spot_closes(cfg["spot_path"], cfg["start_ms"] - HOUR_MS,
                                  last_ret_ts)
        series_by_key["BTC:spot"] = raw_series_fingerprint(sorted(closes.items()))
        return closes

    return (fetch_dvol, fetch_spot)


def _vrp_measure_run(cfg: dict, fetch_dvol, fetch_spot, out_dir) -> dict:
    """Kernel-callable twin of tools.lanes.vrp_measure.main: wires
    moonface.research.vrp_measure's already-pure build_return_series/
    assemble_results directly over the injected dvol/spot fetches -- both
    fully deterministic (fixed BOOTSTRAP_SEED/NULL_SEED_GAUSS/NULL_SEED_T
    module constants, no live randomness). Returns only {"results": ...} --
    the CLI's real results.json nests everything under a top-level "results"
    key alongside "meta" (commit hash + input sha256s, pure run provenance,
    never a reproducible lane output), so compare_fields is the single
    "results" field rather than exploding every inner key. assemble_results
    returns bootstrap_ci/disjoint_ci as tuples and year_buckets keyed by int
    year -- not JSON-native, and `recorded` came from json.loads (tuples ->
    lists, int keys -> str keys), so a live call here would never compare
    equal. Round-tripping through json.dumps/loads keeps this byte-comparable
    to the recorded file, same fix _portfolio_run already established for
    its own non-JSON-native SystemCell rows."""
    dvol = fetch_dvol()
    closes = fetch_spot()
    last_ret_ts = cfg["end_ms"] + (RV_HORIZON_HOURS - 1) * HOUR_MS
    series = build_return_series(closes, cfg["start_ms"], last_ret_ts)
    results = assemble_results(dvol, series,
                               n_null_seeds=cfg.get("null_seeds", N_NULL_SEEDS))
    return {"results": json.loads(json.dumps(results))}


# The CLI (tools/lanes/vrp_measure.py) writes results.json with a top-level
# {"meta": ..., "results": {...}} shape -- "meta" is pure run provenance
# (git commit hash at run time, always mismatches; input file sha256s,
# already covered by data_fingerprint) and is deliberately excluded.
VRP_MEASURE_COMPARE_FIELDS = ("results",)


def _carry_measure_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    """carry_measure.py's own main() never reads through a cache_dir/symbol
    fetcher shape either (same wrinkle as vrp_measure) -- it reads three
    pinned CSVs by direct path (cfg["funding_path"]/["perp_path"]/
    ["spot_path"], real registration.json values: cache/matrix/
    funding_BTC_USDT_USDT.csv, .backtest_cache/BTC_USDT:USDT_1h.csv,
    .backtest_cache/BTC_USDT_1h.csv). cache_dir is accepted (required by
    run_args_builder's shape) but unused."""

    def fetch_funding():
        points = carry_measure_load_funding(cfg["funding_path"], cfg["start_ms"],
                                            cfg["end_ms"])
        series_by_key["BTC:funding"] = raw_series_fingerprint(points)
        return points

    def fetch_perp():
        bars = carry_measure_load_bars_1h(cfg["perp_path"], cfg["start_ms"],
                                          cfg["end_ms"])
        series_by_key["BTC:perp"] = raw_series_fingerprint(sorted(bars.items()))
        return bars

    def fetch_spot():
        bars = carry_measure_load_bars_1h(cfg["spot_path"], cfg["start_ms"],
                                          cfg["end_ms"])
        series_by_key["BTC:spot"] = raw_series_fingerprint(sorted(bars.items()))
        return bars

    return (fetch_funding, fetch_perp, fetch_spot)


def _carry_measure_run(cfg: dict, fetch_funding, fetch_perp, fetch_spot,
                       out_dir) -> dict:
    """Kernel-callable twin of tools.lanes.carry_measure.main: wires
    moonface.research.carry_measure's already-pure assemble_results directly
    over the injected funding/perp/spot fetches -- fully deterministic (fixed
    SEED module constant feeds block_bootstrap_dd, no live randomness).
    Returns only {"results": ...}, mirroring vrp_measure's shape: the CLI's
    real results.json nests everything under a top-level "results" key
    alongside "meta" (commit hash + input sha256s + a data-provenance prose
    note, pure run provenance, never a reproducible lane output). Unlike
    vrp_measure's assemble_results (tuples + int-keyed year_buckets),
    carry_measure's assemble_results already returns a fully JSON-native
    dict (confirmed: json.loads(json.dumps(results)) == results) -- no
    round-trip needed here."""
    funding = fetch_funding()
    perp = fetch_perp()
    spot = fetch_spot()
    return {"results": carry_measure_assemble_results(funding, perp, spot)}


# The CLI (tools/lanes/carry_measure.py) writes results.json with the same
# top-level {"meta": ..., "results": {...}} shape vrp_measure uses -- "meta"
# is pure run provenance (commit hash, seed -- a constant already implied by
# reproducibility, input sha256s, and a data-provenance prose note about the
# Coinbase-spliced spot gap) and is deliberately excluded.
CARRY_MEASURE_COMPARE_FIELDS = ("results",)

def _edge_search_run(cfg: dict, fetch_candles, out_dir) -> dict:
    """Kernel-callable twin of tools.edge.edge_search.main: wires
    moonface.research.edge_search's already-pure search/to_leaderboard
    directly over the injected candles fetch. Reuses _candles_run_args
    verbatim (single symbol, cfg["interval"] doubles as the timeframe key
    both the fetcher and edge_cells.cells_for need). Returns
    {"leaderboard": ...} matching the real leaderboard.json, which
    _load_recorded wraps as {"leaderboard": [...]} since verdict_filename's
    stem is "leaderboard" -- same shape drift_screen/exit_probe already
    established for a list-valued verdict file."""
    full = fetch_candles(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    train_oos = full[:-cfg["holdout_bars"]]
    cells = edge_cells_for(cfg["timeframe"])
    rows = edge_search_search(cells, train_oos, full)
    return {"leaderboard": edge_to_leaderboard(rows)}


# The CLI (tools/edge/edge_search.py) also writes RESULT.md (a rendered
# markdown table, narrative -- excluded) alongside leaderboard.json;
# leaderboard.json is the single substantive output, so compare_fields is
# just the one wrapped field.
EDGE_SEARCH_COMPARE_FIELDS = ("leaderboard",)


def _playbook_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    def fetch_multi_tf(sym: str, start_ms: int, end_ms: int) -> dict:
        data = {}
        for tf in PLAYBOOK_TIMEFRAMES:
            candles = offline_fetch_perp_candles(sym, tf, start_ms, end_ms, cache_dir)
            series_by_key[f"{sym}:{tf}:candles"] = series_fingerprint(candles)
            data[tf] = candles
        return data

    return (fetch_multi_tf,)


def _playbook_run(cfg: dict, fetch_multi_tf, out_dir) -> dict:
    """Kernel-callable twin of tools.playbook.playbook_search.main's
    --explore stage: wires already-pure moonface.research.playbook.explore
    .run_explore over the injected multi-timeframe candle fetch, reusing the
    CLI's own _segment_view (chronological 60/20/20 split + MTFView.build)
    verbatim rather than re-deriving it -- both are private to the CLI module
    but importing them is precedented (e.g. tools.engine.swing_donchian's
    _BASE, moonface.research.mtf.basket's _year). --register/--select/
    --validate are not reproduced: --register only stamps a fresh asof
    timestamp over the same fingerprinted data (verified by hand: identical
    bar counts + per-timeframe data_sha against the frozen
    PREREGISTRATION.md), and --select/--validate are deterministic given
    --explore's output but the frozen frozen_candidates.json/result.json are
    both the trivial empty list (0/12 configs survived selection) -- explore_
    leaderboard.json is the one output carrying real computed content (12
    real DSR + metric rows), so it is the only stage reproduced here."""
    data = fetch_multi_tf(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    configs = playbook_all_configs()
    explore_view = playbook_segment_view(data, "explore")
    rows = playbook_run_explore(configs, explore_view)
    slim = [{k: r[k] for k in ("label", "dsr", "metrics")} for r in rows]
    return {"explore_leaderboard": slim}


# The CLI also writes PREREGISTRATION.md/frozen_candidates.json/RESULT.md/
# result.json; PREREGISTRATION.md is narrative+a fresh asof timestamp
# (excluded, same class as every other lane's provenance file), and the
# frozen select/validate outputs are both the trivial empty list -- see
# _playbook_run's docstring. explore_leaderboard.json is the single
# substantive computed output.
PLAYBOOK_COMPARE_FIELDS = ("explore_leaderboard",)


def _practical_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    def fetch_multi_tf(sym: str, start_ms: int, end_ms: int) -> dict:
        data = {}
        for tf in PRACTICAL_TIMEFRAMES:
            candles = offline_fetch_perp_candles(sym, tf, start_ms, end_ms, cache_dir)
            series_by_key[f"{sym}:{tf}:candles"] = series_fingerprint(candles)
            data[tf] = candles
        return data

    return (fetch_multi_tf,)


def _practical_run(cfg: dict, fetch_multi_tf, out_dir) -> dict:
    """Kernel-callable twin of tools.practical.practical_search.main's
    --explore stage: wires already-pure moonface.research.practical.explore
    .run_explore over the injected multi-timeframe candle fetch, reusing the
    CLI's own _explore_by_tf (the first 60% chronological slice per
    timeframe) verbatim rather than re-deriving it -- same "private-CLI-
    helper reuse" precedent as playbook's _segment_view / swing_donchian's
    _BASE. Unlike playbook_search.py's --explore (which slims each row to
    label/dsr/metrics before writing), practical_search.py's --explore
    writes run_explore's rows UNSLIMMED (json.dumps(rows, ...), verified by
    reading the CLI's own main()) -- so this twin returns the full row shape
    (label/timeframe/family/group/axis/exit_name/params/exit_params/h/dsr/
    metrics), not the slim subset. --register/--select/--validate are not
    reproduced: --register only stamps a fresh asof timestamp over the same
    fingerprinted data (verified by hand against the frozen
    PREREGISTRATION.md: identical bar counts + per-timeframe data_sha), and
    --select/--validate are deterministic given --explore's output but the
    frozen frozen_candidates.json/result.json are both the trivial empty
    list (0/72 configs survived selection, matches [[practical-signal-
    discovery-results]] CLOSED 2026-06-21) -- explore_leaderboard.json is
    the one output carrying real computed content (72 real DSR + metric
    rows), so it is the only stage reproduced here."""
    data = fetch_multi_tf(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    configs = practical_all_configs()
    explore_by_tf = practical_explore_by_tf(data)
    rows = practical_run_explore(configs, explore_by_tf)
    return {"explore_leaderboard": rows}


# The CLI also writes PREREGISTRATION.md/frozen_candidates.json/RESULT.md/
# result.json; PREREGISTRATION.md is narrative+a fresh asof timestamp
# (excluded, same class as every other lane's provenance file), and the
# frozen select/validate outputs are both the trivial empty list -- see
# _practical_run's docstring. explore_leaderboard.json (unslimmed, unlike
# playbook's) is the single substantive computed output.
PRACTICAL_COMPARE_FIELDS = ("explore_leaderboard",)


def _practical_full_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    def fetch_multi_tf(sym: str, start_ms: int, end_ms: int) -> dict:
        data = {}
        for tf in PRACTICAL_FULL_TIMEFRAMES:
            candles = offline_fetch_perp_candles(sym, tf, start_ms, end_ms, cache_dir)
            series_by_key[f"{sym}:{tf}:candles"] = series_fingerprint(candles)
            data[tf] = candles
        return data

    return (fetch_multi_tf,)


def _practical_full_run(cfg: dict, fetch_multi_tf, out_dir) -> dict:
    """Kernel-callable twin of tools.practical_full.btc_practical_full.main's
    full --explore/--select/--validate chain. Unlike practical/playbook (whose
    frozen frozen_candidates.json/result.json are both the trivial empty list,
    so only --explore was worth reproducing), this lane's real
    experiments/practical_full/{frozen_candidates,result}.json both carry real
    computed content (3/132 configs survived selection, matches
    [[practical-full-reeval-results]] CLOSED 2026-06-25 -- all 3 then reverse
    in the sealed segment) -- so this twin runs the CLI's own 4 subcommands'
    logic end to end in one call and reproduces the final gated output
    (result.json) rather than stopping at the intermediate explore leaderboard.
    Reuses the CLI's own private _split_60_20_20/_explore_by_tf verbatim (same
    "private-CLI-helper reuse" precedent as practical/playbook), plus already-
    pure moonface.research.practical_full.{grid.all_configs,select_full.
    select_full,validate_full.validate_all_full} and
    moonface.research.practical.pipeline.{freeze_candidates,to_leaderboard}
    (the latter two already used by practical_search.py's own --select/
    --validate stages, confirmed by reading the CLI's main()). --register only
    stamps a fresh asof timestamp over the same fingerprinted data (verified
    by hand against the frozen PREREGISTRATION.md: identical per-timeframe bar
    counts + data_sha), so not separately reproduced."""
    data = fetch_multi_tf(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    configs = practical_full_all_configs(list(PRACTICAL_FULL_TIMEFRAMES))
    explore_by_tf = practical_full_explore_by_tf(data)
    rows = practical_run_explore(configs, explore_by_tf)
    survivors = select_full(rows, explore_by_tf)
    frozen = freeze_candidates(survivors)
    validate_by_tf, sealed_by_tf = {}, {}
    for tf in PRACTICAL_FULL_TIMEFRAMES:
        _e, v, s = practical_full_split(data[tf])
        validate_by_tf[tf], sealed_by_tf[tf] = v, s
    result_rows = validate_all_full(frozen, validate_by_tf, sealed_by_tf)
    return {"result": to_leaderboard(result_rows)}


# The CLI also writes PREREGISTRATION.md/explore_leaderboard.json/
# frozen_candidates.json/RESULT.md; PREREGISTRATION.md is narrative+a fresh
# asof timestamp (excluded, same class as every other lane's provenance
# file). result.json is the final gated output -- see _practical_full_run's
# docstring for why it, not explore_leaderboard.json, is the reproduced
# field here.
PRACTICAL_FULL_COMPARE_FIELDS = ("result",)


def _btcspec_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    def fetch_multi_tf(sym: str, start_ms: int, end_ms: int) -> dict:
        data = {}
        for tf in BTCSPEC_TIMEFRAMES:
            candles = offline_fetch_perp_candles(sym, tf, start_ms, end_ms, cache_dir)
            series_by_key[f"{sym}:{tf}:candles"] = series_fingerprint(candles)
            data[tf] = candles
        return data

    return (fetch_multi_tf,)


def _btcspec_run(cfg: dict, fetch_multi_tf, out_dir) -> dict:
    """Kernel-callable twin of tools.btcspec.btcspec_search.main's full
    --explore/--select/--validate chain (BTC-Specialized Slice 1: 2h/4h trend
    + breakout entry families). Same non-trivial-output shape as
    practical_full: the real experiments/btc_specialized/slice1_trend_breakout/
    {frozen_candidates,result}.json both carry real computed content (9
    candidates through validate, one opened on the sealed tail, rejected --
    matches [[btc-specialized-lane]] CLOSED 2026-07-02 NEGATIVE), so this twin
    runs explore->select->validate end to end and reproduces the final gated
    result.json rather than stopping at the intermediate explore leaderboard.
    Reuses the CLI's own private _split_55_25_20/_explore_by_tf verbatim (same
    "private-CLI-helper reuse" precedent as practical/practical_full/
    playbook), plus already-pure moonface.research.btcspec.{explore.
    run_explore, families.all_explore_configs, select.select, validate.
    validate_all, pipeline.{freeze_candidates,to_leaderboard}} -- the same
    functions btcspec_search.py's own --explore/--select/--validate stages
    call, confirmed by reading the CLI's main(). --register only stamps a
    fresh asof timestamp over the same fingerprinted data (verified by hand
    against the frozen PREREGISTRATION.md: identical per-timeframe bar counts
    + data_sha), so not separately reproduced."""
    data = fetch_multi_tf(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    configs = btcspec_all_configs()
    explore_by_tf = btcspec_explore_by_tf(data)
    rows = btcspec_run_explore(configs, explore_by_tf)
    frozen = btcspec_freeze_candidates(btcspec_select(rows))
    validate_by_tf, sealed_by_tf = {}, {}
    for tf in BTCSPEC_TIMEFRAMES:
        _e, v, s = btcspec_split(data[tf])
        validate_by_tf[tf], sealed_by_tf[tf] = v, s
    result_rows = btcspec_validate_all(frozen, validate_by_tf, sealed_by_tf)
    return {"result": btcspec_to_leaderboard(result_rows)}


# The CLI also writes PREREGISTRATION.md/explore_leaderboard.json/
# frozen_candidates.json/RESULT.md; PREREGISTRATION.md is narrative+a fresh
# asof timestamp (excluded, same class as every other lane's provenance
# file). result.json is the final gated output, same reasoning as
# _practical_full_run's docstring.
BTCSPEC_COMPARE_FIELDS = ("result",)


def _btcspec_s2_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    def fetch_multi_tf(sym: str, start_ms: int, end_ms: int) -> dict:
        data = {}
        for tf in BTCSPEC_S2_TIMEFRAMES:
            candles = offline_fetch_perp_candles(sym, tf, start_ms, end_ms, cache_dir)
            series_by_key[f"{sym}:{tf}:candles"] = series_fingerprint(candles)
            data[tf] = candles
        return data

    return (fetch_multi_tf,)


def _btcspec_s2_run(cfg: dict, fetch_multi_tf, out_dir) -> dict:
    """Kernel-callable twin of tools.btcspec.btcspec_s2_search.main's full
    --explore/--select/--validate chain (BTC-Specialized Slice 2: 1h short-swing
    ma_cross/trend_pullback/vol_expansion families). Same non-trivial-output shape
    as Slice 1: real experiments/btc_specialized/slice2_short_swing/
    {frozen_candidates,result}.json both carry real computed content. Reuses the
    slice-agnostic moonface.research.btcspec.{explore.run_explore, select.select,
    validate.validate_all, pipeline.{freeze_candidates,to_leaderboard}} already
    wired for Slice 1 (confirmed identical by reading btcspec_s2_search.py's own
    imports), plus families_s2.all_explore_configs_s2 (Slice-2-specific grid) and
    the CLI's own private _split_55_25_20/_explore_by_tf/S2_EXTRA_COST imported
    verbatim (same "private-CLI-helper reuse" precedent as Slice 1). Slice 2's
    --validate branch passes extra_cost=S2_EXTRA_COST (+10bps cost-stress, vs
    Slice 1's plain default) -- confirmed by reading the CLI's main() directly.
    --register only stamps a fresh asof over the same fingerprinted data, not
    separately reproduced."""
    data = fetch_multi_tf(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    configs = btcspec_s2_all_configs()
    explore_by_tf = btcspec_s2_explore_by_tf(data)
    rows = btcspec_run_explore(configs, explore_by_tf)
    frozen = btcspec_freeze_candidates(btcspec_select(rows))
    validate_by_tf, sealed_by_tf = {}, {}
    for tf in BTCSPEC_S2_TIMEFRAMES:
        _e, v, s = btcspec_s2_split(data[tf])
        validate_by_tf[tf], sealed_by_tf[tf] = v, s
    result_rows = btcspec_validate_all(frozen, validate_by_tf, sealed_by_tf,
                                       extra_cost=BTCSPEC_S2_EXTRA_COST)
    return {"result": btcspec_to_leaderboard(result_rows)}


# The CLI also writes PREREGISTRATION.md/explore_leaderboard.json/
# frozen_candidates.json/RESULT.md; PREREGISTRATION.md is narrative+a fresh
# asof timestamp (excluded, same class as every other lane's provenance
# file). result.json is the final gated output, same reasoning as
# BTCSPEC_COMPARE_FIELDS's docstring.
BTCSPEC_S2_COMPARE_FIELDS = ("result",)


def _btcspec_s3_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    def fetch_multi_tf(sym: str, start_ms: int, end_ms: int) -> dict:
        data = {}
        for tf in BTCSPEC_S3_TIMEFRAMES:
            candles = offline_fetch_perp_candles(sym, tf, start_ms, end_ms, cache_dir)
            series_by_key[f"{sym}:{tf}:candles"] = series_fingerprint(candles)
            data[tf] = candles
        return data

    return (fetch_multi_tf,)


def _btcspec_s3_run(cfg: dict, fetch_multi_tf, out_dir) -> dict:
    """Kernel-callable twin of tools.btcspec.btcspec_s3_search.main's full
    --explore/--select/--validate chain (BTC-Specialized Slice 3: 15m/30m
    intraday vol_compression_breakout/liquidity_sweep_reclaim/bb_revert
    families). Same non-trivial-output shape as Slices 1/2: real
    experiments/btc_specialized/slice3_intraday/{frozen_candidates,result}.json
    both carry real computed content (3 candidates through validate, all
    rejected -- matches [[btc-specialized-lane]] CLOSED 2026-07-02 NEGATIVE).
    Reuses the slice-agnostic moonface.research.btcspec.{explore.run_explore,
    select.select, validate.validate_all, pipeline.{freeze_candidates,
    to_leaderboard}} already wired for Slices 1/2 (confirmed identical by
    reading btcspec_s3_search.py's own imports), plus families_s3.
    all_explore_configs_s3 (Slice-3-specific grid) and the CLI's own private
    _split_55_25_20/_explore_by_tf/S3_EXTRA_COST imported verbatim (same
    "private-CLI-helper reuse" precedent as Slices 1/2). Slice 3's --validate
    branch passes extra_cost=S3_EXTRA_COST (+15bps cost-stress, the fastest
    turnover of the three slices) -- confirmed by reading the CLI's main()
    directly. --register only stamps a fresh asof over the same fingerprinted
    data, not separately reproduced."""
    data = fetch_multi_tf(cfg["symbol"], cfg["start_ms"], cfg["end_ms"])
    configs = btcspec_s3_all_configs()
    explore_by_tf = btcspec_s3_explore_by_tf(data)
    rows = btcspec_run_explore(configs, explore_by_tf)
    frozen = btcspec_freeze_candidates(btcspec_select(rows))
    validate_by_tf, sealed_by_tf = {}, {}
    for tf in BTCSPEC_S3_TIMEFRAMES:
        _e, v, s = btcspec_s3_split(data[tf])
        validate_by_tf[tf], sealed_by_tf[tf] = v, s
    result_rows = btcspec_validate_all(frozen, validate_by_tf, sealed_by_tf,
                                       extra_cost=BTCSPEC_S3_EXTRA_COST)
    return {"result": btcspec_to_leaderboard(result_rows)}


# The CLI also writes PREREGISTRATION.md/explore_leaderboard.json/
# frozen_candidates.json/RESULT.md; PREREGISTRATION.md is narrative+a fresh
# asof timestamp (excluded, same class as every other lane's provenance
# file). result.json is the final gated output, same reasoning as
# BTCSPEC_COMPARE_FIELDS's docstring.
BTCSPEC_S3_COMPARE_FIELDS = ("result",)

EXOGENOUS_MACRO_SERIES = ("SP500", "DTWEXBGS", "VIXCLS", "DGS2", "DGS10")


def _exogenous_run_args(cfg: dict, cache_dir: str, series_by_key: dict) -> tuple:
    """tools/exogenous_btc.py's own main() reads BTCUSDT daily klines
    (moonface.research.universe_data.fetch_daily_klines, live-fallback) and 5
    FRED macro series (moonface.research.exogenous.fred_data.fetch_fred_series,
    a straight re-export of moonface.data.macro.fetch_fred_series, live-
    fallback) -- both already have offline, cache-only twins in
    kernel/reproduce.py (offline_fetch_daily_klines, offline_fetch_fred_series;
    the latter's reuse is precedented at [[ls_tournament]]'s own FRED read).
    Deribit DVOL is fetched only by the CLI's --readiness branch, never by
    --screen/--explore/--select/--validate (confirmed by reading run()'s
    branching), so this lane's reproduction -- which targets --validate's
    Stage 2/3 verdict, the only stage with a frozen result -- needs no DVOL
    fetcher at all."""
    def fetch_daily():
        rows = offline_fetch_daily_klines(cfg["symbol"], cfg["start_ms"], cfg["end_ms"], cache_dir)
        series_by_key[f"{cfg['symbol']}:daily"] = raw_series_fingerprint(
            [(r.ts_ms, r.close) for r in rows])
        return rows

    def fetch_macro():
        series = {}
        for sid in EXOGENOUS_MACRO_SERIES:
            points = offline_fetch_fred_series(sid, cache_dir)
            series_by_key[f"FRED:{sid}"] = raw_series_fingerprint(
                [(p.ts_ms, p.value) for p in points])
            series[sid] = points
        return series

    return (fetch_daily, fetch_macro)


def _exogenous_run(cfg: dict, fetch_daily, fetch_macro, out_dir) -> dict:
    """Kernel-callable twin of tools/exogenous_btc.py's `_validate` branch
    (Stage 2 DSR + Stage 3 walk-forward econ verdict over the frozen 4-state
    PRECOMMITTED_STATES grid from research.exogenous.grid -- state_positions
    sums all 4 states' signed votes into one composite position, so this does
    NOT re-derive the Stage-1 screen/select survivor from frozen_candidates.
    json; it's a pure function of (closes, ts, series) only, mirrored
    statement-for-statement from _validate's body. Real
    experiments/exogenous/STAGE23_RESULT.md records passed=false (Stage 2 DSR
    0.0 AND Stage 3 max_dd_r -30.14R breach), matching [[exogenous-lane-
    results]] CLOSED 2026-06-26."""
    rows = fetch_daily()
    ts = [r.ts_ms for r in rows]
    closes = [r.close for r in rows]
    series = fetch_macro()
    v = exogenous_econ_verdict(closes, ts, series)
    rets = exogenous_daily_returns(closes)
    pos = exogenous_state_positions(ts[:len(rets)], series)
    trades = exogenous_episode_trades(pos[:len(rets)], rets)
    dsr = exogenous_dsr_of_trades(trades, EXOGENOUS_N_TRIALS)
    dsr_pass = dsr >= 0.95
    return {
        "passed": bool(v.passed and dsr_pass),
        "dsr_pass": bool(dsr_pass),
        "dsr": round(dsr, 6),
        "econ_passed": bool(v.passed),
        "metrics": v.metrics,
        "n_trials": EXOGENOUS_N_TRIALS,
    }


# STAGE23_RESULT.md's frozen JSON block also carries "reasons" (a narrative
# list explaining the metrics' pass/fail, e.g. "drawdown -30.1378R exceeds
# 30.0R tol") -- excluded per the "no narrative reason field" rule, same
# precedent as donchian_revalidate's Verdict.reasons.
EXOGENOUS_COMPARE_FIELDS = ("passed", "dsr_pass", "dsr", "econ_passed",
                           "metrics", "n_trials")

LANES: dict[str, LaneEntry] = {
    "oibuild_study": LaneEntry(oibuild_study_run, OIBUILD_STUDY_COMPARE_FIELDS,
                               _candles_metric_run_args,
                               ("tools/lanes/oibuild_study.py",)),
    "liqladder": LaneEntry(liqladder_run, LIQLADDER_COMPARE_FIELDS,
                           _candles_raw_metrics_run_args,
                           ("tools/lanes/liqladder.py",)),
    "liqrev": LaneEntry(liqrev_run, LIQREV_COMPARE_FIELDS,
                        _candles_metric_run_args, ("tools/lanes/liqrev.py",)),
    "calseason": LaneEntry(calseason_run, CALSEASON_COMPARE_FIELDS,
                           _candles_run_args, ("tools/lanes/calseason.py",)),
    "macro_event": LaneEntry(macro_event_run, MACRO_EVENT_COMPARE_FIELDS,
                             _candles_run_args, ("tools/lanes/macro_event.py",)),
    "bab": LaneEntry(bab_run, BAB_COMPARE_FIELDS, _daily_funding_run_args,
                     ("tools/lanes/bab.py",)),
    "xsection": LaneEntry(xsection_run, XSECTION_COMPARE_FIELDS,
                          _daily_funding_run_args, ("tools/lanes/xsection.py",)),
    "liqprem": LaneEntry(liqprem_run, LIQPREM_COMPARE_FIELDS,
                         _daily_funding_run_args, ("tools/lanes/liqprem.py",)),
    "resrev": LaneEntry(resrev_run, RESREV_COMPARE_FIELDS,
                        _daily_funding_run_args, ("tools/lanes/resrev.py",)),
    "bookdepth_study": LaneEntry(oibuild_study_run, OIBUILD_STUDY_COMPARE_FIELDS,
                                 _candles_bookdepth_run_args,
                                 ("tools/lanes/bookdepth_study.py",)),
    "drift_screen_stack_path": LaneEntry(
        _drift_screen_stack_path_run, DRIFT_SCREEN_STACK_PATH_COMPARE_FIELDS,
        _ohlcv_loader_run_args, ("tools/lanes/drift_screen_stack_path.py",),
        verdict_filename="result.json"),
    "drift_screen": LaneEntry(
        _drift_screen_run, DRIFT_SCREEN_COMPARE_FIELDS,
        _ohlcv_loader_run_args, ("tools/lanes/drift_screen.py",),
        verdict_filename="leaderboard.json"),
    "drift_screen_multifamily": LaneEntry(
        _drift_screen_multifamily_run, DRIFT_SCREEN_MULTIFAMILY_COMPARE_FIELDS,
        _multifamily_readers_run_args,
        ("tools/lanes/drift_screen_multifamily.py",),
        verdict_filename="leaderboard.json"),
    "bb_breakout": LaneEntry(
        _bb_breakout_run, BB_VARIANT_COMPARE_FIELDS, _bb_candles_run_args,
        ("tools/lanes/bb_breakout.py",), verdict_filename="results_4h.json"),
    "bb_revert": LaneEntry(
        _bb_revert_run, BB_VARIANT_COMPARE_FIELDS, _bb_candles_run_args,
        ("tools/lanes/bb_revert.py",), verdict_filename="results_4h.json"),
    "bb_harvest": LaneEntry(
        _bb_harvest_run, BB_HARVEST_COMPARE_FIELDS, _bb_candles_run_args,
        ("tools/lanes/bb_harvest.py",), verdict_filename="results_4h.json"),
    "ls_exit_ablation": LaneEntry(
        _ls_exit_ablation_run, LS_EXIT_ABLATION_COMPARE_FIELDS, _candles_run_args,
        ("tools/lanes/ls_exit_ablation.py",), verdict_filename="RESULT.json"),
    "exit_probe": LaneEntry(
        _exit_probe_run, EXIT_PROBE_COMPARE_FIELDS, _candles_run_args,
        ("tools/lanes/exit_probe.py",), verdict_filename="leaderboard.json"),
    "advval": LaneEntry(
        _advval_run, ADVVAL_COMPARE_FIELDS, _advval_run_args,
        ("tools/advval/advval_run.py",), verdict_filename="results.json"),
    "eventtime": LaneEntry(
        _eventtime_run, EVENTTIME_COMPARE_FIELDS, _eventtime_run_args,
        ("tools/eventtime/eventtime_run.py",), verdict_filename="results.json"),
    "breadth": LaneEntry(
        _breadth_run, BREADTH_COMPARE_FIELDS, _breadth_universe_run_args,
        ("tools/breadth/breadth.py",), verdict_filename="RESULT.json"),
    "breadth_confirm": LaneEntry(
        _breadth_confirm_run, BREADTH_CONFIRM_COMPARE_FIELDS,
        _breadth_universe_run_args,
        ("tools/breadth_confirm/breadth_confirm.py",),
        verdict_filename="RESULT.json"),
    "breadth_momentum_confirm": LaneEntry(
        _breadth_momentum_confirm_run, BREADTH_MOMENTUM_CONFIRM_COMPARE_FIELDS,
        _breadth_universe_run_args,
        ("tools/breadth/breadth_momentum_confirm.py",),
        verdict_filename="RESULT.json"),
    "breadth_neutral": LaneEntry(
        _breadth_neutral_run, BREADTH_NEUTRAL_COMPARE_FIELDS,
        _breadth_universe_run_args,
        ("tools/breadth/breadth_neutral.py",),
        verdict_filename="RESULT.json"),
    "breadth_xasset_confirm": LaneEntry(
        _breadth_xasset_confirm_run, BREADTH_XASSET_CONFIRM_COMPARE_FIELDS,
        _breadth_universe_run_args,
        ("tools/breadth/breadth_xasset_confirm.py",),
        verdict_filename="RESULT.json"),
    "breadth_internal": LaneEntry(
        _breadth_internal_run, BREADTH_INTERNAL_COMPARE_FIELDS,
        _breadth_universe_run_args,
        ("tools/breadth_internal/breadth_internal.py",),
        verdict_filename="RESULT.json"),
    "breadth_internal_hf": LaneEntry(
        _breadth_internal_hf_run, BREADTH_INTERNAL_HF_COMPARE_FIELDS,
        _breadth_universe_run_args,
        ("tools/breadth_internal/breadth_internal_hf.py",),
        verdict_filename="RESULT.json"),
    "donchian_filter": LaneEntry(
        _donchian_filter_run, DONCHIAN_FILTER_COMPARE_FIELDS,
        _donchian_filter_run_args,
        ("tools/donchian_filter/donchian_filter.py",),
        verdict_filename="RESULT.json"),
    "btc_classic": LaneEntry(
        _btc_classic_run, BTC_CLASSIC_COMPARE_FIELDS,
        _donchian_filter_run_args,
        ("tools/btc_classic/btc_classic.py",),
        verdict_filename="RESULT.json"),
    "donchian_volregime": LaneEntry(
        _donchian_volregime_run, DONCHIAN_VOLREGIME_COMPARE_FIELDS,
        _donchian_filter_run_args,
        ("tools/donchian_volregime/donchian_volregime.py",),
        verdict_filename="RESULT.json"),
    "regime_overlay": LaneEntry(
        _regime_overlay_run, REGIME_OVERLAY_COMPARE_FIELDS,
        _regime_overlay_run_args,
        ("tools/regime_overlay/regime_overlay_btc.py",),
        verdict_filename="RESULT.json"),
    "regime_selector": LaneEntry(
        _regime_selector_run, REGIME_SELECTOR_COMPARE_FIELDS,
        _regime_selector_run_args,
        ("tools/regime_selector/regime_selector_btc.py",),
        verdict_filename="RESULT.json"),
    "ls_tournament": LaneEntry(
        _ls_tournament_run, LS_TOURNAMENT_COMPARE_FIELDS,
        _ls_tournament_run_args,
        ("tools/ls_tournament/ls_tournament.py",),
        verdict_filename="RESULT.json"),
    "sse": LaneEntry(
        _sse_run, SSE_COMPARE_FIELDS, _sse_run_args,
        ("tools/sse/sse.py",),
        verdict_filename="gate0_verdict.json"),
    "portfolio": LaneEntry(
        _portfolio_run, PORTFOLIO_COMPARE_FIELDS, _portfolio_run_args,
        ("tools/portfolio/portfolio_search.py",),
        verdict_filename="explore_leaderboard.json"),
    "liq_twap": LaneEntry(
        _liq_twap_run, LIQ_TWAP_COMPARE_FIELDS, _candles_metric_run_args,
        ("tools/liq_twap/liq_twap_screen.py",)),
    "consolidated_ls": LaneEntry(
        _consolidated_ls_run, CONSOLIDATED_LS_COMPARE_FIELDS,
        _consolidated_ls_run_args,
        ("tools/consolidated/consolidated_ls.py",),
        verdict_filename="RESULT.json"),
    "matrix": LaneEntry(
        _matrix_run, MATRIX_COMPARE_FIELDS,
        _donchian_filter_run_args,
        ("tools/matrix/matrix_evaluate.py",),
        verdict_filename="matrix_slice1b_2026-07.json"),
    "mtf_transfer": LaneEntry(
        _mtf_transfer_run, MTF_TRANSFER_COMPARE_FIELDS,
        _candles_run_args,
        ("tools/mtf/mtf_transfer.py",)),
    "mtf_basket": LaneEntry(
        _mtf_basket_run, MTF_BASKET_COMPARE_FIELDS,
        _candles_run_args,
        ("tools/mtf/mtf_basket.py",)),
    "mtf_broaden": LaneEntry(
        _mtf_broaden_run, MTF_BROADEN_COMPARE_FIELDS,
        _candles_run_args,
        ("tools/mtf/mtf_broaden.py",)),
    "mtf_long_only": LaneEntry(
        _mtf_long_only_run, MTF_LONG_ONLY_COMPARE_FIELDS,
        _candles_run_args,
        ("tools/mtf/mtf_long_only.py",)),
    "donchian_revalidate": LaneEntry(
        _donchian_revalidate_run, DONCHIAN_REVALIDATE_COMPARE_FIELDS,
        _donchian_filter_run_args,
        ("tools/lanes/donchian_revalidate.py",)),
    "vrp_measure": LaneEntry(
        _vrp_measure_run, VRP_MEASURE_COMPARE_FIELDS,
        _vrp_measure_run_args,
        ("tools/lanes/vrp_measure.py",), verdict_filename="results.json"),
    "carry_measure": LaneEntry(
        _carry_measure_run, CARRY_MEASURE_COMPARE_FIELDS,
        _carry_measure_run_args,
        ("tools/lanes/carry_measure.py",), verdict_filename="results.json"),
    "edge_search_swing_4h": LaneEntry(
        _edge_search_run, EDGE_SEARCH_COMPARE_FIELDS,
        _candles_run_args,
        ("tools/edge/edge_search.py",), verdict_filename="leaderboard.json"),
    "edge_search_day_15m": LaneEntry(
        _edge_search_run, EDGE_SEARCH_COMPARE_FIELDS,
        _candles_run_args,
        ("tools/edge/edge_search.py",), verdict_filename="leaderboard.json"),
    "playbook": LaneEntry(
        _playbook_run, PLAYBOOK_COMPARE_FIELDS,
        _playbook_run_args,
        ("tools/playbook/playbook_search.py",),
        verdict_filename="explore_leaderboard.json"),
    "practical": LaneEntry(
        _practical_run, PRACTICAL_COMPARE_FIELDS,
        _practical_run_args,
        ("tools/practical/practical_search.py",),
        verdict_filename="explore_leaderboard.json"),
    "practical_full": LaneEntry(
        _practical_full_run, PRACTICAL_FULL_COMPARE_FIELDS,
        _practical_full_run_args,
        ("tools/practical_full/btc_practical_full.py",),
        verdict_filename="result.json"),
    "btcspec": LaneEntry(
        _btcspec_run, BTCSPEC_COMPARE_FIELDS,
        _btcspec_run_args,
        ("tools/btcspec/btcspec_search.py",),
        verdict_filename="result.json"),
    "btcspec_s2": LaneEntry(
        _btcspec_s2_run, BTCSPEC_S2_COMPARE_FIELDS,
        _btcspec_s2_run_args,
        ("tools/btcspec/btcspec_s2_search.py",),
        verdict_filename="result.json"),
    "btcspec_s3": LaneEntry(
        _btcspec_s3_run, BTCSPEC_S3_COMPARE_FIELDS,
        _btcspec_s3_run_args,
        ("tools/btcspec/btcspec_s3_search.py",),
        verdict_filename="result.json"),
    "exogenous": LaneEntry(
        _exogenous_run, EXOGENOUS_COMPARE_FIELDS,
        _exogenous_run_args,
        ("tools/exogenous/exogenous_btc.py",)),
}
