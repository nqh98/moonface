#!/usr/bin/env python
"""advval adversarial-validation one-touch study CLI (spec H3).

--register freezes the design before any data is read. --run is reserved for
Task 5 and is left as a lazy import hook here.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from moonface.core.models import Candle
from moonface.research.advval.features import (
    funding_features,
    oi_features,
    price_features,
)
from moonface.research.advval.retrodiction import (
    CELLS,
    EXCLUDED,
    N_BOOT,
    SEED,
    STUDIES,
)

_ERA_SPLIT_MS = 1_704_844_800_000
_WINDOW_START_MS = 1_640_995_200_000
_BTC_SYMBOL = "BTCUSDT"
_FUNDING_SYMBOL = "BTC/USDT:USDT"
_EXCHANGE = "binanceusdm"
_Z_WINDOW = 90


def _feature_keys() -> tuple[list[str], list[str], list[str]]:
    candle = Candle(0, 1.0, 1.0, 1.0, 1.0, 1.0)
    price_keys = sorted(price_features([candle]))
    funding_keys = sorted(funding_features([(0, 0.0)]))
    oi_keys = sorted(oi_features([None]))
    return price_keys, funding_keys, oi_keys


PRICE_FEATURES, FUNDING_FEATURES, OI_FEATURES = _feature_keys()

DESIGN = {
    "symbol": _BTC_SYMBOL,
    "funding_symbol": _FUNDING_SYMBOL,
    "exchange": _EXCHANGE,
    "metrics_field": "sum_open_interest",
    "window_start_ms": _WINDOW_START_MS,
    "era_split_ms": _ERA_SPLIT_MS,
    "cells": list(CELLS),
    "price_features": PRICE_FEATURES,
    "funding_features": FUNDING_FEATURES,
    "oi_features": OI_FEATURES,
    "z_window": _Z_WINDOW,
    "gbt": {"rounds": 200, "lr": 0.1, "min_leaf": 20},
    "cv": {"n_folds": 5, "embargo": 90},
    "bootstrap": {"n_boot": N_BOOT, "seed": SEED},
    "kill_rule": "kill unless rho > 0 AND ci_low > 0 (90% percentile CI)",
}


def _study_table_md() -> str:
    lines = ["| study | cell | outcome | basis |", "|---|---|---|---|"]
    for study in STUDIES:
        outcome = "FLIP" if study.outcome else "NO_SIGNAL"
        lines.append(
            f"| `{study.name}` | {study.cell} | {outcome} | {study.basis} |"
        )
    return "\n".join(lines)


def _excluded_md() -> str:
    return "\n".join(f"- `{name}` - {reason}" for name, reason in EXCLUDED)


def cmd_register(out_dir: Path, now_ms: int | None = None) -> None:
    reg_path = out_dir / "registration.json"
    if reg_path.exists():
        sys.exit(f"{reg_path} already exists; the design is frozen")

    now = int(time.time() * 1000) if now_ms is None else now_ms
    reg = dict(DESIGN)
    reg["window_end_ms"] = now
    reg["n_studies"] = len(STUDIES)
    reg["registered_utc"] = dt.datetime.fromtimestamp(
        now / 1000, dt.timezone.utc
    ).isoformat()

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    if out_dir.exists():
        try:
            next(out_dir.iterdir())
        except StopIteration:
            out_dir.rmdir()
        else:
            sys.exit(f"{out_dir} already exists and is not empty; the design is frozen")
    staging = Path(
        tempfile.mkdtemp(prefix=f".{out_dir.name}.staging.", dir=out_dir.parent)
    )
    staging_reg = staging / "registration.json"
    staging_prereg = staging / "PREREGISTRATION.md"
    prereg = f"""# advval - adversarial-validation instrument (H3) - PRE-REGISTRATION

Frozen {reg['registered_utc']} BEFORE any data read. Spec:
`docs/research-log/specs/2026-07-06-freedata-addendum-design.md` (H3).

**Not an edge study.** Claim under test: the recurring IS->OOS sign-flip
failure signature across closed families reflects measurable distribution
shift. Instrument: per-cell adversarial AUC (era A = before 2024-01-10 UTC,
era B = after; spot-ETF approval). Retrodiction: per-study Spearman between
the study's cell AUC and its FLIP/NO_SIGNAL outcome.

## Frozen design

```json
{json.dumps(reg, indent=2)}
```

## Frozen coding table ({len(STUDIES)} studies; FLIP=IS strength that reversed/decayed OOS, NO_SIGNAL=never strong)

{_study_table_md()}

## EXCLUDED studies (coding-scope record)

{_excluded_md()}

## Verdict rule (frozen)

**{DESIGN['kill_rule']}** - a kill means adversarial validation is dead as an
instrument here: the harness keeps its existing gates and no pre-screen is
adopted. A pass adopts the AUC pre-screen for future pre-registrations only;
it rescues nothing and gates no live decision.

## Power note (honest)

Only 4 distinct AUC values map onto 18 studies, so rho is coarse by design;
the bootstrap CI over studies carries that granularity. This is the
pre-committed design; there is no post-hoc refinement path.
"""
    try:
        staging_prereg.write_text(prereg)
        staging_reg.write_text(json.dumps(reg, indent=2))
        staging.replace(out_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(f"registered: {reg_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--out-dir", default="experiments/advval")
    parser.add_argument("--cache-dir", default=".backtest_cache")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    if args.register:
        cmd_register(out_dir)
        return
    if args.run:
        try:
            from tools.advval.advval_run import cmd_run  # Task 5
        except ModuleNotFoundError as exc:
            if exc.name != "tools.advval.advval_run":
                raise
            raise SystemExit("--run is not available until Task 5") from exc
        cmd_run(out_dir, args.cache_dir)
        return
    parser.error("choose --register or --run")


if __name__ == "__main__":
    main()
