# Confluence engine — forward-faithful full-window backtest (2026-06-24)

**Label: engine paper — disciplined heuristic, no validated-edge claim.**
This is a paper-discipline sanity check, **not** an edge claim. The runtime,
state machine, journal, risk/exit logic and paper discipline all work. Nothing
here proves the signal is profitable or robust. Live trading stays disabled.

## Data (verified, not just "file exists")

- Symbol `BTC/USDT:USDT` (Binance **USDT perpetual**, 1h), via ccxt.
- Coverage **2020-01-01 00:00 → 2026-06-24 15:00 UTC**, **56,800 bars, 6.484 y**.
- **Zero gaps, zero duplicate timestamps** (rows == gapless-expected == 56,800).
- **Genuine perp, not a spot proxy:** the cached value at 2021-01-01
  (`28948.19`) matches a fresh ccxt `BTC/USDT:USDT` fetch exactly and differs
  from spot `BTC/USDT` (`28923.63`). The `BTCUSDT` and `BTC_USDT:USDT` caches
  are byte-identical because both are the same Binance futures contract fetched
  under two symbol spellings — both real perp.
- Fingerprint `sha256(.backtest_cache/BTC_USDT:USDT_1h.csv)` =
  `b1da38622859ca3937fe92bab12f7f6e7448099dfeb2d5da6fc4df1bcaeea2da`
  (3,253,567 bytes, refreshed tail to 2026-06-24T15:00Z).

## Method — what "forward-faithful" means here

Live (`moonface-signal`) feeds `evaluate_engine` exactly `lookback_bars` = **1500**
1h candles each tick. The replay therefore feeds a **rolling 1500-bar window**,
bar by bar, through the identical `evaluate_engine` path (regime → panel →
confluence → discipline → position), accumulating the same journal schema.

**Methodology finding 1 — the +39R / PF 1.61 number is not forward-faithful.**
`tools/engine_backtest.py` feeds the *entire growing history* to each bar.
`signal.baseline.vol_ratio` anchors its `long_vol` baseline to **all** candles it
is given, so the full-slice replay uses an ever-expanding volatility baseline
that live never has. On a 6,000-bar control window the full-slice replay scored
net **+26.0R** vs the windowed (live-faithful) **+8.75R** — the full-slice path
**overstates**. The headline +39R/PF1.61 came from that non-faithful path and
should not be used to set forward expectations.

## Forward-faithful result (rolling 1500-bar window, real perp, 6.484 y)

| metric | value |
|---|---|
| closed trades | 66 |
| net R | **+8.75R** |
| expectancy | +0.13R / trade |
| profit factor | **1.12** |
| win rate | 31.8% |
| max drawdown (R) | −15.96R |
| MAR (equity) | 0.19 |
| equity net return | +1.78% (over 6.5y, f≈0.005–0.02) |
| trades / year (6.5y, frozen-diluted) | 10.2 — **misleading, see below** |
| trades / year (active window only) | ~154 |
| % time in position (over 6.5y) | 2.6% |
| decision counts | WAIT 54,916 · LONG 853 · SHORT 631 (LONG/SHORT incl. HOLD bars) |
| action counts | WAIT 54,850 · HOLD 1,418 · OPEN 66 · EXIT 66 |

### Why this is weak / effectively negative

1. **Outlier dependence — fatal.** Best trade +20.6R = 25.4% of gross profit;
   top-3 = 51%. **Net excluding the single best trade = −11.9R**; ex-top-3 =
   −32.7R. The entire positive result is one trend capture.
2. **Cost-fragile.** Net at 1× cost (10 bps round-trip) +8.75R; **2× = +1.2R
   (breakeven); 3× = −6.3R; 5× = −21.3R.** The thin edge dies under modest
   cost/slippage stress.
3. **The engine was alive for only ~5 months.** All 66 trades fall in
   **2020-01-19 → 2020-06-24** (~157 active days, ~154 trades/yr pace). On
   **2020-06-24** the cumulative-R drawdown hit −15.96R, the kill-switch
   latched, and the engine emitted `WAIT — drawdown kill-switch active` for the
   **next 6.0 years**. The +8.75R was earned entirely in the COVID-crash era,
   and the +20.6R best trade (25% of gross profit) is one early-2020 capture.
   We have **zero observation** of the signal from 2020-07 to 2026 — the
   kill-switch design, not the market, hid it.
4. Win rate 31.8% with PF 1.12 is breakeven-grade for trend following.

## Methodology finding 2 — the all-time-DD kill-switch froze the engine

`discipline.is_paused` pauses when `summarize_r(rs).max_drawdown_r ≤ −15R`. That
statistic is the **all-time** peak-to-trough drawdown of the cumulative-R curve,
which is **monotonically non-decreasing**: once the worst-ever drawdown reaches
15R it **never un-trips** (recovery to new highs does not reduce a historical
max). It is a **one-way latch requiring a human reset**.

In this run the cumulative-R drawdown reached **−15.96R on 2020-06-24** (after
just ~5 months of trading), which **permanently paused the engine**. For the
remaining **6.0 years** it emitted `WAIT — drawdown kill-switch active (paused)
— human reset required` on every bar. The scorecard confirms it:
`state: "paused"`, `realized_drawdown_r: −15.96`.

So the full-window result is doubly uninformative for forward expectations: the
positive R is one COVID-era outlier, and **six of the 6.5 years are unobserved**
because the engine was frozen on day ~157.

## Kill-switch review and proposal (do NOT loosen risk to stay active)

The all-time latch answers the wrong question for a **forward paper** engine:

- All-time max-DD = "has this engine *ever* been this deep underwater?" — a
  **verdict statistic**. Belongs in the scorecard, read by a human to kill the
  experiment. Wired as a permanent operational latch, it ends the very forward
  sample we need.
- The operational kill-switch should answer "is this engine in trouble *now*?"
  and recede as the engine recovers.

**Proposal: trailing-window drawdown kill-switch (same −15R budget).** Pause when
the peak-to-trough drawdown computed over **only the closed trades whose exit
falls in a trailing K-day window** reaches −15R. It is **equally protective at
the danger point** (at the trough, window-DD == all-time-DD, so it trips at the
same first moment), but **auto-resumes** as the bad cluster ages out of the
window — without trading through the drawdown and without raising the budget.
Recommended K with hysteresis (resume only after window-DD recovers above
−budget/2) to avoid flapping. A *hard* all-time circuit breaker at 2×budget
(−30R, human reset) can be retained for genuine catastrophe. Note: a pure
current-DD-from-HWM rule does **not** auto-resume, because while paused no new
trades occur and cumulative R cannot recover — only a *time/window-aged* rule
resumes. **This is a proposal; the shipped `discipline.py` is unchanged.**

### Exploratory quantification (monkeypatched harness; shipped code untouched)

Same engine, same −15R budget, all-time latch swapped for a **trailing 90-day**
window rule, to observe the ~6 y the latch hid:

| metric | all-time latch (shipped) | trailing-90d rule (exploratory) |
|---|---|---|
| active window | 2020-01-19 → **2020-06-24** | 2020-01-19 → **2026-06-22** |
| closed trades | 66 | **668** |
| net R | +8.75 | +112.9 |
| expectancy | +0.13R | +0.17R |
| profit factor | 1.12 | 1.16 |
| win rate | 31.8% | 34.4% |
| **cumulative max DD (R)** | −15.96 (latched here) | **−55.9 (3.7× budget!)** |
| last 365d | 0 trades (frozen) | +53.5R, PF 1.50, 111 trades, win 40.5% |
| second half | 0 trades (frozen) | +34.8R, PF 1.10, 321 trades |

Two things this shows:

1. **The latch hid six years of (modest, positive-ish) behavior, not a dead
   signal.** Freed to trade, the engine is net positive across every sub-period,
   and the *most recent* 365 days are its best (PF 1.50). The as-shipped −8R-over-
   6.5y picture is an artifact of the kill-switch, not the signal. PF stays a
   thin 1.1–1.5 throughout — still no validated edge, but not the corpse the
   latched run implied.
2. **The trailing-window rule alone is not sufficient risk control.** It caps
   *90-day-windowed* drawdown near budget, but the *cumulative path* drawdown
   reached **−55.9R** because the engine keeps re-engaging through every fresh
   drawdown. So the proposal must be **layered**: trailing-window pause for
   routine operation **plus** a hard all-time circuit breaker (e.g. 2×budget =
   −30R, human reset) for catastrophe. A −56R cumulative drawdown is not
   acceptable for forward paper and must be capped before any watch starts.

Caveats: exploratory, harness-monkeypatched (shipped `discipline.py` unchanged),
single window K=90d, no cost-stress or outlier re-analysis on the 668-trade set.
**No edge claim — this is risk-control diagnostics, not signal validation.**

## Verdict and next steps

- **As-shipped the engine is broken for forward use: it self-latches after the
  first 15R drawdown and never resumes. It stays WAIT / paper-discipline only.
  Do NOT start a forward watch on the engine until the kill-switch is fixed.**
- The "+39R / PF 1.61" claim is **retired**: it came from the non-faithful,
  expanding-`vol_ratio` full-slice path. The live-faithful number is +8.75R,
  outlier-dependent and cost-fragile — and even that is just 5 months of 2020.
- **The signal itself is not proven dead.** With a sane (trailing-window) kill-
  switch it trades all six years at a thin-but-positive PF 1.1–1.5, recent year
  included. There is still **no validated edge** (PF barely above 1, cost-
  fragile), but the corpse was the risk control, not the signal.

**Next steps (risk-control fix first, human-gated — not signal tuning):**
1. ~~**Fix the kill-switch** to the *layered* design~~ **— DONE 2026-06-25.**
   `discipline.is_paused` is now layered: routine **trailing-window** pause
   (`drawdown_window_days`=90, same −15R `drawdown_budget_r`, auto-resumes as the
   cluster ages out) **plus** a hard all-time circuit breaker
   (`hard_drawdown_budget_r`=−30R, latched, human reset). Config-gated
   (`drawdown_window_days`<=0 falls back to the legacy all-time latch); budget
   unchanged. The scorecard now reports `windowed_drawdown_r` and `pause_reason`
   (`trailing_window`/`hard_breaker`). Hysteresis was *not* added — the existing
   post-loss `cooldown_bars` already damps boundary flapping; revisit if forward
   paper shows flapping.

   **Verification on real perp (2026-06-25, same fingerprinted cache):** with the
   layered switch live, the engine trades **235 trades** (vs 66 under the old
   latch — the trailing window correctly traded *through* routine −15R drawdowns
   instead of freezing after 5 months), net **+71.3R, PF 1.29, exp +0.30R**, and
   the hard breaker caps cumulative DD at **−30.03R** (vs the −55.9R the trailing
   rule alone allowed; `state: paused, pause_reason: hard_breaker`). This 235-
   trade set is also *healthier* than the latched view: only 15% outlier
   dependence (net +23R ex-best-trade) and **cost-robust to 3×** (+71/+46/+21R).
   Honest nuance: this signal still bleeds to −30R in the first half and latches
   there for human review (by design), so the recent year stays gated behind a
   human reset — the no-breaker exploratory run above is what shows the full 6.5y.
   The fix is a risk-control improvement, **not** a green light; engine stays
   paper/WAIT, no forward watch started.
2. Only after the fix, re-run the now-observable full window and re-check
   outlier dependence and ≥3× cost-stress on the larger trade set. A forward
   paper watch is justified only if it clears those.
3. The 4-factor confluence shows no robust edge; a genuine *signal* improvement
   means a different hypothesis, not re-tuning this one.

Reproduce against the fingerprinted cache above (throwaway harness; key logic =
rolling 1500-bar window through `evaluate_engine`): `/tmp/engine_windowed.py`
(forward-faithful primary), `/tmp/engine_rolling.py 90` (exploratory rolling
kill-switch), `/tmp/engine_freeze.py` (freeze-date probe).
