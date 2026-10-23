# Tunnel Core + CHOP — Per-Coin Optimization & 4h Signal Engine

**Date:** 2026-06-15
**Status:** Approved design, ready for implementation plan
**Reference strategy:** `docs/script/tunnel_core_chop.pine` (TradingView Pine v6, unchanged)

## 1. Goal

Port the `tunnel_core_chop.pine` strategy into a self-contained Python module,
find the best-performing 4h configuration **independently for each supported
coin**, validate every configuration through the repository's existing
statistical ladder, and produce a per-coin registry that a batch signal engine
reads every 4 hours to emit LONG / SHORT / WAIT per coin.

Robustness is the objective, not raw return. A configuration that performs well
in-sample but fails the holdout / deflated-Sharpe / lockbox gates is rejected.
Given this program's documented history (every pre-registered family to date has
been rejected by the same gate), a legitimate outcome is **WAIT for every coin**.
The design records that honestly rather than weakening the gate.

## 2. Decisions (locked during brainstorming)

| Decision | Choice |
|---|---|
| Port fidelity | Full faithful port, in a **new module** |
| Validation connection | New sequential simulator → R-stream → **existing ladder gates** |
| Universe | All cached 4h coins (deduped) |
| DSR trial count | **Per-coin = one domain each**, grid_size = per-coin config count |
| Search space | **Core ~6 params**; rest pinned to Pine defaults |
| Data depth | **Fetch deeper history** per coin (back to listing) before searching |
| Signal output | **Registry + multi-coin batch signal** engine |

## 3. Architecture

New package `src/moonface/tunnel/`, independent of the `edge`/`research` signal
generators but **reusing the proven statistical gates** (`research/ladder.py`,
`research/metrics.py`) so the strategy is held to the same honesty bar.

```
src/moonface/tunnel/
  indicators.py   # EMA, ATR, RSI, MACD-hist, Choppiness Index (pure fns over Candle lists)
  state.py        # per-bar tunnel state: slope, vol-regime, chopOK, bull/bear, pullback zones
  entry.py        # tunnel_entry(candles, params) -> [(i, "LONG"/"SHORT")] (Pine composite signal)
  simulator.py    # sequential bar-walker: position mgmt -> R-stream [(i, net_R, atr_frac)]
  metrics.py      # Sortino (downside-deviation) + any tunnel-specific stats not in research/metrics
  grid.py         # the ~6-param core search grid + Pine-default pins
  registry.py     # per-coin registry schema (params, stats, validation) read/write
  signal.py       # batch evaluator: registry -> {coin: Signal(LONG/SHORT/WAIT)}
tools/tunnel.py   # CLI: fetch | search | report | signal
```

**Boundary.** `entry.py` decides *when/which side*. `simulator.py` decides
*what happens to the trade* (the path-dependent part). They are independently
testable: entry against a fixture candle series; simulator against a constructed
entry + price path.

**Reuse, not reinvention.** The simulator emits the same
`(entry_index, net_R, atr_frac)` triple shape that `ladder.r_stream` produces,
so it feeds straight into `ladder.evaluate_research`, `stage1/2/3/4_passed`,
`metrics.equity_summary`, and `metrics.deflated_sharpe` — same −30% drawdown
budget, same DSR ≥ 0.95, same one-touch lockbox. Cost uses the ladder's
`COST_FRACTION = 0.001` round-trip, identically.

## 4. Faithful Pine port

### 4.1 indicators.py
Pure functions matching the Pine math:
- `ema(closes, length)`, `atr(candles, length)` (Wilder; reuse `moonface.risk.atr`
  if signature-compatible), `rsi(closes, length)`, `macd_hist(closes, 12, 26, 9)`.
- `choppiness(candles, length)` = `100 * log10(sum(TR, length) / max(HH−LL, mintick)) / log10(length)`,
  matching Pine lines 76–80 including the `mintick`-floored range and the
  `ta.tr(true)` first-bar handling.

### 4.2 state.py (mirrors Pine 64–112)
- bands `ema ± atr*mult`; `slope = ema − ema[slopeLen]`;
  `volRatio = atr / sma(atr, emaLen)`; `wideTunnel = volRatio >= volMin`.
- `tunnelBull = bullSlope & aboveCenter & wideTunnel & chopOK` (and bear).
- pullback zones `nearLower / nearUpper` + inner `nearCenterDn / nearCenterUp`.

### 4.3 entry.py (mirrors Pine 165–172)
`tunnel_entry(candles, params)` reproduces the composite signal:
`(longOuter or longInner)` with RSI / MACD / candle confirmation gates. Returns
`(i, side)` per framework convention, stopping at `len−1` to leave the fill bar.
**The consecutive-loss brake is NOT here** — it is path-dependent and lives in
the simulator.

### 4.4 simulator.py (the heart of the faithful port)
Sequential bar-walker maintaining `position`, `slPrice`, `tpPrice`, `tunnelSL`,
`trailOn`, `entryATR`, `consLosses`, `coolCounter`. Per bar it replicates Pine's
execution model:
- **fill** on the bar after the signal, using the **signal-bar ATR**
  (Pine `pendingATR` fix, line 247) so stop distance matches sizing.
- **bracket**: SL = `entry − slATR*atr`; TP at the `rrRatio` multiple.
- **breakeven**: once `close > entry + beATR*atr`, lift stop to entry (+ optional
  `beTicks`).
- **tunnel-trail**: after `trailAct*atr` favorable, ratchet the stop to the
  opposite band (`lowerBand − atr*(trailBand−1)`), monotonic.
- **loss-brake**: real last-closed-trade P&L < 0 → `consLosses++`,
  `coolCounter = coolBars`; `consLosses ≥ maxConsL & cooling` ⇒ skip new entries.
- **exit priority** within a bar: if both stop and target are touchable, resolve
  **stop-first** (pessimistic; matches the framework's conservative convention).

Output: `[(entry_index, net_R, atr_frac)]` chronological, one R per **closed
trade**, where `net_R = realized_R − COST_FRACTION / atr_frac`.

### 4.5 Documented fidelity divergences (recorded, not hidden)
1. **Same-bar stop/target ambiguity** — intrabar order is unknowable from OHLC;
   resolved pessimistically (stop-first). Slightly conservative.
2. **Position sizing** — Pine sizes by `riskPct`/equity (compounding qty). The
   ladder works in **R-space** with a fixed `fraction` applied in
   `equity_summary` (leverage-clamped at 5×). The port keeps faithful R-multiples
   and lets the ladder's fraction model handle equity — the framework's standard
   treatment, keeping DSR/MAR comparable across coins. This is an R-space port,
   not a tick-level equity replica.
3. **`process_orders_on_close=false`** — next-bar fill via the existing `_risk`
   convention.

## 5. Per-coin search & validation

### 5.1 Universe
All ~21 cached 4h symbols, deduped (ccxt-style `BTC_USDT:USDT` → `BTCUSDT`):
BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ARBUSDT, AVAXUSDT,
LINKUSDT, NEARUSDT, FILUSDT, ETCUSDT, FTMUSDT, TRBUSDT, HIGHUSDT, JASMYUSDT,
PEOPLEUSDT, 1000PEPEUSDT, 1000SHIBUSDT, 1000FLOKIUSDT. Final list resolved from
the cache at run time. Each coin is an **independent experiment / domain**.

### 5.2 Data
`tools/tunnel.py fetch` extends each coin's 4h archive back to listing via the
existing `fetch_perp_candles` (Binance Vision / fapi, delisting-inclusive),
cached in the standard `OhlcvCache` format. Windows are frozen once fetched →
reproducible. (The currently cached 4h span is only ~2 years; fetching deeper is
required for adequate trade counts and regime coverage.)

### 5.3 Core search grid (~6 params; shape — exact values finalized in the plan)
| param | sweep |
|---|---|
| `emaLen` | 34, 50, 89 |
| `atrMult` (up = lo) | 1.5, 2.0, 2.5 |
| `chopMax` | 38.2, 50, 61.8 |
| `slATR` | 1.0, 1.5, 2.0 |
| `rrRatio` | 1.5, 2.0, 2.5, 3.0 |
| `pbZone` | 0.3, 0.4, 0.5 |

= 972 configs / coin. `atrMult` deliberately ties the upper and lower band
multipliers together (Pine exposes `i_upMult`/`i_loMult` separately) — a
symmetric tunnel halves a grid dimension; an asymmetric sweep can be a later
extension. **Pinned** to Pine defaults: RSI/MACD/candle confirms ON, inner
pullback ON, slope/vol thresholds, trail/breakeven/brake defaults.

### 5.4 Validation ladder (reused, thresholds unchanged)
Each coin = one domain, `grid_size = 972`:
1. **Stage 1 — screen** (first 70% of bars): ≥ 30 trades AND screen
   `expectancy_R > 0`.
2. **Stage 2 — OOS holdout** (last 30%): `holdout_mar > 0` AND
   `holdout_drawdown ≥ −0.30`.
3. **Stage 3 — DSR**: deflated Sharpe ≥ 0.95, deflated against all 972 trials'
   SR variance and count (the gate that has rejected every prior family).
4. **Stage 4 — lockbox** (one-touch tail after the fence): `tail_mar ≥ 1.0`,
   `tail_trades ≥ 10`, `tail_drawdown ≥ −0.30`.

A coin gets a deployable config only if a config clears **all four**. Best config
per coin = the stage-4 survivor with the best risk-adjusted metric (lockbox MAR,
tie-broken by Sortino then Sharpe).

**Sortino** is not in the shared `EquitySummary`; it is added in `tunnel/metrics.py`
(downside-deviation Sharpe) without touching `research/metrics.py`.

### 5.5 Registry (`experiments/tunnel/registry.json`)
Per coin: selected params; in-sample / holdout / lockbox stats (MAR, Sharpe,
Sortino, max-DD, trades, net return); DSR; pass/fail status; provenance (grid
hash, data window, fence timestamp). Coins with zero stage-4 survivors are
recorded as `status: "no_edge"` → WAIT. Schema is versioned for forward
compatibility.

## 6. Batch signal engine

`tunnel/signal.py` + `tools/tunnel.py signal`:
- Loads `registry.json`. For each coin with `status: "pass"`, loads its latest
  closed 4h candles and runs the same `state` + `entry` + position-state logic on
  the most recent closed bar, emitting one `Signal(decision, price, invalidation,
  fraction, reason, timeframe="4h", tier)` (reusing the existing
  `signal/evaluate.py::Signal` dataclass).
- Coins with `status: "no_edge"` emit `WAIT` by construction — signals are never
  fabricated for un-validated coins.
- Output: a coin → Signal table (JSON + human-readable). Designed to run every 4h;
  scheduler/cron wiring is operational and **out of scope** — the engine is
  invokable and idempotent.
- **Sim/live parity guard**: a test asserts the signal engine's decision on a
  historical bar equals the simulator's entry at that same index, so live signals
  cannot silently diverge from what was validated.

## 7. Final report (`tools/tunnel.py report` → `experiments/tunnel/REPORT.md`)
1. **Best config per coin** — params table.
2. **Validation & holdout results** — per coin: screen / holdout / lockbox MAR,
   Sharpe, Sortino, max-DD, trades, DSR, stage reached.
3. **Signal generation logic** — entry / exit / position-management rules + the
   two fidelity caveats from §4.5.
4. **Coin ranking by risk-adjusted performance** — sorted by lockbox MAR
   (then Sortino); survivors above non-survivors.
5. **Recommended deployment configuration** — stage-4 survivors only; an explicit
   "deploy none / WAIT-all" statement if that is the honest result, consistent
   with the program's standing conclusion.

## 8. Testing (TDD throughout)
- `indicators` vs. hand-computed values (incl. CHOP edge cases).
- `entry` against fixture candle series (outer + inner, confirmation gating).
- `simulator` against constructed price paths: verify breakeven lift, trail
  ratchet (monotonic), loss-brake pause/cooldown, same-bar stop-first pessimism.
- ladder integration on a synthetic R-stream (stages 1–4 transitions).
- registry round-trip (write → read → equality), schema-version handling.
- signal/sim parity on historical bars.
- report rendering on a fixture registry (incl. all-`no_edge` case).
- `ruff` clean; existing suite stays green (per workflow conventions).

## 9. Scope guard (YAGNI)
- No new `EXIT_REGISTRY` entries — the simulator owns position management.
- No changes to the promotion/journal git-gate or live order routing.
- No scheduler/cron implementation (engine is invokable; scheduling is ops).
- The Pine file is reference-only and unchanged.

## 10. Honest-outcome statement
This pipeline runs a faithful Tunnel+CHOP port through the same calibrated gate
that has rejected every prior pre-registered family. "Best config per coin" may
legitimately resolve to `no_edge` / WAIT for many or all coins. The deliverable
is a truthful registry and report, not a guaranteed deployable strategy.
