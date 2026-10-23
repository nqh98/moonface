# funding_fade_fwd — Forward-Program Draft Preparation: Design

**Date:** 2026-07-13
**Status:** Design approved for drafting phase. This design governs the DRAFT-PREPARATION
phase only: document drafting, pipeline construction, and a pre-cutoff dry-run. It does
NOT authorize observing market data dated after 2026-06-10, running on forward data, or
writing any verdict. Those are gated behind human sign-off (D-gate, hard stop).
**Source spec:** the `funding_fade_fwd` pre-registration-draft spec (user-supplied,
2026-07-13).

## 1. Verified authoritative facts

All verified against tracked pre-cutoff artifacts on 2026-07-13; no market data was
observed.

- Source row: `experiments/positioning_exits/20260610T065146Z/positioning_exit_probe.md`,
  row 2 — entry `funding_fade {'window': 60, 'z_thr': 1.5}`, exit
  `fixed_bracket {'k_stop': 2.0, 'm_tp': 4.0, 'atr_period': 14}`:
  research 254 trades, +64.7507R net, +0.2549R expectancy, maxDD −32.0R;
  OOS 68 trades, +76.7285R net, +1.1284R expectancy; `valid=False`.
- Row-level gate (`src/moonface/research/edge/exit_score.py::exit_gate`): research
  expectancy > 0 ✓, OOS expectancy > 0 ✓, OOS n ≥ 30 ✓, research DD ≥ −15R ✗.
  Within the row-level gate the −15R cap was the **sole** failing condition.
- Program-level second rejection reason: PROGRAM_CONCLUSION.md also rejected via the
  single-entry robustness rule (a survivor exit had to pass on ≥ 2 of 3 entries;
  fixed_bracket passed only on funding_fade). D1 must state **both** reasons. The
  forward program does not claim cross-entry robustness; it tests this single frozen
  cell on unseen forward data, which is the honest arbiter.
- Expectancy divergence: research +0.25R vs OOS +1.13R (4.4×). All power and
  ruin math in D1 uses the conservative research figure; the divergence gets an
  explicit note so the forward expectation is not anchored on the flattering number.
- Original run mechanics (`tools/positioning_exit_probe.py`): binance via ccxt,
  perp `BTC/USDT:USDT` 4h, funding symbol `BTC/USDT:USDT`, spot `BTC/USDT` (used
  only by basis entries — the forward program needs perp + funding only), window
  = 3 years ending at the run stamp (2026-06-10T06:51:46Z), `oos_tail_bars=1095`,
  `warmup=60`, `future_bars=48`, cache `.backtest_cache`.

## 2. Governance ruling (recorded 2026-07-13, human-approved)

`experiments/funding_fade_voltarget/PREREGISTRATION.md` (frozen 2026-07-01, closed
negative same day) carries the kill rule "no v2, no fraction grid, no budget
relaxation" and its verdict declares the lane terminal for funding_fade +
fixed_bracket. The human ruled the **narrow scope** reading: that kill rule bound its
own lane (the vol/risk-targeting lever, ETH/SOL, historical OOS). `funding_fade_fwd`
is the successor PROGRAM_CONCLUSION.md explicitly recorded as "the one open question
this program did not answer, by design" — BTC, forward-only data, fixed-fractional
sizing, DD budget as the single changed variable. D1's citation section must cite the
voltarget kill rule, quote it, and record this dated ruling distinguishing the two.

## 3. Architecture

One thin frozen runner; every numeric code path is the SAME code that produced the
original row.

| Component | Source | New? |
|---|---|---|
| OHLCV + funding ingestion | `moonface.foundation.data.fetch_history`, `moonface.foundation.series.{FundingCache, fetch_funding_history, align_funding}` | reused |
| Entry signal | `moonface.research.edge.funding_signals.make_funding_fade` | reused |
| Exit simulation | `moonface.foundation.exits.EXIT_REGISTRY["fixed_bracket"]` | reused |
| R accounting | `moonface.research.edge.exit_score.{exit_r_streams, summarize_r}` | reused |
| Runner + window clamp | `tools/funding_fade_fwd.py` (+ `src/moonface/research/funding_fade_fwd.py`) | new |
| Null generator (per-segment shuffle) | new module, small | new |
| Block-bootstrap CI + ruin/TUW analysis | new module, small | new |
| Report writer | new, mirrors existing probe report style | new |

New code never re-implements simulation or accounting — it only windows, orchestrates,
resamples completed trade-R streams, and formats.

### Data-hygiene mechanics (spec §3)

- The runner takes explicit `--start`/`--end`; there is no `now()` default (the
  original runner's `end_ms=now` is the one behavior deliberately not inherited).
- Dry-run mode enforces a hard clamp at the burned-data boundary: the original run's
  `end_ms` (2026-06-10T06:51:46Z — data up to that stamp was observed by the original
  program and is already burned; the forward window starts exactly there, no gap, no
  overlap). Any requested or fetched candle/funding point past the clamp aborts the
  run before any summary is printed. The clamp is enforced at the data-return
  boundary, not just on arguments.
- The shared `.backtest_cache` already contains post-cutoff data written by other
  lanes; the clamp filters reads, and no dry-run output ever includes post-cutoff
  rows. Cache contents are never displayed; only clamped aggregates are.
- Accidental exposure → STOP, written report, await human decision (spec §3).

## 4. Sequence (resolves a dependency hidden by spec §7 ordering)

The DD-budget bootstrap and the power calculation need the **per-trade R stream**,
which only the pipeline can regenerate (the archived JSON holds aggregates only). So
drafting and dry-run interleave:

1. Build runner + clamp + tests (no data).
2. **Dry-run reproduction** on pre-cutoff data only: reconstruct the original window
   (3y ending 2026-06-10T06:51:46Z, tail 1095 bars, warmup 60, future_bars 48) and
   reproduce row 2. Tolerance: exact trade counts (254 / 68) and R figures equal to
   the archived values at their reported precision. Any miss = STOP and ask (spec
   §5.2); no silent patching.
3. Pre-cutoff analysis on the regenerated trade stream: DD-budget candidates, TUW,
   capital-at-risk, P(ruin), power calc for N.
4. Draft D1 (`REGISTRATION_DRAFT.md`), D2 (`PIPELINE_FREEZE_PLAN.md`), D3
   (`STATUS.md`) with real numbers.
5. Null-calibration guard run on pre-cutoff data (guard must FAIL on nulls).
6. Present drafts + candidates → **HUMAN SIGN-OFF (hard stop)**. Freeze identity_hash
   (sha256 over canonical JSON of rules + all frozen parameters, per the
   MOE_ORTHO convention), pipeline commit hash, DD budget, verdict trigger.

## 5. Forward-evaluation model (Approach A — chosen)

Single retroactive evaluation at trigger time. No collector, no daemon, no cron.
Binance 4h klines and funding history are retrievable years back (Binance Vision as
archive fallback). The delisting/feed-loss risk this accepts is precisely what the
pre-committed VOID rule covers. Rejected alternatives: (B) blind cron collector —
ops burden, larger freeze surface, five months of accidental-observation risk;
(C) reuse of confluence paper-daemon infra — spec non-goal, cross-contamination.

## 6. Pre-committed evaluation parameters (proposed; human may adjust at sign-off)

- **Sizing:** fixed fractional f = 0.01 of initial equity per trade; R defined
  identically to the original program (bracket stop distance = 1R). No compounding,
  no equity scaling.
- **DD-budget candidates:** −40R, −50R, −64R (2× research DD). For each: block-
  bootstrap P(budget hit within horizon) under (a) measured-edge resampling and
  (b) zero-edge (demeaned) resampling; historical time-under-water on the
  pre-cutoff path; capital-at-risk at f = 0.01 stated in percent of initial equity
  (−50R ≈ −50%; the known research path already implied −32%). Human chooses; the
  draft does not pre-select.
- **Verdict trigger (later-of):** N completed trades with N from the power
  calculation at the conservative research expectancy (+0.25R) — N chosen so a 95%
  CI excludes 0 with ~80% power if the research-level edge is real (expected
  N ≈ 120, finalized from the regenerated stream's σ) — OR 12 months from sign-off.
  One verdict, written once. No interim aggregate-P&L peeking.
- **Success (EDGE FOUND):** 95% block-bootstrap CI on per-trade expectancy excludes 0
  from above AND cumulative R > 0 at verdict time.
- **Kill (terminal):** cumulative R ≤ chosen DD budget at any point in the window.
- **VOID (distinct from KILL):** > 5% of the forward window unreconstructible from
  feed + archive; or BTC USDⓈ-M delisting; or a structural funding-mechanism change
  (interval or formula), each with a dated note.
- **Null-calibration guard:** per-segment shuffled series (gap structure preserved;
  missing periods dropped, never interpolated or zero-filled) through the identical
  frozen pipeline; guard passes only if ≥ 95% of null runs FAIL the success
  criterion. Run and reported before the real forward evaluation is trusted.
- **Ambiguity protocol:** verdict-affecting ambiguity found after forward data is
  observed VOIDS the cycle; non-gating ambiguities get dated notes; arbitrary
  verdict-affecting conventions resolve toward KILL.

## 7. Testing

- Unit tests: window clamp (rejects post-cutoff timestamps at the data boundary),
  null generator (gap preservation, no fill), bootstrap CI (degenerate inputs — the
  capitulation-lane lesson), report writer.
- Integration test: dry-run reproduction of row 2 is itself the acceptance test.
- Convention: project test/CLI conventions per `moonface-workflow-conventions`.

## 8. Non-goals (reaffirmed from spec §6)

No parameter changes or sweeps; no filters or overlays; no moonface-feed integration;
no liquidation/Deribit collector analysis; no verdict of any kind in this phase.
