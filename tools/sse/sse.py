#!/usr/bin/env python3
# ruff: noqa: E402
"""SSE lane CLI: Gate 0 evaluation plus one-touch lockbox plumbing."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from moonface.core.bundle import DataBundle
from moonface.research.microscope.features import build_matrix, realized_vol, rolling_z
from moonface.research.multifamily_loader import default_readers
from moonface.research.sse.axes import AxisMatrix, build_axes
from moonface.research.sse.clusters import assign_clusters, fit_kmeans
from moonface.research.sse.episodes import assign_eras, entry_episodes
from moonface.research.sse.gate import gate0_result
from moonface.research.sse.report import write_gate0_artifacts
from moonface.research.sse.trajectory import FEATURE_NAMES, summarize_trajectories
from moonface.research.sse.universe import monthly_membership
from moonface.research.universe_data import (
    DailyRow,
    fetch_daily_klines,
    fetch_perp_candles,
    list_um_perp_symbols,
)

POINT_FEATURES = ("breadth_z", "disp_z")
CONTROL_FEATURES = ("position", "velocity", "vol_accel", "crowding")
ERA_BOUNDS = [
    (1_577_836_800_000, 1_656_633_600_000),  # 2020-01-01 -> 2022-07-01
    (1_656_633_600_000, 1_719_792_000_000),  # 2022-07-01 -> 2024-07-01
    (1_719_792_000_000, 1_783_123_200_000),  # 2024-07-01 -> 2026-07-01
]


def _rows_from_axes(axes: AxisMatrix) -> list[dict[str, float | None]]:
    return [
        {"breadth_z": axes.breadth_z[i], "disp_z": axes.disp_z[i]}
        for i in range(len(axes.timestamps))
    ]


def _era_mask(timestamps: list[int]) -> list[bool]:
    return [ERA_BOUNDS[0][0] <= ts < ERA_BOUNDS[0][1] for ts in timestamps]


def _mean2(a: float | None, b: float | None) -> float | None:
    vals = [v for v in (a, b) if v is not None]
    return sum(vals) / len(vals) if vals else None


def build_control_rows(pool: dict[str, DataBundle], *, btc_symbol: str = "BTCUSDT") -> list[dict[str, float | None]]:
    matrix = build_matrix(pool, btc_symbol=btc_symbol)
    btc_rows = matrix.rows[btc_symbol]
    btc_bundle = pool[btc_symbol]
    closes = [c.close for c in btc_bundle.candles]
    rvol = realized_vol(closes)
    delta_rvol = [None if i == 0 or rvol[i] is None or rvol[i - 1] is None else rvol[i] - rvol[i - 1]
                  for i in range(len(rvol))]
    vol_accel = rolling_z(delta_rvol)
    return [
        {
            "position": row["dist_ma_z"],
            "velocity": _mean2(row["ret_6_z"], row["ret_42_z"]),
            "vol_accel": vol_accel[i],
            "crowding": _mean2(row["funding_z"], row["oi_chg_z"]),
        }
        for i, row in enumerate(btc_rows)
    ]


def _attach_eras(rows: list[dict], timestamps: list[int]) -> list[dict]:
    eras = assign_eras(timestamps, ERA_BOUNDS)
    ts_to_era = {ts: era for ts, era in zip(timestamps, eras)}
    return [{**row, "era": ts_to_era.get(row["ts_ms"])} for row in rows]


def _fit_assign(rows: list[dict[str, float | None]], feature_names: tuple[str, ...], timestamps: list[int]) -> list[int]:
    model = fit_kmeans(rows, feature_names=feature_names, fit_mask=_era_mask(timestamps), k=4, seed=1)
    return assign_clusters(rows, model)


def _cached_daily_symbols(cache_dir: str) -> list[str]:
    prefix = "uni1d_"
    suffix = ".csv"
    out = []
    for path in Path(cache_dir).glob(f"{prefix}*{suffix}"):
        name = path.name
        if name.endswith(".cov"):
            continue
        out.append(name[len(prefix):-len(suffix)])
    return sorted(set(out))


def _progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def run_gate0(
    pool: dict[str, DataBundle],
    daily: dict[str, list[DailyRow]],
    out_dir: Path,
    *,
    top_n: int = 50,
    min_history_days: int = 90,
    vol_days: int = 30,
    horizon: int = 24,
    draws: int = 1000,
    btc_symbol: str = "BTCUSDT",
    sealed_lockbox: dict | None = None,
    axes_ma_period: int = 300,
    axes_ret_bars: int = 6,
    axes_z_window: int = 540,
    traj_lookback: int = 20,
    traj_z_window: int = 540,
) -> dict:
    btc = pool[btc_symbol]
    timestamps = [c.timestamp_ms for c in btc.candles]
    membership = monthly_membership(
        daily,
        timestamps,
        top_n=top_n,
        min_history_days=min_history_days,
        vol_days=vol_days,
    )
    axes = build_axes(
        pool,
        membership,
        ma_period=axes_ma_period,
        ret_bars=axes_ret_bars,
        z_window=axes_z_window,
    )
    point_rows = _rows_from_axes(axes)
    traj_rows = summarize_trajectories(
        axes, lookback=traj_lookback, z_window=traj_z_window
    ).rows
    control_rows = build_control_rows(pool, btc_symbol=btc_symbol)

    point_labels = _fit_assign(point_rows, POINT_FEATURES, timestamps)
    traj_labels = _fit_assign(traj_rows, FEATURE_NAMES, timestamps)
    control_labels = _fit_assign(control_rows, CONTROL_FEATURES, timestamps)

    point_eps = _attach_eras(entry_episodes(point_labels, btc.candles, horizon=horizon), timestamps)
    traj_eps = _attach_eras(entry_episodes(traj_labels, btc.candles, horizon=horizon), timestamps)
    control_eps = _attach_eras(entry_episodes(control_labels, btc.candles, horizon=horizon), timestamps)

    points = gate0_result(
        track_n_episodes=point_eps,
        track_l_episodes=control_eps,
        labels=point_labels,
        candles=btc.candles,
        horizon=horizon,
        draws=draws,
    )
    trajectories = gate0_result(
        track_n_episodes=traj_eps,
        track_l_episodes=control_eps,
        labels=traj_labels,
        candles=btc.candles,
        horizon=horizon,
        draws=draws,
    )

    overall = "CLOSED"
    chosen = None
    if points["verdict"] == "SUSPECT_HARNESS" or trajectories["verdict"] == "SUSPECT_HARNESS":
        overall = "SUSPECT_HARNESS"
    elif points["verdict"] == "PASS":
        overall = "PENDING_GATE1"
        chosen = "points"
    elif trajectories["verdict"] == "PASS":
        overall = "PENDING_GATE1"
        chosen = "trajectories"

    result = {"verdict": overall, "chosen_cell": chosen, "points": points, "trajectories": trajectories}
    write_gate0_artifacts(out_dir, result)
    if overall == "PENDING_GATE1":
        state = {"chosen_cell": chosen, "sealed_result": sealed_lockbox}
        (out_dir / "lockbox_state.json").write_text(json.dumps(state, indent=2, sort_keys=True))
    return result


def run_lockbox(out_dir: Path, *, ack: bool) -> str:
    result_path = out_dir / "lockbox_result.json"
    if result_path.exists():
        return "REFUSED: lockbox already opened (one-touch)."
    if not ack:
        return "REFUSED: pass --i-understand-one-touch to open the lockbox."
    state_path = out_dir / "lockbox_state.json"
    if not state_path.exists():
        return "REFUSED: no pending Gate 1 state."
    state = json.loads(state_path.read_text())
    sealed = state.get("sealed_result")
    if sealed is None:
        return "REFUSED: no sealed lockbox payload is available."
    result_path.write_text(json.dumps(sealed, indent=2, sort_keys=True))
    return f"LOCKBOX: {sealed.get('verdict', 'UNKNOWN')}"


def load_gate0_inputs(
    cache_dir: str,
    start_ms: int,
    end_ms: int,
    *,
    progress: bool = False,
) -> tuple[dict[str, DataBundle], dict[str, list[DailyRow]], dict]:
    symbols = _cached_daily_symbols(cache_dir)
    if not symbols:
        symbols = list_um_perp_symbols()
        if progress:
            _progress(f"sse: discovered {len(symbols)} symbols from Binance Vision")
    elif progress:
        _progress(f"sse: using {len(symbols)} symbols from cached daily files")
    daily = {sym: fetch_daily_klines(sym, start_ms, end_ms, cache_dir) for sym in symbols}
    timestamps = [ts for ts in range(start_ms, end_ms, 14_400_000)]
    members = monthly_membership(daily, timestamps)
    union = sorted({sym for bucket in members.members for sym in bucket} | {"BTCUSDT"})
    if progress:
        _progress(f"sse: monthly top-volume union requires {len(union)} 4h series")
    readers = default_readers(cache_dir, start_ms, end_ms)
    pool: dict[str, DataBundle] = {}
    fetched = 0
    for sym in union:
        candles = fetch_perp_candles(sym, "4h", start_ms, end_ms, cache_dir)
        if not candles:
            continue
        fetched += 1
        if progress and (fetched == 1 or fetched % 10 == 0 or fetched == len(union)):
            _progress(f"sse: loaded {fetched}/{len(union)} required 4h series")
        bundle = DataBundle(candles=candles)
        if sym == "BTCUSDT":
            bundle = DataBundle(
                candles=candles,
                funding=readers["funding"](sym),
                feature=readers["metrics"](sym, "sum_open_interest"),
            )
        pool[sym] = bundle
    meta = {
        "symbol_count": len(symbols),
        "union_count": len(union),
        "loaded_4h_count": fetched,
    }
    return pool, daily, meta


def run_prewarm(cache_dir: str, start_ms: int, end_ms: int) -> dict:
    pool, daily, meta = load_gate0_inputs(
        cache_dir, start_ms, end_ms, progress=True
    )
    return {
        **meta,
        "daily_loaded_count": sum(1 for rows in daily.values() if rows),
        "pool_count": len(pool),
        "btc_ready": "BTCUSDT" in pool,
    }


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sse", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    g0 = sub.add_parser("gate0")
    g0.add_argument("--cache-dir", default="cache")
    g0.add_argument("--start-ms", type=int, default=1_577_836_800_000)
    g0.add_argument("--end-ms", type=int, default=1_783_123_200_000)
    g0.add_argument("--out", default="experiments/sse")
    g0.add_argument("--draws", type=int, default=1000)
    pw = sub.add_parser("prewarm")
    pw.add_argument("--cache-dir", default="cache")
    pw.add_argument("--start-ms", type=int, default=1_577_836_800_000)
    pw.add_argument("--end-ms", type=int, default=1_783_123_200_000)
    lb = sub.add_parser("lockbox")
    lb.add_argument("--out", default="experiments/sse")
    lb.add_argument("--i-understand-one-touch", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_argparser().parse_args(argv)
    if args.cmd == "gate0":
        pool, daily, _ = load_gate0_inputs(
            args.cache_dir, args.start_ms, args.end_ms, progress=True
        )
        result = run_gate0(pool, daily, Path(args.out), draws=args.draws)
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.cmd == "prewarm":
        print(json.dumps(run_prewarm(args.cache_dir, args.start_ms, args.end_ms), indent=2, sort_keys=True))
    else:
        print(run_lockbox(Path(args.out), ack=args.i_understand_one_touch))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
