# session_sweeps_backtest.py — Time-of-Day / Session Sweep (Fade) Baseline

**Design spec / pre-registration — 2026-07-08**
**Status:** approved, pre-implementation. **Params, split, and gate are FROZEN as of this document.**
**Kind:** pre-registered confirmatory research study (symmetric mean-reversion fade). Standalone
prototype; **not wired into any engine.**

> Placed here (tracked `experiments/`) rather than `docs/research-log/specs/` because `docs/` is in
> the user's global `.gitignore_global` and does not persist in this repo; `experiments/` is the
> durable record. Same convention as `experiments/capitulation/` and `experiments/macro_regime/`.

---

## 0. Context & honest framing

Higher-frequency structural anomaly, following the capitulation lane (CLOSED inconclusive/dead
2026-07-08: too rare to power a confirmatory test). This study tests a **liquidity-sweep** premise:
around session opens, price pokes past the prior session's high/low (tripping resting stops), then
**rejects** back inside the range — a liquidity grab to fade.

The mechanism is **new to this program** and, unlike capitulation, is **high-frequency** (3
session-opens/day → ~7,000 opportunities over 6.5y), so it can clear the `n > block` bootstrap floor
that made capitulation's sealed slice underpowered. It is treated with the program's standard
discipline: **pre-registration (this doc) + a single sealed OOS window opened exactly once.** The
in-sample slice is the descriptive base rate (params frozen — **not** a tuning surface); the sealed
slice is the confirmatory verdict.

No edge is claimed until the sealed OOS bootstrap CI clears the gate in §6. A pass is a *candidate*,
not a deployable — it would still owe a forward paper period before any live claim.

---

## 1. Resolved design decisions (frozen)

| Fork | Decision |
|------|----------|
| Rigor | Pre-registered confirmatory; single signed test; single-shot sealed OOS. |
| Mechanism | Sweep-and-**reversal** (fade), **symmetric**: fade high-sweeps SHORT, low-sweeps LONG. |
| Robustness variant | Sweep-and-**continuation** (`--mode continuation`) — documented, **not** a second confirmatory test. |
| Sessions | 3 fixed non-overlapping 8h UTC blocks: **Asia 00:00–08:00, EU 08:00–16:00, US 16:00–24:00**. |
| Prior level | The immediately preceding 8h block's **high and low**. |
| Trigger | On 15m bars within the current session, first bar where `high > prior_high AND close < prior_high` (→ fade SHORT) **or** `low < prior_low AND close > prior_low` (→ fade LONG). |
| One-per-session | Only the **first** qualifying sweep-reject per session is taken (non-overlapping, independent). |
| Entry | Close of the sweep-reject 15m bar. |
| Primary metric | **Signed** forward **16-bar (4h)** log-return: LONG = `+ln(close[t+16]/entry)`, SHORT = `−ln(...)`. |
| Secondary | Signed forward **8-bar (2h)** log-return — reported, **not** gated. |
| Win-rate | Directional hit-rate (fraction with signed 4h return > 0) — **descriptive only**, not the gated statistic. No TP/SL bracket (avoids re-introducing path-dependence/DOF). |
| Split | In-sample `2020-01-01 → 2024-06-30`; **sealed OOS `2024-07-01 → present`.** |
| Gate | Moving-block bootstrap (block 20, 10,000 resamples, seed 0) **95% CI lower bound > 0** on the sealed-OOS mean signed 4h return. |
| Power guard | `min_n = 30` (> block 20 ⇒ CI can never be degenerate). `n_OOS < 30` ⇒ `UNDERPOWERED — inconclusive`. |
| Timeframe | BTCUSDT **15m** (`.backtest_cache/BTCUSDT_15m.csv`). No funding feed needed. |
| Deps / location | Isolated `experiments/session_sweeps/` with own venv + pinned `requirements.txt`; numpy + pandas only; quarantined from the stdlib main tree and main pytest. |

---

## 2. Layout

```
experiments/session_sweeps/
  session_sweeps_backtest.py    # module: OO class + analytics + CLI (this spec)
  requirements.txt              # numpy, pandas, pytest (pinned)
  README.md                     # setup + "pre-registered confirmatory" framing
  DESIGN.md                     # this file (the frozen pre-registration)
  RESULTS.md                    # written ONCE, after the run
  tests/test_session_sweeps.py  # deterministic, synthetic, no-network
  tests/conftest.py             # puts module on sys.path
```

- Own venv at `experiments/session_sweeps/.venv`.
- **Not** added to root `pyproject.toml`; excluded from the main pytest run.

---

## 3. Data

Read directly from the existing cache (no network fetch):

| Feed | File | Format |
|------|------|--------|
| OHLCV 15m | `.backtest_cache/BTCUSDT_15m.csv` | headerless: `ts_ms, open, high, low, close, volume` (~226.8k rows, 2020-01-01 → ~2026-06) |

- `ts_ms` is epoch milliseconds, UTC. Parse to a UTC `DatetimeIndex`, sort ascending.
- Path is a CLI argument defaulting to the above (loader accepts any file of the same schema).

---

## 4. Session tagging & prior level (causal)

- **Session id:** each bar is assigned `session_id ∈ {0=Asia, 1=EU, 2=US}` from the UTC hour of its
  open timestamp: `hour // 8`.
- **Session key:** `(date(UTC), session_id)` uniquely labels each 8h block.
- **Per-session high/low:** the max `high` / min `low` over the bars of that block.
- **Prior level:** for block `k`, `prior_high`/`prior_low` = the high/low of block `k−1` (the
  immediately preceding 8h block in time order). Fully known at the moment block `k` opens →
  **no leakage.** The first block in the dataset (no predecessor) yields no signals.

---

## 5. Components (each independently testable)

1. **`load_data(ohlcv_path, start=None, end=None) -> DataFrame`**
   Reads the headerless 15m cache, UTC `DatetimeIndex`, columns `open, high, low, close, volume`,
   date-sliced inclusive.

2. **`tag_sessions(df) -> DataFrame`**
   Adds columns: `session_id` (`hour // 8`), `session_key` (ordinal block index, contiguous integers
   in time order), `prior_high`, `prior_low` (the previous block's high/low, broadcast to every bar
   of the current block; `NaN` for the first block).

3. **`SessionSweepStrategy`** — OO, parameterized:
   `mode="reversal", fwd_horizon=16, secondary_horizon=8`.
   `.generate_signals(df_tagged) -> DataFrame` with one row per accepted signal:
   columns `entry_ts, entry_price, direction` (`+1` long / `−1` short).
   Logic per session block (in time order), scanning its bars earliest-first, taking the **first**
   qualifying bar:
   - **reversal mode:** `high > prior_high AND close < prior_high` → `direction = −1` (fade short);
     `low < prior_low AND close > prior_low` → `direction = +1` (fade long).
     (If both a high-sweep-reject and a low-sweep-reject occur, the earlier bar wins; if the same bar
     qualifies both ways — a bar that sweeps both extremes and closes inside — it is **skipped** as
     ambiguous.)
   - **continuation mode:** `close > prior_high` → `direction = +1`; `close < prior_low` →
     `direction = −1` (first bar to close beyond the level). Robustness only.
   - Entry price = the qualifying bar's `close`.

4. **`signed_forward_returns(df, signals, horizons=(8, 16)) -> dict[int, np.ndarray]`**
   For each signal at integer position `i`, `direction * ln(close[i+h] / close[i])` for each
   horizon `h`; signals without a full `i+h` bar (right edge) dropped from that horizon.

5. **`block_bootstrap_ci(returns, block=20, n_boot=10000, alpha=0.05, seed=0) -> (lo, hi)`**
   Moving-block bootstrap 95% CI on the mean. **Hardened vs. capitulation:** if `len(returns) <=
   block` the CI would be degenerate, so callers must satisfy the §6 power guard (`min_n=30 > block`).
   Returns `(nan, nan)` on empty input.

6. **`slice_stats(df_tagged, strategy) -> dict`** — keys: `n_signals, win_rate, mean_fwd_2h,
   mean_fwd_4h, ci4_lo, ci4_hi, ci2_lo, ci2_hi`. `win_rate` = fraction of trades whose signed 4h
   return > 0 (descriptive). `verdict(oos_stats, min_n=30) -> str`: `PASS` iff `n_signals >= min_n and
   ci4_lo > 0`; `UNDERPOWERED — inconclusive` iff `n_signals < min_n`; else `FAIL`.
   `format_tear_sheet(label, stats) -> str`.

7. **CLI `main(argv=None) -> int`** — splits at `--oos-cutoff` into in-sample (`< cutoff`) and sealed
   OOS (`>= cutoff`), prints both tear-sheets + the verdict line reading off the **OOS** 4h CI.

---

## 6. Confirmatory gate (frozen)

- **Statistic:** mean signed forward-16-bar (4h) log-return of sealed-OOS signals.
- **Null H₀:** mean = 0 (the sweep-fade has no edge).
- **Decision rule:** `PASS` iff the block-bootstrap 95% CI **lower bound > 0** (one-sided; we
  hypothesize a positive fade).
- **Power guard / degeneracy fix:** `min_n = 30`. Since `min_n (30) > block (20)`, the moving-block
  bootstrap always resamples with real variability (no zero-width collapse — the capitulation
  gotcha). If `n_OOS < 30` ⇒ `UNDERPOWERED — inconclusive` (seal considered spent; no second look).
- The in-sample CI is reported for context only and carries **no** verdict weight.
- The sealed window is opened **once**. Re-running with altered params after seeing OOS voids the
  pre-registration.

---

## 7. CLI

```
experiments/session_sweeps/.venv/bin/python experiments/session_sweeps/session_sweeps_backtest.py \
  --ohlcv .backtest_cache/BTCUSDT_15m.csv \
  --oos-cutoff 2024-07-01 \
  --mode reversal          # or: continuation  (robustness variant)
```

Prints both tear-sheets and the verdict line. Params overridable via flags **for robustness/stability
checks only** — the registered run uses the defaults in this doc.

---

## 8. Tests (deterministic, synthetic, no network)

- **session-tagging:** bars at UTC hours 03/10/18 map to session_id 0/1/2; `session_key` increments
  per 8h block in time order.
- **prior-level:** a block's `prior_high`/`prior_low` equal the previous block's high/low; first
  block is `NaN` (no signals).
- **sweep-reject fires (long & short):** a bar poking below prior_low that closes back above it →
  LONG; a bar poking above prior_high that closes back below it → SHORT.
- **no-fire on clean breakout:** a bar that closes *beyond* the level (no rejection) does **not** fire
  in reversal mode (but **does** fire in continuation mode → inversion test).
- **first-per-session dedup:** two qualifying bars in one session → exactly one signal (the earlier).
- **signed-return sign:** LONG on an up-move is positive; SHORT on an up-move is negative.
- **non-degenerate CI:** with `n > block` the bootstrap CI has `hi > lo` (degeneracy fix guard).
- **leakage-guard:** modifying a *future* block's bars does not change the current block's
  `prior_high`/`prior_low` or its signal.
- **verdict:** PASS / FAIL / UNDERPOWERED branches at `min_n = 30`.

---

## 9. Deliverable after the run

`RESULTS.md` (written once): both tear-sheets, the sealed-OOS verdict, n-counts, the bootstrap CIs,
the `--mode continuation` robustness read, and an honest one-paragraph interpretation consistent with
§0 (candidate vs. dead; explicit `UNDERPOWERED` note if n_OOS < 30; no deployment claim from this
study alone).
