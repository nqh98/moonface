# Macro-Liquidity Regime Instrument — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `experiments/macro_regime/macro_regime_model.py` — a quarantined, zero-leakage GMM instrument that classifies macro-liquidity regimes from cross-asset data and emits regime probabilities + entropy.

**Architecture:** Four cohesive units in one module — `MacroDataLoader` (fetch/align/cache, with an injectable `fetcher` so tests never hit the network), `build_features` (pure stationary-feature function, exogenous-only), `CausalRegimeModel` (single-split scaler+GMM primitive with deterministic label canonicalization + a fit-only leakage boundary), and `WalkForwardRegimeLabeler` (expanding-window wrapper). A `build_regime_frame` orchestrator + `argparse` CLI tie them together.

**Tech Stack:** Python 3.12, numpy, pandas, scikit-learn (`GaussianMixture`, `StandardScaler`), yfinance — all installed **only** in a dedicated `experiments/macro_regime/.venv`, never in the main tree.

## Global Constraints

- **Spec:** `experiments/macro_regime/DESIGN.md` is the source of truth. Every task implements part of it.
- **Quarantine:** No numpy/pandas/sklearn/yfinance in the main `.venv`, `pyproject.toml`, or `src/`. All new deps live in `experiments/macro_regime/.venv` via `experiments/macro_regime/requirements.txt`.
- **Test isolation is structural:** the main suite is `testpaths = ["tests"]`, so tests under `experiments/macro_regime/tests/` are auto-excluded — **no `--ignore`/conftest edit is needed** (this refines DESIGN.md §2, which predates checking the pytest config). Task 1 verifies this.
- **Determinism:** all randomness seeded; module constant `SEED = 7`; `GaussianMixture(random_state=SEED)`. Tests use fixed synthetic data, **no network**.
- **Exogenous-only regime:** GMM features are DXY / US10Y / Gold **only**. BTC is carried in output, never a GMM input.
- **No semantic state names** anywhere. States are integer ids `0..K-1` under a deterministic canonical ordering.
- **Instrument only:** no trading signal, no engine wiring, no edge claim.
- **Git:** stage **explicit paths only** (never `git add -A`/chaining), no AI-attribution trailers, no force-push, local commits only. **Commit steps run only on the user's go-ahead.**
- **Run commands** with the quarantined interpreter: `experiments/macro_regime/.venv/bin/python` and `experiments/macro_regime/.venv/bin/pytest`.

---

## File Structure

- `experiments/macro_regime/requirements.txt` — pinned deps.
- `experiments/macro_regime/README.md` — setup + "instrument, not an edge claim".
- `experiments/macro_regime/.gitignore` — ignore `data/` and `.venv/`.
- `experiments/macro_regime/macro_regime_model.py` — the module (all four units + CLI).
- `experiments/macro_regime/tests/test_macro_regime.py` — deterministic, no-network tests.
- `experiments/macro_regime/tests/_synthetic.py` — shared synthetic-data helpers for tests.

---

### Task 1: Scaffold, isolated env, quarantine verification

**Files:**
- Create: `experiments/macro_regime/requirements.txt`
- Create: `experiments/macro_regime/.gitignore`
- Create: `experiments/macro_regime/README.md`
- Create: `experiments/macro_regime/macro_regime_model.py` (stub)
- Create: `experiments/macro_regime/tests/__init__.py` (empty)

**Interfaces:**
- Produces: an importable `macro_regime_model` module in the quarantined venv; module constants `SEED`, `EXOG_FEATURES`, `ORDERING_FEATURE`, `TICKERS` used by every later task.

- [ ] **Step 1: Create `requirements.txt`**

```
numpy>=1.26
pandas>=2.1
scikit-learn>=1.4
yfinance>=0.2.40
pytest>=8.0
```

- [ ] **Step 2: Create `.gitignore`**

```
.venv/
data/
__pycache__/
*.pyc
```

- [ ] **Step 3: Create `README.md`**

```markdown
# macro_regime — Causal Macro-Liquidity Regime Instrument

**Status:** research instrument. Emits regime probabilities + entropy from cross-asset
macro data (DXY / US10Y / Gold). **Not an edge claim, not a trading signal, not wired
into any engine.** See `DESIGN.md`.

Quarantined from the stdlib-only main tree: its numpy/pandas/sklearn/yfinance deps live
only in this directory's own venv.

## Setup

    python3 -m venv experiments/macro_regime/.venv
    experiments/macro_regime/.venv/bin/pip install -r experiments/macro_regime/requirements.txt

## Run

    experiments/macro_regime/.venv/bin/python experiments/macro_regime/macro_regime_model.py \
      --start 2015-01-01 --components 3 --mode walkforward --out regimes.csv

## Test

    experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests -v
```

- [ ] **Step 4: Create the module stub with shared constants**

```python
"""Causal macro-liquidity regime instrument (GMM over exogenous cross-asset macro data).

Instrument only: emits regime probabilities + entropy. No trading signal, no edge claim.
See DESIGN.md.
"""
from __future__ import annotations

SEED = 7

# GMM is fit on these exogenous features ONLY (never BTC).
EXOG_FEATURES = [
    "dxy_logret",
    "dxy_vol",
    "gold_logret",
    "gold_vol",
    "tnx_dyield",
    "tnx_vol",
    "gold_dxy_ratio_logret",
]

# Deterministic canonical-ordering axis for GMM label-switching (see CausalRegimeModel).
ORDERING_FEATURE = "dxy_logret"

# internal name -> yfinance ticker
TICKERS = {
    "DXY": "DX-Y.NYB",
    "TNX": "^TNX",
    "GOLD": "GC=F",
    "BTC": "BTC-USD",
}
```

- [ ] **Step 5: Create the isolated venv and install deps**

Run:
```bash
python3 -m venv experiments/macro_regime/.venv
experiments/macro_regime/.venv/bin/pip install -r experiments/macro_regime/requirements.txt
```
Expected: pip reports successful install of numpy, pandas, scikit-learn, yfinance, pytest.

- [ ] **Step 6: Verify the module imports in the quarantined venv**

Run:
```bash
experiments/macro_regime/.venv/bin/python -c "import sys; sys.path.insert(0,'experiments/macro_regime'); import macro_regime_model as m; print(m.EXOG_FEATURES)"
```
Expected: prints the 7-item feature list.

- [ ] **Step 7: Verify quarantine — main tree stays clean, main suite ignores the new tests**

Run:
```bash
.venv/bin/python -c "import numpy" 2>&1 | head -1
.venv/bin/python -m pytest --collect-only -q 2>/dev/null | grep -c macro_regime
```
Expected: first line `ModuleNotFoundError: No module named 'numpy'` (main venv is clean); second line prints `0` (main suite does not collect the new tests).

- [ ] **Step 8: Commit** *(on user go-ahead)*

```bash
git add experiments/macro_regime/requirements.txt experiments/macro_regime/.gitignore experiments/macro_regime/README.md experiments/macro_regime/macro_regime_model.py experiments/macro_regime/tests/__init__.py
git commit -m "feat(macro_regime): scaffold quarantined regime instrument + constants"
```

---

### Task 2: Entropy helpers

**Files:**
- Modify: `experiments/macro_regime/macro_regime_model.py`
- Test: `experiments/macro_regime/tests/test_macro_regime.py`

**Interfaces:**
- Produces: `regime_entropy(proba: np.ndarray) -> np.ndarray` (shape `(n,)`, nats) and `normalized_entropy(proba: np.ndarray) -> np.ndarray` (shape `(n,)`, in `[0, 1]`). `proba` has shape `(n, K)`.

- [ ] **Step 1: Write the failing test**

```python
import unittest
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import macro_regime_model as m


class TestEntropy(unittest.TestCase):
    def test_uniform_is_max_normalized_entropy(self):
        proba = np.full((5, 3), 1 / 3)
        np.testing.assert_allclose(m.normalized_entropy(proba), np.ones(5), atol=1e-9)

    def test_one_hot_is_zero_entropy(self):
        proba = np.zeros((4, 3))
        proba[:, 1] = 1.0
        np.testing.assert_allclose(m.regime_entropy(proba), np.zeros(4), atol=1e-9)
        np.testing.assert_allclose(m.normalized_entropy(proba), np.zeros(4), atol=1e-9)

    def test_entropy_nats_matches_formula(self):
        proba = np.array([[0.5, 0.5]])
        np.testing.assert_allclose(m.regime_entropy(proba), [np.log(2)], atol=1e-9)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests/test_macro_regime.py::TestEntropy -v`
Expected: FAIL — `AttributeError: module 'macro_regime_model' has no attribute 'normalized_entropy'`.

- [ ] **Step 3: Implement the helpers**

Add to `macro_regime_model.py` (after the constants; add `import numpy as np` at the top of the import block):

```python
import numpy as np


def regime_entropy(proba: np.ndarray) -> np.ndarray:
    """Shannon entropy (nats) of each row of a proba matrix, shape (n, K) -> (n,)."""
    p = np.clip(np.asarray(proba, dtype=float), 1e-12, 1.0)
    return -(p * np.log(p)).sum(axis=1)


def normalized_entropy(proba: np.ndarray) -> np.ndarray:
    """Entropy scaled to [0, 1] by ln(K). K<=1 -> all zeros."""
    proba = np.asarray(proba, dtype=float)
    k = proba.shape[1]
    if k <= 1:
        return np.zeros(proba.shape[0])
    return regime_entropy(proba) / np.log(k)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests/test_macro_regime.py::TestEntropy -v`
Expected: 3 passed.

- [ ] **Step 5: Commit** *(on user go-ahead)*

```bash
git add experiments/macro_regime/macro_regime_model.py experiments/macro_regime/tests/test_macro_regime.py
git commit -m "feat(macro_regime): entropy + normalized-entropy helpers"
```

---

### Task 3: `build_features` — stationary, exogenous-only feature matrix

**Files:**
- Modify: `experiments/macro_regime/macro_regime_model.py`
- Create: `experiments/macro_regime/tests/_synthetic.py`
- Modify: `experiments/macro_regime/tests/test_macro_regime.py`

**Interfaces:**
- Consumes: nothing from earlier tasks except the module.
- Produces:
  - `build_features(raw: pd.DataFrame, window: int = 20) -> pd.DataFrame` — `raw` is indexed by date with **level** columns `DXY`, `TNX`, `GOLD`, `BTC`; returns a frame containing the 7 `EXOG_FEATURES` columns **plus** carried `BTC_close`, `BTC_logret`, `BTC_Gold_Ratio_Return`, with all-NaN warm-up rows dropped.
  - Test helper `make_synthetic_raw(n=900, seed=0) -> pd.DataFrame` in `_synthetic.py` producing a `raw`-shaped frame (deterministic random walks; `TNX` is a yield-like level).

- [ ] **Step 1: Create the synthetic-data helper**

`experiments/macro_regime/tests/_synthetic.py`:
```python
"""Deterministic, no-network synthetic data for macro_regime tests."""
import numpy as np
import pandas as pd


def make_synthetic_raw(n=900, seed=0):
    """A `raw`-shaped frame: bdate index, level columns DXY, TNX, GOLD, BTC."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2018-01-01", periods=n)
    dxy = 95 + rng.normal(0, 0.3, n).cumsum() * 0.1
    gold = 1500 + rng.normal(0, 5, n).cumsum() * 0.1
    tnx = 25 + rng.normal(0, 0.05, n).cumsum() * 0.1   # yield-like level (e.g. 2.5% -> 25)
    btc = 8000 + rng.normal(0, 200, n).cumsum() * 0.1
    return pd.DataFrame({"DXY": dxy, "TNX": tnx, "GOLD": gold, "BTC": btc}, index=dates)


def make_synthetic_fetcher(n=900, seed=0):
    """A fetcher(ticker, start, end) -> Series, backed by make_synthetic_raw columns."""
    raw = make_synthetic_raw(n=n, seed=seed)
    # map yfinance ticker -> internal column
    col_by_ticker = {"DX-Y.NYB": "DXY", "^TNX": "TNX", "GC=F": "GOLD", "BTC-USD": "BTC"}

    def fetch(ticker, start, end):
        col = col_by_ticker[ticker]
        return raw[col].rename(ticker).copy()

    return fetch
```

- [ ] **Step 2: Write the failing test**

Append to `test_macro_regime.py`:
```python
from _synthetic import make_synthetic_raw


class TestFeatures(unittest.TestCase):
    def test_columns_and_stationarity(self):
        raw = make_synthetic_raw(n=300, seed=1)
        feat = m.build_features(raw, window=20)
        for col in m.EXOG_FEATURES:
            self.assertIn(col, feat.columns)
        for carried in ("BTC_close", "BTC_logret", "BTC_Gold_Ratio_Return"):
            self.assertIn(carried, feat.columns)
        # no raw level column leaks into the feature frame
        for level in ("DXY", "TNX", "GOLD", "BTC"):
            self.assertNotIn(level, feat.columns)
        # no NaNs after warm-up drop
        self.assertFalse(feat.isna().any().any())

    def test_tnx_uses_first_difference_not_pct_return(self):
        raw = make_synthetic_raw(n=300, seed=1)
        feat = m.build_features(raw, window=20)
        expected = raw["TNX"].diff().reindex(feat.index)
        np.testing.assert_allclose(feat["tnx_dyield"].values, expected.values, atol=1e-9)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests/test_macro_regime.py::TestFeatures -v`
Expected: FAIL — `AttributeError: ... has no attribute 'build_features'`.

- [ ] **Step 4: Implement `build_features`**

Add to `macro_regime_model.py` (add `import pandas as pd` to the import block):
```python
import pandas as pd


def build_features(raw: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """Level frame (DXY, TNX, GOLD, BTC) -> stationary exogenous features + carried BTC.

    GMM inputs are exogenous-only (DXY / US10Y / Gold). BTC columns are carried for
    per-regime study but are never GMM inputs. Warm-up NaN rows are dropped.
    """
    out = pd.DataFrame(index=raw.index)
    out["dxy_logret"] = np.log(raw["DXY"]).diff()
    out["dxy_vol"] = out["dxy_logret"].rolling(window).std()
    out["gold_logret"] = np.log(raw["GOLD"]).diff()
    out["gold_vol"] = out["gold_logret"].rolling(window).std()
    out["tnx_dyield"] = raw["TNX"].diff()                      # rate -> first difference
    out["tnx_vol"] = out["tnx_dyield"].rolling(window).std()
    out["gold_dxy_ratio_logret"] = np.log(raw["GOLD"] / raw["DXY"]).diff()
    # carried, not GMM inputs
    out["BTC_close"] = raw["BTC"]
    out["BTC_logret"] = np.log(raw["BTC"]).diff()
    out["BTC_Gold_Ratio_Return"] = np.log(raw["BTC"] / raw["GOLD"]).diff()
    return out.dropna()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests/test_macro_regime.py::TestFeatures -v`
Expected: 2 passed.

- [ ] **Step 6: Commit** *(on user go-ahead)*

```bash
git add experiments/macro_regime/macro_regime_model.py experiments/macro_regime/tests/test_macro_regime.py experiments/macro_regime/tests/_synthetic.py
git commit -m "feat(macro_regime): exogenous-only stationary feature builder"
```

---

### Task 4: `CausalRegimeModel` — single-split primitive + label canonicalization + leakage boundary

**Files:**
- Modify: `experiments/macro_regime/macro_regime_model.py`
- Modify: `experiments/macro_regime/tests/test_macro_regime.py`

**Interfaces:**
- Consumes: `EXOG_FEATURES`, `ORDERING_FEATURE`, `SEED`, `regime_entropy`, `normalized_entropy`, `build_features`.
- Produces: `CausalRegimeModel(n_components=3, seed=SEED, features=EXOG_FEATURES)` with:
  - `.fit(train_df) -> self` — fits `StandardScaler` then `GaussianMixture`, computes canonical component order.
  - `.predict_proba(test_df) -> np.ndarray` shape `(len(test), K)`, columns in canonical order; raises `RuntimeError` if called before `fit`.
  - `.label(test_df) -> pd.DataFrame` with columns `P_State_0..P_State_{K-1}`, `entropy`, `entropy_norm`, `regime_argmax`, plus any carried `BTC_*` columns present in `test_df`.

- [ ] **Step 1: Write the failing tests**

Append to `test_macro_regime.py`:
```python
from unittest import mock


class TestCausalRegimeModel(unittest.TestCase):
    def setUp(self):
        raw = make_synthetic_raw(n=500, seed=2)
        self.feat = m.build_features(raw, window=20)
        self.train = self.feat.iloc[:300]
        self.test = self.feat.iloc[300:]

    def test_predict_before_fit_raises(self):
        model = m.CausalRegimeModel(n_components=3)
        with self.assertRaises(RuntimeError):
            model.predict_proba(self.test)

    def test_label_frame_shape_and_columns(self):
        model = m.CausalRegimeModel(n_components=3).fit(self.train)
        out = model.label(self.test)
        for k in range(3):
            self.assertIn(f"P_State_{k}", out.columns)
        for c in ("entropy", "entropy_norm", "regime_argmax",
                  "BTC_close", "BTC_logret", "BTC_Gold_Ratio_Return"):
            self.assertIn(c, out.columns)
        # probabilities sum to 1 per row
        p = out[[f"P_State_{k}" for k in range(3)]].to_numpy()
        np.testing.assert_allclose(p.sum(axis=1), np.ones(len(out)), atol=1e-6)

    def test_canonical_order_is_ascending_on_ordering_axis(self):
        model = m.CausalRegimeModel(n_components=3).fit(self.train)
        idx = model.features.index(m.ORDERING_FEATURE)
        ordered_means = model.gmm.means_[model._order, idx]
        self.assertTrue(np.all(np.diff(ordered_means) >= 0))

    def test_same_data_same_labels(self):
        a = m.CausalRegimeModel(n_components=3).fit(self.train).label(self.test)
        b = m.CausalRegimeModel(n_components=3).fit(self.train).label(self.test)
        np.testing.assert_array_equal(a["regime_argmax"].values, b["regime_argmax"].values)

    def test_no_fit_in_predict_path(self):
        model = m.CausalRegimeModel(n_components=3).fit(self.train)
        with mock.patch.object(type(model.scaler), "fit") as sfit, \
             mock.patch.object(type(model.gmm), "fit") as gfit:
            model.predict_proba(self.test)
            model.label(self.test)
        sfit.assert_not_called()
        gfit.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests/test_macro_regime.py::TestCausalRegimeModel -v`
Expected: FAIL — `AttributeError: ... has no attribute 'CausalRegimeModel'`.

- [ ] **Step 3: Implement `CausalRegimeModel`**

Add to `macro_regime_model.py` (add `from sklearn.mixture import GaussianMixture` and `from sklearn.preprocessing import StandardScaler` to the import block):
```python
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


class CausalRegimeModel:
    """Single-split causal primitive: fit scaler+GMM on train, transform/predict on test only.

    Component indices are canonicalized (ascending component mean on ORDERING_FEATURE) so
    P_State_k has a stable identity across refits. This is a mechanical ordering, not a
    semantic label.
    """

    def __init__(self, n_components: int = 3, seed: int = SEED, features=EXOG_FEATURES):
        self.n_components = n_components
        self.seed = seed
        self.features = list(features)
        self.scaler: StandardScaler | None = None
        self.gmm: GaussianMixture | None = None
        self._order = None

    def fit(self, train_df: pd.DataFrame) -> "CausalRegimeModel":
        x = train_df[self.features].to_numpy()
        self.scaler = StandardScaler().fit(x)
        xs = self.scaler.transform(x)
        self.gmm = GaussianMixture(n_components=self.n_components, random_state=self.seed).fit(xs)
        idx = self.features.index(ORDERING_FEATURE)
        self._order = np.argsort(self.gmm.means_[:, idx])
        return self

    def predict_proba(self, test_df: pd.DataFrame) -> np.ndarray:
        if self.gmm is None:
            raise RuntimeError("fit() must be called before predict_proba()")
        xs = self.scaler.transform(test_df[self.features].to_numpy())  # transform only
        return self.gmm.predict_proba(xs)[:, self._order]              # predict only

    def label(self, test_df: pd.DataFrame) -> pd.DataFrame:
        proba = self.predict_proba(test_df)
        out = pd.DataFrame(
            {f"P_State_{k}": proba[:, k] for k in range(self.n_components)},
            index=test_df.index,
        )
        out["entropy"] = regime_entropy(proba)
        out["entropy_norm"] = normalized_entropy(proba)
        out["regime_argmax"] = proba.argmax(axis=1)
        for carried in ("BTC_close", "BTC_logret", "BTC_Gold_Ratio_Return"):
            if carried in test_df.columns:
                out[carried] = test_df[carried].to_numpy()
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests/test_macro_regime.py::TestCausalRegimeModel -v`
Expected: 5 passed.

- [ ] **Step 5: Commit** *(on user go-ahead)*

```bash
git add experiments/macro_regime/macro_regime_model.py experiments/macro_regime/tests/test_macro_regime.py
git commit -m "feat(macro_regime): causal single-split GMM primitive w/ canonical labels"
```

---

### Task 5: `WalkForwardRegimeLabeler` — expanding-window wrapper

**Files:**
- Modify: `experiments/macro_regime/macro_regime_model.py`
- Modify: `experiments/macro_regime/tests/test_macro_regime.py`

**Interfaces:**
- Consumes: `CausalRegimeModel`, `EXOG_FEATURES`, `SEED`.
- Produces: `WalkForwardRegimeLabeler(n_components=3, warmup=504, step=63, seed=SEED, features=EXOG_FEATURES)` with `.run(feat_df) -> pd.DataFrame` — same columns as `CausalRegimeModel.label`, covering every row from index `warmup` onward; raises `ValueError` if `len(feat_df) <= warmup`.

- [ ] **Step 1: Write the failing tests**

Append to `test_macro_regime.py`:
```python
class TestWalkForward(unittest.TestCase):
    def setUp(self):
        raw = make_synthetic_raw(n=800, seed=3)
        self.feat = m.build_features(raw, window=20)

    def test_covers_rows_past_warmup(self):
        wf = m.WalkForwardRegimeLabeler(n_components=3, warmup=300, step=50)
        out = wf.run(self.feat)
        self.assertEqual(len(out), len(self.feat) - 300)
        self.assertEqual(list(out.index), list(self.feat.index[300:]))

    def test_too_few_rows_raises(self):
        wf = m.WalkForwardRegimeLabeler(n_components=3, warmup=len(self.feat) + 10, step=50)
        with self.assertRaises(ValueError):
            wf.run(self.feat)

    def test_causality_future_mutation_does_not_change_past_labels(self):
        wf = m.WalkForwardRegimeLabeler(n_components=3, warmup=300, step=50)
        base = wf.run(self.feat)
        mutated = self.feat.copy()
        mutated.iloc[-1, mutated.columns.get_loc("dxy_logret")] += 5.0  # perturb final row
        after = wf.run(mutated)
        # every label strictly before the final block start is unchanged
        cutoff = self.feat.index[len(self.feat) - ((len(self.feat) - 300) % 50 or 50)]
        common = base.index[base.index < cutoff]
        np.testing.assert_array_equal(
            base.loc[common, "regime_argmax"].values,
            after.loc[common, "regime_argmax"].values,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests/test_macro_regime.py::TestWalkForward -v`
Expected: FAIL — `AttributeError: ... has no attribute 'WalkForwardRegimeLabeler'`.

- [ ] **Step 3: Implement `WalkForwardRegimeLabeler`**

Add to `macro_regime_model.py`:
```python
class WalkForwardRegimeLabeler:
    """Expanding-window causal labeler: refit every `step` rows on all prior data.

    At date t only data <= t has touched any .fit, so every emitted label is leak-free.
    """

    def __init__(self, n_components: int = 3, warmup: int = 504, step: int = 63,
                 seed: int = SEED, features=EXOG_FEATURES):
        self.n_components = n_components
        self.warmup = warmup
        self.step = step
        self.seed = seed
        self.features = list(features)

    def run(self, feat_df: pd.DataFrame) -> pd.DataFrame:
        n = len(feat_df)
        if n <= self.warmup:
            raise ValueError(f"need > warmup ({self.warmup}) rows, got {n}")
        blocks = []
        start = self.warmup
        while start < n:
            end = min(start + self.step, n)
            train = feat_df.iloc[:start]
            test = feat_df.iloc[start:end]
            model = CausalRegimeModel(self.n_components, self.seed, self.features).fit(train)
            blocks.append(model.label(test))
            start = end
        return pd.concat(blocks)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests/test_macro_regime.py::TestWalkForward -v`
Expected: 3 passed.

- [ ] **Step 5: Commit** *(on user go-ahead)*

```bash
git add experiments/macro_regime/macro_regime_model.py experiments/macro_regime/tests/test_macro_regime.py
git commit -m "feat(macro_regime): expanding-window walk-forward labeler"
```

---

### Task 6: `MacroDataLoader` — fetch (injectable), align, cache

**Files:**
- Modify: `experiments/macro_regime/macro_regime_model.py`
- Modify: `experiments/macro_regime/tests/test_macro_regime.py`

**Interfaces:**
- Consumes: `TICKERS`.
- Produces:
  - `MacroDataLoader(cache_dir="data", fetcher=None)` — `fetcher` is a callable `(ticker: str, start: str, end: str|None) -> pd.Series` (indexed by date). Defaults to the real yfinance fetcher `_yf_fetch`.
  - `.load(start, end=None) -> pd.DataFrame` — a `raw`-shaped frame: inner-join of DXY/TNX/GOLD on the weekday calendar, BTC left-joined; columns `DXY`, `TNX`, `GOLD`, `BTC`. Uses/writes a per-`(name, start, end)` CSV cache under `cache_dir`. Raises `ValueError` on an empty fetch.
  - `_yf_fetch(ticker, start, end) -> pd.Series` — real network fetch (not exercised by tests).

- [ ] **Step 1: Write the failing tests**

Append to `test_macro_regime.py` (add near the other imports at top: `import tempfile`):
```python
from _synthetic import make_synthetic_fetcher


class TestDataLoader(unittest.TestCase):
    def test_align_shapes_and_columns(self):
        with tempfile.TemporaryDirectory() as d:
            loader = m.MacroDataLoader(cache_dir=d, fetcher=make_synthetic_fetcher(n=400, seed=4))
            raw = loader.load("2018-01-01")
            self.assertEqual(list(raw.columns), ["DXY", "TNX", "GOLD", "BTC"])
            self.assertFalse(raw[["DXY", "TNX", "GOLD"]].isna().any().any())
            self.assertEqual(len(raw), 400)

    def test_cache_roundtrip_avoids_second_fetch(self):
        calls = {"n": 0}
        base = make_synthetic_fetcher(n=300, seed=5)

        def counting_fetch(ticker, start, end):
            calls["n"] += 1
            return base(ticker, start, end)

        with tempfile.TemporaryDirectory() as d:
            m.MacroDataLoader(cache_dir=d, fetcher=counting_fetch).load("2018-01-01")
            first = calls["n"]
            m.MacroDataLoader(cache_dir=d, fetcher=counting_fetch).load("2018-01-01")
            self.assertEqual(first, 4)          # one fetch per ticker on cold cache
            self.assertEqual(calls["n"], first)  # warm cache: no further fetches

    def test_empty_fetch_raises(self):
        def empty_fetch(ticker, start, end):
            return pd.Series([], dtype=float, name=ticker)

        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                m.MacroDataLoader(cache_dir=d, fetcher=empty_fetch).load("2018-01-01")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests/test_macro_regime.py::TestDataLoader -v`
Expected: FAIL — `AttributeError: ... has no attribute 'MacroDataLoader'`.

- [ ] **Step 3: Implement the loader**

Add to `macro_regime_model.py` (add `from pathlib import Path` to the import block):
```python
from pathlib import Path


def _yf_fetch(ticker: str, start: str, end: str | None) -> pd.Series:
    """Real network fetch of daily close via yfinance. Not exercised by tests."""
    import yfinance as yf

    df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    if df.empty:
        raise ValueError(f"empty pull for {ticker}")
    close = df["Close"]
    if hasattr(close, "columns"):   # yfinance can return a 1-col frame
        close = close.iloc[:, 0]
    return close.rename(ticker)


class MacroDataLoader:
    """Fetch + align + cache the four cross-asset series into a `raw`-shaped frame."""

    def __init__(self, cache_dir: str = "data", fetcher=None):
        self.cache_dir = Path(cache_dir)
        self.fetcher = fetcher or _yf_fetch

    def _get_series(self, name: str, ticker: str, start: str, end: str | None) -> pd.Series:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        key = f"{name}_{start}_{end or 'latest'}.csv".replace(":", "-")
        path = self.cache_dir / key
        if path.exists():
            s = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
            s.name = name
            return s
        s = self.fetcher(ticker, start, end)
        if s is None or len(s) == 0:
            raise ValueError(f"empty fetch for {name} ({ticker})")
        s = s.rename(name)
        s.to_frame().to_csv(path)
        return s

    def load(self, start: str, end: str | None = None) -> pd.DataFrame:
        series = {n: self._get_series(n, t, start, end) for n, t in TICKERS.items()}
        exog = pd.concat([series["DXY"], series["TNX"], series["GOLD"]], axis=1, join="inner")
        exog.columns = ["DXY", "TNX", "GOLD"]
        raw = exog.join(series["BTC"].rename("BTC"), how="left")
        return raw
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests/test_macro_regime.py::TestDataLoader -v`
Expected: 3 passed.

- [ ] **Step 5: Commit** *(on user go-ahead)*

```bash
git add experiments/macro_regime/macro_regime_model.py experiments/macro_regime/tests/test_macro_regime.py
git commit -m "feat(macro_regime): injectable-fetch data loader w/ align + CSV cache"
```

---

### Task 7: Orchestrator + CLI + text summary, and full-suite verification

**Files:**
- Modify: `experiments/macro_regime/macro_regime_model.py`
- Modify: `experiments/macro_regime/tests/test_macro_regime.py`

**Interfaces:**
- Consumes: `MacroDataLoader`, `build_features`, `CausalRegimeModel`, `WalkForwardRegimeLabeler`.
- Produces:
  - `build_regime_frame(start, end=None, n_components=3, window=20, mode="walkforward", warmup=504, step=63, cache_dir="data", fetcher=None) -> pd.DataFrame`.
  - `summarize(frame: pd.DataFrame, n_components: int) -> str`.
  - `main(argv=None) -> int` — argparse CLI writing CSV + printing the summary.

- [ ] **Step 1: Write the failing tests**

Append to `test_macro_regime.py`:
```python
class TestOrchestratorAndCLI(unittest.TestCase):
    def test_build_regime_frame_split_mode(self):
        with tempfile.TemporaryDirectory() as d:
            frame = m.build_regime_frame(
                start="2018-01-01", n_components=3, window=20, mode="split",
                cache_dir=d, fetcher=make_synthetic_fetcher(n=500, seed=6),
            )
            for k in range(3):
                self.assertIn(f"P_State_{k}", frame.columns)
            self.assertIn("entropy_norm", frame.columns)
            self.assertGreater(len(frame), 0)

    def test_build_regime_frame_walkforward_mode(self):
        with tempfile.TemporaryDirectory() as d:
            frame = m.build_regime_frame(
                start="2018-01-01", n_components=3, window=20, mode="walkforward",
                warmup=300, step=50, cache_dir=d, fetcher=make_synthetic_fetcher(n=600, seed=7),
            )
            self.assertGreater(len(frame), 0)
            self.assertIn("regime_argmax", frame.columns)

    def test_summarize_mentions_every_state(self):
        with tempfile.TemporaryDirectory() as d:
            frame = m.build_regime_frame(
                start="2018-01-01", n_components=3, mode="split",
                cache_dir=d, fetcher=make_synthetic_fetcher(n=500, seed=6),
            )
            text = m.summarize(frame, 3)
            for k in range(3):
                self.assertIn(f"State {k}", text)

    def test_main_writes_csv(self):
        import sys as _sys
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "regimes.csv")
            # inject the synthetic fetcher via monkeypatching the default fetch
            orig = m._yf_fetch
            m._yf_fetch = make_synthetic_fetcher(n=500, seed=6)
            try:
                rc = m.main([
                    "--start", "2018-01-01", "--components", "3", "--mode", "split",
                    "--cache-dir", d, "--out", out,
                ])
            finally:
                m._yf_fetch = orig
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(out))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests/test_macro_regime.py::TestOrchestratorAndCLI -v`
Expected: FAIL — `AttributeError: ... has no attribute 'build_regime_frame'`.

- [ ] **Step 3: Implement orchestrator, summary, and CLI**

Add to `macro_regime_model.py` (add `import argparse` and `import sys` to the import block). Note the CLI resolves the fetcher through the module-level name `_yf_fetch` so tests can monkeypatch it:
```python
import argparse
import sys


def build_regime_frame(start, end=None, n_components=3, window=20, mode="walkforward",
                       warmup=504, step=63, cache_dir="data", fetcher=None):
    """End-to-end: load -> features -> regime labels. `mode` is 'walkforward' or 'split'."""
    raw = MacroDataLoader(cache_dir=cache_dir, fetcher=fetcher).load(start, end)
    feat = build_features(raw, window=window)
    if mode == "walkforward":
        return WalkForwardRegimeLabeler(n_components, warmup, step).run(feat)
    if mode == "split":
        cut = int(len(feat) * 0.7)
        model = CausalRegimeModel(n_components).fit(feat.iloc[:cut])
        return model.label(feat.iloc[cut:])
    raise ValueError(f"unknown mode: {mode!r}")


def summarize(frame: pd.DataFrame, n_components: int) -> str:
    lines = []
    for k in range(n_components):
        mask = frame["regime_argmax"] == k
        occ = float(mask.mean())
        me = float(frame.loc[mask, "entropy_norm"].mean()) if mask.any() else float("nan")
        lines.append(f"State {k}: occupancy={occ:.3f} mean_entropy_norm={me:.3f}")
    lines.append(f"overall mean_entropy_norm={float(frame['entropy_norm'].mean()):.3f}")
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Causal macro-liquidity regime instrument.")
    p.add_argument("--start", required=True)
    p.add_argument("--end", default=None)
    p.add_argument("--components", type=int, default=3)
    p.add_argument("--window", type=int, default=20)
    p.add_argument("--mode", choices=["split", "walkforward"], default="walkforward")
    p.add_argument("--warmup", type=int, default=504)
    p.add_argument("--step", type=int, default=63)
    p.add_argument("--cache-dir", default="data")
    p.add_argument("--out", default="regimes.csv")
    a = p.parse_args(argv)
    frame = build_regime_frame(
        start=a.start, end=a.end, n_components=a.components, window=a.window,
        mode=a.mode, warmup=a.warmup, step=a.step, cache_dir=a.cache_dir,
        fetcher=_yf_fetch,
    )
    frame.to_csv(a.out)
    print(summarize(frame, a.components))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests/test_macro_regime.py::TestOrchestratorAndCLI -v`
Expected: 4 passed.

- [ ] **Step 5: Run the FULL quarantined suite**

Run: `experiments/macro_regime/.venv/bin/pytest experiments/macro_regime/tests -v`
Expected: all tests pass (Task 2–7).

- [ ] **Step 6: Re-verify quarantine after all code lands**

Run:
```bash
.venv/bin/python -m pytest --collect-only -q 2>/dev/null | grep -c macro_regime
```
Expected: `0` — the main suite still does not collect the instrument's tests.

- [ ] **Step 7: Smoke-run the CLI end-to-end against live data** *(optional; requires network)*

Run:
```bash
experiments/macro_regime/.venv/bin/python experiments/macro_regime/macro_regime_model.py --start 2018-01-01 --mode walkforward --out /tmp/regimes.csv
```
Expected: prints a per-state occupancy + mean-entropy summary and writes `/tmp/regimes.csv`. (If yfinance rate-limits, rely on the synthetic-fetch tests — the network path is `_yf_fetch` only.)

- [ ] **Step 8: Commit** *(on user go-ahead)*

```bash
git add experiments/macro_regime/macro_regime_model.py experiments/macro_regime/tests/test_macro_regime.py
git commit -m "feat(macro_regime): orchestrator, CLI, and text summary"
```

---

## Self-Review

**Spec coverage (DESIGN.md → task):**
- §2 layout / requirements / README / quarantine → Task 1.
- §3.1 `MacroDataLoader` (fetch/align/cache, error on empty) → Task 6.
- §3.2 `build_features` (exogenous-only, Δyield for TNX, Gold/DXY ratio, carried BTC, no levels) → Task 3.
- §3.3 `CausalRegimeModel` (fit-on-train/transform-predict-on-test, canonical ordering, leakage boundary) → Task 4.
- §3.4 `WalkForwardRegimeLabeler` (expanding window, causality) → Task 5.
- §4 output columns (`P_State_*`, `entropy`, `entropy_norm`, `regime_argmax`, carried BTC) → Tasks 4 & 7.
- §5 CLI (`--start/--end/--components/--window/--mode/--warmup/--step/--out`) + text summary → Task 7.
- §6 tests (leakage guard, walk-forward causality, entropy math, label stability, stationarity smoke) → Tasks 2–7 (entropy T2, stationarity T3, leakage+stability T4, causality T5).
- §7 guardrails (instrument-only, no semantic names, quarantine, git hygiene) → Global Constraints + README (Task 1).
- *Deviations from DESIGN.md, both faithful refinements:* (a) test isolation is via `testpaths=["tests"]` (auto-exclude) rather than an `--ignore` edit; (b) raw cache is CSV, not parquet, to avoid a `pyarrow` dependency. Both noted in Global Constraints / Task 6.

**Placeholder scan:** none — every code step contains complete, runnable code; the only "optional" step (7.7) is a live-network smoke test explicitly marked optional.

**Type consistency:** `build_features` output columns (`EXOG_FEATURES` + carried `BTC_*`) are consumed unchanged by `CausalRegimeModel.label`, `WalkForwardRegimeLabeler.run`, and `build_regime_frame`. `fetcher` signature `(ticker, start, end) -> pd.Series` is identical across `_yf_fetch`, `make_synthetic_fetcher`, and `MacroDataLoader`. `label`/`run`/`build_regime_frame` all emit the same column set consumed by `summarize`.
