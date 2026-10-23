# MTF Confluence L/S BTC — Findings

**Mandate:** find a strategy from 15m to 1d that combines multiple timeframes and
produces long/short BTC signals.

**Data:** BTCUSDT perp, free Binance OHLCV, 226,848 15m bars (2020-01 → 2026-06,
~6.5y). Every higher timeframe is a closed-bar resample of the single 15m base;
point-in-time alignment, no look-ahead. Paper research — promotes nothing to live.

## The signal

```
regime  (1d) : long-only when 15m-resampled-daily close > its 50-day SMA,
               short-only when below   (price_vs_sma bias)
trigger (15m): RSI(14) <= 30 -> dip ;  RSI(14) >= 70 -> rip
entry        : take the trigger ONLY on the side the 1d regime allows
               => buy 15m dips in a 1d uptrend / sell 15m rips in a 1d downtrend
exit         : hold 2 days (192 x 15m), 3xATR wide stop (horizon_wide_stop)
```

The higher timeframe is a **regime gate**; the lower timeframe is a **counter-trend
entry**. Combining them is the whole point: the 1d trend says which direction is
allowed, the 15m oversold/overbought says when to enter at a good price.

## What the experiments showed

1. **Momentum-on-momentum fails (run 1).** HTF trend + LTF breakout — the crowded
   style — had the regime filter working but the breakout buys local highs
   (max adverse excursion). Best gross drift Z=2.58, died at DSR.

2. **Counter-trend entry is the discovery (run 2).** Swapping the LTF breakout for
   an LTF dip/reclaim gave the strongest gross drift in the lane (Z=2.82) and,
   decisively, **survived the recent out-of-sample period** where the momentum
   version decayed:

   | recent 2y (>= 2024-07) | PF | exp/trade | verdict |
   |---|---|---|---|
   | 1d + RSI-dip (counter-trend) | 1.23 | +1.00R | **positive** |
   | 1d + donchian (momentum)     | 0.98 | −0.10R | decayed |

   Year by year the counter-trend cell is positive in 5 of 7 years (only 2022's
   bear and a flat partial-2026 are negative). "No recent edge" is the program's
   recurring killer; this cell does not have that problem.

3. **The 1d regime gate is load-bearing.** Every top-leaderboard cell uses the 1d
   bias; every 4h-bias cell is materially weaker. Daily trend is the signal.

4. **Wide stop is the drawdown lever (run 3).** A tight ATR trail whipsaws on 15m
   and destroys the edge (PF<1). No stop (horizon_hold) leaves a huge path
   drawdown. A 3xATR wide stop with the 2-day cap cuts single-path drawdown
   −219R → −125R (−43%) while keeping PF ~1.24 and the recent period positive.

## Honest verdict

Full 6.5y, single-path, headline cell (1d + RSI-dip + 2-day hold + 3xATR stop):
**973 trades, balanced 520L/453S, PF ~1.25, +~0.6R/trade, MAR ~4.5.**

This is a real, persistent, balanced long/short BTC signal — the strongest the
program has surfaced, and the only one to stay positive in recent data. It does
**not** clear the two academic/deployable gates:

- **DSR 0.26 ≪ 0.95** — it does not beat the expected max of 24 zero-skill trials;
  by the academic bar it is selection-consistent.
- **Drawdown ≫ 30R cap** — −125..−219R at f=0.01. This is a *sizing* failure, not
  a sign-of-edge failure: at f ≈ 0.002 the drawdown is ~30% and the edge is intact,
  but the return is then modest.
- **robust_frac ~0.55 < 0.60** — 2022 and partial-2026 are down quarters.

**Bottom line:** the multi-timeframe combination (1d regime + 15m counter-trend
entry) produces a genuine long/short BTC signal that works out-of-sample, but it
is a thin edge wrapped in large drawdown — a conservative-sized paper candidate,
not an academically bulletproof or large-capacity edge.

## Cross-asset transfer (ETH / SOL) — TRANSFERS

The frozen cell, run on ETH and SOL (each gated by its OWN 1d trend), is positive
in the recent out-of-sample window on all three majors:

| asset | recent 2y (entries >= 2024-06) | PF | exp/trade | positive |
|---|---|---|---|---|
| BTC (control) | 317 trades | 1.14 | +0.36R | yes |
| ETH | 316 trades | 1.08 | +0.21R | yes |
| SOL | 316 trades | 1.09 | +0.23R | yes |

Full-history: BTC PF 1.24, SOL PF 1.13, ETH PF 1.01 (weak historically, positive
recently). The mechanism generalises. **Caveat:** crypto majors share beta, so
ETH/SOL are correlated confirmations, not independent ones — a market-neutral
claim would need a BTC hedge. Details in `TRANSFER.md`.

## Cross-asset basket — does a portfolio structure relax the wall? (PARTIAL)

The program's standing question for any real-but-DD-bound signal is whether a
*portfolio structure* relaxes the single-asset drawdown wall. Tested on this
signal via an equal-weight (1/3 each) merged single-path book over BTC/ETH/SOL
(`BASKET.md`, `tools/mtf_basket.py`). Result is honest and partial:

- **De-correlation is real:** merged-path drawdown −107R vs −156R perfect-
  correlation reference — a **31% drawdown cut** from imperfectly-correlated
  loser-clustering across assets.
- **Robustness is fixed:** basket robust_frac **0.714 (5/7 years)** clears the
  0.60 floor that the single-asset signal (0.553) *failed* — only 2022 (−1.2R)
  and 2024 (−17.8R) are down years, both mild. In the recent OOS window the
  basket MAR (1.18) beats every single asset (BTC 0.996 / SOL 0.891 / ETH 0.724).
- **But the edge is not thickened:** basket PF 1.13 still < 1.2, and the single-
  path DD still exceeds the 30R fixed-f cap (sizing failure, f≈0.003 → ~30%
  equity). The basket is a MORE ROBUST deployment of the same thin signal, NOT a
  deployable edge — and the assets share crypto beta, so this diversifies
  idiosyncratic/survivorship risk, not market risk (breadth-neutral finding).

## Broadened search re-rank (15m–1d, new regime definitions)

A pre-registered 72-cell broadening (`BROADEN_FINDINGS.md`) added new regime
DEFINITIONS (trend-sign / momentum-sign / regime-QUALITY) and a 1d/2d hold. No
cell clears DSR or ECON_BAR (wall still binds), but the frozen BETTER-THAN-
HEADLINE rule fired on a structurally new cell that survives the headline's own
discriminators: **`4h:trend_strength|rsi_reversion|horizon_hold@2d`** — a 4h
regime-QUALITY gate (trade only when price is ≥1σ from its 4h mean, skip the chop)
on the same 15m counter-trend entry, 2-day hold, no stop. Single path beats the
headline (MAR 4.83 vs 4.53, expectancy +0.897 vs +0.581, **positive in all 7 years
vs 6/7**), is much stronger in the recent OOS window (BTC PF 1.406 vs 1.140; SOL
1.310 vs 1.095), and transfers to ETH/SOL. Still paper-only (DSR 0.376, no-stop DD
−135.6R over the cap). Negative sub-results: momentum-sign regime is worse than
trend-sign; the 2-day hold is load-bearing (every 1d-hold cell collapses).

## Regime-quality gate × basket — the closest-to-deployable result (PARTIAL)

Combining the two levers — the broadened best cell (4h regime-quality gate, skip
the chop) run as the equal-weight BTC/ETH/SOL basket (`BASKET_REGIME_QUALITY.md`,
`mtf_basket.py --cell broaden_best`) — is the strongest practical result the
program has produced. It is a deterministic combination of two already-frozen
elements (no new selection / no new DSR deflation):

| metric | headline basket | **regime-quality basket** | ECON floor |
|---|---|---|---|
| PF (full) | 1.129 | **1.197** | ≥1.2 — at the line |
| PF (recent ≥2024-06) | 1.106 | **1.235** | ≥1.2 — **clears** |
| expectancy (full) | +0.102R | **+0.254R** | ≥0.05 — clears |
| MAR (full) | 2.684 | **5.807** | ≥0.5 — clears ×10 |
| robust_frac | 0.714 | **0.857** (6/7 yrs) | ≥0.60 — clears |
| single-path DD (1/3) | −107R | −93.7R | ≤30R@f=0.01 — fails |
| DD de-correlation cut | 31.2% | **33.7%** | — |

It clears **three of five** ECON gates outright (expectancy, MAR, robust), sits
right **at** the PF line on full history and **clears PF in the recent OOS window**
(1.235), and the only clean failure is the fixed-f drawdown cap — a *sizing*
convention, not an edge failure: MAR 5.807 means at a 30% equity-DD budget the
basket returns ~27%/yr over the sample. This is the nearest miss in the program's
history.

**Honest caveats (load-bearing):** the 4h cell was selected from a 72-cell grid,
so the basket inherits winner's-curse risk — the recent-window PF (1.235, OOS-ish)
is the more trustworthy number and it does clear 1.2. Crypto majors share beta, so
this is a robust crypto-beta timing overlay, not market-neutral alpha. Still paper
only.

**Wide stop does NOT rescue the DD cap (CONFIRMED negative).** The natural fix —
add the 3×ATR wide stop (the headline's drawdown lever) to the regime-quality
cell — was tested on the frozen sibling
`4h:trend_strength|rsi_reversion|horizon_wide_stop@2d` (already in the grid). It
makes everything *worse*: basket DD **deepens** −93.7R → −111.4R, PF 1.197 → 1.148,
MAR 5.81 → 2.22, total +544R → +247R, and the recent-OOS edge collapses (recent PF
1.235 → 1.075, SOL recent flips negative). Mechanism: regime-quality entries buy
dips already ≥1σ extended, so their adverse excursions are wide but **recover
within the 2-day hold**; a stop converts recoverable paper losses into realized,
clustered losses. The counter-trend dip-buy needs room — which is why the grid
selected the no-stop variant. So the DD-cap miss is **structural to the mechanism,
not an exit-tuning artifact**; the only honest path to a 30R budget is conservative
sizing (f≈0.0032), which MAR 5.81 supports as viable but modest.

**4th uncorrelated major (+DOGE) — diversification works as designed
(`BASKET_REGIME_QUALITY_4LEG.md`).** The 4th leg was chosen A PRIORI by the only
honest criterion — lowest 1d-return correlation to BTC among long-history liquid
majors (selection independent of strategy outcome, so no asset-cherry-picking):

| candidate | corr to BTC | | candidate | corr to BTC |
|---|---|---|---|---|
| **DOGEUSDT** | **0.533** ← pick | | ADAUSDT | 0.700 |
| TRXUSDT | 0.581 | | BNBUSDT | 0.704 |
| XRPUSDT | 0.611 | | BCHUSDT | 0.731 |
| LINKUSDT | 0.699 | | LTCUSDT | 0.753 |

Equal-weight 1/4 basket (BTC/ETH/SOL/DOGE), regime-quality cell, vs the 3-leg:

| metric | 3-leg | **4-leg (+DOGE)** | floor |
|---|---|---|---|
| DD de-correlation cut | 33.7% | **45.6%** | — |
| single-path DD (scaled) | −93.7R | **−78.1R** | ≤30R@f.01 — fails |
| MAR | 5.81 | **6.23** | ≥0.5 — clears |
| robust_frac | 0.857 (6/7) | **1.000 (7/7)** | ≥0.60 — clears |
| PF (full) | 1.197 | 1.184 | ≥1.2 — fails (worse) |
| PF (recent) | 1.235 | 1.215 | ≥1.2 — clears |

The least-correlated leg cut the loser-clustering harder (de-corr 33.7% → 45.6%),
lifted MAR to 6.23, and made the basket **positive in every one of 7 years** —
2022 (the 3-leg's lone down year, −16.7R) flips to **+24.8R**. DOGE standalone
carries the edge (full PF 1.136, recent 1.157, positive), so the regime-quality
mechanism generalises to a 4th, least-correlated asset — a stronger confirmation
than the correlated ETH/SOL legs. **Cost:** DOGE's thinner per-trade edge dilutes
basket PF (1.197 → 1.184 full), so **PF — not drawdown — is now the binding
constraint**; the DD gap narrowed (−93.7 → −78R) but still misses the fixed-f cap.
Reproduce: `mtf_basket.py --cell broaden_best --symbols BTCUSDT ETHUSDT SOLUSDT
DOGEUSDT`. Caveat: DOGE is meme/outlier-driven; the recent-window confirmation
(PF 1.157) is the trust anchor. Still paper only — no deployable line crossed.

**Forward-tracking gate (frozen):** the regime-quality basket is the basket
variant worth watching; the 4-leg is its more-robust (7/7), lower-drawdown form.
Resolve on forward trades (entry ≥ 1_782_000_000_000) at n ≥ 120 and ≥ 6 months:
**REAFFIRM** iff basket PF ≥ 1.15 AND expectancy_r > 0 AND both sides traded AND
it beats the headline-basket PF over the same forward window; **DOWNGRADE**
otherwise. Re-run with `mtf_basket.py --cell broaden_best` (3-leg) and the 4-leg
`--symbols` form above. Paper only; no live capital.

## Market-neutral falsification — the cross-asset "confirmation" is crypto beta (DECISIVE)

The standing caveat on every basket result was that crypto majors share beta, so
ETH/SOL/DOGE are *correlated* confirmations — a market-neutral claim "would need a
BTC hedge." That hedge is now done (`NEUTRAL.md`, `tools/mtf_neutral.py`,
`mtf/neutral.py`). It reuses the program's proven beta-hedge arithmetic
(`breadth_confirm.neutral.hedge_entries`, bit-identical to raw at beta=0): for each
non-BTC leg it removes the BTC component of every trade's PnL over its actual
2-day holding window, using a point-in-time trailing-90-day daily beta (no
look-ahead). BTC itself is un-hedgeable against itself, so it carries raw.

**The alt legs' edge is crypto beta.** Mean betas to BTC are 1.11 (ETH) / 1.27
(SOL) / 1.30 (DOGE). Removing the beta component flips every alt leg negative in
the recent OOS window — the program's trust anchor:

| recent OOS (≥2024-06), exp/trade | raw | BTC-hedged |
|---|---|---|
| ETHUSDT | +0.226 | **−0.268** |
| SOLUSDT | +1.125 | **−0.205** |
| DOGEUSDT | +0.628 | **−0.312** |

The pure **market-neutral alt book** (hedged ETH/SOL/DOGE, BTC excluded) is
positive on full history (+0.100R, PF 1.12 — carried by the alts' idiosyncratic
2020–23 runs) but **negative in the recent window (−0.087R, PF 0.897)**; the 3-leg
form agrees (−0.118R, PF 0.906). This is the *same* outcome the breadth cross-asset
leads met (`breadth_neutral`): the transfer diversifies crypto-beta timing, not
market risk — a robust crypto-beta timing overlay, **not** market-neutral alpha.

**What survives the hedge:** BTC's own directional edge is untouched
(un-hedgeable against itself; +0.897R full / +1.413R recent) — it is the one
genuinely independent signal in the book. And the practical "keep BTC directional,
beta-hedge the alts" basket still has a positive full-history path with *lower*
drawdown (hedging cuts the alts' adverse excursions: 4-leg hedged DD −87R vs raw
−78R merged but MAR-neutral; 3-leg hedged MAR 7.67), but recently it is thin
(+0.04R) and rests entirely on BTC's directional edge. **Net:** the "closest-to-
deployable" reading stands, but its market-neutral interpretation is now falsified,
not merely caveated — the deployable content is a BTC-directional counter-trend
signal plus a crypto-beta overlay, not diversified alpha. Paper only.

## BTC standalone edge — characterization of the one signal that survived (`CHARACTERIZE.md`)

The BTC-beta hedge left exactly one independent component standing: BTC's own
counter-trend signal (un-hedgeable against itself). `tools/mtf_characterize.py`
(+ `mtf/characterize.py`) x-rays that single-path edge. Descriptive only — no
selection, no new cell. Three findings matter:

1. **It is long-dominated, not a symmetric L/S edge.** On PnL the whole 6.5y edge
   is the long book; the short book is a drag:

   | full-history book | n | PF | exp/trade | totalR | MAR | +ve |
   |---|---|---|---|---|---|---|
   | LONG (dip-buys in 4h up-regime) | 391 | **1.57** | +1.94 | **+759** | 8.67 | yes |
   | SHORT (rip-sells in 4h down-regime) | 340 | **0.93** | −0.31 | **−104** | 0.40 | **no** |

   The balanced 391L/340S *count* hides a one-sided *PnL*. The short book loses
   because 2020–23 "down-regimes" in a structural bull were shakeouts that
   snapped back. **It only turns positive in the recent two-sided market**
   (2024-06+: short PF 1.36, +131R) — so the short overlay is regime-dependent and
   unproven across a full cycle, while the long book is the load-bearing edge.

2. **It is broad, not outlier-carried** — the failure mode that killed prior
   candidates. Full sample survives dropping the top 10 winners (+76.7R still
   positive; expectancy +0.106R), the top 5% of trades carry a moderate 39% of
   gross profit (not the 80%+ of an outlier-carried curve), and it is **positive
   in all 7 years (robust_frac 1.0)**. Positive skew +1.04 / kurtosis +9.85: a
   right-tailed trend-rider profile (best +81.7R, ~50% win rate, payoff 1.24). The
   recent window is thinner (drop-top-10 goes negative at n=237) — small-sample
   fragility, not a structural change.

3. **MAE/MFE confirms the mechanism.** Median winner goes −2.7R underwater before
   paying (losers −9.6R); a tight stop inside ~3R would convert winners into
   losers — the mechanism reason wide-stop is CONFIRMED harmful and the 2-day hold
   is load-bearing (ties the exit and hold-curve findings together).

**Deployability read:** the cleanest-shaped object in the lane is the **BTC
long-only counter-trend dip-buy** (`LONG_ONLY.md`) — it clears **4 of 5 ECON gates**
(PF 1.57, exp 1.94R, MAR 8.67, robust 0.857), better than the L/S basket's 3/5, with
lower drawdown than the L/S whole. But the beta test refines the picture: long-only
is **6 of 7 years positive, NOT all-weather** — it LOSES the severe 2022 bear
(−33.6R while BTC fell −64%; the short book was that year's hero, which is why the
L/S whole survived 2022). It IS positive in the shallow down years 2025 (+68R vs BTC
−6%) and 2026 (+16R vs BTC −27%), so it is a long-biased *timing* overlay with real
alpha in mild drawdowns, carrying partial beta a full-cycle bear overwhelms. Still
paper: the 30R fixed-f DD cap (−87.5R) and DSR bar are unchanged — decomposition
relocates the edge, it does not newly clear a gate. It is a **post-hoc side filter**,
so it is honestly resolved only forward: registered in
`LONG_ONLY_FORWARD_REGISTRATION.md` at a stricter PF ≥ 1.20 forward bar (vs 1.10 for
the pre-registered L/S cells) to guard the selection.

## Status & next step

Three independent frozen single-path forward registrations (plus the two basket
forward gates above):
- single-asset BTC headline cell — `FORWARD_REGISTRATION.md` (REAFFIRM iff PF >=
  1.10, positive expectancy, both sides traded; DOWNGRADE closes the lineage).
- equal-weight basket — `BASKET_FORWARD_REGISTRATION.md` (REAFFIRM iff the basket
  stays PF >= 1.10 AND beats the median single-asset MAR forward; DOWNGRADE if the
  diversification advantage does not persist).
- broadened best cell (4h regime-quality gate) — `BROADEN_FORWARD_REGISTRATION.md`
  (REAFFIRM iff PF >= 1.10, positive expectancy, both sides traded; DOWNGRADE
  reverts the lane to the headline). Tracked in parallel, not replacing the
  headline.
- BTC LONG-ONLY dip-buy — `LONG_ONLY_FORWARD_REGISTRATION.md` (REAFFIRM iff the
  forward LONG sample holds PF >= **1.20** and positive expectancy/total; stricter
  bar because it is a post-hoc side filter). The cleanest-shaped single-asset form
  (4/5 ECON gates) but not all-weather (loses a full-cycle bear). Tracked in
  parallel.

All are single-asset-selection / cross-asset-confirmed, paper only — no live
capital. The market-neutral question is settled (crypto beta, `NEUTRAL.md`); the
independent survivor is BTC's own directional signal, whose long book is the
cleanest deployable *shape* but still wall-bound and now forward-registered on its
own terms. The frozen 4h Donchian Slice-3 strategy is untouched.
