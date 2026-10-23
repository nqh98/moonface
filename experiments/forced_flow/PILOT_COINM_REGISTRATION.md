# forced_flow — COIN-M Pilot Registration (DRAFT — awaiting human sign-off)

- **Date drafted:** 2026-07-13
- **Status:** FROZEN — approved 2026-07-13. Design only. **No pilot code exists and none may
  be downloaded, and nothing may run until a human approves this frozen registration** (D3
  gate). Approval must be recorded by changing this Status line to FROZEN with the date.
- **Lane relation:** separate pilot under the forced_flow line; the main USDⓈ-M lane stays
  blocked until ~2027-01-09 per `STAGE0_FEASIBILITY.md`.

## Evidence-weight clause

This pilot runs on a different instrument (BTCUSD_PERP COIN-M), a single era, with throttled
magnitude. Its only possible outcomes are KILL (kills the gravity-well hypothesis) or WEAK
SUPPORT (updates the prior for the main USDⓈ-M lane). It CANNOT validate the hypothesis, and
no result from it licenses any promotion, signal emission, or "EDGE FOUND" claim.

## Claim under test

BTCUSD_PERP forward returns may stratify by realized forced-liquidation flow (cluster
presence, direction, imbalance) — a directional read on the gravity-well mechanism (concept
spec §2.2) and nothing more.

## Data (keyless Binance Vision only)

- Liquidations: `data/futures/cm/daily/liquidationSnapshot/BTCUSD_PERP/`,
  2023-06-25 → 2024-10-14 (472 files, 478-day span, coverage 0.987, 6 missing days —
  missing days are dropped, never interpolated). Exact-duplicate rows are dropped
  (duplicates observed in Stage 0). Archive is frozen and throttle-sampled; magnitude is
  undercounted by construction.
- Price: Binance Vision `cm` klines, BTCUSD_PERP, **1h**, same window.
- **Nothing else.** No funding, no OI (Axis F is VOID per D1 §1). No candle-derived
  liquidation proxies (banned). No sealed data; the program lockbox is not touched.

## Frozen parameters (complete — any post-run change voids the lane)

| Parameter | Frozen value |
|---|---|
| Bar size | 1h |
| `liq_count` | number of liquidation prints in the bar (after dedupe) |
| `liq_imb` | (BUY-side print count − SELL-side print count) / max(total prints, 1). BUY-side forced order = short position liquidated (forced buying); SELL-side = long liquidated (forced selling) |
| `liq_burst_z` | z-score of log(1 + `liq_count`) on a trailing 30-day causal window (720 bars; min 240 bars of history before any episode is eligible) |
| Episode entry | first bar with `liq_burst_z ≥ 2.0` after ≥6 consecutive bars with `liq_burst_z < 2.0` (re-arm rule) |
| Episode direction | sign of `liq_imb` on the entry bar; `liq_imb = 0` → episode discarded |
| Outcome | BTCUSD_PERP log close-to-close return over H = 24 × 1h bars from episode-entry close |
| Buckets | direction (up/down) × tercile of `liq_burst_z` at entry (terciles over all episodes) — ≤6 buckets |
| Power floor | n ≥ 30 per bucket; buckets below the floor are excluded; **< 2 qualifying buckets → verdict `UNDERPOWERED_KILL`** (no threshold re-tuning to manufacture power) |
| Spread statistic | mean outcome of top qualifying bucket − mean outcome of bottom qualifying bucket (buckets ranked by mean outcome) |
| Null iterations | 1000 per null; threshold p97.5 |
| RNG seed | 1337 (all resampling) |
| Split-half boundary | episodes entered 2023-06-25→2024-02-15 vs 2024-02-16→2024-10-14 |

## Pre-data amendments (2026-07-13)

- Tercile ties: stable ordinal assignment by (`liq_burst_z`, `bar_index`) — deterministic and reproducible.
- p97.5: empirical quantile with higher interpolation. Where a convention is arbitrary, the frozen choice must bias toward KILL — a slightly higher null threshold makes the gate strictly harder to pass, never easier.
- Missing archive days: drop the missing day and its bars; never zero-fill. Procedurally, a frozen registration is never amended to match code: code is corrected to match the registration. Methodologically, zero-filling fabricates observations, deflates the 30-day rolling mean/std, inflates neighboring burst-z values, and can manufacture episodes — an error biased toward passing that violates the KILL-bias principle.
- Gap adjacency: an episode is eligible only if both its trailing 720-bar z-window and its forward 24-bar outcome horizon contain zero dropped days. Episodes touching a gap are discarded. Where gap handling is arbitrary, this convention biases toward fewer episodes (toward KILL/UNDERPOWERED_KILL), never more. The rolling z-window is computed on the contiguous bar series only; it never spans across a gap by concatenation.
- Null gap structure: nulls preserve the exact gap structure of the real data so the identical frozen pipeline applies to real and null runs; concatenation is prohibited because it fabricates continuity and exempts nulls from real-run rules.
- Circular shift: perform independently within each contiguous segment; each iteration draws an independent uniform offset per segment from the seed-1337 stream, with every offset at least 30 days. Segments shorter than 60 days are excluded from episode eligibility in the real run and all nulls, biasing toward KILL/UNDERPOWERED_KILL.
- iid return null: resample returns with replacement and rebuild a synthetic price path independently per segment, preserving each segment length and the overall gap structure; run the full frozen pipeline on those segmented paths.
- Episode pooling: pool episodes from all qualifying segments before bucketing and spread computation in the real run and every null.
- Timeline: the real archive was downloaded and its filenames/schema were inspected, but no pilot analysis was run; this conflict originated from document review, not from data observation.
- Variance: use sample variance (`ddof=1`) for the causal z-score. The larger denominator lowers z-scores and biases toward fewer episodes (KILL direction).
- Undefined z-bars: they are ineligible for entry and reset the re-arm streak; re-arming requires 6 consecutive valid sub-threshold bars, biasing toward fewer episodes (KILL direction).
- Tercile boundaries: use the implemented ordinal rule `min(2, 3 * rank // n)`; deterministic and frozen.
- Circular-shift range: use `[720, segment_length - 720]`; the symmetric upper exclusion prevents near-identity shifts at both ends and refines the 30-day minimum.
- RNG streams: use independent deterministic streams per null, derived from base seed 1337 and the null name (`label`, `circular`, `iid`), preventing cross-null coupling.
- Null power: discard null draws with fewer than 2 qualifying buckets and report discard counts. If more than 50% of any null's draws are discarded, return `SUSPECT_HARNESS`; powered draws alone define p97.5.
- Verdict precedence: `SUSPECT_HARNESS` → `UNDERPOWERED_KILL` → `KILL` → `WEAK SUPPORT`.
- Zero-row liquidation archive: an existing zero-row file is an observed zero-liquidation day; an absent file is a gap.
- Missing 1h kline bars: treat them as gaps under the same drop and gap-adjacency rules; never interpolate. If kline gaps exceed 1% of window bars, stop before the run and report the data-quality failure.
- Horizon endpoint: include an episode whose entry plus 24 bars lands exactly on the final bar.
- UTC window and ordering: inclusive UTC `2023-06-25 00:00` through `2024-10-14 23:00`, with chronological segment ordering.
- Archive downloaded to /tmp on 2026-07-14; filenames, counts, and schemas inspected; no liquidation or price observations analyzed before the amendment window closed.

The tercile and p97.5 conventions were resolved before any real archive data was downloaded or observed; the iid guard was built and proven on synthetic data only at the time of that amendment. The gap-adjacency amendment was resolved after download and schema inspection but before any pilot analysis.

### Post-window clarification (2026-07-14; non-gating, cannot affect verdict space)

Split-half consistency is descriptive supporting evidence only, never a pass condition. Identify the globally top and bottom qualifying buckets once from the full pooled episode set, ranked by mean outcome. In each half, compute the spread between those same fixed buckets. Report whether each half-spread is positive; if either fixed bucket has fewer than 10 episodes in a half, report `NOT_EVALUABLE` for that half. This clarification cannot affect the verdict space or any gate.

## Gate-0 battery (all three required)

1. **Label shuffle:** permute episode outcomes across episodes 1000× (seed 1337); real spread
   must exceed the p97.5 shuffle spread.
2. **Circular shift:** circularly shift the liquidation feature series against the price
   series by 1000 uniformly-drawn offsets (≥ 30 days each, seed 1337); real spread must exceed
   the p97.5 shifted spread.
3. **iid null-calibration guard:** run the identical frozen pipeline on directionless
   iid-resampled returns (returns resampled with replacement, seed 1337, price path rebuilt).
   The gate must **FAIL** on this null. If it passes, the verdict is `SUSPECT_HARNESS` —
   debug only, no hypothesis interpretation (vol_compression lesson: a gate that passes on
   null is measuring its own selection bias).

## Single-era honesty

No lockbox exists or is claimed — the archive ends 2024-10-14 and the whole window is one
open sample inside a single market era. The split-half sign check (top-minus-bottom spread
sign agrees in both halves) is **supporting evidence only, never a pass condition**.

## Verdict space and kill rules (terminal; one cycle; verdict written once)

- Any Gate-0 condition fails → **KILL** (gravity-well prior down-weighted; recorded).
- < 2 qualifying buckets → **UNDERPOWERED_KILL**.
- iid guard passes → **SUSPECT_HARNESS** (no verdict on the hypothesis).
- All conditions pass → **WEAK SUPPORT** — nothing more, per the evidence-weight clause.
- No second cycle, no parameter changes, no added features after the run. A null is archived
  as-is; no rescue by adding bodies.

## No-promotion clause

If the pilot passes, the sole next step is running the main forced_flow lane when USDⓈ-M
data matures (~2027-01-09); nothing connects to the live v2.2 engine (hash `b4924f8e…`),
Telegram, or any decision-emitting journal.
