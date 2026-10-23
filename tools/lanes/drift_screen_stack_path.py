#!/usr/bin/env python
# tools/drift_screen_stack_path.py
"""Stage-0 drawdown-aware drift screen for the stack_path strategy.

register: freeze the construction (stack_path params + the inherited design)
          BEFORE any run, and record its identity hash.
run     : screen stack_path over the frozen 16-asset fresh universe under the
          same path-aware gate every prior drift screen used; write the verdict.

Mechanism science only: ONE frozen construction, a single fixed primary
horizon, no exits/stops/TPs/grids/sweeps. The design (universe, h, atr_period,
floor, min_events, min_assets) is inherited VERBATIM from the already-frozen
experiments/drift_screen/registration.json so this lane introduces no new
degree of freedom. The multi-horizon curve is descriptive only, never a gate.

Kill rule (pre-committed): mechanism_does_not_exist => stack_path is closed at
stage 0. No parameter rescue, no v2, no re-run with different params.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research.drift_screen import screen_signal
from moonface.strategies.spec import PromotedStrategy
from moonface.strategies.impls.stack_path import STACK_PATH

Entry = tuple[int, str]

# The frozen construction under test. These are the params as they exist in the
# working tree at registration time. Their provenance is UNKNOWN (the strategy
# and its test arrived untracked), which is exactly why the screen runs on the
# fresh 16-asset universe with BTC/ETH/SOL excluded: if the params were ever
# tuned, BTC is where it would have happened.
PARAMS = {
    "lookback_bars": 20,
    "penalty_factor": 1.0,
    "stack_threshold": 1,
    "slope_threshold": 0.01,
    "long_only": False,
    "atr_period": 14,          # exit.params.atr_period; matches screen atr_period
    "k_stop": 2.0,             # only scales the (unused-by-the-screen) invalidation
}

# Descriptive only — NOT a gate. The binding verdict is at the primary horizon.
CURVE_HORIZONS = [6, 12, 24, 48]

INHERITED = Path("experiments/drift_screen/registration.json")


def _build_strategy(params: dict) -> PromotedStrategy:
    return PromotedStrategy(
        family="stack_path",
        params={k: params[k] for k in ("lookback_bars", "penalty_factor",
                                       "stack_threshold", "slope_threshold",
                                       "long_only")},
        exit={"name": "fixed_bracket",
              "params": {"atr_period": params["atr_period"],
                         "k_stop": params["k_stop"]}},
        fraction=0.01,
        status="paper",
        asset={"exchange": "binance", "symbol": "BTC/USDT:USDT",
               "timeframe": "4h"},
        provenance={},
        max_drawdown_p95=0.2,
    )


def stack_path_generator(candles: list[Candle], params: dict) -> list[Entry]:
    """Adapt the single-bar STACK_PATH.evaluate() to the screen's Generator
    interface. Bar i is evaluated on the prefix candles[:i+1], so the signal
    sees only closed history and the entry lands on close[i] — identical
    causality to the native generators in research.edge.signals.

    Stops one bar early (range ends at len-1) to match those generators; the
    horizon filter in event_outcome drops the tail anyway.

    NOTE: stack_path fires on ~58% of bars, so this is a dense STATE indicator,
    not a sparse event signal. nonoverlap(h) therefore grid-samples the state
    at a fixed cadence with an arbitrary phase. That is accepted deliberately:
    nonoverlap is frozen prior art and inventing new selection semantics for
    one lane is how selection artifacts are born."""
    strat = _build_strategy(params)
    lookback = params["lookback_bars"]
    out: list[Entry] = []
    for i in range(lookback, len(candles) - 1):
        sig = STACK_PATH.evaluate(strat, DataBundle(candles=candles[:i + 1]))
        if sig.decision in ("LONG", "SHORT"):
            out.append((i, sig.decision))
    return out


def identity_hash(reg: dict) -> str:
    """sha256 over the canonical JSON of the verdict-relevant content only."""
    payload = {k: reg[k] for k in ("timeframe", "h", "atr_period", "floor",
                                   "min_events", "min_assets", "universe",
                                   "params")}
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cmd_register(out_dir: Path, inherited: Path) -> None:
    path = out_dir / "registration.json"
    if path.exists():
        sys.exit(f"{path} already exists; the construction is frozen")
    src = json.loads(inherited.read_text())
    reg = {
        "lane": "drift_screen_stack_path",
        "timeframe": src["timeframe"],
        "h": src["h"],
        "atr_period": src["atr_period"],
        "floor": src["floor"],
        "min_events": src["min_events"],
        "min_assets": src["min_assets"],
        "universe": src["universe"],
        "discovery_excluded": src["discovery"],
        "params": PARAMS,
        "curve_horizons": CURVE_HORIZONS,
        "inherited_from": str(inherited),
        "inherited_registered_utc": src["registered_utc"],
        "kill_rule": ("mechanism_does_not_exist => stack_path closed at stage 0;"
                      " no parameter rescue, no v2, no re-run"),
        "expected_outcome": ("NEGATIVE. drift_screen already returned"
                             " mechanism_does_not_exist for 5 trend/breakout"
                             " signals on this exact universe/h/floor, and the"
                             " microscope lane found forward-R does not"
                             " stratify by regime over 1838 events."),
        "params_provenance": "UNKNOWN — strategy + test arrived untracked",
    }
    reg["identity_hash"] = identity_hash(reg)
    reg["registered_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reg, indent=2) + "\n")
    print(f"registered: {path}")
    print(f"identity_hash: {reg['identity_hash']}")


def _loader(cache_dir: str = ".backtest_cache"):
    from moonface.data.ohlcv import OhlcvCache
    cache = OhlcvCache(cache_dir)
    return lambda sym, tf: cache.load(sym, tf)


def cmd_run(out_dir: Path, cache_dir: str = ".backtest_cache") -> None:
    reg = json.loads((out_dir / "registration.json").read_text())
    if identity_hash(reg) != reg["identity_hash"]:
        sys.exit("identity_hash mismatch: the frozen construction was edited")
    load = _loader(cache_dir)
    tf = reg["timeframe"]
    pool: dict[str, list[Candle]] = {}
    for sym in reg["universe"]:
        candles = load(sym, tf)
        if candles:
            pool[sym] = candles
    print(f"pool: {len(pool)}/{len(reg['universe'])} assets loaded")

    primary = screen_signal(
        "stack_path", stack_path_generator, reg["params"], pool,
        h=reg["h"], atr_period=reg["atr_period"], floor=reg["floor"],
        min_events=reg["min_events"], min_assets=reg["min_assets"])

    curve = []
    for h in reg["curve_horizons"]:
        r = screen_signal("stack_path", stack_path_generator, reg["params"],
                          pool, h=h, atr_period=reg["atr_period"],
                          floor=reg["floor"], min_events=reg["min_events"],
                          min_assets=reg["min_assets"])
        v = r["verdict"]
        curve.append({"h": h, "m_assets": v["m_assets"],
                      "pooled_ret_r": v["pooled_ret_r"],
                      "pooled_abs_mae_r": v["pooled_abs_mae_r"],
                      "ratio": v["ratio"], "p_sign": v["p_sign"],
                      "stouffer_z": v["stouffer_z"],
                      "n_events": sum(a["n"] for a in r["assets"])})

    out = {"registration": reg, "primary": primary, "curve_descriptive": curve}
    (out_dir / "result.json").write_text(json.dumps(out, indent=2) + "\n")
    (out_dir / "result.md").write_text(_render_md(reg, primary, curve))
    v = primary["verdict"]
    print(f"\nVERDICT: {v['verdict']}\n  {v['reason']}")
    print(f"-> {out_dir / 'result.md'}")


def _f(x) -> str:
    return "" if x is None else f"{x:.4f}"


def _render_md(reg: dict, primary: dict, curve: list[dict]) -> str:
    v = primary["verdict"]
    n = sum(a["n"] for a in primary["assets"])
    lines = [
        "# stack_path — stage-0 drawdown-aware drift screen", "",
        f"- **VERDICT: {v['verdict']}**",
        f"- reason: {v['reason']}",
        f"- identity_hash: `{reg['identity_hash']}`",
        f"- registered: {reg['registered_utc']}",
        "",
        "## Frozen construction", "",
        f"- params: `{reg['params']}`",
        f"- params provenance: **{reg['params_provenance']}**",
        f"- primary horizon h={reg['h']} ({reg['timeframe']} bars), "
        f"atr_period={reg['atr_period']}, floor={reg['floor']}",
        f"- universe: {len(reg['universe'])} fresh assets "
        f"(discovery {reg['discovery_excluded']} excluded)",
        f"- design inherited verbatim from `{reg['inherited_from']}` "
        f"(frozen {reg['inherited_registered_utc']})",
        f"- kill rule: {reg['kill_rule']}",
        "",
        "## Primary gate (binding)", "",
        f"- evaluable assets: {v['m_assets']} (min {reg['min_assets']})",
        f"- total non-overlapping events: {n}",
        f"- assets with positive mean_ret_r: {v.get('k_positive')}/{v['m_assets']}",
        f"- sign test p = {_f(v['p_sign'])} (need <= 0.05)",
        f"- Stouffer Z = {_f(v['stouffer_z'])} (need >= 1.645)",
        f"- pooled mean_ret_r = {_f(v['pooled_ret_r'])}",
        f"- pooled mean_abs_mae_r = {_f(v['pooled_abs_mae_r'])}",
        f"- **path ratio = {_f(v['ratio'])}** (floor {reg['floor']})",
        "",
        "## Per-asset evidence", "",
        "| asset | n | mean_ret_r | mean_abs_mae_r | mean_mfe_r | sign_rate | t |",
        "|---|---|---|---|---|---|---|",
    ]
    for a in primary["assets"]:
        lines.append(f"| {a['sym']} | {a['n']} | {_f(a['mean_ret_r'])} "
                     f"| {_f(a['mean_abs_mae_r'])} | {_f(a['mean_mfe_r'])} "
                     f"| {_f(a['sign_rate'])} | {_f(a['t'])} |")
    lines += ["", "## Horizon curve (DESCRIPTIVE — not a gate)", "",
              "| h | m | n | pooled_ret_r | pooled_abs_mae_r | ratio | p_sign | Z |",
              "|---|---|---|---|---|---|---|---|"]
    for c in curve:
        lines.append(f"| {c['h']} | {c['m_assets']} | {c['n_events']} "
                     f"| {_f(c['pooled_ret_r'])} | {_f(c['pooled_abs_mae_r'])} "
                     f"| {_f(c['ratio'])} | {_f(c['p_sign'])} "
                     f"| {_f(c['stouffer_z'])} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="stack_path stage-0 drift screen")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register", help="freeze the construction")
    r.add_argument("--out", type=Path,
                   default=Path("experiments/drift_screen_stack_path"))
    r.add_argument("--inherited", type=Path, default=INHERITED)
    n = sub.add_parser("run", help="screen -> verdict")
    n.add_argument("--out", type=Path,
                   default=Path("experiments/drift_screen_stack_path"))
    n.add_argument("--cache-dir", default=".backtest_cache")
    a = p.parse_args(argv)
    if a.cmd == "register":
        cmd_register(a.out, a.inherited)
    else:
        cmd_run(a.out, a.cache_dir)


if __name__ == "__main__":
    main()
