# Bollinger Band Mean-Reversion Backtest — Design

**Date:** 2026-06-30
**Status:** Approved (brainstormed)
**Scope:** Add a mean-reversion Bollinger Band entry signal and backtest it with the
existing forward-path / `score_variant` harness on BTC perpetual futures.

## Context & locked decisions

The user asked to "backtest BB strategy". Three forks were resolved in brainstorming:

1. **Entry logic — mean reversion (fade the bands).**
   LONG when price closes below the lower band; SHORT when it closes above the upper
   band; expectation is reversion toward the mean. (Chosen over breakout/momentum and
   squeeze variants.)
2. **Harness — forward-path scoring (`score_variant` / `smc_decompose` style).**
   Exit-free: fire BB entry events, declump overlaps, measure R-normalized forward
   returns at fixed horizons, and attach a bootstrap CI + sign test + conditional
   decomposition. (Chosen over a full equity-curve backtest with exits/sizing.)
3. **Parameter scope — small sweep scored as variants.**
   period ∈ {20, 50} × mult ∈ {2.0, 2.5, 3.0} = **6 variants**, each evaluated long &
   short via the decomposition slices.

**Code organization — Approach A (approved).** Reusable code lives in `src/`; a new
focused tool `tools/bb_revert.py` reuses the scorer from `tools/smc_decompose.py` by
import. No existing code is refactored.

## Non-goals (YAGNI)

- No wiring of `bb_revert` into `signals.REGISTRY` or the `research.py` domain pipeline.
- No full equity backtest, exits, or position sizing.
- No broader edge search and no squeeze logic.
- No promotion gate or edge claim — this is a research-only diagnostic, matching the
  repo's disciplined WAIT stance (see `docs/findings/PROGRAM_CONCLUSION.md`).

## Architecture

Three components. The first two are reusable library code; the third is orchestration.

### Component 1 — `rolling_std` indicator

**File:** `src/moonface/foundation/indicators.py` (next to `sma`).

```python
def rolling_std(closes: list[float], period: int) -> float:
    """Population std (ddof=0) of the last `period` closes. Caller ensures len >= period."""
    window = closes[-period:]
    m = sum(window) / period
    return (sum((x - m) ** 2 for x in window) / period) ** 0.5
```

Population std (ddof=0) is the classic Bollinger Band convention. Contract mirrors
`sma`: the caller guarantees `len(closes) >= period`.

### Component 2 — `bb_revert` entry generator

**File:** `src/moonface/research/edge/signals.py` (next to `atr_channel_break`,
`reversion_in_range`).

Signature: `bb_revert(h1: list[Candle], params: dict) -> list[Entry]` where
`Entry = tuple[int, str]` (index, `"LONG"` | `"SHORT"`) — the same contract every
generator in this module already satisfies.

`params`: `{"period": int, "mult": float}`.

Event semantics use **crossing** (discrete, declumpable events — matches the `price_vs_ma`
idiom rather than continuous "state" firing):

- `mid[i] = sma(last period closes incl. i)`; `sd[i] = rolling_std(same window)`
- `lower[i] = mid[i] - mult·sd[i]`; `upper[i] = mid[i] + mult·sd[i]`
- **LONG** at `i` when `close[i-1] >= lower[i-1]` and `close[i] < lower[i]`
  (closes below the lower band → buy the fade)
- **SHORT** at `i` when `close[i-1] <= upper[i-1]` and `close[i] > upper[i]`
  (closes above the upper band → sell the fade)

Bounded windows (`closes[max(0, i-period+1):i+1]` for "now", `closes[max(0, i-period):i]`
for "prev") keep per-bar cost O(1), honoring the O(n²)→O(n) signal-generator fix. Loop
warmup is `range(period + 1, len(h1) - 1)`.

### Component 3 — `tools/bb_revert.py` CLI

Mirrors `tools/smc_decompose.py`. After adding the tools dir to `sys.path`, imports the
scoring helpers directly:

```python
from smc_decompose import (
    HORIZONS, aggregate_4h, _load_candles, score_variant, slice_events,
)
```

Owns: the BB `GRID`, `cmd_run`, `render_report` (BB-specific header), and `main`.

```python
GRID = {
    "bb_revert": (
        bb_revert,
        [{"period": p, "mult": m} for p in (20, 50) for m in (2.0, 2.5, 3.0)],
    ),
}
```

CLI arguments mirror `smc_decompose.py` exactly:

| arg | default | note |
|---|---|---|
| `--symbol` | `BTC/USDT:USDT` | Binance perp |
| `--tf` | `4h` | choices `1h` / `4h` / `both` |
| `--start-ms` | `1577836800000` | 2020-01-01 |
| `--end-ms` | `2000000000000` | all cached |
| `--cache-dir` | `.backtest_cache` | |
| `--out-dir` | `experiments/bb_revert` | |
| `--from-1h` | `True` | derive 4h from the 1h cache |

**Outputs:** `experiments/bb_revert/results_{tf}.json` + `REPORT.md`.

## Data flow

```
BTC/USDT:USDT 1h candles (cached)
  └─ aggregate_4h ────────────────────────────────────────► 4h candles
       for each of 6 BB configs (period × mult):
         bb_revert(candles, params) ─► raw events [(i, side), ...]
           └─ nonoverlap(.. , REF_HORIZON=12) ─► declumped events
                for h in (6,12,18,30):
                  event_outcome(candles, i, side, h, ATR=14) ─► (ret_r, mae_r, mfe_r)
                asset_stats + bootstrap_expectancy + binom_p_geq ─► per-horizon block
         score_variant ─► {params, horizons, events}
       slice_events ─► structure / side / atr_tercile / half decomposition
  └─ doc{symbol, tf, n_bars, variants, slices} ─► results_4h.json + REPORT.md
```

Every helper in the flow (`score_variant`, `slice_events`, `_load_candles`,
`aggregate_4h`, `event_outcome`, `nonoverlap`, `bootstrap_expectancy`, `asset_stats`,
`binom_p_geq`, `one_sided_lower`) already exists and is reused unchanged.

## Defaults (adopted; override by request)

- Instrument/timeframe: `BTC/USDT:USDT` @ 4h, derived from the 1h cache (`--from-1h`).
- Window: full available range, 2020-01-01 → end of cache (~6.5y).
- Directions: both LONG and SHORT, reported per-side via the slices.
- Horizons: 6 / 12 / 18 / 30 bars. Declump horizon `REF_HORIZON = 12`. ATR period 14.
- Bootstrap: 20,000 resamples, seed 20260630 (inherited from `score_variant`).

## Reporting & honesty framing

`REPORT.md` carries a **RESEARCH-ONLY** banner identical in spirit to `smc_decompose`'s:
diagnostic, not a strategy; no edge is claimed; no PASS/FAIL. Body is a per-variant
horizon table — `| variant | params | h | n | win_rate | mean_ret_r | ci95 |` — followed by
the conditional slices (structure trend / side / ATR tercile / first-vs-second half) so
any BB-reversion drift can be localized rather than averaged away.

## Testing

- **Unit — `rolling_std`:** known short series against a hand-computed population std.
- **Unit — `bb_revert`:** synthetic candle series with a controlled lower-band
  cross-down (assert a LONG fires) and an upper-band cross-up (assert a SHORT fires),
  and no events while price stays inside the bands.
- **Smoke — CLI:** `tools/bb_revert.py` produces a well-formed `results_4h.json` and a
  non-empty `REPORT.md` on a small cached slice.
- **Regression:** existing `smc_decompose` tests remain green (it is not modified).

## Risks & notes

- **tools→tools import** is slightly informal. If it proves unclean (e.g. `tools` not
  being importable as a module in some context), fall back to **Approach B**: promote
  `score_variant` / `slice_events` into `src/moonface/research/variant_score.py` and
  import from there. Deferred until needed (YAGNI).
- **Population vs sample std:** chose population (ddof=0) per classic BB; documented in
  the docstring so a future switch to sample std is a one-line, conscious change.
- **Structure slice is SMC-derived:** the "structure" conditioning label comes from
  `classify_structure` (swing-based market structure). It is a generic regime tag and is
  meaningful for BB reversion (does the fade work in trends vs ranges?), so BB reuses it
  unchanged via the shared `slice_events`.

## Open questions

None — all forks resolved during brainstorming.
