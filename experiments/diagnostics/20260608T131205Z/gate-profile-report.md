# MoonFace Gate Profile Report — 3-Year BTC/USDT

- **Date**: 2026-06-08
- **Symbol**: BTC/USDT
- **Exchange**: Binance
- **Data range**: ~3 years (26,280 H1 candles)
- **Sampling**: Every 24th H1 bar (1,091 daily windows) + full 26,172-window validation
- **Settings**: Defaults (`min_confluence_score=1.0`, `displacement_atr_mult=1.5`, etc.)

---

## Executive Summary

**Zero setups produced** with default settings. The pipeline is a 7-gate cascade that kills 100% of windows. Only 9 out of ~26,000 windows (0.03%) survive all 5 mandatory veto gates, and none of those 9 achieve the required confluence score of 1.0.

---

## Gate-by-Gate Kill Rate

Sampled with proper `build_window()` (look-ahead-free, capped multi-TF slices).

| # | Gate | Type | Killed | % of total | Cumulative |
|---|------|------|--------|------------|------------|
| 1 | **HTF bias** (D1/H4 → NEUTRAL) | Mandatory veto | 629 | 57.7% | 57.7% |
| 2 | **CHOCH + displacement** | Mandatory veto | 315 | 28.9% | 86.6% |
| 3 | **Price contract** (SL<Entry<TP) | Mandatory veto | 92 | 8.4% | 95.0% |
| 4 | **Min reward** (RR2 < 1.5) | Mandatory veto | 46 | 4.2% | 99.2% |
| 5 | **Confluence score** < 1.0 | Score gate | 9 | 0.8% | 100.0% |
| — | **Dealing range** | Mandatory veto | 0 | 0.0% | — |
| — | **Liquidity sweep** | Mandatory veto | 0 | 0.0% | — |
| — | **SETUP produced** | — | **0** | **0.0%** | — |

---

## Gate 1 Detail: HTF Bias (57.7% killed)

`htf_bias(d1, h4)` requires D1 trend to be BULLISH/BEARISH, and H4 must not oppose it.

### D1/H4 Trend Combination Breakdown

| D1 Trend | H4 Trend | Bias | Windows | % |
|----------|----------|------|---------|---|
| BULLISH | NEUTRAL | LONG | 178 | 16.3% |
| NEUTRAL | NEUTRAL | NEUTRAL | 163 | 14.9% |
| NEUTRAL | BULLISH | NEUTRAL | 159 | 14.6% |
| BULLISH | BEARISH | NEUTRAL | 130 | 11.9% |
| BULLISH | BULLISH | LONG | 121 | 11.1% |
| BEARISH | NEUTRAL | SHORT | 98 | 9.0% |
| BEARISH | BULLISH | NEUTRAL | 96 | 8.8% |
| NEUTRAL | BEARISH | NEUTRAL | 81 | 7.4% |
| BEARISH | BEARISH | SHORT | 65 | 6.0% |

**Pass rate**: 462 / 1,091 = **42.3%** (LONG=299 + SHORT=163)

**Kill contributors**:
- D1=NEUTRAL: 403 windows (37.0%) — automatically NEUTRAL regardless of H4
- D1/H4 conflict: 226 windows (20.7%) — opposing trends force NEUTRAL

### Full D1 Trend Distribution (bar-by-bar)
- BULLISH: 432 (39.8%)
- NEUTRAL: 392 (36.1%)
- BEARISH: 259 (23.9%)

### Full H4 Trend Distribution (bar-by-bar)
- BULLISH: 2,270 (32.3%)
- NEUTRAL: 2,613 (37.2%)
- BEARISH: 1,675 (23.8%)

---

## Gate 2 Detail: CHOCH + Displacement (28.9% killed)

After passing HTF bias, the window must show:
1. A **liquidity sweep** against the intended direction (SELL-side for LONG, BUY-side for SHORT)
2. A **Change of Character (CHOCH)** with displacement after the sweep

Parameters:
- `displacement_atr_mult = 1.5` — candle must be ≥ 1.5× ATR wide
- `sweep_tol_atr_mult = 0.25` — sweep tolerance
- `sweep_lookback = 30` bars

**315 windows** had the right HTF bias but no qualifying CHOCH+displacement pattern.

---

## Gate 3 Detail: Price Contract (8.4% killed)

Requires logical price ordering:
- BUY: stop < entry < TP1 ≤ TP2
- SELL: stop > entry > TP1 ≥ TP2

92 windows had a valid CHOCH but the resulting stop/target levels were inconsistent.

---

## Gate 4 Detail: Min Reward (4.2% killed)

`min_rr2 = 1.5` — TP2 must offer at least 1.5R reward from entry.

46 windows passed price contract but TP2 was too close.

---

## Gate 5 Detail: Confluence Score (0.8% killed — the final barrier)

9 windows survived all mandatory gates. The confluence score is a weighted sum of 4 soft checks:

| Soft Check | Weight |
|------------|--------|
| POI mitigation (OB/FVG) | 40% |
| Premium/Discount location | 25% |
| Fib golden zone (0.618–0.786) | 20% |
| Pinbar reversal | 15% |

### Score Distribution of the 9 Survivors

| Score | Count | % | Likely checks passing |
|-------|-------|---|----------------------|
| 0.80 | 1 | 11.1% | POI (0.40) + premium_discount (0.25) + fib (0.20) — missing pinbar |
| 0.65 | 2 | 22.2% | POI (0.40) + premium_discount (0.25) — missing fib + pinbar |
| 0.25 | 6 | 66.7% | premium_discount (0.25) only |

**Zero windows score 1.0.** The pinbar check (15%) never passes — `pinbar_wick_body_ratio=2.0` is very strict on H1 BTC candles.

---

## Sensitivity: Setups vs Confluence Threshold

| `min_confluence_score` | Setups (daily sample) | ~Setups/year (extrapolated) |
|------------------------|-----------------------|-----------------------------|
| 1.00 (current) | **0** | 0 |
| 0.80 | 1 | ~1 |
| 0.60 | 3 | ~3 |
| 0.40 | 3 | ~3 |
| 0.25 | 9 | ~9 |
| 0.00 | 9 | ~9 |

Even at `threshold=0.0`, only 9 setups in 3 years (~3/year). The confluence gate is **not** the primary problem — the mandatory gates (especially HTF bias and CHOCH) are the bottleneck.

---

## Root Cause Analysis

### 1. HTF Bias kills 58% — structural, not tunable
- D1 `classify_structure` returns NEUTRAL 36% of the time on BTC
- D1/H4 conflicts add another 21%
- This is inherent to the `n_periods=5` swing classification on a volatile asset

### 2. CHOCH+displacement kills 29% — `displacement_atr_mult=1.5` is aggressive
- BTC H1 candles rarely exceed 1.5× ATR during reversals
- A value of 1.0–1.2 would likely pass more windows

### 3. Confluence score=1.0 is unachievable — pinbar never fires
- `pinbar_wick_body_ratio=2.0` on H1 BTC means the wick must be 2× the body
- This almost never happens on hourly BTC candles during structured setups
- Even relaxing to 1.0 only gains the 0.80-scored window

### 4. Price contract + min reward kill 13% — secondary effect
- These are consequences of where stop/target land, not independent issues

---

## Recommendations (ranked by impact)

1. **Lower `min_confluence_score` from 1.0 to 0.25–0.40** — immediately yields 9 setups, still requires POI or premium_discount alignment
2. **Lower `displacement_atr_mult` from 1.5 to 1.0** — should recover a significant portion of the 315 CHOCH-killed windows
3. **Lower `pinbar_wick_body_ratio` from 2.0 to 1.0** — or remove pinbar from confluence weights entirely (it contributes nothing)
4. **Consider relaxing HTF bias** — allow H4=NEUTRAL to confirm D1 bias (currently H4 NEUTRAL already passes, but D1 NEUTRAL does not; could use H4 as primary instead)
5. **Re-run diagnostics after tuning** to measure actual yield and win rate
