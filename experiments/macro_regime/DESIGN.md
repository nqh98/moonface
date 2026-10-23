# macro_regime_model.py — Causal Macro-Liquidity Regime Instrument

**Design spec — 2026-07-07**
**Status:** approved, pre-implementation.
**Kind:** standalone research *instrument*. Emits regime probabilities + entropy. **No edge claim,
no trading signal, not wired into any engine.**

> Placed here (tracked `experiments/`) rather than `docs/research-log/specs/` because `docs/` is in
> the user's global `.gitignore_global` and does not persist in this repo; `experiments/` is the
> durable record.

---

## 0. Context & the honest framing

The MoonFace program has a single, exhaustively-replicated negative result (the "drawdown wall").
Macro-conditioning of BTC trading is a **heavily-falsified axis** here — `exogenous` (FRED + DVOL),
`regime_overlay`, `regime_selector`, `macro_event`, and `donchian_volregime` are all **CLOSED
NEGATIVE**. Program hard-constraint #2/#3 forbids reopening macro/exogenous conditioning under a new
framing.

This artifact is reconciled with that discipline by being an **instrument, not an edge**: it fetches
cross-asset macro data and produces a leak-free regime classification (probabilities + entropy). It
makes **no** claim that the regime improves trading. Establishing that would be a *separate,
pre-registered* study requiring explicit human authorization, because it touches the closed lanes
above.

The genuinely new element vs. the closed lanes: the regime is **unsupervised** (GMM probabilities +
uncertainty), not hand-thresholded macro rules.

---

## 1. Resolved design decisions (from brainstorming)

| Fork | Decision |
|------|----------|
| Role | Standalone instrument; **not** wired into live/paper engine. |
| Deps / location | Isolated under `experiments/macro_regime/` with own venv + `requirements.txt`; quarantined from the stdlib-only main tree and the main pytest run. |
| Split method | **Both**: single-split causal primitive **+** expanding walk-forward wrapper. |
| Feature set | **Exogenous-only** — GMM fit on DXY / US10Y / Gold only; BTC fetched and carried in output for per-regime study but **never** a regime input. |
| `K` (n_components) | Default **3** (configurable; 2 supported). |
| Refit cadence / warm-up | Walk-forward warm-up **504d (~2y)**, refit every **63d (~quarterly)**. |
| Cross-asset ratio | **Gold/DXY** ratio log-return (exogenous real-asset-vs-dollar axis). |

---

## 2. Layout

```
experiments/macro_regime/
  macro_regime_model.py       # module: OO classes + CLI (this spec)
  requirements.txt            # numpy, pandas, scikit-learn, yfinance (pinned)
  README.md                   # setup + "instrument, not an edge claim"
  DESIGN.md                   # this file
  data/                       # cached raw pulls (gitignored)
  tests/test_macro_regime.py  # deterministic, synthetic, no-network
```

- Own venv at `experiments/macro_regime/.venv`.
- **Not** added to root `pyproject.toml`.
- Test file added to the existing main-suite `--ignore` set (alongside the pathsig tests) so the
  stdlib-only main run never imports numpy/pandas/sklearn.

---

## 3. Units (each independently testable)

### 3.1 `MacroDataLoader`
- `yfinance` daily pulls: `DX-Y.NYB` (DXY), `^TNX` (US10Y yield), `GC=F` (Gold), `BTC-USD` (carried).
- **Alignment:** inner-join on dates where the three exogenous macro assets all have data (weekday
  cash calendar). BTC left-joined onto those dates (BTC weekend bars dropped for the daily model).
- Raw pulls cached to `data/<ticker>_<start>_<end>.parquet`; reproducible/offline after first fetch.
- Network failure or short/partial pull → **clear error, no silent partial data** (echoes the repo's
  stale-cache-truncation lesson).

### 3.2 `RegimeFeatureBuilder` (pure function, no fit state)
Raw aligned series → stationary feature matrix. GMM sees **only** DXY / US10Y / Gold. Transforms:

| Asset | Level feature | Vol feature |
|-------|---------------|-------------|
| DXY (`DX-Y.NYB`) | daily log return | rolling std of log returns, window `W` (default 20d) |
| Gold (`GC=F`) | daily log return | rolling std of log returns |
| US10Y (`^TNX`) | **Δyield (first difference)** — correct stationary transform for a rate, *not* a pct return | rolling std of Δyield |
| Cross-asset | **Gold/DXY ratio log-return** | — |

- No price-level columns are ever emitted (stationarity requirement).
- Standardization is **not** done here — it belongs to `CausalRegimeModel` (fit-on-train only), to
  keep the leakage boundary in one place.
- Carried (not GMM inputs): `BTC_close`, `BTC_logret`, `BTC_Gold_Ratio_Return`.

### 3.3 `CausalRegimeModel` — single-split primitive
- `fit(train_df)`: `StandardScaler().fit(train)` → `GaussianMixture(n_components=K,
  random_state=SEED).fit(scaled_train)`.
- `predict(test_df)`: scaler `.transform()` only → `.predict_proba()` only. **Never** `.fit` on the
  test path. A guard records the train fingerprint and asserts the predict input is not routed
  through `.fit`.
- **Label-switching canonicalization (the one real algorithmic choice):** GMM component indices are
  arbitrary and permute across refits. After each fit, components are re-ordered by a **deterministic
  numeric key — ascending component-mean of the standardized DXY-return axis** — so `P_State_0…K-1`
  keep a stable identity across refits. This is a *mechanical* ordering, **not** a semantic label (no
  "bull/bear/expansion" names anywhere).
  - *Alternative considered & rejected:* Hungarian match each refit's components to the previous
    fit's means — heavier and drift-prone vs. a fixed deterministic key.

### 3.4 `WalkForwardRegimeLabeler` — expanding-window wrapper
- Initial train = first `warmup` rows (default 504d). Refit every `step` rows (default 63d). Each fit
  labels its forward block via the primitive's `predict` only.
- Guarantee: at date *t*, only data ≤ *t* touched any `.fit` → leak-free regime label + entropy for
  every date past warm-up.
- §3.3 canonicalization applied per refit → state IDs comparable across the whole series.

---

## 4. Output

`pandas.DataFrame` indexed by date:

| Column | Meaning |
|--------|---------|
| `P_State_0 … P_State_{K-1}` | GMM `predict_proba` per canonical state |
| `entropy` | `-Σ p·ln p` (nats) |
| `entropy_norm` | `entropy / ln K` → [0, 1] |
| `regime_argmax` | int id of the max-proba state |
| `BTC_close`, `BTC_logret`, `BTC_Gold_Ratio_Return` | carried for per-regime study (not GMM inputs) |

---

## 5. CLI

```
python macro_regime_model.py \
  --start 2015-01-01 [--end YYYY-MM-DD] \
  --components 3 --window 20 \
  --mode {split,walkforward} \
  [--warmup 504 --step 63] \
  --out regimes.csv
```

- Writes the DataFrame to CSV.
- Prints a compact text summary: per-state occupancy fraction + mean entropy. **No plotting
  dependency** (kept lean).

---

## 6. Testing & determinism (quarantined, synthetic, no-network; fixed `SEED`)

1. **Leakage guard** — constructed case proves test rows never reach `.fit` (spy on scaler + GMM).
2. **Walk-forward causality** — label at *t* is invariant when future rows are mutated.
3. **Entropy math** — uniform proba → `entropy_norm == 1`; one-hot → `0`.
4. **Label stability** — two refits on permuted-but-equivalent data yield the same canonical ordering.
5. **Feature stationarity smoke** — builder emits no raw-level columns; `^TNX` uses Δyield.

---

## 7. Non-goals / guardrails

- **Instrument only** — no edge claim, no trading signal, no engine wiring. Downstream "does the
  regime improve trading" is a separate, pre-registered, human-authorized study (closed macro lanes).
- No semantic state names.
- No numpy/pandas/sklearn/yfinance in the main tree; quarantined venv + `--ignore`d tests.
- No `git add`-chaining; explicit-path staging only; no AI-attribution trailers; no force-push.
