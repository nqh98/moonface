# vol_compression_backtest.py — Volatility Compression → Expansion (Straddle-Proxy) Baseline

**Design spec / pre-registration — 2026-07-08**
**Status:** approved (blanket "apply your recommend"), pre-implementation. **Params, split, and gate
are FROZEN as of this document.**
**Kind:** pre-registered confirmatory research study (direction-agnostic volatility-expansion
capture). Standalone prototype; **not wired into any engine.**

> Placed here (tracked `experiments/`) rather than `docs/research-log/specs/` because `docs/` is in the
> user's global `.gitignore_global`. Same convention as `experiments/capitulation/` and
> `experiments/session_sweeps/`.

---

## 0. Context & honest framing

Third lane after capitulation (CLOSED underpowered/dead) and session_sweeps (CLOSED well-powered
FAIL). Both tested **directional/return** edges. This lane is deliberately **distinct**: the trigger
is a volatility **state** (a compression/squeeze) and the tested outcome is a volatility
**expansion** captured **direction-agnostically** — no directional bet anywhere.

**The tautology trap (and how the design avoids it):** "vol expands after compression" is nearly
tautological — realized vol mean-reverts, so `future_RV > current_RV | compressed` is almost
guaranteed and worthless (a statement about vol, not money). The gate therefore tests an
**executable, direction-agnostic, net-of-cost payoff**: a synthesized long straddle **priced off the
compressed volatility itself**. You "buy" the straddle at the cheap squeeze price and win only if
realized expansion exceeds that fair price plus cost. Under the null (compression carries no
expansion information) the payoff nets to **−cost < 0**, so the test can genuinely FAIL. That is the
whole point — the direction-agnostic, net-of-cost payoff is the untested, falsifiable part.

We have **no options data** (Deribit collection not ready until ~2027), so the straddle is
synthesized from spot. Limitation, documented: the spot synthesis pays **no premium when no
expansion occurs** (a real option bleeds theta), so it is mildly optimistic vs. a real straddle; the
frozen cost term and the fair-premium subtraction are the guards against a free lunch.

No edge is claimed until the sealed OOS bootstrap CI clears the gate in §6. A pass is a *candidate*,
not a deployable.

---

## 1. Resolved design decisions (frozen)

| Fork | Decision |
|------|----------|
| Rigor | Pre-registered confirmatory; single test; single-shot sealed OOS. |
| Timeframe | BTCUSDT **1h** (`.backtest_cache/BTCUSDT_1h.csv`). |
| Return | `r_t = ln(close_t / close_{t-1})` (hourly log-return). |
| Compression feature | `RV_N(t)` = sample std of the last **N = 24** hourly returns (per-bar sigma). |
| Trigger | `RV_N(t) <= q20(t)` where `q20(t)` = 20th percentile of `RV_N` over the trailing **W = 720 bars (30d)** window **ending at t−1** (`.shift(1)`, strictly causal). |
| Cooldown | **24 bars** after an accepted signal (one signal per squeeze episode). |
| Payoff (per signal) | `net = |ln(close[t+H]/close[t])| − premium − cost` (direction-agnostic). |
| Premium | `premium = sqrt(2/pi) * RV_N(t) * sqrt(H)`. `sqrt(2/pi)=E|N(0,1)|` — the fair ATM-straddle expected payoff under the compressed vol. **Not** a free parameter. |
| Cost | frozen `0.0006` (6 bp all-in round-trip), charged on every signal. |
| Horizon | **H = 24 bars (1 day) — PRIMARY (gated)**; H = 48 bars (2 day) — secondary, reported not gated. |
| Split | in-sample `2020-01-01 → 2024-06-30`; **sealed OOS `2024-07-01 → present`**. |
| Gate | moving-block bootstrap (block 20, 10,000 resamples, seed 0) **95% CI lower bound > 0** on the sealed-OOS mean net payoff. |
| Power guard | `min_n = 30` (> block 20 ⇒ no degenerate CI; the capitulation lesson). `n_OOS < 30` ⇒ `UNDERPOWERED — inconclusive`. |
| Robustness (not gated) | (a) range/ATR-squeeze feature variant (`--feature atr`); (b) alt horizon. Documented only. |
| Deps / location | Isolated `experiments/vol_compression/` with own venv + pinned `requirements.txt`; numpy + pandas only; quarantined. |

---

## 2. Layout

```
experiments/vol_compression/
  vol_compression_backtest.py    # module: OO class + analytics + CLI (this spec)
  requirements.txt               # numpy, pandas, pytest (pinned)
  README.md                      # setup + "pre-registered confirmatory" framing
  DESIGN.md                      # this file (the frozen pre-registration)
  RESULTS.md                     # written ONCE, after the run
  tests/test_vol_compression.py  # deterministic, synthetic, no-network
  tests/conftest.py              # puts module on sys.path
```

- Own venv at `experiments/vol_compression/.venv`. **Not** in root `pyproject.toml`; excluded from
  the main pytest run.

---

## 3. Data

| Feed | File | Format |
|------|------|--------|
| OHLCV 1h | `.backtest_cache/BTCUSDT_1h.csv` | headerless: `ts_ms, open, high, low, close, volume` (~56.7k rows, 2020-01-01 → ~2026-06) |

- `ts_ms` epoch ms, UTC → UTC `DatetimeIndex`, sorted ascending. Path is a CLI arg defaulting to the
  above.

---

## 4. Zero-leakage rule (explicit)

- `RV_N(t)` uses returns through bar `t` (known at close `t`).
- The compression **threshold** `q20(t)` is the 20th percentile of `RV_N` over the window ending at
  `t−1` (`.shift(1)`), so the decision at `t` never uses `RV_N(t)` in its own threshold.
- `premium(t)` uses `RV_N(t)` and the constant `H` — all known at `t`.
- Only the payoff's realized `|move|` over `t→t+H` looks ahead (that is the outcome). Signals without
  a full `t+H` bar (right edge) are dropped from the gated horizon.

---

## 5. Components (each independently testable)

1. **`load_data(ohlcv_path, start=None, end=None) -> DataFrame`** — headerless 1h cache, UTC index,
   columns `open,high,low,close,volume`, date-sliced inclusive. (Same shape as the session_sweeps
   loader.)

2. **Feature helpers (causal):**
   - `log_returns(close) -> Series` = `ln(close/close.shift(1))`.
   - `realized_vol(close, n) -> Series` = rolling std (ddof=1) of `log_returns` over `n`, `min_periods=n`.
   - `atr_pct(df, n) -> Series` = ATR(n)/close (for the `--feature atr` robustness variant).
   - `rolling_pct_threshold(series, window, pct) -> Series` = `series.shift(1).rolling(window,
     min_periods=window).quantile(pct/100)` (the compression threshold; reused pattern).

3. **`VolCompressionStrategy`** — OO, parameterized:
   `rv_period=24, comp_window_days=30, comp_pct=20, cooldown_bars=24, fwd_horizon=24,
   secondary_horizon=48, cost=0.0006, feature="rv"`.
   - `.compression_signals(df) -> Series[bool]`: `feature="rv"` → `RV_N <= q20` (threshold from
     §4); `feature="atr"` → `atr_pct <= q20` of `atr_pct`. Then apply the 24-bar cooldown (suppress
     fires within `cooldown_bars` of the previous accepted fire).
   - `.premium_at(df) -> Series`: `sqrt(2/pi) * feature_vol(t) * sqrt(fwd_horizon)`, where
     `feature_vol` is `RV_N` (rv mode) or `atr_pct` (atr mode) — the per-bar sigma used for pricing.

4. **`straddle_payoffs(df, signals, sigma, horizons=(24,48), cost=0.0006) -> dict[int, np.ndarray]`**
   `sigma` = the per-bar feature vol at each bar (`RV_N` or `atr_pct`). For each accepted signal at
   position `i` and horizon `h`: `net_h = |ln(close[i+h]/close[i])| − sqrt(2/pi)*sigma[i]*sqrt(h) −
   cost`. Premium is thus recomputed per horizon (horizon-consistent). Right-edge signals (no `i+h`
   bar) dropped per horizon.

5. **`block_bootstrap_ci(returns, block=20, n_boot=10000, alpha=0.05, seed=0) -> (lo,hi)`** — moving-
   block bootstrap 95% CI on the mean; `(nan,nan)` on empty. (Reused hardened version from
   session_sweeps; `min_n>block` prevents degeneracy.)

6. **`slice_stats(df, strategy) -> dict`** — keys: `n_signals, win_rate, mean_net_1d, mean_net_2d,
   ci1d_lo, ci1d_hi, ci2d_lo, ci2d_hi`. `win_rate` = fraction of 1d net payoffs > 0 (descriptive).
   `verdict(oos_stats, min_n=30) -> str`: `PASS` iff `n_signals>=min_n and ci1d_lo>0`;
   `UNDERPOWERED — inconclusive` iff `n_signals<min_n`; else `FAIL`. `format_tear_sheet(label,stats)`.

7. **CLI `main(argv=None) -> int`** — split at `--oos-cutoff` into in-sample (`<cutoff`) / sealed OOS
   (`>=cutoff`); print both tear-sheets + the verdict off the OOS 1d CI. Flags: `--ohlcv --start
   --oos-cutoff --feature {rv,atr} --rv-period --comp-pct --fwd-horizon --secondary-horizon --cost
   --min-oos`.

---

## 6. Confirmatory gate (frozen)

- **Statistic:** mean net straddle payoff at H = 24 bars (1 day) of sealed-OOS signals.
- **Null H₀:** mean = 0 (compression carries no net-of-cost expansion edge; realized expansion just
  matches the fair squeeze-priced premium).
- **Decision rule:** `PASS` iff block-bootstrap 95% CI **lower bound > 0** (one-sided; we hypothesize
  a positive net payoff).
- **Power guard / degeneracy fix:** `min_n = 30 > block = 20` ⇒ real resampling variability always.
  `n_OOS < 30` ⇒ `UNDERPOWERED — inconclusive` (seal spent; no second look).
- In-sample CI is context only, no verdict weight. Sealed window opened **once**; altered-param reruns
  after seeing OOS void the pre-registration.

---

## 7. CLI

```
experiments/vol_compression/.venv/bin/python experiments/vol_compression/vol_compression_backtest.py \
  --ohlcv .backtest_cache/BTCUSDT_1h.csv \
  --oos-cutoff 2024-07-01 \
  --feature rv          # or: atr  (robustness variant)
```

Prints both tear-sheets and the verdict. Params overridable **for robustness/stability checks only**
— the registered run uses the defaults in this doc.

---

## 8. Tests (deterministic, synthetic, no network)

- **log-return & realized-vol:** known constant-growth series → correct `r`, correct rolling std.
- **compression fires:** a synthetic series with a low-vol window inside a high-vol baseline → trigger
  in the low-vol window, not in the high-vol baseline.
- **cooldown:** two compressed bars within 24 → only the first fires.
- **premium formula:** `premium = sqrt(2/pi)*sigma*sqrt(H)` exactly, for a known sigma/H.
- **payoff sign/tautology guard:** if `|move|` exactly equals the fair premium, `net == −cost`
  (payoff is zero-edge minus cost under the null); a `|move|` larger than premium+cost → positive.
- **right-edge drop:** a signal without a full `t+H` bar is excluded from that horizon.
- **non-degenerate CI:** with `n>block` and varied payoffs, `hi>lo`.
- **empty CI:** empty input → `(nan,nan)`.
- **verdict branches:** PASS / FAIL / UNDERPOWERED at `min_n=30`.
- **leakage guard:** the compression threshold at `t` is unchanged by mutating a future bar `>t`.

---

## 9. Deliverable after the run

`RESULTS.md` (written once): both tear-sheets, the sealed-OOS verdict, n-counts, the bootstrap CIs,
the `--feature atr` robustness read, and an honest one-paragraph interpretation consistent with §0
(candidate vs. dead; explicit `UNDERPOWERED` note if n_OOS < 30; note the spot-synthesis limitation;
no deployment claim from this study alone).
