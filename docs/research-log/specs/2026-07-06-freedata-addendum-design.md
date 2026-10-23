# Final Free-Data Addendum — Measurement, Liquidity, and Non-Stationarity

- **Date:** 2026-07-06
- **Status:** DESIGN (approved in brainstorm; implementation plan to follow)
- **Scope:** the last pre-registered free-data science cycle-set. Three
  hypotheses, run one at a time, each with a permanent kill rule. If all
  three close negative, free data is unconditionally and permanently
  finished — no reopening under any future framing.

## Why this exists

The program's stop rules have fired three times (2026-06-10 conclusion,
2026-06-12 backlog, 2026-06-17 reopening closeout). A creative-direction
review (2026-07-06) asked for non-obvious, mechanism-based architectures on
the free-data axes (OHLCV, funding, basis, OI, calendar, cross-asset price).
Mapping the creative space against the ~60 closed families leaves exactly
three items whose result is **not already implied by a fired kill rule**:

1. the **time-sampling axis** — every closed test sampled in clock time;
2. the **liquidity premium** — the one documented cross-sectional premium
   class never tested (momentum, carry, beta, residual reversal all dead);
3. the **non-stationarity instrument** — three closed families failed with
   the identical signature (sign flips between time halves; candidates
   reversing in the recent sealed window: `liqrev`, `calseason`,
   `practical_full` re-eval), and no tool exists to measure whether that
   signature is detectable distribution shift.

Everything else on the creative list is excluded, with reasons in §6.

## Architecture conclusion

The best structure on free data is **not a single scoring engine and not
specialist bots behind a meta-gate**. Both shapes were tested here and died:
confluence scoring is live-but-uncalibrated (v2.2, frozen clock), regime
conditioning subtracted value in five independent tests (`regime_overlay`,
`regime_selector`, `donchian_adx`, `donchian_volregime`, `exogenous`), and
ensembles went 0/8 (`portfolio` tournament). The surviving architecture is a
three-layer **evidence pipeline**, kept unchanged:

1. **Evidence generators** — frozen, pre-registered paper threads
   (confluence v2.2, MTF forward registrations), never retuned;
2. **Validation harness** — the DSR ladder + one-touch sealed lockboxes,
   demonstrably calibrated (it rejected `mom_30`, DSR 0.83, whose sealed
   tail carried −91.6% drawdown);
3. **WAIT-default authorizer** — the participation advisor; "I don't know"
   is the standing output unless a frozen thread earns otherwise.

This addendum adds one instrument to layer 2 (H3) and runs one final science
cycle-set through the harness (H1, H2). Nothing touches layer 1 or layer 3.

## H3 — `advval`: adversarial validation as a harness instrument

Run **first** (zero lockbox spend; its verdict is an instrument for reading
H1/H2 and all future cycles, including the ~2027 options program).

1. **Behavior claimed:** none traded. Claim: the recurring IS→OOS sign-flip
   failure signature reflects *measurable* distribution shift in the
   underlying feature space, not small-sample noise.
2. **Economic/structural rationale:** crypto market structure changed
   materially inside the 3y sample (spot-ETF approval 2024-01,
   institutionalization, funding-regime compression). Distribution shift is
   exactly what a discriminator measures.
3. **Data:** existing cached free features only (OHLCV-derived, funding, OI
   metrics). Features must be stationarized (returns, z-scores, ratios —
   never raw levels such as absolute volume or price) so the classifier
   cannot win on trivial time trends. The stationarization list is frozen in
   the pre-registration before anything is computed.
4. **Forward target (two measurable outputs):**
   - (a) **adversarial AUC** per frozen feature family: a classifier
     distinguishing era-A bars from era-B bars, era split frozen at
     **2024-01-10** (spot-ETF approval), 5-fold cross-validated;
   - (b) **retrodiction** — the falsifiable claim: per-family adversarial
     AUC must rank-correlate with the *known* IS→OOS flip/no-flip outcomes
     across the already-closed families. The validation set is sealed
     history; no lockbox is spent.
5. **Failure modes:** trivially high AUC from time-trending features
   (mitigated by frozen stationarization); AUC ≈ 0.5 despite the observed
   flips (shift undetectable in these features → instrument useless);
   misuse as a post-hoc excuse machine (mitigated: its only sanctioned role
   is a pre-registered **pre-screen** for future cycles, never a rescue of a
   failed one).
6. **Validation without overfitting:** era split, feature families,
   stationarization, classifier class (gradient-boosted trees, fixed default
   hyperparameters, no tuning), and the retrodiction outcome-coding of
   closed families are all frozen in the PREREGISTRATION before any
   computation. One run.
7. **Permanent kill:** if per-family AUC bears no positive relationship to
   the known flip outcomes (pre-committed criterion: Spearman ρ ≤ 0, or its
   bootstrap 90% CI spans 0), adversarial validation is dead as an
   instrument here. The harness keeps its existing gates unchanged and no
   pre-screen is adopted.

**Promotion (if it passes):** a frozen pre-screen rule for all future
pre-registrations — any candidate whose feature family shows adversarial
AUC above the calibrated threshold must justify, in its prereg, why its
mechanism survives the measured shift. Advisory shadow diagnostics on the
live paper threads write to their own journal and never gate anything.

**ML justification (required by the brief):** the classifier predicts a
mechanical label (era membership); nothing it outputs is traded, so leakage
in the trading sense is impossible. Model drift is not a risk of the method
— it is the quantity being measured. No transparent rule can measure
multivariate distribution shift, which is the single job asked of it.

## H1 — `eventtime`: is the drawdown wall a clock artifact?

The program's one replicated finding — positive fixed-horizon drift exists,
but no bounded-risk exit harvests it within budget — was established
entirely in **clock time**. H1 attacks the finding's measurement basis, not
the signal space.

1. **Behavior claimed:** the −100R-class excursions that blew every exit are
   partly produced by clock sampling: stops sized in clock-ATR are
   systematically mis-scaled during activity bursts, exactly where
   liquidation cascades live.
2. **Economic/structural rationale:** information arrival is clustered;
   dollar-volume bars are a documented variance-stabilizing transform
   (returns closer to IID, kurtosis drops — López de Prado). If bar-level
   risk is homogenized, a per-bar-sized bracket has a structurally better
   chance of bounding the cascade tail.
3. **Data:** free Binance Vision 1m BTCUSDT-perp klines, aggregated to
   dollar bars. **One frozen bar size**, fixed by procedure (not by search):
   the median rolling dollar volume per 4h over the pre-2023 calibration
   window, targeting ≈6 bars/day so trade counts are comparable to the
   closed 4h program. The calibration window never overlaps the test window.
4. **Forward target:** net R of the frozen `donchian_break` entry (the
   program's one replicated drift carrier) through the standard 10-exit
   registry — a **paired comparison** against its already-sealed clock-time
   twin. Same ladder, same 15R-analog budget scaled to bar count, pooled
   n_trials, one-touch lockbox.
5. **Failure modes:** cascades occur *within* bars regardless of sampling
   (gap risk unchanged); any bar-size tuning converts this into a parameter
   rescue (hence one procedurally-frozen size); a pass is **research-only**
   — event-time bars close at unpredictable clock times and the paper
   engines are cron-driven, so promotion would require a separately
   registered event-driven executor before any paper thread.
6. **Validation without overfitting:** single frozen construction (one
   entry, one bar size, the standard exit registry), n_trials pooled
   honestly across all rows, one-touch lockbox tail. The control arm costs
   nothing — it is already sealed history.
7. **Permanent kill:** if no exit row improves its research MaxDD-to-net-R
   ratio by ≥50% vs its clock-time twin, or the ladder still fails end to
   end, the wall is **sampling-invariant** and the entire time-sampling axis
   (volume, tick, imbalance bars) closes forever.

## H2 — `liqprem`: the last untested cross-sectional premium

1. **Behavior claimed:** illiquid perps out-return liquid ones —
   compensation for exit-cost risk (Amihud 2002), the one premium class not
   yet fired at on this universe.
2. **Economic/structural rationale:** capital demands payment to hold
   positions that are expensive to unwind; crypto's retail-driven long tail
   plausibly amplifies the effect. Distinct from the dead sorts: momentum
   and carry (first moment), BAB (second moment), residual reversal
   (short-horizon liquidity *demand*) — this is the standing *level* premium
   for liquidity *provision*.
3. **Data:** already-ingested survivorship-clean daily klines (714-symbol
   USDT-perp universe). Amihud illiquidity = |daily return| / dollar volume,
   trailing 30d mean. No new sources.
4. **Forward target:** daily return of a beta-neutral long-illiquid /
   short-liquid quintile book, weekly rebalance, equal weight, judged on the
   existing daily-return `gate_construction` ladder.
5. **Failure modes:** the crux — the premium is defined by the very spreads
   that eat it, so costs are frozen **punitively asymmetric** (5 bps/side on
   the liquid leg, 25 bps/side on the illiquid leg); top-N-by-volume
   universes truncate the illiquid tail, so the universe uses a
   minimum-viability floor (listed ≥ 1 year AND trailing 30d median daily
   dollar volume ≥ $1M) instead of top-20; long-tail data quality and
   listing-age confounds; capacity is negligible even if real.
6. **Validation without overfitting:** `resrev`-style **cost-first
   pre-screen** — net-of-punitive-cost Stouffer Z > 0 required before the
   ladder is allowed to run; single frozen construction, n_trials = 1,
   one-touch lockbox tail.
7. **Permanent kill:** gross premium absent (Z ≤ 0) ⇒ no liquidity premium
   exists in this cross-section; gross present but net ≤ 0 under the frozen
   punitive costs ⇒ book-depth verdict class (real but unharvestable).
   Either outcome closes the **entire cross-sectional space permanently** —
   every documented premium class will then have been tested and killed.

## Sequencing and isolation

- **Order: H3 → H1 → H2.** One cycle at a time; each kill rule honored
  before the next cycle starts. Each run is a per-cycle human go (existing
  convention).
- **Artifacts:** `experiments/advval/`, `experiments/eventtime/`,
  `experiments/liqprem/` — each with a committed PREREGISTRATION (frozen
  grids, gates, kill rules, data fingerprints) **before** any real-data run.
- **Hard isolation:** never read/write `promotion/strategy.json`, the v2.2
  journal, or any frozen forward registration; never reopen closed lanes.
  No subagents for runs.
- **Pre-committed terminal rule:** these three hypotheses are the *entire*
  remaining free-data budget. If all close negative, free data is
  unconditionally, permanently finished; the program's only forward paths
  are the frozen paper threads and the maturing new-data collectors
  (Deribit options readiness ~2027-01).

## Excluded ideas, with reasons on record

From the 2026-07-06 creative-direction list, mapped against fired kill
rules:

| Idea | Status | Killed / implied by |
|---|---|---|
| Regime detection before signals | implied dead | `regime_selector` (no cell beats always_trend), `regime_overlay`, `donchian_adx`, `donchian_volregime`, `exogenous` — conditioning *subtracts*, five independent tests |
| Specialist bots + meta-gate | implied dead | the above + `portfolio` tournament (0/8 ensembles) + `ls_tournament` |
| Cross-asset confirmation / breadth | dead | breadth family — transfer was entirely crypto beta (`breadth_neutral`, decisive) |
| Funding/OI imbalance | dead | `funding_*`, `oibuild_study` (mechanism does not exist), `liqrev` — OI retired both directions |
| Microstructure / order-flow | dead | `bookdepth_study` (real gross effect, 10× under cost), `taker_flow_momentum`, aggTrades Hawkes |
| Liquidity sweep / stop-run | implied dead | SMC-flip, `liqladder`, pivot `levelbreak` |
| Vol compression/expansion | implied dead | `bb_breakout` harvest, `atr_channel_break`, squeeze variants in system search |
| Event-risk filters | dead | `macro_event` (FOMC/CPI windows, no cell near gate) |
| Adaptive holding periods | implied dead | H1/H4 exit probes, exit ablation (failure is entry, not exit), `positioning_exits` |
| Options-market information | not free-data today | Deribit collector live; admissible ~2027-01 under its own program |
| ETF/macro flow proxies | blocked | `etf-flow` Stage 0 (bot-walled); `exogenous` (FRED/DVOL) dead |
| New scoring engine / signal-quality score | out of scope | v2.2 calibration verdict stands until its clock runs out (~2027-01, ≥30 setups); trend-score repair closed negative 2026-07-05 |
| Correlation eigenstructure / funding-dispersion states | excluded | regime-conditioner class — five prior failures; result implied |

## Success criteria for the addendum as a whole

- **H3 passes:** the harness gains a calibrated non-stationarity pre-screen;
  every future prereg (including options 2027) gets cheaper and safer.
- **H1 passes:** the program's central negative finding is qualified — the
  wall is (partly) a measurement artifact, opening a *new, separately
  registered* event-time research program. No existing thread changes.
- **H2 passes:** a market-neutral paper candidate enters the standard
  frozen-forward pipeline as PAPER ONLY.
- **All fail:** the free-data question is closed with no residual ambiguity
  — the strongest possible justification for the WAIT stance, on the record.
