# capitulation_backtest.py — Quantitative Capitulation (Mean-Reversion) Baseline

**Design spec / pre-registration — 2026-07-08**
**Status:** approved, pre-implementation. **Params, split, and gate are FROZEN as of this document.**
**Kind:** pre-registered confirmatory research study (long-only, mean-reversion). Standalone
prototype; **not wired into any engine.**

> Placed here (tracked `experiments/`) rather than `docs/research-log/specs/` because `docs/` is in
> the user's global `.gitignore_global` and does not persist in this repo; `experiments/` is the
> durable record. Same convention as `experiments/macro_regime/`.

---

## 0. Context & honest framing

The MoonFace program has a single, exhaustively-replicated negative result (the "drawdown wall"),
and the predictive macro-regime instrument was just closed FRAGILE/DEAD on the OOS era-probe. This
study pivots to a **rule-based structural anomaly**: *Quantitative Capitulation* — identify extreme
liquidation cascades + crowd panic and fade them long-only.

The mechanism is **new to this program** (forced-liquidation overshoot reversion, gated on extreme
negative funding), not a re-framing of a closed macro/exogenous lane. It is nonetheless treated with
the program's standard anti-overfitting discipline: **pre-registration (this doc) + a single sealed
out-of-sample window opened exactly once.** The in-sample slice is a *descriptive base rate* (params
are frozen, so it is **not** a tuning surface); the sealed slice is the **confirmatory verdict.**

No edge is claimed until the sealed OOS bootstrap CI clears the gate in §6. A pass here is a
*candidate*, not a deployable — it would still owe a forward paper period before any live claim.

---

## 1. Resolved design decisions (frozen)

| Fork | Decision |
|------|----------|
| Rigor | Pre-registered confirmatory; single-shot sealed OOS. |
| Split | In-sample `2020-01-01 → 2024-06-30`; **sealed OOS `2024-07-01 → present`.** |
| Deps / location | Isolated under `experiments/capitulation/` with own venv + pinned `requirements.txt`; quarantined from the stdlib-only main tree and the main pytest run. numpy + pandas only. |
| Asset / timeframe | BTC-USD, 1H. |
| Direction | Long only. |
| Keltner | EMA(20) ± **3.0**×ATR(20); trigger = close below **lower** band. |
| Volume | Trigger bar volume ≥ **95th** pct of trailing **30-day** hourly volume, **and** bar is a down-candle (`close < open`). |
| Funding (primary) | Funding ≤ **5th** pct of trailing **30-day** funding window (`--funding-mode percentile`). |
| Funding (robustness) | Fixed threshold ≤ **−0.01%** per 8H epoch (`--funding-mode fixed`) — documented variant, **not** a second confirmatory test. |
| Cooldown | **24 bars** after a fire (one trade per cascade). |
| TP / SL | **+2% / −1%**, SL-first, same-bar tie = loss, **48-bar** timeout → scratch-at-close. |
| Primary metric | Mean forward **24H log-return** after signal, tested vs 0. |
| Secondary | Mean forward 4H log-return (reported, not gated). |
| Win-rate | 2%/1% TP/SL win-rate — **descriptive only**, not the gated statistic. |
| Gate | Block-bootstrap **95% CI on mean 24H log-return excludes 0 on the positive side**, evaluated on the **sealed OOS trades**. Underpowered flag if n_OOS < 20. |

---

## 2. Layout

```
experiments/capitulation/
  capitulation_backtest.py    # module: OO classes + simulator + CLI (this spec)
  requirements.txt            # numpy, pandas (pinned)
  README.md                   # setup + "pre-registered confirmatory" framing
  DESIGN.md                   # this file (the frozen pre-registration)
  RESULTS.md                  # written ONCE, after the run
  data/                       # gitignored working snapshots (if any)
  tests/test_capitulation.py  # deterministic, synthetic, no-network
```

- Own venv at `experiments/capitulation/.venv`.
- **Not** added to root `pyproject.toml`; excluded from the main pytest run.

---

## 3. Data

Read directly from existing repo caches (no network fetch required):

| Feed | File | Format |
|------|------|--------|
| OHLCV 1H | `.backtest_cache/BTCUSDT_1h.csv` | headerless: `ts_ms, open, high, low, close, volume` (~56.7k rows from 2020-01-01) |
| Funding | `.backtest_cache/unifunding_BTCUSDT.csv` | headerless: `ts_ms, funding_rate` (8H epochs, 2020-01-01 → present) |

- Both paths are **CLI arguments** defaulting to the above, honoring the "provided historical
  dataset" requirement (the loader accepts any file of the same schema).
- `ts_ms` is epoch milliseconds, UTC. Parse to a UTC `DatetimeIndex`.
- **Funding alignment:** funding publishes on 8H epochs. Forward-fill onto the hourly grid so that at
  bar `t` the "current funding" is the most recent epoch published **at or before** `t`. No future
  epoch ever visible at `t`.
- Rows with missing OHLCV or pre-first-funding bars are dropped from the eligible-signal universe
  (recorded in the tear-sheet as `n_bars_dropped`).

---

## 4. Zero-leakage rule (crucial, explicit)

Every rolling input is computed through bar `t−1` (i.e. `.shift(1)` applied to the rolling result),
then compared against bar `t`'s realized values:

- **Keltner bands** — `EMA(20)` and `ATR(20)` are computed on bars up to `t−1`; bar `t`'s close is
  tested against that prior lower band. (Strictly causal: the band is fully known before `t` opens.)
- **Volume distribution** — the 30-day hourly-volume percentile threshold is built from the window
  ending at `t−1`; bar `t`'s volume is tested against it.
- **Funding distribution** — the 30-day funding percentile threshold is built from the
  hourly-forward-filled funding ending at `t−1`; bar `t`'s current funding is tested against it.

A dedicated unit test constructs a series where a late spike would change a band/threshold and
asserts the signal at `t` is unaffected by information at `≥ t`.

---

## 5. Components (each independently testable)

1. **`load_data(ohlcv_path, funding_path, start, end) -> DataFrame`**
   Reads caches, parses UTC index, forward-fills funding onto the hourly grid, merges, slices
   `[start, end]`. Returns columns: `open, high, low, close, volume, funding`.

2. **Indicators (causal helpers)** — `ema(series, n)`, `atr(df, n)`, `keltner_lower(df, ema_n,
   atr_n, mult)`, `rolling_percentile_threshold(series, window, pct)`. Each returns a series already
   `.shift(1)`-aligned so callers compare against bar `t` directly.

3. **`CapitulationStrategy`** — OO, all thresholds parameterized in `__init__`:
   `ema_period=20, atr_period=20, atr_mult=3.0, vol_pct=95, vol_window_days=30, funding_pct=5,
   funding_window_days=30, funding_mode="percentile", fixed_funding_thresh=-0.0001,
   cooldown_bars=24, tp=0.02, sl=0.01, timeout_bars=48`.
   `.generate_signals(df) -> Series[bool]`: computes the three conditions, ANDs them, then applies
   the 24-bar cooldown (suppress fires within `cooldown_bars` of the previous accepted fire).

4. **`simulate_trades(df, signals, tp, sl, timeout_bars) -> DataFrame`**
   For each accepted signal at close of `t`: entry = `close[t]`; walk forward bars `t+1…t+timeout`.
   - If a bar's `low ≤ entry*(1−sl)` → **loss** (SL-first: SL checked before TP within a bar).
   - Else if `high ≥ entry*(1+tp)` → **win**.
   - Same-bar where both would trigger → **loss** (SL-first tie rule).
   - No resolution by `t+timeout` → **scratch-at-close**: win iff `close[t+timeout] > entry`.
   Records per-trade: entry_ts, outcome ∈ {win, loss, scratch_win, scratch_loss}, bars_held.

5. **`forward_returns(df, signals, horizons=(4,24)) -> DataFrame`**
   Log-return `ln(close[t+h] / close[t])` for h ∈ {4, 24} bars. Trades without a full `t+h` bar
   (right edge of data) are dropped from that horizon's mean and counted.

6. **`block_bootstrap_ci(returns, block=24, n_boot=10000, alpha=0.05) -> (lo, hi)`**
   Stationary/moving-block bootstrap on the ordered OOS signal returns (block length 24 bars to
   respect residual autocorrelation) → 95% CI on the mean. Seeded RNG for reproducibility.

7. **`tear_sheet(...)`** — prints, **separately for in-sample and sealed OOS**:
   `n_signals`, win-rate (TP/SL, descriptive), mean fwd 4H log-ret, mean fwd 24H log-ret, mean trade
   return, 95% bootstrap CI on 24H (and 4H), and an `UNDERPOWERED` flag if `n < 20`. The **verdict
   line** reads off the sealed-OOS 24H CI: `PASS` iff CI lower bound > 0, else `FAIL`
   (or `UNDERPOWERED — inconclusive`).

---

## 6. Confirmatory gate (frozen)

- **Statistic:** mean forward 24H log-return of sealed-OOS signals.
- **Null H₀:** mean = 0 (capitulation long has no edge).
- **Decision rule:** `PASS` iff the block-bootstrap 95% CI lower bound > 0.
- **Power guard:** if n_OOS < 20 accepted trades, report `UNDERPOWERED — inconclusive` (neither pass
  nor fail; the seal is considered *spent* regardless — no second look).
- The in-sample CI is reported for context only and carries **no** verdict weight.
- The sealed window is opened **once**. Re-running with different params after seeing OOS voids the
  pre-registration.

---

## 7. CLI

```
experiments/capitulation/.venv/bin/python experiments/capitulation/capitulation_backtest.py \
  --ohlcv .backtest_cache/BTCUSDT_1h.csv \
  --funding .backtest_cache/unifunding_BTCUSDT.csv \
  --oos-cutoff 2024-07-01 \
  --funding-mode percentile      # or: fixed  (robustness variant)
```

Prints both tear-sheets and the verdict line. All frozen params overridable via flags **for
robustness/stability checks only** — the registered run uses the defaults in this doc.

---

## 8. Tests (deterministic, synthetic, no network)

- **fires-once:** injected single capitulation bar (below lower Keltner, ≥95th-pct down-volume,
  ≤5th-pct funding) → exactly one signal at that bar.
- **all-three-required:** dropping any one condition → zero signals.
- **leakage-guard:** a spike at `≥ t` does not change the signal decision at `t`.
- **SL-first:** a future bar whose range spans both TP and SL resolves as **loss**.
- **cooldown:** two qualifying bars within 24 bars → only the first fires.
- **timeout-scratch:** no TP/SL within 48 bars → scratch, win iff final close > entry.
- **funding-align:** funding forward-fill never exposes a future epoch at bar `t`.

---

## 9. Deliverable after the run

`RESULTS.md` (written once): both tear-sheets, the sealed-OOS verdict, n-counts, the bootstrap CIs,
the robustness read from `--funding-mode fixed`, and an honest one-paragraph interpretation
consistent with §0 (candidate vs. dead; no deployment claim from this study alone).
