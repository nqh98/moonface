# SSE v1 Registration

Frozen on 2026-07-12 from `docs/research-log/specs/2026-07-12-sse-state-matrix-design.md`.

## Claim

BTC 4h forward returns may stratify by the crypto market's cross-sectional
state, using breadth and dispersion plus a 20-bar trajectory through that
plane, beyond the adjudicated single-asset legacy state control.

## Data

- BTC 4h perp candles: 2020-01-01 through 2026-06-30.
- Cross-section: monthly top-50 USDT perps by trailing 30d quote volume,
  delistings included, 90d listing floor.
- Pool-level values are missing unless at least 30 active members are present.

## Features

- Track N points: `breadth_z`, `disp_z`.
- Track N trajectories: 20-bar summaries of per-axis mean, displacement, path
  length, each standardized causally.
- Track L control: `position`, `velocity`, `vol_accel`, `crowding`.
- Clustering: k-means, `k=4`, fixed seed, fit once on Era 1 only.

## Eras

- Era 1: 2020-01-01 to 2022-06-30.
- Era 2: 2022-07-01 to 2024-06-30.
- Era 3: 2024-07-01 to 2026-06-30.

## Gate 0

- Observation unit: cluster-entry episode.
- Outcome: BTC log return over `H = 24` bars from entry close.
- Bucket power floor: `n >= 30`.
- Two Track N cells: points and trajectories.
- Per-cell pass conditions:
  1. Label-shuffle spread exceeds the p97.5 null threshold.
  2. Circular-shift spread exceeds the p97.5 null threshold.
  3. Track N spread exceeds Track L spread.
  4. Era-1 top-minus-bottom sign holds in Era 2 and Era 3 with power.
- If Track L clears either null, verdict is `SUSPECT_HARNESS` and Track N is
  not interpreted.

## Gate 1

Only if Gate 0 survives:

- Use the best Era-1 cluster from the passing cell; points win ties.
- Fixed ATR(14) bracket: 2.0 target / 1.0 stop.
- Cost: 6 bp per side.
- Anchored walk-forward, DSR gate, iid-null calibration, one-touch lockbox.

## Kill Criteria

- Both Track N cells fail any Gate-0 condition: `CLOSED`.
- `SUSPECT_HARNESS`: debug only, no verdict.
- Gate 1 fail: `CLOSED`.
- Best possible outcome: forward-paper candidacy, never live.
