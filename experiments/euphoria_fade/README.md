# euphoria_fade v1

Pre-registered SHORT fade of the `UP/HIGH/CROWDED_LONG` microscope texture.
Registration: `PREREGISTRATION.md` (frozen 2026-07-10, commit 1f94d1b) —
constants there are law; best possible outcome is FORWARD PAPER.

## Run (stages 1-4; lockbox stays sealed)

    .venv/bin/python experiments/euphoria_fade/euphoria_fade_backtest.py run \
        --cache-dir cache/matrix --start 2020-01-01 --end 2026-07-01 --seed 1

Requires the pre-warmed 17-asset 4h cache (`cache/matrix`, candles + funding
+ OI through 2026-06-30). Offline; bookdepth is skipped. Writes
`run_verdict.json`, `run_report.md`, sealed `lockbox_trades.json`.

## Lockbox (one-touch, only if a cell passes stages 1-4)

    .venv/bin/python experiments/euphoria_fade/euphoria_fade_backtest.py lockbox \
        --i-understand-one-touch

Refuses if already opened or if no cell is pending.

## Tests

    .venv/bin/python -m pytest experiments/euphoria_fade/tests -q
