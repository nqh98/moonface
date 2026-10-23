#!/usr/bin/env python
"""eventtime H1 one-touch study CLI (spec H1).

--register freezes the design before any data is read. --run is reserved for
Task 5 and stays a lazy import so the register path remains lightweight.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moonface.research.eventtime.paired import EXIT_ROWS

DESIGN = {
    "symbol": "BTCUSDT",
    "exchange": "binanceusdm",
    "entry": {"family": "donchian_break", "params": {"n": 55}},
    "exit_rows": [[name, params] for name, params in EXIT_ROWS],
    "calib_start_ms": 1577836800000,
    "calib_end_ms": 1672531200000,
    "test_start_ms": 1672531200000,
    "clock_timeframe": "4h",
    "bar_size_window_min": 240,
    "fence_fraction": 0.75,
    "fraction": 0.1,
    "grid_size": 10,
    "min_improve": 0.5,
    "kill_rule": (
        "KILL unless (>=1 exit dollar-bar MaxDD/net-R ratio improves >=50% vs "
        "its clock twin, dollar net-R > 0) AND the dollar-bar ladder clears "
        "stage1->stage4"
    ),
}


def _exit_rows_md() -> str:
    return "\n".join(f"- `{name}` {params}" for name, params in EXIT_ROWS)


def cmd_register(out_dir: Path, now_ms: int | None = None) -> None:
    reg_path = out_dir / "registration.json"
    if reg_path.exists():
        sys.exit(f"{reg_path} already exists; the design is frozen")

    now = int(time.time() * 1000) if now_ms is None else now_ms
    reg = dict(DESIGN)
    reg["test_end_ms"] = now
    reg["registered_utc"] = dt.datetime.fromtimestamp(
        now / 1000, dt.timezone.utc
    ).isoformat()

    out_dir.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(json.dumps(reg, indent=2))
    prereg = f"""# eventtime - is the drawdown wall a clock artifact? (H1) - PRE-REGISTRATION

Frozen {reg["registered_utc"]} BEFORE any data read. Spec:
`docs/research-log/specs/2026-07-06-freedata-addendum-design.md` (H1).

**Not a new signal.** The program's one replicated finding - positive
fixed-horizon drift exists but no bounded-risk exit harvests it within budget -
was established entirely in clock time. H1 attacks the measurement basis:
dollar bars homogenize per-bar risk, so a per-bar-sized bracket may bound the
cascade tail the clock-ATR bracket could not.

## Frozen design

```json
{json.dumps(reg, indent=2)}
```

## Frozen entry x the frozen exit rows

Entry: `donchian_break` `{{"n": 55}}` (two-sided, no search).
Frozen exit rows (`EXIT_REGISTRY` snapshot):

{_exit_rows_md()}

## Both arms (same test window {reg["test_start_ms"]} -> {reg["test_end_ms"]})

- **Control (clock):** 4h fapi klines, recomputed fresh this run.
- **Treatment (event-time):** dollar bars at one procedurally-frozen size - the
  median trailing-4h dollar volume over the pre-2023 calibration window. No
  bar-size search.

## Verdict rule (frozen)

**{DESIGN["kill_rule"]}**

- ratio = abs(research MaxDD in R) / research net R; "improves >=50%" means
  dollar_ratio <= 0.5 * clock_ratio on the same exit row.
- Ladder = stage1 screen -> stage2 holdout -> stage3 DSR (>=0.95, grid_size 10)
  -> stage4 one-touch lockbox tail (last 25%).
- **KILL** => the wall is sampling-invariant; the entire time-sampling axis
  (dollar bars, volume bars, tick bars, imbalance bars) closes forever.
- **PASS is research-only** - event-time bars close at unpredictable clock
  times; promotion would need a separately registered event-driven executor.
"""
    (out_dir / "PREREGISTRATION.md").write_text(prereg)
    print(f"registered: {reg_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--out-dir", default="experiments/eventtime")
    parser.add_argument("--cache-dir", default=".backtest_cache")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    if args.register:
        cmd_register(out_dir)
        return
    if args.run:
        try:
            from tools.eventtime.eventtime_run import cmd_run
        except ModuleNotFoundError as exc:
            if exc.name != "tools.eventtime.eventtime_run":
                raise
            raise SystemExit("--run is not available until Task 5") from exc
        cmd_run(out_dir, args.cache_dir)
        return
    parser.error("choose --register or --run")


if __name__ == "__main__":
    main()
