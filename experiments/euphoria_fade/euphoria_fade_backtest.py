#!/usr/bin/env python
"""euphoria_fade v1 — pre-registered SHORT fade of UP/HIGH/CROWDED_LONG.

Frozen registration: PREREGISTRATION.md (2026-07-10). Origin: the sole
replicated microscope texture, itself flagged within-null — the prior is
LOW and the lane is built to fail cleanly. Contamination cap: best possible
outcome is FORWARD PAPER registration, never live."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from moonface.foundation.metrics import (_kurtosis, _sharpe, _skew,
                                         deflated_sharpe)
from moonface.foundation.risk import atr
from moonface.research.microscope.factors import state_vectors
from moonface.research.microscope.features import build_matrix
from moonface.research.microscope.regimes import UNLABELED, label_series

# ---- frozen registration constants (PREREGISTRATION.md — do not tune) ----
CELL = "UP/HIGH/CROWDED_LONG"
CONTROL_PREFIX = "UP/HIGH/"        # control = crowding gate removed
PERSISTENCE = (1, 2)               # the 2 treatment cells; n_trials = 2
K_STOP = 2.0
M_TP = 1.0
ATR_PERIOD = 14
COST = 0.0006                      # all-in round-trip, fraction of notional
FRACTION = 0.01
N_TRIALS = 2
NULL_DRAWS = 200
NULL_PASS_MAX = 0.05
POWER_SCREEN = 30
POWER_LOCKBOX = 20
DD_FLOOR = -0.30
DSR_GATE = 0.95


def _ms(day: str) -> int:
    d = dt.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp() * 1000)


WINDOWS = {"IS": (_ms("2020-01-01"), _ms("2024-01-01")),
           "OOS": (_ms("2024-01-01"), _ms("2025-07-01")),
           "LOCKBOX": (_ms("2025-07-01"), _ms("2026-07-01"))}


def gen_entries(in_cell: list[bool], p: int) -> list[int]:
    """Indices i where bars i-p+1..i are all in-cell and bar i-p is not —
    the transition completes exactly p bars of persistence. One signal per
    label episode by construction. A series that *starts* in-cell never
    fires (no observable transition)."""
    return [i for i in range(p, len(in_cell))
            if all(in_cell[i - q] for q in range(p)) and not in_cell[i - p]]


@dataclass(frozen=True)
class Trade:
    symbol: str
    signal_ts: int
    entry_ts: int
    entry: float
    risk: float          # price distance worth 1R (= K_STOP * ATR)
    r_gross: float
    r_net: float
    outcome: str         # "tp" | "stop" | "eod"


def simulate_symbol(symbol: str, candles, signal_idxs: list[int]) -> list[Trade]:
    """SHORT at next-bar open with a frozen ATR bracket. Stop is checked
    before TP within a bar (conservative for a short). One position at a
    time: signals whose fill bar falls on or before the previous trade's
    resolution bar are dropped."""
    trades: list[Trade] = []
    busy_until = -1
    for i in sorted(signal_idxs):
        if i + 1 >= len(candles) or i + 1 <= busy_until:
            continue
        a = atr(candles[: i + 1], ATR_PERIOD)
        if a <= 0.0:
            continue
        entry_bar = candles[i + 1]
        entry = entry_bar.open
        risk = K_STOP * a
        stop = entry + risk
        tp = entry - M_TP * a
        cost_r = COST * entry / risk
        outcome = "eod"
        r_gross = None
        j = i + 1
        for j in range(i + 1, len(candles)):
            bar = candles[j]
            if bar.high >= stop:
                outcome, r_gross = "stop", -1.0
                break
            if bar.low <= tp:
                outcome, r_gross = "tp", M_TP / K_STOP
                break
        if r_gross is None:
            r_gross = (entry - candles[-1].close) / risk
            j = len(candles) - 1
        busy_until = j
        trades.append(Trade(symbol, candles[i].timestamp_ms,
                            entry_bar.timestamp_ms, entry, risk,
                            round(r_gross, 6), round(r_gross - cost_r, 6),
                            outcome))
    return trades


def expectancy(rs: list[float]) -> float:
    return sum(rs) / len(rs) if rs else 0.0


def equity_stats(rs: list[float], f: float = FRACTION) -> tuple[float, float]:
    """(total_return, max_drawdown) of the compounding f-fraction curve."""
    eq, peak, max_dd = 1.0, 1.0, 0.0
    for r in rs:
        eq *= 1.0 + f * r
        peak = max(peak, eq)
        max_dd = min(max_dd, eq / peak - 1.0)
    return eq - 1.0, max_dd


def mar(rs: list[float], f: float = FRACTION) -> float:
    total, dd = equity_stats(rs, f)
    if dd == 0.0:
        return float("inf") if total > 0.0 else 0.0
    return total / abs(dd)


def dsr_of(rs: list[float], trial_srs: list[float]) -> float:
    if len(rs) < 2:
        return 0.0
    return deflated_sharpe(_sharpe(rs), len(rs), _skew(rs), _kurtosis(rs),
                           trial_srs, N_TRIALS)


def partition(trades: list[Trade]) -> dict[str, list[Trade]]:
    out: dict[str, list[Trade]] = {w: [] for w in WINDOWS}
    for t in trades:
        for w, (lo, hi) in WINDOWS.items():
            if lo <= t.entry_ts < hi:
                out[w].append(t)
    return out


def null_gate(is_rs: list[float], oos_rs: list[float]) -> bool:
    """Stage-1+2 numeric gates plus pooled DSR, applied to a null draw.
    A valid gate must FAIL on nulls at ~nominal rate (vol_compression
    gotcha); pass-rate is compared against NULL_PASS_MAX upstream."""
    if len(is_rs) < POWER_SCREEN or expectancy(is_rs) <= 0.0:
        return False
    _, dd = equity_stats(oos_rs)
    if (expectancy(oos_rs) <= 0.0 or mar(oos_rs) <= 0.0 or dd < DD_FLOOR):
        return False
    pooled = is_rs + oos_rs
    return dsr_of(pooled, [_sharpe(pooled)]) >= DSR_GATE


def run_null(candles_by_sym, cmaps, ts, elig, counts, seed,
             n_draws: int = NULL_DRAWS) -> dict:
    """Count-matched random-entry null through the frozen pipeline."""
    rng = random.Random(seed)
    exps: list[float] = []
    passes = 0
    for _ in range(n_draws):
        trades: list[Trade] = []
        for sym, by_win in counts.items():
            sig_axis: list[int] = []
            for w in ("IS", "OOS"):
                pool_i = elig[sym][w]
                n = min(by_win.get(w, 0), len(pool_i))
                if n:
                    sig_axis.extend(rng.sample(pool_i, n))
            if not sig_axis:
                continue
            sig = sorted(cmaps[sym][ts[i]] for i in sig_axis)
            trades.extend(simulate_symbol(sym, candles_by_sym[sym], sig))
        part = partition(trades)
        is_rs = [t.r_net for t in part["IS"]]
        oos_rs = [t.r_net for t in part["OOS"]]
        exps.append(expectancy(is_rs + oos_rs))
        if null_gate(is_rs, oos_rs):
            passes += 1
    return {"exps": exps,
            "pass_rate": passes / n_draws if n_draws else 0.0}


def stage1(is_rs: list[float]) -> bool:
    return len(is_rs) >= POWER_SCREEN and expectancy(is_rs) > 0.0


def stage2(oos_rs: list[float], ctrl_oos_rs: list[float]) -> bool:
    _, dd = equity_stats(oos_rs)
    return (expectancy(oos_rs) > 0.0 and mar(oos_rs) > 0.0
            and dd >= DD_FLOOR
            and expectancy(oos_rs) > expectancy(ctrl_oos_rs))


def stage3(pooled_rs: list[float], trial_srs: list[float]) -> bool:
    return dsr_of(pooled_rs, trial_srs) >= DSR_GATE


def stage4(real_exp: float, null_exps: list[float],
           null_pass_rate: float) -> bool:
    if not null_exps:
        return False
    p95 = sorted(null_exps)[min(len(null_exps) - 1,
                                int(0.95 * len(null_exps)))]
    return real_exp > p95 and null_pass_rate <= NULL_PASS_MAX


def stage5(lb_rs: list[float], ctrl_lb_rs: list[float]) -> bool:
    _, dd = equity_stats(lb_rs)
    return (len(lb_rs) >= POWER_LOCKBOX and expectancy(lb_rs) > 0.0
            and dd >= DD_FLOOR
            and expectancy(lb_rs) > expectancy(ctrl_lb_rs))


def assemble_verdict(cells: dict, nulls: dict) -> dict:
    """Stages 1-4 for both persistence cells. Never reads LOCKBOX lists —
    the lockbox is one-touch and opened only by run_lockbox()."""
    pooled = {p: cells[p]["treat"]["IS"] + cells[p]["treat"]["OOS"]
              for p in PERSISTENCE}
    trial_srs = [_sharpe(pooled[p]) for p in PERSISTENCE]
    out: dict = {"cells": {}, "verdict": "CLOSED_NEGATIVE"}
    pending: list[int] = []
    for p in PERSISTENCE:
        t, c = cells[p]["treat"], cells[p]["ctrl"]
        s = {"stage1": stage1(t["IS"]),
             "stage2": stage2(t["OOS"], c["OOS"]),
             "stage3": stage3(pooled[p], trial_srs),
             "stage4": stage4(expectancy(pooled[p]), nulls[p]["exps"],
                              nulls[p]["pass_rate"]),
             "dsr": round(dsr_of(pooled[p], trial_srs), 4),
             "n_is": len(t["IS"]), "n_oos": len(t["OOS"]),
             "exp_is": round(expectancy(t["IS"]), 4),
             "exp_oos": round(expectancy(t["OOS"]), 4),
             "exp_ctrl_oos": round(expectancy(c["OOS"]), 4),
             "null_pass_rate": nulls[p]["pass_rate"]}
        s["pass_1_4"] = all(s[f"stage{k}"] for k in (1, 2, 3, 4))
        out["cells"][p] = s
        if s["pass_1_4"]:
            pending.append(p)
    if any(nulls[p]["pass_rate"] > NULL_PASS_MAX for p in PERSISTENCE):
        out["verdict"] = "GATE_VOID_NULL_PASSES"
    elif pending:
        out["verdict"] = "PENDING_LOCKBOX"
        out["pending_cells"] = pending
    return out


def _pf(flag: bool) -> str:
    return "PASS" if flag else "FAIL"


def render_report(verdict: dict) -> str:
    lines = [
        "# euphoria_fade v1 — run report (stages 1-4; lockbox SEALED)",
        "",
        "Registered: PREREGISTRATION.md (frozen 2026-07-10). Best possible",
        "outcome is FORWARD PAPER registration (contamination cap).",
        "",
        f"Verdict: **{verdict['verdict']}**",
        "",
        "| cell | n_IS | exp_IS | n_OOS | exp_OOS | exp_ctrl_OOS | DSR "
        "| null pass-rate | s1 | s2 | s3 | s4 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for p, s in verdict["cells"].items():
        lines.append(
            f"| p={p} | {s['n_is']} | {s['exp_is']:+.4f} | {s['n_oos']} "
            f"| {s['exp_oos']:+.4f} | {s['exp_ctrl_oos']:+.4f} "
            f"| {s['dsr']:.3f} | {s['null_pass_rate']:.3f} "
            f"| {_pf(s['stage1'])} | {_pf(s['stage2'])} "
            f"| {_pf(s['stage3'])} | {_pf(s['stage4'])} |")
    lines += ["",
              "Lockbox is one-touch: `lockbox` subcommand, only when a cell",
              "passes stages 1-4. Kill rule on any failure: family terminal."]
    return "\n".join(lines) + "\n"


def build_labels(pool):
    matrix = build_matrix(pool)
    return matrix, label_series(state_vectors(matrix))


def execute_run(pool, seed: int = 1,
                out_dir: Path = Path("experiments/euphoria_fade")) -> dict:
    matrix, labels = build_labels(pool)
    ts = matrix.timestamps
    cmaps = {sym: {c.timestamp_ms: k
                   for k, c in enumerate(pool[sym].candles)}
             for sym in matrix.symbols if pool[sym].candles}
    if len(cmaps) < 8:
        raise SystemExit(f"pool collapsed to {len(cmaps)} assets with "
                         "candles — pre-warm cache/matrix first "
                         "(microscope run-gotcha #1)")
    elig = {sym: {w: [i for i in range(len(labels[sym]))
                      if labels[sym][i] != UNLABELED
                      and lo <= ts[i] < hi and ts[i] in cmaps[sym]]
                  for w, (lo, hi) in WINDOWS.items()}
            for sym in cmaps}
    cells: dict = {}
    counts: dict = {}
    for p in PERSISTENCE:
        raw = {"treat": [], "ctrl": []}
        for sym in cmaps:
            labs = labels[sym]
            flag_sets = {
                "treat": [lab == CELL for lab in labs],
                "ctrl": [lab != UNLABELED and lab.startswith(CONTROL_PREFIX)
                         for lab in labs],
            }
            for name, flags in flag_sets.items():
                sig = sorted(cmaps[sym][ts[i]]
                             for i in gen_entries(flags, p)
                             if ts[i] in cmaps[sym])
                raw[name].extend(
                    simulate_symbol(sym, pool[sym].candles, sig))
        part = {name: partition(raw[name]) for name in raw}
        counts[p] = {sym: {"IS": 0, "OOS": 0} for sym in cmaps}
        for w in ("IS", "OOS"):
            for t in part["treat"][w]:
                counts[p][t.symbol][w] += 1
        cells[p] = {name: {w: [t.r_net for t in part[name][w]]
                           for w in WINDOWS} for name in raw}
    candles_by_sym = {sym: pool[sym].candles for sym in cmaps}
    nulls = {p: run_null(candles_by_sym, cmaps, ts, elig, counts[p],
                         seed + p) for p in PERSISTENCE}
    verdict = assemble_verdict(cells, nulls)
    out_dir.mkdir(parents=True, exist_ok=True)
    sealed = {str(p): {name: cells[p][name]["LOCKBOX"]
                       for name in ("treat", "ctrl")} for p in PERSISTENCE}
    (out_dir / "lockbox_trades.json").write_text(json.dumps(sealed))
    (out_dir / "run_verdict.json").write_text(json.dumps(
        {"verdict": verdict["verdict"],
         "pending_cells": verdict.get("pending_cells", []),
         "cells": verdict["cells"], "seed": seed}, indent=2))
    (out_dir / "run_report.md").write_text(render_report(verdict))
    return verdict


def load_pool_skip_bookdepth(cache_dir: str, start: str, end: str):
    """Microscope pool with bookdepth stubbed out (unused by build_matrix;
    fetching it wastes ~20 min/asset — microscope run-gotcha #2)."""
    from moonface.research.multifamily_loader import (default_readers,
                                                      load_pool_bundles)
    from tools.microscope import OI_FIELD, UNIVERSE
    readers = default_readers(cache_dir, _ms(start), _ms(end))
    return load_pool_bundles(UNIVERSE, OI_FIELD, readers["candles"],
                             readers["funding"], readers["metrics"],
                             lambda s: None)


def run_lockbox(out_dir: Path, ack: bool) -> str:
    """One-touch lockbox evaluation (stage 5). Registered discipline:
    opened once, only after stages 1-4 pass, never re-run."""
    result_path = out_dir / "lockbox_result.json"
    if result_path.exists():
        return "REFUSED: lockbox already opened (one-touch)."
    if not ack:
        return "REFUSED: pass --i-understand-one-touch to open the lockbox."
    verdict = json.loads((out_dir / "run_verdict.json").read_text())
    pending = verdict.get("pending_cells", [])
    if verdict.get("verdict") != "PENDING_LOCKBOX" or not pending:
        return "REFUSED: no cell passed stages 1-4; lockbox stays sealed."
    sealed = json.loads((out_dir / "lockbox_trades.json").read_text())
    out: dict = {}
    passed_any = False
    for p in pending:
        t = sealed[str(p)]["treat"]
        c = sealed[str(p)]["ctrl"]
        ok = stage5(t, c)
        _, dd = equity_stats(t)
        out[str(p)] = {"stage5": ok, "n": len(t),
                       "exp": round(expectancy(t), 4),
                       "exp_ctrl": round(expectancy(c), 4),
                       "max_dd": round(dd, 4)}
        passed_any = passed_any or ok
    out["final_verdict"] = ("FORWARD_PAPER_REGISTERED" if passed_any
                            else "CLOSED_NEGATIVE")
    result_path.write_text(json.dumps(out, indent=2))
    return json.dumps(out, indent=2)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="euphoria_fade", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--cache-dir", default="cache/matrix")
    r.add_argument("--start", default="2020-01-01")
    r.add_argument("--end", default="2026-07-01")
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--out", default="experiments/euphoria_fade")
    lb = sub.add_parser("lockbox")
    lb.add_argument("--out", default="experiments/euphoria_fade")
    lb.add_argument("--i-understand-one-touch", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "run":
        pool = load_pool_skip_bookdepth(args.cache_dir, args.start, args.end)
        verdict = execute_run(pool, seed=args.seed, out_dir=Path(args.out))
        print(render_report(verdict))
    else:
        print(run_lockbox(Path(args.out), args.i_understand_one_touch))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
