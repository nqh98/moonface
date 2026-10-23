# tda_topology_v1 — descriptive instrument

Design: `docs/research-log/specs/2026-07-16-tda-topology-design.md`

**NOT A GATE.** No lockbox, no DSR ladder, no promotion path. This answers one
question and stops: does persistent homology of the cross-sectional correlation
matrix stratify forward-R of the frozen 1838 Donchian events, beyond a null that
preserves time structure? Microscope's 5-factor state vector did not
(effect 0.609 vs shuffle p95 0.835).

## Install

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pip install -e ../..

Quarantined on purpose: the main tree is stdlib-only, so numpy/scipy/ripser
must not enter `src/`. PH backend in use: ripser.

## Test

    .venv/bin/pytest tests/ -v

## Run (offline, cache-only)

    .venv/bin/python run.py --cache-dir ../../cache/matrix \
        --events ../microscope/donchian_universe_events.csv \
        --out . --seed 1

Reads cached 4h candles only. Never fetches. Writes features.csv, labels.csv,
outcomes.csv, report.md, run.log.
