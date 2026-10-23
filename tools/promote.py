#!/usr/bin/env python
# tools/promote.py
"""Promote a lockbox-passed hypothesis to PAPER status.

Writes promotion/strategy.json for moonface-signal. Hardened deployability vet
(beyond the ladder's own gates): tail MAR >= 2.0 and the research drawdown
budget on both the holdout and the tail. Never mutates the research store.
The later paper -> live flip is a manual edit, allowed only when
`moonface-signal --report` shows the forward gate passed."""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.research import ladder
from moonface.data.bundle import load_bundle
from moonface.kernel.bootstrap import iid_resample_randrange
from moonface.kernel.lockbox import FencedBundle
from moonface.core.metrics import equity_summary
from moonface.kernel.spec import spec_from_json
from moonface.kernel.store import Store

HARDENED_TAIL_MAR = 2.0
MC_BOOTSTRAPS = 1000
MC_SEED = 7


def mc_drawdown_p95(trades: list[tuple[float, float]], fraction: float,
                    n_boot: int = MC_BOOTSTRAPS, seed: int = MC_SEED) -> float:
    """95th-percentile bootstrap max drawdown (positive magnitude) of the
    research R-stream at the strategy's fraction — the forward gate's bound."""
    rng = random.Random(seed)
    dds = []
    for _ in range(n_boot):
        sample = iid_resample_randrange(rng, trades)
        dds.append(equity_summary(sample, fraction).max_drawdown)
    dds.sort()  # most negative first
    return round(-dds[int(0.05 * n_boot)], 6)


def promote(store: Store, h: str, out_path: str | Path,
            research_stream: list[tuple[int, float, float]]) -> dict:
    row = store.row(h)
    if row["status"] != "lockbox_pass":
        sys.exit(f"refusing: hypothesis status is {row['status']!r},"
                 " not lockbox_pass")
    m = row["stage_results"]
    if m.get("tail_mar", 0.0) < HARDENED_TAIL_MAR:
        sys.exit(f"refusing: tail_mar {m.get('tail_mar')} is below the"
                 f" hardened floor {HARDENED_TAIL_MAR}")
    for key in ("tail_drawdown", "holdout_drawdown"):
        if m.get(key, -1.0) < ladder.DRAWDOWN_BUDGET:
            sys.exit(f"refusing: {key} {m.get(key)} violates the drawdown"
                     f" budget {ladder.DRAWDOWN_BUDGET}")
    spec = spec_from_json(row["spec_json"])
    trades = [(r, af) for _, r, af in research_stream]
    if not trades:
        sys.exit("refusing: empty research stream")
    p95 = mc_drawdown_p95(trades, spec.fraction)
    payload = {
        "family": spec.entry["family"],
        "params": spec.entry["params"],
        "exit": spec.exit,
        "fraction": spec.fraction,
        "status": "paper",
        "asset": spec.asset,
        "provenance": {
            "domain": spec.domain,
            "version": spec.version,
            "spec_hash": h,
            "report": f"experiments/research/{spec.domain}_v{spec.version}.md",
            "promoted_ts": int(time.time() * 1000),
        },
        "max_drawdown_p95": p95,
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("domain")
    p.add_argument("--version", type=int, default=1)
    p.add_argument("--spec-hash", required=True)
    p.add_argument("--db", default="experiments/research/research.db")
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--out", default="promotion/strategy.json")
    args = p.parse_args()
    store = Store(args.db)
    d = store.domain(args.domain, args.version)
    if d is None:
        sys.exit(f"unknown domain {args.domain} v{args.version}")
    row = store.row(args.spec_hash)
    spec = spec_from_json(row["spec_json"])
    bundle = load_bundle(spec.asset, d["start_ms"], d["end_ms"], args.cache_dir)
    fb = FencedBundle(bundle, d["fence_ts"])
    stream = ladder.r_stream(spec, fb.research())
    payload = promote(store, args.spec_hash, args.out, stream)
    print(f"PAPER strategy written to {args.out}"
          f" (mc p95 drawdown {payload['max_drawdown_p95']:.2%})."
          " Commit it; flip to live only after moonface-signal --report"
          " shows gate.passed = true.")


if __name__ == "__main__":
    main()
