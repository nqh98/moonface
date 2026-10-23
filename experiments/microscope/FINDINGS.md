# Market State Microscope — First Studies (2026-07-10)

**DESCRIPTIVE DIAGNOSTIC — NOT A GATE, NOT A RESULT.** The microscope buckets an
external signal's entry events by rule-based regime label and reports the forward
risk distribution per bucket, with built-in label-shuffle null calibration and an
n<30 power floor. Nothing here is a pass/fail or a promotion path.

Instrument: `src/moonface/research/microscope/` + `tools/microscope.py` (built +
merged, 12 commits `b69ae47`→`33aecd3`, 66 tests). Pool: the 16-asset + BTC 4h
universe via `multifamily_loader`.

## Studies run

Events source in all three = the frozen Donchian breakout (`deployed_base()`,
`entry_n=40/trail_n=20`, `long_only=True`) via `trend_sim.simulate_donchian`.

| study | events source | window | events | labeled | buckets ≥30 | verdict |
|---|---|---|---|---|---|---|
| anchor | BTC-only frozen anchor (n=76) | 2020-01→2023-12 | 76 | 57 | 0 | INDISTINGUISHABLE_FROM_NULL (underpowered) |
| universe | breakout across all 17 assets | 2020-01→2023-12 | 949 | 803 | 6 | INDISTINGUISHABLE_FROM_NULL (real 0.757 vs p95 0.80) |
| universe_2026 | breakout across all 17 assets | 2020-01→2026-07 | 1838 | 1748 | 6 | INDISTINGUISHABLE_FROM_NULL (real 0.609 vs p95 0.835) |

## Result

**The Donchian breakout's forward-risk distribution does not stratify by regime.**
The between-bucket spread is within what pure label-shuffling produces, and the
conclusion is robust: doubling the event count and using the fullest cross-section
(universe_2026) pushed the result *further* into the null (real/p95 ratio 0.73 vs
0.95 at 949 events), not toward signal. Two buckets have CIs excluding zero, but the
null calibration correctly flags them as the expected multiple-comparisons artifact
across 14 buckets — the report fires its SELECTION ARTIFACT WARNING.

This is the descriptive explanation for why the program's ~8 regime-filter lanes all
closed negative: there is no regime structure in the forward-R distribution to filter
on (within the UP-ish regimes where long breakouts fire; RANGE buckets are thin and
DOWN is absent, since a long breakout does not fire in a downtrend).

## Lone texture (hypothesis-generator only, NOT a result)

`UP/HIGH/CROWDED_LONG` — breakouts into an already-hot, crowded-long tape — is the
**only negative bucket, and it is negative in both independent windows** (−0.10 in
2020-2026, −0.14 in 2020-2023) with the highest stop-out rate. This is the "buying
euphoria" cell. Per the instrument's discipline it is within-null across 14 buckets
and would require a separate pre-registered lane before it could influence anything.

**2026-07-11 update:** tested as the registered `experiments/euphoria_fade/` lane
(frozen SHORT-fade pre-registration) — verdict CLOSED_NEGATIVE (fade loses OOS and
underperforms its crowding-gate-removed control; null calibration clean; lockbox
unspent); see `experiments/euphoria_fade/RESULTS.md`. The texture is recorded as
noise; the euphoria/crowding-fade family is terminal.

## Reproduce

- Events: `simulate_donchian(cache.load(sym,"4h"), deployed_base(), None)` per asset
  → `donchian_universe_events.csv` (or the BTC anchor → `donchian_anchor_events.csv`).
- Study: `tools/microscope.py study --cache-dir cache/matrix --start … --end …
  --events <csv> --out <dir>` (bookdepth is unused by `build_matrix` and can be
  skipped to avoid a slow fetch). Cache holds all 17 assets' 4h candles + funding +
  OI through 2026-06-30.
- Large regenerable dumps (`features.csv`, `states.csv`, `pool.csv`) are gitignored;
  the committed `report.md` + `outcomes.csv` are the study record.
