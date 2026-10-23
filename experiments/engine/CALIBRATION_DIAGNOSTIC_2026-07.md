# Confluence Engine v2 — Score-Calibration Diagnostic (2026-07)

**STATUS: CRITERIA FROZEN (pre-run). Results section empty until the single
registered run completes; criteria may not change afterward.**

Spec: `docs/research-log/specs/2026-07-04-v2-calibration-diagnostic-design.md`
Tooling: `src/moonface/signal/engine/calibration.py`, `tools/engine_calibration.py`
Engine identity: frozen v2, `engine_hash
10bb5a442758e1c1387b0518c0dfb8f2a23f3954bbc262f9a4adc275b1fe16cf` — this lane
is READ-ONLY: no frozen constant, config, journal, or registration text is
touched, and the forward-paper clock is unaffected.

## The one question

Does the v2 confluence score order trade outcomes on history? If score buckets
do not order by expectancy, the weights are noise and no threshold placement
can fix it.

## Registered run (frozen)

- Command: `.venv/bin/python -m tools.engine_calibration
  --start-ms 1577836800000 --end-ms 1782316800000 --warmup 6000
  --out experiments/engine/calibration_report_2026-07.json`
- Data: cached `BTC/USDT:USDT` 1h perp (`.backtest_cache`), 2020-01 →
  2026-06; series fingerprint recorded by the tool in the report JSON.
- One run. Re-runs are permitted only for mechanical failure (crash,
  truncated data), never to revisit a completed result.

## Frozen criteria (spec §4c, verbatim semantics)

- **Primary, per book (TREND and MEAN_REVERT separately):** Spearman ρ between
  score-at-entry and net R over the overlapping hypothetical-trade panel.
  *Pass* = ρ > 0 with 95% moving-block-bootstrap CI excluding 0 (block 168
  bars, 1000 draws, seed 20260704), AND bucket mean net R weakly increasing
  across score buckets <40, 40–59, 60–74, ≥75 (point estimates; empty buckets
  skipped), AND sign of ρ agrees across the first/second halves of the scored
  span (midpoint split).
- **Power floor (applies regardless of pass/fail):** a book with < 200 panel
  events, or < 30 events at score ≥ 60, is UNDERPOWERED.
- **Verdict (one, written once):** CALIBRATED = both books pass;
  PARTIALLY_CALIBRATED = exactly one passes; UNCALIBRATED = neither passes
  and at least one affirmatively fails; UNDERPOWERED = both books below the
  floor.
- **Reported, never gated:** policy / direction / vol-state splits;
  non-overlapping stream ρ (robustness); reversal-sensitivity bound;
  per-module rank-IC table (SECONDARY suspect-ranking only — fixed-horizon
  drift is not evidence of tradeable quality in this program's record).

## Assumptions (first-class caveats)

1. `deriv=None`: the verdict covers the PRICE-STRUCTURE core only (trend book
   caps at 85/100; revert book lacks its two derivative modules). The live
   engine additionally sees derivatives confirmation.
2. Sub-threshold hypothetical trades are counterfactual — the engine never
   takes them; they exist to measure score ordering.
3. Primary panels omit the opposite-SETUP reversal exit (undefined
   sub-threshold); the reversal-sensitivity block bounds the distortion on
   the actual-trigger subset.
4. Extreme-vol bars are excluded from entries (frozen `decide()` stands flat
   there at any score); excluded counts are reported.

## What this diagnostic can and cannot conclude

It interprets the frozen forward record's meaning (is the score measuring
anything?). It CANNOT: validate an edge, recommend constant changes, or
trigger any engine action. Any future v2.1 is a separate human decision
requiring a new ENGINE_VERSION → new hash → new registration.

## Results (registered run, 2026-07-04)

Report JSON: `experiments/engine/calibration_report_2026-07.json` (exit 0).
Data: 56,800 candles; 50,800 scored bars; first scored bar 1599436800000
(2020-09-06, full 6000-bar window → macro gate live from bar one); last bar
1782313200000; series fingerprint sha256 `fedf68d49ad3ac17…` (full value in
the JSON). Engine hash at run time: `10bb5a44…` (frozen registration hash).

### TREND book — status: fail

- Panel: 46,529 events (31 incomplete excluded, 402 extreme-vol skipped);
  score ≥ 60: 2,301. Floors met → affirmative fail, not underpowered.
- Spearman ρ = 0.052, 95% block-bootstrap CI [0.0223, 0.0805] — positive and
  CI excludes 0. Halves: 0.0321 / 0.0605, sign stable.
- Buckets (mean net R): [0,40) −0.0625 (n=34,671); [40,60) +0.0987 (n=9,557);
  [60,75) +0.1283 (n=2,265); ≥75 **−0.1529 (n=36)**. Weak monotonicity FAILS
  at the ≥75 bucket → primary criterion fails.
- Non-overlapping stream: 1,928 events, ρ = 0.0498 (agrees with panel).
- Reversal sensitivity (triggered subset, n=2,301): no-reversal net
  +285.09R vs with-reversal +401.15R (gap +116.06R) — the no-reversal
  assumption is conservative for this book.
- Splits: LONG +0.0683 (n=26,933) vs SHORT −0.1418 (n=19,596);
  ALLOW −0.0200 (n=40,305) vs REJECT (vetoed-shadow) −0.0211 (n=6,224);
  high-vol +0.2102 (n=5,511) vs normal −0.0511 (n=41,018).

### MEAN_REVERT book — status: fail

- Panel: 31,801 events (3 incomplete, 266 extreme-vol skipped); score ≥ 60:
  2,314. Floors met → affirmative fail.
- Spearman ρ = −0.0029, CI [−0.0237, 0.0178] — indistinguishable from zero.
  Halves: −0.0036 / −0.0042.
- Buckets (mean net R): [0,40) −0.2419; [40,60) −0.1993; [60,75) −0.1706;
  ≥75 −0.2326 (n=960). Not monotone; EVERY bucket deeply negative under the
  book's own CT exit discipline.
- Non-overlapping stream: 4,014 events, ρ = −0.0079.
- Reversal sensitivity (n=1,714): −431.57R no-reversal vs −459.28R
  with-reversal (gap −27.71R) — negative either way.
- Splits: LONG −0.2301 / SHORT −0.2335; ALLOW −0.2402 / ALLOW_CT −0.2226;
  high-vol −0.1393 / normal −0.2437.

### Module IC (SECONDARY, suspect-ranking only)

No module has |NW t| ≥ 2. Strongest: m1_macro rank-IC +0.0259 (t 1.50),
m3_divergence −0.0169 (t −1.52); everything else |IC| < 0.015. The three
derivative modules are None by construction (deriv=None). Nothing is
individually predictive at the 24-bar horizon.

## Verdict

**UNCALIBRATED** (both books affirmatively fail the frozen primary criterion
at ample power).

Within this diagnostic's bounds: on the price-structure core over 2020-09 →
2026-06, the v2 confluence score does not order trade outcomes to the
registered standard. The MEAN_REVERT book shows no ordering at all (ρ ≈ 0)
and is uniformly negative under its own exit discipline at every score level
— its sub-book ≥ 0 forward requirement looks historically improbable. The
TREND book carries a small, CI-clean, half-stable positive ordering
(ρ ≈ 0.05) through the first three buckets, but the Tier-A region (≥75,
n=36) inverts, so the frozen monotonicity requirement fails; what ordering
exists is concentrated in LONG direction and high-vol bars. The macro gate's
vetoed-shadow trades performed the same as allowed trades in this panel
(−0.021 vs −0.020 mean R) — no historical evidence the gate adds or destroys
value; the forward gate-ablation report remains the binding test. This
diagnostic recommends no constant change and triggers no engine action; the
frozen forward-paper record continues unchanged and remains the only test of
the engine's selectivity-plus-discipline proposition.
