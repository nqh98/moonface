# Research backlog — post-program reboot (2026-06-12)

Mandate: find the most credible source of profitable futures trading signals.
No prior architecture or assumption is protected. Items are ranked by expected
value against implementation cost; each carries a pre-committed validation
gate and a kill rule. An item that fails its rule is closed, not retried with
variations — that discipline is the only thing that kept 58 domains honest.

## Ground truth this backlog is built on

- Eleven probe cycles plus 58 registered research domains have closed every
  single-asset directional family on free BTC/ETH/SOL data: price TA (trend,
  breakout, mean-reversion, pivots, SMC), funding, basis, OI/positioning,
  ETH→BTC lead-lag, relaxed (MAR-judged) budgets, and multi-asset price
  transfer. Strongest corrected signal ever produced: `oi_build_momentum`
  DSR 0.30 against the 0.95 gate (`docs/findings/PROGRAM_CONCLUSION.md`).
- The one replicated structural finding: positive fixed-horizon drift exists,
  but no bounded-risk exit harvests it — the drawdown wall is
  signal-independent for single-asset directional exposure.
- Ranking implication: further entry/exit/sizing variations on single assets
  have ~zero expected value. Credible remaining ideas must either
  (a) confirm the one strongest signal on independent data, or
  (b) change the portfolio structure so the wall no longer binds
  (cross-sectional, market-neutral) rather than fight it head-on.

## Ranked backlog

### 1. `positioning_transfer` — oi_build_momentum on ETH/SOL metrics  [CLOSED NEGATIVE 2026-06-12]

**Verdict:** clean run (0 errors, 38 rejected, 2 anomalies, lockbox untouched);
no row reached the 0.95 DSR gate, so the kill rule fires: the positioning
family is terminal on every feasible asset, no v2. **Honest footnote:** this
was the program's closest-ever miss, replicated on both independent assets —
ETH DSR 0.933, SOL DSR 0.890 (prior all-time best was BTC's 0.30), both led
by the same `breakeven_horizon` exit shape. Three assets now show the same
mechanism below threshold. Per the rule this is recorded, not pursued; whether
a *new* program with a pre-registered cross-asset aggregation test is
warranted is a human decision, not a backlog item.

- **Hypothesis:** the OI-build momentum mechanism that led positioning_btc
  (DSR 0.30) is real and therefore appears on independent assets' metrics
  archives, not just BTC's.
- **EV / cost:** low-to-moderate EV (single prior result, mechanism-chosen
  direction; the ap_* precedent says version-bumping winners usually dies) /
  **lowest cost on the board** — engine, entries, exits, and gates all exist;
  only the frozen 40-spec grid and the ETH/SOL Vision metrics backfill are new.
- **Pre-registration:** 2 assets × 2 frozen oi_build entries × the standard
  10-exit registry × f=0.01 (grid in `positioning_transfer_grid()`,
  registered 2026-06-12, window frozen 3y back, final 20% lockboxed).
- **Gate:** the standard ladder — screen, OOS, lineage-deflated DSR ≥ 0.95,
  one-touch lockbox tail.
- **Kill rule:** closed_negative ⇒ the positioning family is terminal on every
  feasible asset; no v2, no parameter rescue.

### 2. Cross-sectional momentum / carry long-short over a perp universe  [CLOSED NEGATIVE 2026-06-12]

**Verdict** (`experiments/xsection/report.md`, 714 symbols with data,
survivorship-clean): all three constructions fail. `mom_7` and `carry_7` die
in the OOS holdout (drawdowns −51%/−35% against the −30% budget). `mom_30`
passes screen and holdout (MAR 3.19) but is rejected at DSR 0.83 vs 0.95 —
and its never-selected lockbox tail *ratifies* the rejection emphatically:
−91.6% tail drawdown, MAR −0.97. The gate refused a strategy that would have
been ruinous live; this is a true negative, not a near-miss. Kill rule fires;
the family is closed.

- **Hypothesis:** ranking the top-N USDT perps and holding a market-neutral
  decile long-short (momentum rank; separately, funding-carry rank) earns
  positive OOS risk-adjusted return. This is the only family left with strong
  external evidence (the most replicated anomaly in the crypto cross-section
  literature) and it is structurally exempt from the program's drawdown-wall
  finding, which binds single-asset directional exposure.
- **EV / cost:** moderate EV / **high cost** — needs universe ingestion
  (Binance Vision daily klines, free), funding accrual accounting, and a
  portfolio-level backtester; the per-trade bracket engine does not apply.
- **Pre-registration (frozen before any data look, expand only via new
  version):** universe = top 20 USDT-margined perps by rolling 30d quote
  volume, listed ≥ 1 year, rebuilt monthly; weekly rebalance; rankings =
  trailing 7d and 30d return (momentum) and trailing 7d mean funding (carry);
  long top quintile / short bottom quintile, equal weight; costs = 5 bps taker
  per side + actual funding; judged on holdout MAR and the same DSR ≥ 0.95
  gate with a frozen 20% lockbox tail.
- **Kill rule:** if neither momentum nor carry construction clears the gate,
  close the family — and with it the free-data signal program (condition
  below), because no remaining family has comparable external priors.

### 3. Delta-neutral funding carry (long spot / short perp)  [PARKED]

- **Hypothesis:** none — this is harvestable yield, not signal alpha. Real
  desks run it; returns are small, decaying, and exposed to basis blowouts.
- **EV / cost:** known-positive but low EV / moderate cost.
- **Why parked:** the mandate asks for trading *signals*. Pursue only on an
  explicit human re-scope from "signals" to "any return stream."

## Not on the backlog (and why)

- **More single-asset entry/exit/sizing variations** — implied dead by 58
  closed domains; zero EV.
- **HF / microstructure** — execution assumptions dominate any free-data
  backtest; not honestly validatable in this harness.
- **On-chain, sentiment, news** — no free point-in-time-clean history, so not
  OOS-testable (the same standard that shelved OI until the Vision archive
  was found).
- **LLM/autopilot self-optimization** — produced artifact champions (−99.93%
  holdout drawdown); it is a hypothesis generator, never a validator.

## Program-level stop rule (pre-committed)

Items 1 and 2 are the entire budget: two cycles. If both close negative, the
honest output of this codebase is the WAIT advisor plus a validated research
harness, and further signal work requires *new data* (paid, proprietary, or
higher-frequency with real execution modeling) — not new searches over the
same free series.

**STATUS 2026-06-12: FIRED.** Both cycles closed negative on the same day
they were registered, with clean runs and untouched-until-spent tails. The
backlog is empty by rule. Two facts the next program (if any) should start
from: (a) the OI-build mechanism scored DSR 0.93/0.89/0.30 on three
independent assets — sub-threshold everywhere, but the only family that ever
replicated; a pre-registered *pooled* cross-asset test is the one honest
design left on free data. (b) The validation harness is demonstrably
calibrated: the single construction the DSR gate rejected this cycle
(`mom_30`, DSR 0.83) carried a −91.6% drawdown in its sealed tail.

**ADDENDUM 2026-06-12 (later the same day):** the human authorized the
pooled cross-asset OI-build mechanism study as a separate science program
(`experiments/oibuild_study/`). Verdict: **mechanism does not exist** —
16 fresh assets, ~963 non-overlapping events, pooled mean directional
return −0.64% per event, sign test 8/16 (a coin flip), Stouffer Z −1.02,
and every pre-registered slice (horizons, lookback, costs, liquidity,
time halves, leave-one-out) non-positive. The BTC/ETH/SOL DSRs are
attributed to selection + multiple-comparisons in the exit-grid search.
**The OI-build lineage is permanently retired.** Nothing remains on free
data; the program conclusion above is now unconditional.

---

# 2026-06-17 reopening — new-mechanism families (human-authorized)

The closed program above exhausted *directional* alpha. The reopening targets a
different question: are there profitable mechanisms that are **not directional
prediction at all** — market-neutral mean-reversion, second-moment sorts, or
clock-structural effects — and therefore structurally exempt from the
drawdown wall? Same discipline: one frozen construction per cycle, pre-committed
gate + kill rule, one-touch lockbox tail, a near-miss is a reject.

## Cycle 3. `bab` — betting-against-beta / low-vol cross-sectional  [CLOSED NEGATIVE 2026-06-17]

**Verdict** (`experiments/bab/`, single construction `bab_60`, n_trials=1,
714 symbols, one-touch tail spent): the low-beta-long / high-beta-short
beta-neutral book shows the anomaly *in-sample* (screen +0.00164/day, research
MAR 1.93) but **reverses out of sample** — holdout MAR −0.48 / DD −0.45 (blows
the −0.30 budget), fails stage 2, never reaches DSR; the spent lockbox tail
ratifies (MAR −0.94, DD −0.69). Same shape as `mom_30`. **Falsified:** the
BAB/leverage-constraint premium does not survive net of costs on this universe;
with momentum/carry already dead, *both* signed first- and second-moment
cross-sectional risk premia are now closed. Kill rule fired — no lookback grid,
no v2. Harness (`src/moonface/research/bab.py`, `tools/bab.py`) reuses
`xsection.build_universe` + `gate_construction` unchanged.

## Ranked next candidates (designs frozen-ready; run is per-cycle human go)

These are the only mechanistically-new hypotheses judged worth budget. Ranked by
expected information gain × novelty × P(real edge) ÷ cost. Each carries a
pre-registration sufficient to freeze and a kill rule. **None has been run** —
running spends a lockbox and is a per-cycle decision.

### 4. `resrev` — cross-sectional short-term residual reversal (stat-arb)  [CLOSED NEGATIVE 2026-06-17]

**Verdict** (`experiments/resrev/`, daily form per the declared feasibility
deviation, single construction `resrev_1`, n_trials=1, 714 symbols, one-touch
tail spent): the cost-first pre-screen fails on the **gross** series — research
mean −0.000318/day, Z −0.18 (a coin flip) — so the ladder never runs. This is
the *gross-effect-absent* branch, not the cost-eaten one: one-day idiosyncratic
reversion does not exist on the top-20 perp universe; the −5 bps/side daily
turnover only deepens it to net −0.00125/day (Z −0.71). Distinct from book-depth
(real gross effect killed by cost) — here there is no gross premium to begin
with. Kill rule fires: no horizon grid, no lookback grid, no v2. With momentum
(continuation) and reversal both dead and BAB dead, the cross-sectional
mean-reversion and risk-premium spaces are now closed on this universe.

- **Hypothesis:** after removing market (index-beta) return, a perp's
  idiosyncratic residual return mean-reverts over 1–3 bars; a market-neutral
  book short of recent idiosyncratic winners / long recent idiosyncratic losers
  earns positive OOS expectancy.
- **Mechanism:** liquidity-demand shocks (single-name unwinds, liquidation
  wicks) push a perp off its peer-implied fair value; liquidity providers who
  absorb the flow are paid the reversion. This is the *inverse* of momentum
  (continuation of informed flow) at a shorter horizon on the *residual*, not
  the raw return — distinct from the dead `xsection` momentum/carry sorts.
- **EV / cost:** highest information gain of the three / medium cost — reuses
  `bab`'s `return_series`/`index_returns`/beta machinery and the daily-return
  `gate_construction`; new code is the residual computation and a 4h calendar.
- **Pre-registration (freeze before data look):** same top-20 monthly universe,
  **4h bars**; each bar regress each name's last-bar return on the
  contemporaneous index return, residual = ret − β·index; rank by trailing
  1-bar residual; **long bottom decile / short top decile**, equal-weight,
  beta-neutralized, hold 1 bar; 5 bps/side. One horizon, one lookback,
  n_trials = 1.
- **Gate (cost-first, then the standard ladder):** because turnover is high, a
  **necessary pre-screen**: net-of-cost Stouffer Z > 0 at ≥ 5 bps/side *before*
  the ladder runs (the book-depth post-mortem killer — gross Z 2.07 but 10×
  under cost). Then screen / holdout MAR > 0, DD ≥ −0.30 / DSR ≥ 0.95 /
  one-touch tail MAR ≥ 1.0.
- **Kill rule:** gross effect absent ⇒ idiosyncratic reversion does not exist
  here; gross present but net < 0 ⇒ the premium is entirely eaten by perp costs
  (book-depth verdict class). Either closes the cross-sectional mean-reversion
  space; no v2.

### 5. `liqrev` — liquidation-cascade reversion  [CLOSED NEGATIVE 2026-06-17]

**Verdict** (`experiments/liqrev/`, 4h form, 16 confirmation assets from the
volume-ranked queue with BTC/ETH/SOL excluded, joint price-shock + OI-collapse
event, fixed horizon h=6, one-touch tail spent): the pooled net-of-cost mean
reversion is **+0.229%/event** — positive, so not `mechanism_does_not_exist` —
but it misses the frozen gate on **both** co-primary axes: Stouffer
**Z = 0.92** (gate >2) and breadth **9/16** assets positive (gate ≥12),
sign-test p = 0.40 (a coin flip). The effect also time-decays: first half
**+0.42%** (11/16 positive, Z 1.28), second half **≈0 (+0.012%, 8/16, Z −0.28)**
— the reversion did not survive the sample. Leave-one-out pooled mean stays
positive (min +0.14%). The frozen verdict function returned `inconclusive`
(positive mean, gate-miss); per the pre-registered kill rule (pooled mean
positive but gate fails ⇒ closes, no parameter rescue), `liqrev` closes with no
horizon grid, no lookback grid, no v2. The liquidation-cascade overshoot shows
weak, statistically-null, decaying reversion on 4h event-time — not tradable at
this universe.

- **Hypothesis:** a sharp price move with a *simultaneous open-interest
  collapse* (forced deleveraging, not informed positioning) overshoots and
  partially reverts over the following hours.
- **Mechanism:** cascading liquidations are mechanical, price-insensitive flow;
  the wick overshoots equilibrium and the reversion is the liquidity rebate for
  absorbing it. This is the **opposite sign** of the retired OI-build-momentum
  family (OI rising → continuation; here OI collapsing → reversion) on a joint
  OI-drop + range-expansion signature that study never isolated.
- **EV / cost:** medium / low cost — reuses the `oibuild_study` 16-asset pooled
  event-study harness and the Vision metrics archive (`sum_open_interest`,
  already cached).
- **Pre-registration:** one event def — bar |return| > trailing 95th pct **and**
  `sum_open_interest` single-bar drop > trailing 95th pct; measure **pooled**
  net-of-cost mean reversion over a fixed horizon (e.g. next 6 bars), event-time,
  across 16 assets. No per-asset exit grid (that grid was the OI-build selection
  artifact).
- **Gate:** pooled net Stouffer **Z > 2**, sign test favorable on **≥ 12/16**
  assets, positive in both time-halves and leave-one-out (the oibuild robustness
  battery). Only then does an exit/sizing study get funded.
- **Kill rule:** pooled reversion non-positive ⇒ forced-deleveraging overshoots
  are absent or arbitraged at 5-min granularity, retiring the OI/positioning
  datasource in *both* directions. **Caveat:** closest to a retired family —
  admissible only because it tests the opposite sign on a distinct joint signal
  with the pooled (not exit-grid) design. Drop if judged too adjacent.

### 6. `calseason` — calendar / funding-settlement seasonality  [CLOSED NEGATIVE 2026-06-17]

**Verdict** (`experiments/calseason/`, 4h form, 16 confirmation assets from the
volume-ranked queue with BTC/ETH/SOL excluded, 730-day window, four fixed
calendar cells, one-touch tail spent): **no cell clears the frozen gate.** The
strongest cell, `weekend`, reaches Stouffer **|Z| = 1.540** — far below the
>3 gate — on same-sign breadth **12/16**, but its pooled mean flips sign across
time halves (first −0.000478, second +0.000094), so it is unstable.
`funding_post` is the only time-stable cell (both halves negative) but posts
**|Z| = 0.822** on breadth **11/16**; `funding_pre` (**|Z| 0.815**, breadth 11)
and `weekday` (**|Z| 0.682**, breadth 7) are also weak and unstable. Every
cell's |Z| sits well under the raised >3 bar, and three of four flip sign
between halves. Per the pre-registered kill rule (no fixed calendar cell clears
⇒ no exploitable bar-level calendar structure on free OHLCV), `calseason`
closes with no cell expansion, no alternate partition, no v2. Bar-level
calendar / funding-settlement seasonality does not exist as a tradable timing
overlay on this universe at 4h.

- **Hypothesis:** expected returns differ by clock position — around the 8h
  funding settlement windows and the weekend/Monday boundary — independent of
  any price signal.
- **Mechanism:** calendar-pinned flows (squaring before funding, weekend
  deleveraging, session handoffs). Not a price prediction — a fixed partition of
  the clock, the lowest multiple-comparison risk on the board (the partition
  cannot be fit).
- **EV / cost:** highest novelty, likely smallest magnitude / **lowest cost** —
  OHLCV + timestamps only, no new data.
- **Pre-registration:** declare the (small, fixed) partition set up front —
  pre- vs post-funding-settlement bar mean, and weekend vs weekday mean — pooled
  across the universe; one two-sided test per partition, Bonferroni-corrected
  for the declared count.
- **Gate:** a cell with **|Stouffer Z| > 3** (raised bar — near-zero-cost to
  express as a timing overlay), stable across both time-halves and ≥ 12/16
  assets. Promotion = a usable timing overlay, not a standalone strategy.
- **Kill rule:** no cell clears ⇒ no exploitable bar-level calendar structure on
  free data — closing the last non-price, non-positioning information axis and
  leaving genuinely-new-data acquisition as the only remaining move.

## Sequencing

Run **one** cycle at a time, in rank order (4 → 5 → 6), honoring each kill rule
before the next. `resrev` (4) has the highest information gain but is the
cost-fragile one; `liqrev` (5) and `calseason` (6) are cheap and orthogonal. If
all three close negative, the unconditional program conclusion stands and the
honest output remains the WAIT advisor plus a new-data requirement.

## Next Step: New-Data Readiness Gate

The free-data backlog is closed. The next admissible move is not another
OHLCV/funding/basis/OI/calendar variant, but a separately pre-registered
new-data readiness cycle under `experiments/newdata/`.

The readiness cycle evaluates only provider/data admissibility: frozen data
class, BTCUSDT coverage, history length, timestamp coverage, duplicate rate,
field completeness, and license permissions. It must not run signal tests,
return tests, strategy backtests, or parameter search. A passed readiness gate
only authorizes a later alpha preregistration for that exact provider/data
class; it does not promote a trading strategy.

---

# 2026-06-20 main lane — BTC 15m–4h System-Level Strategy Search

The next main workstream is backtest-first system-level research (human-authorized),
separate from the frozen Donchian forward thread. Donchian 4h Slice-3 remains a
**frozen background paper thread** governed ONLY by its forward protocol
(`experiments/deployable/DONCHIAN_SLICE3_FORWARD_REGISTRATION.md`); it is not the
active lane and is never retuned or rescued by this work.

- **Scope:** BTCUSDT only, free Binance OHLCV, no live capital. Timeframes
  15m/30m/1h/2h/4h. Full trading systems (entry+exit+cost+slippage+funding+
  sizing+drawdown) — NOT fixed-horizon gross drift, which is a diagnostic only.
- **Gate (frozen):** DSR>=0.95 (pooled n_trials = total cells) -> ECON_BAR
  (PF>=1.2/exp>=0.05R/MAR>=0.5/MaxDD<=30R@f=0.01/robust>=0.60) -> robustness
  battery (plateau, non-overlap WF, cost-stress, recent-period, regime breakdown,
  outlier-dependence, trade-count, no-lookahead).
- **Anti-overfit:** one swept primary param x 3 coarse points per family; pooled
  n_trials; plateau rule (center + >=1 neighbor must clear ECON_BAR). No tuning
  after results; a failed family is closed, not retried.
- **Decision rules:** no candidate passes -> NEGATIVE, force nothing (WAIT stands).
  A candidate passing all stages is a PAPER CANDIDATE ONLY — never live — and must
  later get its own frozen paper-forward protocol; it does NOT inherit the swing slot.
- **Artifacts:** spec `docs/research-log/specs/2026-06-20-btc-system-level-strategy-search-design.md`;
  code `research/system_{cells,search,battery}.py` + `research/edge/system_signals.py`
  + `tools/system_search.py`; outputs under `experiments/system_search/`
  (`PREREGISTRATION.md` committed BEFORE the run, then `RESULT.md` + `leaderboard.json`).
- **Run protocol:** `python tools/system_search.py --register ...` -> commit the
  PREREGISTRATION.md -> `python tools/system_search.py --run ...`. No subagents.

**STATUS — CLOSED NEGATIVE 2026-06-20** (`experiments/system_search/RESULT.md`,
prereg `2abc5c7`, result `0a5f1ff`): all 72 frozen cells failed at STAGE 1
(DSR>=0.95, pooled n_trials=72); none reached ECON_BAR, sealed holdout never
opened; top DSR 0.401 (`4h:atr_channel_break:k=2.0`). The frozen 72-cell lane is
CLOSED — **do not rescue, retune, or rewrite it.** Post-hoc design critique (not
a rescue): exit holding horizons were frozen in BARS across all timeframes
(`max_bars=48`/`h=24` ⇒ 12h on 15m vs 8 days on 4h) and each family carried a
single fixed exit (mean-reversion paired with a pure time exit). Those design
limits are the explicit motivation for the NEW lane below — addressed there with
timeframe-scaled holds and family-matched exits, NOT by reopening this one.

---

# 2026-06-20 main lane — BTC Practical Signal Discovery — 15m to 4h

**Direction change (human mandate 2026-06-20):** the program goal is no longer
*only* academic edge research. It is now to find **practical BTC paper-signal
candidates** — configs good enough to produce PAPER signals first, then later be
validated by forward evidence. This is a SEPARATE lane; it does not reopen the
closed 72-cell system-search lane and does not touch the frozen Donchian Slice-3
config. **No live capital, no automatic execution** — the WAIT-on-live mandate
(participation advisor) is unchanged; this lane can only ever produce a PAPER
candidate.

- **Scope:** BTCUSDT only, free Binance OHLCV, backtest-first. Timeframes
  15m/30m/1h/2h/4h. Output target = **paper-signal candidates, clearly labelled
  PAPER ONLY**; never live, never auto-executed.
- **Core change vs. the closed lane:** NO single fixed exit horizon across
  timeframes. Parameters AND exits are scaled to the timeframe and matched to the
  strategy family.
- **Timeframe-scaled max hold (approx):** 15m intraday 6h–48h; 30m intraday swing
  12h–72h; 1h short swing 1–5d; 2h swing 2–10d; 4h swing/trend 5–20d.
- **Exit-family matching (no shared exit assumption):**
  - mean reversion → exit on mean/EMA/VWAP reclaim or range midpoint (not pure
    time exit only);
  - trend/breakout → ATR trail, Donchian trail, chandelier, or vol-scaled
    stop/trail;
  - volatility expansion → ATR bracket or trailing exit;
  - seasonality / time-of-day → time exits permitted.
- **Workflow (4 stages):**
  1. **Exploratory search** — wider parameter exploration over entry+exit jointly
     to locate plausible config regions. NOT proof of edge; selection-biased by
     construction.
  2. **Candidate selection** — keep only configs with: positive OOS net R;
     PF>=1.15 (preferably >=1.2); positive expectancy; acceptable max drawdown;
     enough trades; no obvious parameter island; no extreme top-1/top-3 trade
     dependence; survives reasonable cost/slippage stress; recent-period not
     catastrophic.
  3. **Frozen validation** — freeze selected configs/ranges BEFORE validating;
     validate on OOS/holdout NOT used for exploratory selection; **no post-hoc
     parameter rescue** after validation.
  4. **Paper signal** — a passing candidate is promoted ONLY to paper signal and
     gets its own frozen paper-forward protocol. Passing backtest does NOT
     authorize live capital.
- **Gate tier (practical, not DSR-only):** DSR>=0.95 remains the strong
  RESEARCH-PASS tier, but a PAPER-signal candidate may be accepted on strong
  backtest/OOS behaviour + robustness + cost-stress survival + clean frozen
  validation even below that DSR bar. Any such candidate is labelled **PAPER
  ONLY** and never inherits the live/Donchian slot.
- **Hard isolation:** never read/write `promotion/strategy.json`, the Donchian
  Slice-3 config (`strategy_hash df7cc856…`), or `journal/signals.jsonl`; never
  reopen or retune the closed 72-cell lane; reuse research engine pieces but keep
  this lane's artifacts under a new `experiments/` path.
- **Next step (NOT yet built):** this is the recorded direction only. The actual
  search is a separate engineering effort — brainstorm the exploratory-vs-
  validation leakage controls + the family/exit/hold matrix, then write a frozen
  plan before any code or data run.

---

# 2026-07-16 `tda_topology_v1` — geometric signal research CLOSED [CLOSED NEGATIVE]

**Verdict:** `INDISTINGUISHABLE_FROM_NULL` — persistent homology (H0/H1) of the
rolling 17-asset cross-sectional correlation matrix does not stratify forward-R
of the frozen 1838 Donchian events beyond a circular-block-permutation null
(real effect 0.6867 vs null p95 1.0291). Full result:
`experiments/tda_topology/RESULTS.md`. This was a **descriptive instrument,
not a gate** — no lockbox, no DSR ladder, spends none of the free-data
terminal budget (`68ca474`).

Notably, the row-wise null (same method the microscope used) would have shown
`EXCEEDS_NULL` (0.6867 vs 0.4922) — a false pass the block null caught because
the market-level label is autocorrelated. Any future instrument built on a
rolling market-level label must use a block/run-preserving null, not a
row-wise shuffle; row-wise is the wrong null shape for this class of label.

**Closure mapping — all six geometric directions from
`docs/research-log/concepts/crypto_geometric_signal_research_ai_readable.md` are now closed. No
future session should reopen any of them under a new framing:**

| Doc direction | Verdict | Where |
|---|---|---|
| 1. Cosmic Web → Dynamic Market Graph | crypto beta / CLOSED | `breadth-neutral-results`, `lead-lag-results` (H3), `xsection-results` (H2, sealed tail −91.6% DD) |
| 2. Fractal Geometry | CLOSED, all cells | `donchian-adx-filter`, `donchian-volregime`, `regime-overlay`, `regime-selector`, `stack-path-screen-results` |
| 3. Gyroid → Manifold | CLOSED FRAGILE | `macro-regime-instrument-results`, `regime-moe-*` |
| 4. Topological Data Analysis | `INDISTINGUISHABLE_FROM_NULL` | `experiments/tda_topology/RESULTS.md` (this entry) |
| 5. Einstein Ring → Conditional amplification | coin flip | `matrix-step-a-router-results` |
| 6. Spiral / Fibonacci | not recommended by source doc; agreed, never run | — |

No v2, no window rescue (`W=30`/`W=120` untried by design — spec §7), no
alternate point-cloud construction (Takens embedding, Mapper) as a follow-on.
