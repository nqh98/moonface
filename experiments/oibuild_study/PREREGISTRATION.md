# Pre-registration: pooled cross-asset test of the OI-build mechanism

- **Registered:** 2026-06-12 (this document is frozen at commit time, before
  any confirmation-asset metrics data is downloaded)
- **Question:** does the OI-build mechanism — open-interest expansion
  confirming a concurrent price move predicts continuation — exist as a
  market mechanism, or are the BTC/ETH/SOL results (DSR 0.30 / 0.933 / 0.890)
  noise, selection, or multiple-comparisons artifacts?
- **Null hypothesis:** no edge exists; directional forward returns after
  OI-build events have mean ≤ 0 on fresh assets.
- **This is mechanism science, not strategy research.** No exits, stops,
  sizing, leverage, or execution are modeled or optimized. The output is a
  verdict, not a system.

## Why this is the one legitimate exception

The prior program closed every family by pre-committed rule. OI-build is the
only mechanism that produced sub-threshold signal on three independent
assets' independent data series. The three observed results are **excluded
from this study's evidence**: BTC generated the hypothesis and ETH/SOL were
selected as its first confirmation, so all three are contaminated by
selection. Evidence here comes only from assets never before tested.

## Frozen design

### Event definition (inherited verbatim, zero re-implementation)

`make_oi_build_momentum` (`src/moonface/backtest/edge/positioning_signals.py`)
on `sum_open_interest` from the Binance Vision 5-min metrics archive, as-of
joined to 4h candles by the existing `align_metric`:

- **Primary variant:** `window=180, lookback=6, z_thr=1.5` — the original
  `positioning_btc` leaderboard #1 (chosen because it led the *discovery*
  asset; ETH's leader was lookback=24, recorded below as a secondary).
- Event at bar *i*; direction = sign of the lookback price return at *i*.
- **Non-overlap rule:** events within `h` bars after an accepted event are
  discarded (events are otherwise serially dependent and would overstate n).

### Outcome (no strategy)

Directional simple forward return per event:
`sign × (close[i+h] / close[i] − 1)`, **h = 24 bars (96 hours), gross** —
matching the horizon that recurred across the lineage's leaderboards.
Events with fewer than h bars remaining are discarded.

### Universe (survivorship-clean, selected blind to outcomes)

- Window: **2 years of 4h bars ending at registration** (frozen timestamps in
  `registration.json`).
- Candidates: every archived USDT perp (Vision S3 listing, includes delisted)
  with cached daily klines from the 2026-06-12 xsection run. Daily quote
  volume is the only data consulted for selection; it contains no
  open-interest or forward-return information.
- Rank by **mean daily quote volume over the 30 days ending at window start**
  (information available at window start only — no survivorship or
  momentum-of-success leak), require listing ≥ 365 days before window start,
  **exclude BTCUSDT, ETHUSDT, SOLUSDT** (discovery set).
- The top 24 form the frozen candidate queue. Walking it in rank order, the
  first **16** with ≥ 80% aligned metrics coverage over the window (the
  pipeline's existing coverage gate; a data-presence check, not an outcome
  check) form the confirmation set. Skips are logged. Fewer than **8**
  evaluable assets ⇒ automatic `inconclusive (insufficient data)`.

### Primary endpoint (the only confirmatory test)

Per evaluable asset *i* (requires n_i ≥ 10 non-overlapping events):
mean_i, t_i = mean_i / sd_i × √n_i. Each asset is one unit of evidence;
no pooling of raw events across assets (assets with more events must not
dominate).

Co-primary criteria, **both required**:
1. **Breadth:** exact one-sided binomial sign test on k = #{mean_i > 0} of m:
   P(Bin(m, ½) ≥ k) ≤ 0.05.
2. **Magnitude:** Stouffer Z = Σ t_i / √m ≥ 1.645.

### Verdict rule (frozen, tripartite)

- **Mechanism exists** — both co-primary criteria pass.
- **Mechanism does not exist** — the equal-weight pooled mean (mean of
  mean_i) ≤ 0: the point estimate itself is non-positive on fresh assets.
- **Inconclusive** — pooled mean > 0 but criteria not met, or m < 8.

### Secondary / descriptive analyses (frozen list; no influence on verdict)

Reported to characterize the mechanism if it survives, or document the
failure mode if it doesn't: horizons h ∈ {6, 48}; the lookback=24 variant;
net-of-cost pooled stats (0.1% round-trip per event, the program's standard
`COST_FRACTION`); long vs short events; first half vs second half of the
window (time stability / regimes); upper vs lower half of the universe by
selection volume (liquidity); leave-one-asset-out pooled-mean range
(concentration); the discovery set (BTC/ETH/SOL) computed identically and
reported separately, labeled contaminated.

### Stopping rules

- `analyze` is **one-touch**: it runs once on the frozen design; the verdict
  file blocks re-runs. Data *fetching* is resumable (network failures don't
  spend the analysis).
- No parameter changes, no added variants, no threshold adjustments, no
  re-tests of near-misses, regardless of how close any number lands.
- **If the verdict is `does not exist` or `inconclusive`: the OI-build
  lineage is permanently retired.** Inconclusive is a stop, not an
  invitation.
- If the verdict is `exists`, signal-generation research may **not** resume
  until both: (a) a second pre-registered confirmation on data that does not
  yet exist (a future window, accrued after this registration — true
  out-of-sample time), and (b) the net-of-cost secondary Z ≥ 1.645 in this
  study (a mechanism that cannot survive one round-trip cost at h=96h is not
  economically meaningful).

### Known limitations (stated in advance)

- Binance-only; one venue's OI snapshot semantics.
- The 30d-volume universe rule biases toward 2024-era liquid alts; the
  listing-age floor mitigates churn but the universe is not the full
  cross-section of crypto history.
- h is fixed; the test is of the mechanism at the lineage's characteristic
  horizon, not of all horizons.
