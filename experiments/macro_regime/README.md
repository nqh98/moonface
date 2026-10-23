# macro_regime — Causal Macro-Liquidity Regime Instrument

**Status:** research instrument. Emits regime probabilities + entropy from cross-asset
macro data (DXY / US10Y / Gold). **Not an edge claim, not a trading signal, not wired
into any engine.** See `DESIGN.md`.

Quarantined from the stdlib-only main tree: its numpy/pandas/sklearn/yfinance deps live
only in this directory's own venv.

## Setup

    python3 -m venv experiments/macro_regime/.venv
    experiments/macro_regime/.venv/bin/pip install -r experiments/macro_regime/requirements.txt

## Run

    experiments/macro_regime/.venv/bin/python experiments/macro_regime/macro_regime_model.py \
      --start 2015-01-01 --components 3 --mode walkforward --out regimes.csv

## Test

    experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests -v
