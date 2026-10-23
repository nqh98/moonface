#!/usr/bin/env python3
"""Targeted regeneration of the 2 C1-affected lanes (practical, btcspec) on their
NATIVE timeframes, then patch + re-sort the existing RESULT.json/LEADERBOARD.md.

The full pipeline re-run hung (~2h, stuck on playbook 12x full-window replay / the
now-heavier TF-dispatched btcspec). C1 only changes practical+btcspec; the other 16
rows are deterministic and unaffected, so re-running them is wasteful. This script
loads only the price candles those 2 lanes need and patches the artifacts —
result-identical to a full re-run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moonface.research.consolidated.adapters import ADAPTERS  # noqa: E402
from moonface.research.consolidated.report import render_markdown  # noqa: E402
from moonface.research.consolidated.result import metric_block  # noqa: E402
from moonface.research.universe_data import fetch_perp_candles  # noqa: E402

START, END, CACHE = 1577836800000, 1782300000000, ".backtest_cache"
SYMBOL = "BTCUSDT"
OUT = Path("experiments/consolidated_ls")


class _Ctx:
    def __init__(self):
        self.btc_4h = fetch_perp_candles(SYMBOL, "4h", START, END, CACHE)
        self.btc_1h = fetch_perp_candles(SYMBOL, "1h", START, END, CACHE)
        self.btc_2h = fetch_perp_candles(SYMBOL, "2h", START, END, CACHE)
        self.funding = []
        self.daily = {}
        self.is_member = lambda sym, ts: True
        self.macro = {}
        self.start_ms = START
        self.end_ms = END
        self.cache_dir = CACHE


def main():
    ctx = _Ctx()
    new_rows = []
    for lane in ("practical", "btcspec"):
        for res in ADAPTERS[lane](ctx):
            row = {
                "key": res.key, "lane": res.lane, "config": res.config,
                "config_source": res.config_source, "exit_name": res.exit_name,
                "current_signal": res.current_signal, "status": "ok",
            }
            row.update(metric_block(res))
            new_rows.append(row)
            print(f"  {lane}: {res.key}  exp={row['expectancy_r']} n={row['n']} total={row['total_r']}", flush=True)

    doc = json.load(open(OUT / "RESULT.json"))
    kept = [r for r in doc["rows"]
            if r.get("lane") not in ("practical", "btcspec") and r.get("status", "ok") == "ok"]
    rows = kept + new_rows
    rows.sort(key=lambda r: (
        r.get("expectancy_r") is None,
        -(r.get("expectancy_r") or 0.0),
        -(r.get("n") or 0),
        -(r.get("total_r") or 0.0),
    ))
    doc["rows"] = rows
    with open(OUT / "RESULT.json", "w") as fh:
        json.dump(doc, fh, indent=2, default=str)
    result = {k: doc.get(k) for k in ("rows", "excluded", "errors", "window", "btc_bars", "btc_sha")}
    (OUT / "LEADERBOARD.md").write_text(render_markdown(result, doc.get("asof", "2026-06-29")))
    print(f"patched {len(new_rows)} rows; total rows now {len(rows)}")


if __name__ == "__main__":
    main()
