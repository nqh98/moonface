# Exogenous-Conditioned BTC State Model -- Pre-registration

**Date:** 2026-06-25
**Lane:** `research/exogenous/` (PAPER ONLY, no promotion path)
**Status:** Frozen before any scoring run. All values below are locked.

---

## Hypothesis

- **H1:** BTC directional exposure has a durable edge conditional on exogenous
  macro + implied-vol state. Specific states (equity risk-on, USD weakness, VIX
  calm/stress, yield-curve steepness, DVOL premium) partition the return
  distribution such that conditional BTC drift is economically meaningful and
  stable across train and holdout.

- **H2 (null):** No such conditional edge exists. The 2025-26 BTC
  mean-reversion/decay observed in prior lanes is structural, not
  state-dependent. Exogenous conditioning adds no exploitable information.

This is a falsification attempt. The expected outcome is **NEGATIVE**.

---

## Frozen PRECOMMITTED_STATES

Verbatim from `src/moonface/research/exogenous/grid.py`:

| # | name | series_id | lag_days | lookback_days | op | threshold | sign |
|---|------|-----------|----------|---------------|----|-----------|------|
| 1 | `equity_riskon` | `SP500` | 1 | 20 | `>` | `0.0` | `+1` |
| 2 | `dollar_weak` | `DTWEXBGS` | 1 | 20 | `<` | `0.0` | `+1` |
| 3 | `vix_low` | `VIXCLS` | 1 | 0 | `<` | `20.0` | `+1` |
| 4 | `vix_high` | `VIXCLS` | 1 | 0 | `>` | `30.0` | `-1` |

**Derived states (reserved, counted in `N_TRIALS` for conservative deflation):**

| # | name | construction | sign |
|---|------|-------------|------|
| 5 | yield-curve steep | `DGS10 - DGS2` level | `+1` |
| 6 | dvol-premium high | DVOL-implied > realized vol | `-1` |

> **Scope note (honest):** the v1 Stage-1 screen evaluates the **4 precommitted
> single-series states** above. The 2 derived multi-series states (yield-curve,
> dvol-premium) are **reserved** — their construction is documented but they are
> **not screened** in this build. They are nonetheless counted in `N_TRIALS` so
> the DSR deflation penalizes the full pre-registered search breadth; this makes
> the Stage-2 gate **harder**, never easier. (See open item in the lane handoff.)

### N_TRIALS

```python
N_TRIALS = len(PRECOMMITTED_STATES) + 2   # = 6
```

Source: `src/moonface/research/exogenous/grid.py`

---

## Staged Gate

### Stage 0 -- Newdata readiness

Macro series (`FRED` provider, `macro_series` data class) and implied vol
(`Deribit` provider, `implied_vol` data class) must pass the
`assess_manifest` gate from `research/newdata.py`. Fields, coverage,
monotonicity, and license are checked.

### Stage 1 -- Gross conditional-drift screen

```python
SCREEN_T = 2.0   # |t| >= 2.0 to survive
```

Source: `src/moonface/research/exogenous/screen.py`

For each state, compute the Newey-West t-statistic of conditional BTC daily
returns (signed by `state.sign`). If **no state** reaches `|t| >= 2.0`,
`screen_passes` returns `False` and the lane is **CLOSED NEGATIVE** at Stage 1.

### Stage 2 -- Deflated Sharpe Ratio

```python
deflated_sharpe >= 0.95,  n_trials = N_TRIALS (= 6)
```

Computed by `dsr_of_trades` in
`src/moonface/research/exogenous/evaluate.py`. Pooled over the full grid.

### Stage 3 -- Walk-forward economic bar

Verbatim from `src/moonface/research/econ.py`:

```python
ECON_BAR = EconBar(
    profit_factor=1.2,
    expectancy_r=0.05,
    mar_floor=0.5,
    max_dd_r=30.0,
    robust_frac=0.6,
)
```

All five thresholds must be met. The bar is imported, never redefined.

### Stage 4 -- ETH/SOL transfer

All-pass transfer: the surviving state(s) are tested on ETHUSDT and SOLUSDT
daily klines (same window, same macro conditioning). `transfer_passes`
evaluates whether the conditional edge generalizes across BTC-correlated
assets.

### Stage 5 -- Forward paper rule

Once a survivor reaches Stage 5, the forward paper watch is bound via
`EXO_FORWARD_REGISTRATION.md`. Outcomes:

| Outcome | Condition |
|---------|-----------|
| `REAFFIRM` | net_r > 0, closed trades >= min, elapsed weeks >= min, drawdown within budget |
| `DOWNGRADE_DD` | drawdown exceeds budget (first negative outcome) |
| `DOWNGRADE_HORIZON` | minimum trade/week counts met but gate not passed |
| `INCONCLUSIVE` | insufficient trades or elapsed time |

Forward constants (from `src/moonface/research/exogenous/forward.py`):

```
FORWARD_MIN_TRADES = 20
FORWARD_MIN_WEEKS = 12.0
MAX_DD_BUDGET     = 0.30
```

---

## Window

```
start_ms = 1577836800000   (2020-01-01 00:00:00 UTC)
end_ms   = 1782300000000   (2026-06-23 00:00:00 UTC)
```

Source: CLI defaults in `tools/exogenous_btc.py` (`--start-ms`, `--end-ms`).

---

## Data Sources

| Source | Key required | Cadence | Variables | Since |
|--------|-------------|---------|-----------|-------|
| FRED | No | Daily (T+1 pub lag) | SP500, DTWEXBGS, VIXCLS, DGS2, DGS10 | varies |
| Deribit DVOL | No | Daily | dvol_open, dvol_high, dvol_low, dvol_close | ~2021+ |
| Binance | No (existing) | Daily klines | BTC/ETH/SOL OHLCV | existing universe_data |

FRED fetches use `fetch_fred_series` (no API key). Deribit fetches use
`fetch_dvol` (no key, public endpoint). BTC/ETH/SOL daily klines use
`universe_data.fetch_daily_klines` (existing infrastructure).

---

## Look-Ahead Discipline

All FRED macro series use a publication-lag aligned feature:
`lag_days = 1` (T+1 business-day publication lag for daily macro data).
This is enforced by `StateDef.lag_days` and implemented in `exo_features.py`
via `aligned_value_at`. A gating test in the test suite verifies that
look-ahead is absent (the feature value at time t uses only data published
by t - lag_days).

---

## Kill Rule

**Fail ANY stage** => lane **CLOSED NEGATIVE**, no v2.

This is absolute. No parameter retuning, no state additions, no window
adjustments. The pre-registered hypothesis is either supported or falsified
by the frozen procedure.

---

## Expected Outcome

**NEGATIVE.**

Consistent with the program's structural-drawdown findings across all prior
lanes (72-cell system search, practical signal discovery, dual-timeframe,
playbook engine, confluence engine, portfolio tournament, cross-sectional
premia). Exogenous conditioning is a falsification attempt, not an
exploration. A Stage-1 kill (no state clears `|t| >= 2.0`) would be the
expected and valuable outcome -- confirming that BTC's 2025-26 decay is
structural, not state-dependent.
