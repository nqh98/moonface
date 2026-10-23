#!/usr/bin/env python3
"""SMC failure decomposition CLI (research-only).

Runs the five decomposition variants from moonface.research.edge.smc_variants on
cached BTC candles, scores each exit-free via drift_screen path stats + a
single-asset bootstrap CI, slices events by regime, and writes a JSON results
doc + markdown report. No promotion, no edge claim, no live path."""
from __future__ import annotations

import argparse  # noqa: F401  (used by cmd_run/main, added in Task 6)
import json  # noqa: F401  (used by cmd_run/render_report, added in Task 6)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.core.models import Candle  # noqa: E402
from moonface.core.risk import atr  # noqa: E402
from moonface.research.drift_screen import event_outcome  # noqa: E402
from moonface.research.edge._smc import classify_structure  # noqa: E402
from moonface.features.oi_features import (  # noqa: E402
    asset_stats, binom_p_geq, nonoverlap)
from moonface.kernel.power_harness import (  # noqa: E402
    bootstrap_expectancy, one_sided_lower)
from moonface.research.edge.smc_variants import (  # noqa: E402
    choch_only, flip, full_reversal, structure_bias, sweep_only)
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

BAR4_MS = 4 * 3_600_000


def aggregate_4h(candles_1h: list[Candle]) -> list[Candle]:
    """Roll 1h candles up to 4h candles aligned to 4h UTC boundaries. open of the
    first bar in a bucket, max high, min low, close of the last bar, summed
    volume. Buckets with gaps keep whatever bars exist (best-effort)."""
    buckets: dict[int, list[Candle]] = {}
    for c in candles_1h:
        buckets.setdefault(c.timestamp_ms // BAR4_MS, []).append(c)
    out: list[Candle] = []
    for key in sorted(buckets):
        grp = buckets[key]
        out.append(Candle(
            timestamp_ms=key * BAR4_MS,
            open=grp[0].open,
            high=max(g.high for g in grp),
            low=min(g.low for g in grp),
            close=grp[-1].close,
            volume=sum(g.volume for g in grp),
        ))
    return out


HORIZONS = (6, 12, 18, 30)
REF_HORIZON = 12          # event records + declump horizon for conditioning
_ATR_PERIOD = 14
_N_PERIODS = 5
_WINDOW_CAP = 100
_BOOTSTRAP_N = 20_000
_BOOTSTRAP_SEED = 20260630


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _atr_terciles(candles: list[Candle], indices: list[int]) -> dict[int, str]:
    """Label each event bar's ATR as low/mid/high against the tercile cutpoints of
    the events' own ATR distribution (empty -> all 'mid')."""
    vals = []
    for i in indices:
        w = candles[max(0, i + 1 - _WINDOW_CAP): i + 1]
        a = atr(w, _ATR_PERIOD)
        vals.append((i, a))
    sorted_a = sorted(a for _, a in vals if a > 0)
    lo_cut = sorted_a[len(sorted_a) // 3] if sorted_a else 0.0
    hi_cut = sorted_a[2 * len(sorted_a) // 3] if sorted_a else 0.0
    labels: dict[int, str] = {}
    for i, a in vals:
        labels[i] = ("low" if a <= lo_cut else "high" if a >= hi_cut else "mid")
    return labels


def _event_records(candles: list[Candle], events: list[tuple[int, str]],
                   terciles: dict[int, str]) -> list[dict]:
    recs: list[dict] = []
    for i, side in events:
        out = event_outcome(candles, i, side, REF_HORIZON, _ATR_PERIOD)
        if out is None:
            continue
        ret_r, mae_r, mfe_r = out
        w = candles[max(0, i + 1 - _WINDOW_CAP): i + 1]
        recs.append({
            "ts": candles[i].timestamp_ms,
            "side": side,
            "h": REF_HORIZON,
            "ret_r": ret_r,
            "mae_r": mae_r,
            "mfe_r": mfe_r,
            "structure": classify_structure(w, _N_PERIODS).trend,
            "atr_tercile": terciles.get(i, "mid"),
        })
    return recs


def score_variant(candles: list[Candle], generator, params: dict,
                  horizons: tuple[int, ...] = HORIZONS) -> dict:
    """Exit-free per-horizon path stats + bootstrap CI for one variant, plus
    per-event regime records at REF_HORIZON. Events are declumped once at
    REF_HORIZON (nonoverlap) so all horizons share the same trade set."""
    events = nonoverlap(generator(candles, params), REF_HORIZON)
    terciles = _atr_terciles(candles, [i for i, _ in events])
    per_h: dict[int, dict] = {}
    for h in horizons:
        rets: list[float] = []
        maes: list[float] = []
        mfes: list[float] = []
        for i, side in events:
            out = event_outcome(candles, i, side, h, _ATR_PERIOD)
            if out is None:
                continue
            r, mae, mfe = out
            rets.append(r)
            maes.append(abs(mae))
            mfes.append(mfe)
        st = asset_stats(rets)
        n = st["n"]
        means, _ = bootstrap_expectancy(rets, n_resamples=_BOOTSTRAP_N,
                                        seed=_BOOTSTRAP_SEED)
        k_pos = sum(1 for r in rets if r > 0)
        per_h[h] = {
            "n": n,
            "win_rate": k_pos / n if n else 0.0,
            "mean_ret_r": st["mean"],
            "t": st["t"],
            "sign_p": binom_p_geq(k_pos, n) if n else None,
            "mean_mae_r": _mean(maes),
            "mean_mfe_r": _mean(mfes),
            "ci_lo": one_sided_lower(means, 0.025),
            "ci_hi": one_sided_lower(means, 0.975),
        }
    return {"params": params, "horizons": per_h,
            "events": _event_records(candles, events, terciles)}


def _agg(records: list[dict]) -> dict:
    n = len(records)
    if not n:
        return {"n": 0, "win_rate": 0.0, "mean_ret_r": 0.0, "mean_mae_r": 0.0}
    return {
        "n": n,
        "win_rate": sum(1 for r in records if r["ret_r"] > 0) / n,
        "mean_ret_r": _mean([r["ret_r"] for r in records]),
        "mean_mae_r": _mean([abs(r["mae_r"]) for r in records]),
    }


def slice_events(records: list[dict]) -> dict:
    """Conditional decomposition: aggregate per-event records by structure-trend,
    side, ATR tercile, and a first/second-half time split. Answers whether any
    sub-slice carries drift the aggregate drowns."""
    out: dict[str, dict] = {}
    for key in ("structure", "side", "atr_tercile"):
        groups: dict[str, list[dict]] = {}
        for r in records:
            groups.setdefault(r[key], []).append(r)
        out[key] = {g: _agg(rs) for g, rs in groups.items()}
    ordered = sorted(records, key=lambda r: r["ts"])
    mid = len(ordered) // 2
    out["half"] = {"first": _agg(ordered[:mid]), "second": _agg(ordered[mid:])}
    return out


GRID: dict[str, tuple[list[dict], object]] = {
    "full_reversal": ([{"lookback": 10}, {"lookback": 30}], full_reversal),
    "flip": ([{"lookback": 10}, {"lookback": 30}], flip),
    "sweep_only": ([{"lookback": 10}, {"lookback": 30}], sweep_only),
    "choch_only": ([{}], choch_only),
    "structure_bias": ([{"n_periods": 5}], structure_bias),
}


def _load_candles(args) -> list[Candle]:
    if args.tf == "4h" and args.from_1h:
        base = fetch_perp_candles(args.symbol, "1h", args.start_ms,
                                  args.end_ms, args.cache_dir)
        return aggregate_4h(base)
    return fetch_perp_candles(args.symbol, args.tf, args.start_ms,
                              args.end_ms, args.cache_dir)


def cmd_run(args) -> dict:
    candles = _load_candles(args)
    variants: dict[str, list[dict]] = {}
    for name, (param_grid, gen) in GRID.items():
        variants[name] = [score_variant(candles, gen, params)
                          for params in param_grid]
    doc = {
        "symbol": args.symbol, "tf": args.tf,
        "start_ms": args.start_ms, "end_ms": args.end_ms,
        "n_bars": len(candles), "variants": variants,
        "slices": {name: [{**{"params": r["params"]}, "slices": slice_events(r["events"])}
                          for r in rows]
                   for name, rows in variants.items()},
    }
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"results_{args.tf}.json").write_text(json.dumps(doc, indent=2))
    return doc


def print_table(doc: dict) -> None:
    print(f"\n== {doc['symbol']} {doc['tf']}  bars={doc['n_bars']} ==")
    hdr = f"{'variant':<16}{'lb':<4}{'h':<4}{'n':<6}{'win':<7}{'ret_r':<8}{'ci95':<18}"
    print(hdr)
    for name, rows in doc["variants"].items():
        for row in rows:
            lb = (row["params"].get("lookback")
                  or row["params"].get("n_periods"))
            for h, b in row["horizons"].items():
                print(f"{name:<16}{str(lb):<4}{h:<4}{b['n']:<6}"
                      f"{b['win_rate']:<7.2f}{b['mean_ret_r']:<8.3f}"
                      f"[{b['ci_lo']:.3f},{b['ci_hi']:.3f}]  ")


def render_report(docs: dict) -> str:
    """Markdown report from {out_dir: doc} mappings. RESEARCH-ONLY banner;
    per-variant horizon table + the headline conditional slices. No PASS/FAIL."""
    lines = [
        "# SMC failure decomposition — RESEARCH-ONLY", "",
        "> Diagnostic, not a strategy. No edge is claimed; the WAIT stance and",
        "> `docs/findings/PROGRAM_CONCLUSION.md` are unchanged. Single-asset BTC",
        "> mechanism check (within-BTC sign test + bootstrap 95% CI on mean_ret_r),",
        "> not a promotion gate.", "",
    ]
    for _out_dir, doc in docs.items():
        lines += [f"## {doc['symbol']} {doc['tf']}  (bars={doc['n_bars']})", "",
                  "| variant | params | h | n | win_rate | mean_ret_r | ci95 |",
                  "|---|---|---|---|---|---|---|"]
        for name, rows in doc["variants"].items():
            for row in rows:
                p = json.dumps(row["params"], sort_keys=True)
                for h, b in row["horizons"].items():
                    lines.append(
                        f"| {name} | {p} | {h} | {b['n']} | {b['win_rate']:.2f} "
                        f"| {b['mean_ret_r']:.3f} "
                        f"| [{b['ci_lo']:.3f}, {b['ci_hi']:.3f}] |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", default="BTC/USDT:USDT")
    p.add_argument("--tf", choices=["1h", "4h", "both"], default="both")
    p.add_argument("--start-ms", type=int, default=1_577_836_800_000)  # 2020-01-01
    p.add_argument("--end-ms", type=int, default=2_000_000_000_000)    # all cached
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--out-dir", default="experiments/smc_decompose")
    p.add_argument("--from-1h", action="store_true", default=True,
                   help="derive 4h from the 1h cache (default on)")
    args = p.parse_args(argv)
    tfs = ["1h", "4h"] if args.tf == "both" else [args.tf]
    docs: dict[str, dict] = {}
    for tf in tfs:
        args.tf = tf
        doc = cmd_run(args)
        print_table(doc)
        docs[str(Path(args.out_dir) / f"results_{tf}.json")] = doc
    report = render_report(docs)
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    (Path(args.out_dir) / "REPORT.md").write_text(report)


if __name__ == "__main__":
    main()

