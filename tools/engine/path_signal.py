#!/usr/bin/env python
# tools/path_signal.py
"""BTC distributional path signal CLI.

register : freeze the design (timeframe, horizons, feature list, split,
           gate) into registration.json. Run once; the file is the frozen
           pre-registration the model plans must not silently change.

Design frozen in experiments/path_signal/PREREGISTRATION.md."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.pathsig.features import FEATURE_NAMES

TIMEFRAME = "4h"
HORIZONS = [6, 12]
ATR_PERIOD = 14
DEPLOY_ASSET = "BTCUSDT"
DSR_THRESHOLD = 0.95
LOCKBOX_FRACTION = 0.2


def register(out_path: str) -> None:
    reg = {
        "timeframe": TIMEFRAME,
        "horizons": HORIZONS,
        "atr_period": ATR_PERIOD,
        "deploy_asset": DEPLOY_ASSET,
        "dsr_threshold": DSR_THRESHOLD,
        "lockbox_fraction": LOCKBOX_FRACTION,
        "features": list(FEATURE_NAMES),
    }
    Path(out_path).write_text(json.dumps(reg, indent=2))
    print(f"wrote {out_path} ({len(FEATURE_NAMES)} features frozen)")


def baseline(out_path: str, cache_dir: str, n_folds: int,
             horizons: list[int], readers=None,
             pool_symbols=None) -> None:
    import time

    from moonface.research.pathsig.baseline import (POOL_SYMBOLS,
                                                    run_baseline_to_doc)

    if readers is None:
        from moonface.research.multifamily_loader import default_readers
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - int(3 * 365 * 86_400_000)
        readers = default_readers(cache_dir, start_ms, end_ms)
    doc = run_baseline_to_doc(readers, n_folds=n_folds, horizons=horizons,
                              pool_symbols=pool_symbols or POOL_SYMBOLS)
    Path(out_path).write_text(json.dumps(doc, indent=2))
    ok = [r for r in doc["rows"] if r["status"] == "ok"]
    print(f"wrote {out_path}: {len(doc['rows'])} rows, {len(ok)} scored")
    for r in sorted(ok, key=lambda r: r["fixed_cap"]["total_r"],
                    reverse=True)[:5]:
        fc = r["fixed_cap"]
        print(f"  {r['family']:<20} h={r['h']} total_r={fc['total_r']:+.2f} "
              f"maxdd_r={fc['max_drawdown_r']:+.2f} cap_ok={fc['within_cap']}")


def ensemble(out_path: str, cache_dir: str, n_folds: int,
             horizons: list[int], rung0_path: str | None = None,
             readers=None, pool_symbols=None) -> None:
    import time

    from moonface.research.pathsig.baseline import POOL_SYMBOLS
    from moonface.research.pathsig.ensemble import run_ensemble_to_doc

    rung0_doc = None
    if rung0_path and Path(rung0_path).exists():
        rung0_doc = json.loads(Path(rung0_path).read_text())
    if readers is None:
        from moonface.research.multifamily_loader import default_readers
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - int(3 * 365 * 86_400_000)
        readers = default_readers(cache_dir, start_ms, end_ms)
    doc = run_ensemble_to_doc(readers, n_folds=n_folds, horizons=horizons,
                              pool_symbols=pool_symbols or POOL_SYMBOLS,
                              rung0_doc=rung0_doc)
    Path(out_path).write_text(json.dumps(doc, indent=2))
    print(f"wrote {out_path}")
    for res, v in zip(doc["rung1"], doc["verdict"]):
        if res["status"] != "ok":
            print(f"  h={res['h']} {res['status']}")
            continue
        fc, ra = res["fixed_cap"], res["risk_adjusted"]
        print(f"  h={res['h']} trades={res['n_trades']} "
              f"total_r={fc['total_r']:+.2f} maxdd_r={fc['max_drawdown_r']:+.2f} "
              f"cap_ok={fc['within_cap']} dsr={ra['dsr']:.3f} "
              f"beats_rung0={v['beats_rung0']} clears_gate={v['clears_gate']}")


def rung2(out_path: str, cache_dir: str, n_folds: int,
          horizons: list[int], rung0_path: str | None = None,
          rung1_path: str | None = None, open_lockbox: bool = False,
          readers=None, pool_symbols=None) -> None:
    import time

    from moonface.research.pathsig.baseline import POOL_SYMBOLS
    from moonface.research.pathsig.rung2 import run_rung2_to_doc

    rung0_doc = (json.loads(Path(rung0_path).read_text())
                 if rung0_path and Path(rung0_path).exists() else None)
    rung1_doc = (json.loads(Path(rung1_path).read_text())
                 if rung1_path and Path(rung1_path).exists() else None)
    if readers is None:
        from moonface.research.multifamily_loader import default_readers
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - int(3 * 365 * 86_400_000)
        readers = default_readers(cache_dir, start_ms, end_ms)
    doc = run_rung2_to_doc(readers, n_folds=n_folds, horizons=horizons,
                           pool_symbols=pool_symbols or POOL_SYMBOLS,
                           rung0_doc=rung0_doc, rung1_doc=rung1_doc)
    Path(out_path).write_text(json.dumps(doc, indent=2))
    print(f"wrote {out_path}")
    for res, v in zip(doc["rung2"], doc["verdict"]):
        if res["status"] != "ok":
            print(f"  h={res['h']} {res['status']}")
            continue
        fc, ra = res["fixed_cap"], res["risk_adjusted"]
        print(f"  h={res['h']} trades={res['n_trades']} "
              f"total_r={fc['total_r']:+.2f} maxdd_r={fc['max_drawdown_r']:+.2f} "
              f"cap_ok={fc['within_cap']} dsr={ra['dsr']:.3f} "
              f"beats_rung0={v['beats_rung0']} beats_rung1={v['beats_rung1']} "
              f"clears_gate={v['clears_gate']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    reg = sub.add_parser("register", help="freeze the design")
    reg.add_argument("--out", default="experiments/path_signal/registration.json")
    bl = sub.add_parser("baseline", help="run the rung-0 signal replay")
    bl.add_argument("--out", default="experiments/path_signal/rung0_baseline.json")
    bl.add_argument("--cache-dir", default=".backtest_cache")
    bl.add_argument("--n-folds", type=int, default=5)
    bl.add_argument("--horizons", type=int, nargs="+", default=[6, 12])
    en = sub.add_parser("ensemble", help="run the rung-1 regime ensemble")
    en.add_argument("--out", default="experiments/path_signal/rung1_ensemble.json")
    en.add_argument("--rung0", default="experiments/path_signal/rung0_baseline.json")
    en.add_argument("--cache-dir", default=".backtest_cache")
    en.add_argument("--n-folds", type=int, default=5)
    en.add_argument("--horizons", type=int, nargs="+", default=[6, 12])
    r2 = sub.add_parser("rung2", help="run the rung-2 distributional forest")
    r2.add_argument("--out", default="experiments/path_signal/rung2_forest.json")
    r2.add_argument("--rung0", default="experiments/path_signal/rung0_baseline.json")
    r2.add_argument("--rung1", default="experiments/path_signal/rung1_ensemble.json")
    r2.add_argument("--cache-dir", default=".backtest_cache")
    r2.add_argument("--n-folds", type=int, default=5)
    r2.add_argument("--horizons", type=int, nargs="+", default=[6, 12])
    args = parser.parse_args(argv)
    if args.cmd == "register":
        register(args.out)
        return 0
    if args.cmd == "baseline":
        baseline(args.out, args.cache_dir, args.n_folds, args.horizons)
        return 0
    if args.cmd == "ensemble":
        ensemble(args.out, args.cache_dir, args.n_folds, args.horizons,
                 rung0_path=args.rung0)
        return 0
    if args.cmd == "rung2":
        rung2(args.out, args.cache_dir, args.n_folds, args.horizons,
              rung0_path=args.rung0, rung1_path=args.rung1)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
