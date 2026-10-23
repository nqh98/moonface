#!/usr/bin/env python
# tools/research.py
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moonface.data.bundle import load_bundle
from moonface.research.domains import (register_v1, reconcile_new_families,
                                       reregister_domain)
from moonface.research.funding_fade_ref import (BTC_REF_ASSET, btc_reference,
                                                format_reference)
from moonface.kernel.report import write_domain_report
from moonface.research.orderflow_runner import (ORDERFLOW_DOMAIN,
                                                register as register_orderflow,
                                                run_domain as run_orderflow)
from moonface.research.forced_error_runner import (
    FORCED_ERROR_DOMAIN, register as register_forced_error,
    run_domain as run_forced_error)
from moonface.research.price_oi_divergence_runner import (
    DIVERGENCE_DOMAIN, register as register_divergence,
    run_domain as run_divergence)
from moonface.research.universe_donchian_runner import (
    UNIVERSE_DONCHIAN_DOMAIN, register as register_universe_donchian,
    run_domain as run_universe_donchian)
from moonface.research.voltarget_runner import (VOLTARGET_DOMAIN,
                                                register as register_voltarget,
                                                run_domain as run_voltarget)
from moonface.core.provenance import code_hash, data_fingerprint, registration_hash
from moonface.kernel.reproduce import reproduce
from moonface.kernel.runner import run
from moonface.kernel.store import Store
from tools.lane_registry import LANES


def _store(args: argparse.Namespace) -> Store:
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    return Store(args.db)


def cmd_init(args: argparse.Namespace) -> None:
    store = _store(args)
    names = register_v1(store, int(time.time() * 1000))
    reconciled = reconcile_new_families(store)
    print(f"registered: {', '.join(names)}" if names
          else "all v1 domains already registered")
    if reconciled:
        print(f"reconciled: {', '.join(reconciled)}")


def cmd_run(args: argparse.Namespace) -> None:
    def loader(asset: dict, start_ms: int, end_ms: int):
        return load_bundle(asset, start_ms, end_ms, args.cache_dir)

    b = run(_store(args), loader, out_root=Path(args.out_root),
            budget=args.budget, only_domain=args.domain)
    print(f"[{b.kind}] {b.domain or '-'}: {b.message}")


def cmd_status(args: argparse.Namespace) -> None:
    store = _store(args)
    domains = store.domains_in_order()
    if not domains:
        print("no domains registered; run `python tools/research.py init`")
        return
    for d in domains:
        counts = store.counts(d["name"], d["version"])
        funnel = " ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        print(f"{d['name']} v{d['version']} [{d['status']}]"
              f" grid={d['grid_size']} lockbox_touched={d['lockbox_touched']}"
              f" {funnel}")


def cmd_report(args: argparse.Namespace) -> None:
    path = write_domain_report(_store(args), args.domain, args.version,
                               Path(args.out_root))
    print(f"report written to {path}")


def cmd_gate(args: argparse.Namespace) -> None:
    store = _store(args)
    d = store.domain(args.domain, args.version)
    if d is None:
        sys.exit(f"unknown domain {args.domain} v{args.version}")
    if not args.open_lockbox:
        sys.exit("nothing to do: pass --open-lockbox to spend the one-touch tail")
    if d["status"] != "awaiting_gate":
        sys.exit(f"{args.domain} is '{d['status']}', not awaiting_gate")
    survivors = store.counts(args.domain, args.version).get("corrected_survivor", 0)
    if survivors == 0:
        sys.exit(f"refusing: {args.domain} v{args.version} has no corrected"
                 " survivors — this awaiting_gate came from the error boundary;"
                 " opening the lockbox would spend the one-touch tail on"
                 " nothing. Fix the errored rows (or reregister) first.")
    store.set_domain_status(args.domain, args.version, "lockbox_open")
    print(f"{args.domain} v{args.version}: lockbox OPEN — the next `run`"
          " spends the one-touch tail")


def cmd_reregister(args: argparse.Namespace) -> None:
    store = _store(args)
    try:
        new_version = reregister_domain(store, args.domain, args.from_version)
    except ValueError as exc:
        sys.exit(str(exc))
    print(f"{args.domain} v{new_version}: registered active with"
          f" v{args.from_version}'s frozen grid, window, and fence")


def cmd_retry_errors(args: argparse.Namespace) -> None:
    """Reset bug/network-errored rows to pending and reactivate the domain.
    Errored rows never produced a result, so re-running them is not a
    second look at any data — unlike the lockbox, this is always safe."""
    store = _store(args)
    d = store.domain(args.domain, args.version)
    if d is None:
        sys.exit(f"unknown domain {args.domain} v{args.version}")
    if d["status"].startswith("closed"):
        sys.exit(f"{args.domain} v{args.version} is '{d['status']}'; closed"
                 " verdicts are never reopened — reregister a new version")
    n = store.reset_errors(args.domain, args.version)
    if n == 0:
        sys.exit(f"{args.domain} v{args.version} has no errored rows")
    store.set_domain_status(args.domain, args.version, "active")
    print(f"{args.domain} v{args.version}: {n} errored rows reset to pending;"
          " domain active")


def cmd_funding_ref(args: argparse.Namespace) -> None:
    """Print the BTC Q1 in-sample reference. Touches no store and no lockbox."""
    start_ms = int(time.time() * 1000) - int(3 * 365 * 86_400_000)
    end_ms = int(time.time() * 1000)
    bundle = load_bundle(BTC_REF_ASSET, start_ms, end_ms, args.cache_dir)
    print(format_reference(btc_reference(bundle)))


def cmd_voltarget(args: argparse.Namespace) -> None:
    """Register + run the funding_fade_voltarget domain and print the verdict.
    Drives its own paired ladder + walk-forward + one-touch lockbox."""
    store = _store(args)
    now_ms = int(time.time() * 1000)
    register_voltarget(store, now_ms)

    def loader(asset: dict, start_ms: int, end_ms: int):
        return load_bundle(asset, start_ms, end_ms, args.cache_dir)

    verdict = run_voltarget(store, loader, Path(args.out_root))
    print(f"{VOLTARGET_DOMAIN} v1: {verdict}")
    print(f"verdict: {Path(args.out_root) / VOLTARGET_DOMAIN / 'verdict.md'}")


def cmd_orderflow(args: argparse.Namespace) -> None:
    """Register + run the orderflow_microstructure domain and print the verdict.
    Drives its own entry-pair dominance ladder + walk-forward + one-touch
    lockbox against a donchian_break control."""
    store = _store(args)
    now_ms = int(time.time() * 1000)
    register_orderflow(store, now_ms)

    def loader(asset: dict, start_ms: int, end_ms: int):
        return load_bundle(asset, start_ms, end_ms, args.cache_dir)

    verdict = run_orderflow(store, loader, Path(args.out_root))
    print(f"{ORDERFLOW_DOMAIN} v1: {verdict}")
    print(f"verdict: {Path(args.out_root) / ORDERFLOW_DOMAIN / 'verdict.md'}")


def cmd_price_oi_divergence(args: argparse.Namespace) -> None:
    """Register + run the price_oi_divergence lane and print the verdict."""
    store = _store(args)
    now_ms = int(time.time() * 1000)
    register_divergence(store, now_ms)

    def loader(asset: dict, start_ms: int, end_ms: int):
        return load_bundle(asset, start_ms, end_ms, args.cache_dir)

    verdict = run_divergence(store, loader, Path(args.out_root))
    print(f"{DIVERGENCE_DOMAIN} v1: {verdict}")
    print(f"verdict: {Path(args.out_root) / DIVERGENCE_DOMAIN / 'verdict.md'}")


def cmd_forced_error(args: argparse.Namespace) -> None:
    """Register + run the forced_error lane and print the verdict."""
    store = _store(args)
    now_ms = int(time.time() * 1000)
    register_forced_error(store, now_ms)

    def loader(asset: dict, start_ms: int, end_ms: int):
        return load_bundle(asset, start_ms, end_ms, args.cache_dir)

    verdict = run_forced_error(store, loader, Path(args.out_root))
    print(f"{FORCED_ERROR_DOMAIN} v1: {verdict}")
    print(f"verdict: {Path(args.out_root) / FORCED_ERROR_DOMAIN / 'verdict.md'}")


def cmd_universe_donchian(args: argparse.Namespace) -> None:
    """Register + run the universe_donchian domain and print the verdict.
    Drives its own universe-expansion dominance ladder + walk-forward +
    one-touch lockbox."""
    store = _store(args)
    now_ms = int(time.time() * 1000)
    register_universe_donchian(store, now_ms)
    verdict = run_universe_donchian(store, args.cache_dir, Path(args.out_root))
    print(f"{UNIVERSE_DONCHIAN_DOMAIN} v1: {verdict}")
    print(f"verdict: {Path(args.out_root) / UNIVERSE_DONCHIAN_DOMAIN / 'verdict.md'}")


def _write_run_record(lane: str, result, verdict_path: Path, triple: dict,
                      kernel_runs_root: Path | None = None) -> Path:
    run_id = dt.datetime.now(dt.timezone.utc).isoformat(
        timespec="seconds").replace(":", "-")
    out_dir = kernel_runs_root or Path(f"experiments/{lane}/kernel_runs")
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "lane": lane,
        "run_id": run_id,
        "matched": result.matched,
        "mismatches": {k: list(v) for k, v in result.mismatches.items()},
        "compared_against": str(verdict_path),
        **triple,
    }
    path = out_dir / f"{run_id}.json"
    path.write_text(json.dumps(record, indent=2))
    return path


def _load_recorded(verdict_path: Path, verdict_filename: str) -> dict:
    """Load the recorded verdict. A list-shaped file (e.g. drift_screen's
    leaderboard.json -- a bare per-signal list, not a dict) is wrapped as
    {<filename stem>: [...]} so reproduce()'s field-by-field dict comparison
    has something to index into; a dict-shaped file passes through unchanged."""
    recorded = json.loads(verdict_path.read_text())
    if isinstance(recorded, list):
        return {Path(verdict_filename).stem: recorded}
    return recorded


def cmd_reproduce(args: argparse.Namespace) -> None:
    entry = LANES[args.lane]
    reg_path = Path(f"experiments/{args.lane}/registration.json")
    verdict_path = Path(f"experiments/{args.lane}/{entry.verdict_filename}")
    if not reg_path.exists() or not verdict_path.exists():
        sys.exit(f"missing {reg_path} or {verdict_path}")
    cfg = json.loads(reg_path.read_text())
    recorded = _load_recorded(verdict_path, entry.verdict_filename)

    series_by_key: dict = {}
    run_args = entry.run_args_builder(cfg, args.cache_dir, series_by_key)

    with TemporaryDirectory() as tmp:
        result = reproduce(entry.run_fn, cfg, recorded,
                           compare_fields=entry.compare_fields,
                           scratch_dir=Path(tmp), run_args=run_args)

    triple = {
        "registration_hash": registration_hash(cfg),
        "data_fingerprint": data_fingerprint(series_by_key),
        "code_hash": code_hash(list(entry.code_paths)),
    }
    record_path = _write_run_record(args.lane, result, verdict_path, triple)
    print(f"run record: {record_path}")

    if result.matched:
        print(f"REPRODUCED: {args.lane} -- every compared field matches"
              f" the recorded {entry.verdict_filename}")
    else:
        print(f"DID NOT REPRODUCE: {args.lane}")
        for field_name, (rec, new) in result.mismatches.items():
            print(f"  {field_name}: recorded={rec!r} recomputed={new!r}")
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="MoonFace autonomous research pipeline (signal discovery"
                    " and validation only; no live trading).")
    p.add_argument("--db", default="experiments/research/research.db")
    p.add_argument("--out-root", default="experiments/research")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="register v1 domains and build their grids"
                   ).set_defaults(fn=cmd_init)
    run_p = sub.add_parser("run", help="drain until a boundary or the budget")
    run_p.add_argument("--domain")
    run_p.add_argument("--budget", type=int)
    run_p.add_argument("--cache-dir", default=".backtest_cache")
    run_p.set_defaults(fn=cmd_run)
    sub.add_parser("status", help="per-domain funnel").set_defaults(fn=cmd_status)
    rep = sub.add_parser("report", help="(re)render a domain report")
    rep.add_argument("domain")
    rep.add_argument("--version", type=int, default=1)
    rep.set_defaults(fn=cmd_report)
    gate = sub.add_parser("gate", help="approve the one-touch lockbox run")
    gate.add_argument("domain")
    gate.add_argument("--version", type=int, default=1)
    gate.add_argument("--open-lockbox", action="store_true")
    gate.set_defaults(fn=cmd_gate)
    rer = sub.add_parser(
        "reregister",
        help="re-register a closed domain's frozen grid as the next version"
             " (only when its lockbox tail was never evaluated)")
    rer.add_argument("domain")
    rer.add_argument("--from-version", type=int, default=1)
    rer.set_defaults(fn=cmd_reregister)
    retry = sub.add_parser(
        "retry-errors",
        help="reset errored rows (bug/network, never a verdict) to pending"
             " and reactivate the domain")
    retry.add_argument("domain")
    retry.add_argument("--version", type=int, default=1)
    retry.set_defaults(fn=cmd_retry_errors)
    ref = sub.add_parser("funding-ref",
                         help="print the BTC funding_fade Q1 in-sample reference"
                              " (no store, no lockbox)")
    ref.add_argument("--cache-dir", default=".backtest_cache")
    ref.set_defaults(fn=cmd_funding_ref)
    vt = sub.add_parser("voltarget",
                        help="register + run funding_fade_voltarget (paired"
                             " vol-targeted vs fixed-fractional, ETH/SOL)")
    vt.add_argument("--cache-dir", default=".backtest_cache")
    vt.set_defaults(fn=cmd_voltarget)
    of = sub.add_parser("orderflow",
                        help="register + run orderflow_microstructure"
                             " (intraday order-flow vs donchian_break control,"
                             " BTC/USDT:USDT 15m)")
    of.add_argument("--cache-dir", default=".backtest_cache")
    of.set_defaults(fn=cmd_orderflow)
    div = sub.add_parser("price-oi-divergence",
                         help="run the price_oi_divergence lane")
    div.add_argument("--cache-dir", default=".backtest_cache")
    div.set_defaults(fn=cmd_price_oi_divergence)
    fe = sub.add_parser("forced-error",
                        help="register + run forced_error (Setup 1 failed-"
                             "breakout SHORT + Setup 2 failed-fade-squeeze"
                             " LONG, each vs isolation control, BTC/USDT:USDT"
                             " 1h)")
    fe.add_argument("--cache-dir", default=".backtest_cache")
    fe.set_defaults(fn=cmd_forced_error)
    ud = sub.add_parser("universe-donchian",
                        help="register + run universe_donchian (dynamic"
                             " alt-perp universe expansion vs static-basket"
                             " control)")
    ud.add_argument("--cache-dir", default=".backtest_cache")
    ud.set_defaults(fn=cmd_universe_donchian)
    rep2 = sub.add_parser("reproduce",
                          help="re-run a lane from its frozen registration.json"
                               " against a scratch dir and diff the recorded"
                               " verdict.json (the G3 reproduction gate)")
    rep2.add_argument("lane", choices=tuple(LANES))
    rep2.add_argument("--cache-dir", default=".backtest_cache")
    rep2.set_defaults(fn=cmd_reproduce)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
