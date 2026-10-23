#!/usr/bin/env python3
"""Isolated research-side forward PAPER-watch for the 4h vol_expansion finalist.

PAPER ONLY — never live. Deliberately self-contained: it does NOT read or write
promotion/strategy.json, promotion/*, or journal/signals.jsonl (those belong to
the Donchian paper-watch). It freezes the finalist config + a pre-committed
forward gate, then reports — read-only — whether fresh out-of-time evidence
REAFFIRMs or DOWNGRADEs the paper status.

  --register : write the frozen config + VOL_EXPANSION_FORWARD_REGISTRATION.md (t0).
  --report   : read-only forward gate over fresh 4h candles (run this recurrently).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research.practical_full import forward  # noqa: E402
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

DEFAULT_CONFIG = "experiments/practical_full/forward/vol_expansion_4h.json"
FETCH_START_MS = 1577836800000  # 2020-01-01; warmup history for the generator

# The frozen finalist (byte-identical to experiments/practical_full/frozen_candidates.json)
FINALIST = {
    "family": "vol_expansion",
    "params": {"mult": 3.0, "atr_period": 14, "lookback": 24},
    "exit_name": "atr_trail",
    "exit_params": {"k_trail": 2.0, "max_bars": 120, "atr_period": 14},
    "h": 24,
    "fraction": 0.01,
    "status": "paper",
    "asset": {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "4h"},
}


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _load_candles(cfg, cache_dir):
    return fetch_perp_candles(cfg["asset"]["symbol"], cfg["asset"]["timeframe"],
                              FETCH_START_MS, _now_ms(), cache_dir)


def build_report(cfg, candles) -> dict:
    rep = forward.forward_report(candles, cfg, cfg["t0_ms"], _now_ms())
    if rep["gate"]["passed"]:
        verdict = "REAFFIRM PAPER (paper-only; NOT live)"
    elif not rep["gate"]["drawdown_within_p95"] and rep["closed_trades"] > 0:
        verdict = "DOWNGRADE — early drawdown kill"
    elif rep["gate"]["min_trades"] and rep["gate"]["min_weeks"]:
        verdict = "DOWNGRADE — horizon reached, gate not met"
    else:
        verdict = "INCONCLUSIVE — keep paper-tracking"
    return {**rep, "verdict": verdict}


_REG_DOC = """# 4h vol_expansion — Forward Paper Registration (frozen {asof})

Isolated research-side paper-watch for the practical-full finalist. PAPER ONLY —
REAFFIRM does NOT authorize live capital; going live stays a separate human-only
decision. Touches nothing in promotion/ or journal/signals.jsonl (those belong to
the Donchian watch). Evaluation is read-only via
`tools/vol_expansion_watch.py --report`.

## Strategy under test (byte-identical to frozen_candidates.json)
- entry vol_expansion mult=3.0, atr_period=14, lookback=24 ; nonoverlap h=24
- exit atr_trail k_trail=2.0, max_bars=120, atr_period=14 ; fraction=0.01
- asset BTC/USDT:USDT 4h ; status=paper

## Why it is on watch
Cleared the full practical bar (net-positive, |DD|<=30R, outlier-clean, robust to
2x/3x cost) on Explore AND Validate, then REVERSED to negative expectancy in the
sealed/most-recent window (2025-03 -> 2026-06, exp -0.32, n=32). This forward
watch tests whether that recent decay is a regime-transient or a real death,
using fresh out-of-time evidence — NOT a re-cut of the 6.5y path.

## t0 and counting
- t0 = {t0_iso} (t0_ms={t0_ms}).
- The forward window counts CLOSED trades whose ENTRY bar timestamp >= t0 and
  whose full max_bars window has elapsed within available data (edge positions
  count as open, never marked-to-end).
- State at registration: 0 closed forward trades (data ends ~2026-06-20 < t0).

## Frozen resolution rule (fields from research.practical_full.forward.forward_report)
| Outcome | Pre-committed trigger |
|---|---|
| REAFFIRM PAPER | gate.passed == True — closed_trades >= 20 AND elapsed_weeks >= 12 AND net_r > 0 AND gate.drawdown_within_p95 == True (max_drawdown >= -0.30). |
| DOWNGRADE — early kill | gate.drawdown_within_p95 == False at ANY --report with >=1 closed trade (forward equity DD breaches the 0.30 budget). |
| DOWNGRADE — horizon | min_trades AND min_weeks both True but gate.passed False (fails on net_positive). |
| Stay INCONCLUSIVE | none of the above — keep paper-tracking. |

Thresholds (FORWARD_MIN_TRADES=20, FORWARD_MIN_WEEKS=12.0, MAX_DD_BUDGET=0.30)
mirror moonface.signal.journal.forward_report and the locked economic bar. No
threshold may change after this date.

## Honest caveats
- Single-asset BTC, paper-only. REAFFIRM != live.
- A 4h vol-expansion entry fires infrequently; reaching >=20 CLOSED forward
  trades will likely take well beyond 12 weeks. Continued INCONCLUSIVE is the
  expected near-term state, not a failure. The early-DD-kill guards a slow bleed.
- The finalist already FAILED the most-recent backtest window; this watch can
  only REAFFIRM or DOWNGRADE forward, it does not relitigate the negative holdout.
"""


def _register(cfg_path: Path) -> None:
    t0 = _now_ms()
    cfg = {**FINALIST, "t0_ms": t0}
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n")
    doc = _REG_DOC.format(
        asof=datetime.fromtimestamp(t0 / 1000, timezone.utc).date().isoformat(),
        t0_iso=datetime.fromtimestamp(t0 / 1000, timezone.utc).isoformat(),
        t0_ms=t0)
    (cfg_path.parent / "VOL_EXPANSION_FORWARD_REGISTRATION.md").write_text(doc)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="4h vol_expansion forward paper-watch")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--register", action="store_true")
    mode.add_argument("--report", action="store_true")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--cache-dir", default=".backtest_cache")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    cfg_path = Path(args.config)
    if args.register:
        _register(cfg_path)
        print(f"registered -> {cfg_path} + "
              f"{cfg_path.parent}/VOL_EXPANSION_FORWARD_REGISTRATION.md")
        return 0

    if not cfg_path.exists():
        print(f"no config at {cfg_path}; run --register first")
        return 3
    cfg = json.loads(cfg_path.read_text())
    candles = _load_candles(cfg, args.cache_dir)
    rep = build_report(cfg, candles)
    if args.as_json:
        print(json.dumps(rep, indent=2, sort_keys=True))
    else:
        g = rep["gate"]
        print(f"verdict: {rep['verdict']}")
        print(f"  closed_trades={rep['closed_trades']} open={rep['open_trades']} "
              f"net_r={rep['net_r']} exp={rep['expectancy_r']} "
              f"max_dd={rep['max_drawdown']} weeks={rep['elapsed_weeks']}")
        print(f"  gate: trades>=20 {g['min_trades']} | weeks>=12 {g['min_weeks']} | "
              f"net>0 {g['net_positive']} | dd_ok {g['drawdown_within_p95']} "
              f"=> passed {g['passed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
