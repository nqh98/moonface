#!/usr/bin/env python
# tools/microscope.py
"""Market State Microscope CLI.

matrix : build the normalized feature matrix, state vectors, and regime
         labels for the 16-asset+BTC 4h pool; dump CSVs.
study  : conditional event study — read an events CSV
         (columns ts_ms,symbol,direction), bucket forward outcomes by
         regime label, write outcomes CSV + markdown report with built-in
         null calibration.

DESCRIPTIVE DIAGNOSTIC — output is never a gate. See
docs/research-log/specs/2026-07-09-market-state-microscope-design.md."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.microscope.events import (Event, HORIZONS,
                                                 bucket_report,
                                                 event_outcomes,
                                                 null_calibration)
from moonface.research.microscope.factors import FACTOR_NAMES, state_vectors
from moonface.research.microscope.features import (FEATURE_KEYS,
                                                   build_matrix)
from moonface.research.microscope.regimes import UNLABELED, label_series
from moonface.research.microscope.report import (render_study_report,
                                                 write_csv)
from moonface.research.multifamily_loader import (default_readers,
                                                  load_pool_bundles)

UNIVERSE = ["1000PEPEUSDT", "PEOPLEUSDT", "DOGEUSDT", "BNBUSDT",
            "1000SHIBUSDT", "1000FLOKIUSDT", "XRPUSDT", "LINKUSDT",
            "HIGHUSDT", "NEARUSDT", "JASMYUSDT", "TRBUSDT", "FILUSDT",
            "ARBUSDT", "AVAXUSDT", "ETCUSDT", "BTCUSDT"]
OI_FIELD = "sum_open_interest"


def _ms(day: str) -> int:
    d = dt.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp() * 1000)


def load_pool(cache_dir: str, start: str, end: str):
    readers = default_readers(cache_dir, _ms(start), _ms(end))
    return load_pool_bundles(UNIVERSE, OI_FIELD, readers["candles"],
                             readers["funding"], readers["metrics"],
                             readers["bookdepth"])


def parse_events_csv(path: Path) -> list[Event]:
    events: list[Event] = []
    with path.open() as fh:
        for rec in csv.DictReader(fh):
            events.append(Event(ts_ms=int(rec["ts_ms"]),
                                symbol=rec["symbol"],
                                direction=int(rec["direction"])))
    return events


def run_matrix(pool, out_dir: Path) -> dict:
    matrix = build_matrix(pool)
    states = state_vectors(matrix)
    labels = label_series(states)
    feat_rows: list[dict] = []
    state_rows: list[dict] = []
    for sym in matrix.symbols:
        for t, ts in enumerate(matrix.timestamps):
            feat_rows.append({"symbol": sym, "ts_ms": ts,
                              **matrix.rows[sym][t]})
            state_rows.append({"symbol": sym, "ts_ms": ts,
                               **states[sym][t], "label": labels[sym][t]})
    pool_rows = [{"ts_ms": ts, "mkt_ret_z": matrix.mkt_ret_z[t],
                  "breadth_z": matrix.breadth_z[t]}
                 for t, ts in enumerate(matrix.timestamps)]
    write_csv(out_dir / "features.csv", feat_rows,
              ["symbol", "ts_ms", *FEATURE_KEYS])
    write_csv(out_dir / "states.csv", state_rows,
              ["symbol", "ts_ms", *FACTOR_NAMES, "label"])
    write_csv(out_dir / "pool.csv", pool_rows,
              ["ts_ms", "mkt_ret_z", "breadth_z"])
    return {"matrix": matrix, "states": states, "labels": labels,
            "n_bars": len(matrix.timestamps)}


def run_study(pool, events: list[Event], out_dir: Path, seed: int) -> str:
    built = run_matrix(pool, out_dir)
    outcomes = event_outcomes(pool, built["labels"],
                              built["matrix"].timestamps, events)
    buckets = bucket_report(outcomes, seed=seed)
    null_result = null_calibration(outcomes, seed=seed)
    n_unlabeled = sum(1 for r in outcomes if r["label"] == UNLABELED)
    write_csv(out_dir / "outcomes.csv", outcomes,
              ["symbol", "ts_ms", "direction", "label",
               *[f"fwd_r_{h}" for h in HORIZONS],
               "mfe_r", "mae_r", "stop_first", "fwd_vol"])
    text = render_study_report(buckets, null_result, len(events),
                               len(outcomes), n_unlabeled)
    (out_dir / "report.md").write_text(text)
    return text


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="microscope", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("matrix", "study"):
        s = sub.add_parser(name)
        s.add_argument("--cache-dir", default="cache")
        s.add_argument("--start", default="2023-01-01")
        s.add_argument("--end", default="2026-07-01")
        s.add_argument("--out", default="experiments/microscope")
    sub.choices["study"].add_argument("--events", required=True)
    sub.choices["study"].add_argument("--seed", type=int, default=1)
    return p


def main(argv=None) -> int:
    args = build_argparser().parse_args(argv)
    out_dir = Path(args.out)
    pool = load_pool(args.cache_dir, args.start, args.end)
    if args.cmd == "matrix":
        built = run_matrix(pool, out_dir)
        print(f"wrote features/states/labels for {len(pool)} assets,"
              f" {built['n_bars']} bars -> {out_dir}")
    else:
        events = parse_events_csv(Path(args.events))
        text = run_study(pool, events, out_dir, args.seed)
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
