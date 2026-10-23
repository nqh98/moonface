#!/usr/bin/env python3
"""One-off: capture the golden-master fixture for tests/test_edge_signals_perf.py
from the CURRENT signal generators. Run once before the O(n) fix; commit the
fixture so the behavior-preservation test can detect any divergence afterward.

    .venv/bin/python tools/_gen_edge_signals_golden.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))
sys.path.insert(0, str(HERE / "tests"))

from test_edge_signals_perf import CASES, _synth  # noqa: E402

OUT = HERE / "tests" / "fixtures" / "edge_signals_perf_golden.json"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    golden: dict[str, list[list]] = {}
    for series_tag, n, seed in [("A", 2000, 20260630), ("B", 1500, 7)]:
        h1 = _synth(n, seed)
        for label, gen, params in CASES:
            entries = gen(h1, params)
            golden[f"{series_tag}|{label}"] = [[i, side] for i, side in entries]
            print(f"  {series_tag}|{label}: {len(entries)} entries", flush=True)
    OUT.write_text(json.dumps(golden, indent=2))
    print(f"wrote {OUT}  ({len(golden)} keys)", flush=True)


if __name__ == "__main__":
    main()
