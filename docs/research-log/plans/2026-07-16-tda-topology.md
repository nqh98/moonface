# TDA Correlation Topology (`tda_topology_v1`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a descriptive instrument that answers one question — does persistent homology of the cross-sectional correlation matrix stratify the forward-R distribution of the frozen 1838 Donchian events, beyond a time-structure-preserving null?

**Architecture:** A quarantined package under `experiments/tda_topology/` with its own venv (numpy/scipy/ripser must not enter the stdlib-only main tree). It loads cached 4h candles offline, builds a rolling Spearman correlation matrix over a 17-asset cross-section, converts it to a distance matrix, runs Vietoris-Rips persistent homology, derives seven causal topology features per bar, labels each bar with frozen expanding-median thresholds, and feeds those labels into `moonface.research.microscope.events` **verbatim**. The novel piece is a circular-block-permutation null that preserves the label series' autocorrelation.

**Tech Stack:** Python 3.12, pytest, numpy, scipy (`linear_sum_assignment`), ripser (fallback gudhi). Correlation, entropy, landscape norms, labels, and the null are hand-rolled pure-Python — no persim, no sklearn.

**Spec:** `docs/research-log/specs/2026-07-16-tda-topology-design.md` (commit `ef37b31` + amendments). Read it before starting; it carries the reasoning this plan only executes.

## Global Constraints

- **The main tree changes zero lines.** Nothing under `src/`, `tools/`, `tests/`, or `pyproject.toml` may be modified. All new code lives in `experiments/tda_topology/`.
- **NOT-A-GATE.** No pass/fail for any trading decision. No lockbox, no seal, no DSR ladder, no promotion path, no writes to `EXIT_REGISTRY` or any journal.
- **Frozen parameters, copied verbatim from spec §3:** `W = 60`, `XS_MIN_ASSETS = 8`, `BURN_IN = 250`, `BLOCK = 30`, `N_SHUFFLES = 200`, `maxdim = 1`.
- **No parameter rescue.** If the verdict is negative, do not re-run at another `W`, `BLOCK`, or threshold. This is the `stack_path` `h=6` trap (spec §7).
- **Reuse `microscope.events` verbatim** — `event_outcomes`, `bucket_report`, `effect_size`, and the constants `HORIZONS = (6, 12, 42)`, `PRIMARY_HORIZON = 12`, `POWER_FLOOR = 30`, `K_ATR = 2.0`, `ATR_PERIOD = 14`. Do not copy, fork, or "improve" them.
- **Causality is a hard invariant.** Every feature and label at bar `t` uses only bars `≤ t`. Expanding quantiles use history strictly before `t`.
- **Cache-only, offline.** Never fetch. `OhlcvCache.load` returns `None` for a missing file — fail loudly, never silently shrink the cross-section (microscope run gotcha #1).
- **Commit style:** no `Co-Authored-By` or any AI attribution trailer (user global rule). `docs/` is in `~/.gitignore_global`, so plan/spec files need `git add -f`. Never chain `git add && git commit` — stage, verify `git diff --cached --stat`, then commit.

## File Structure

Spec §3 sketched three modules; this plan splits two responsibilities out because each carries its own test cycle and a reviewer could reject one while approving its neighbour.

| File | Responsibility |
|---|---|
| `experiments/tda_topology/requirements.txt` | pinned deps for the quarantined venv |
| `experiments/tda_topology/.gitignore` | `.venv/`, `*.csv`, `*.log` |
| `experiments/tda_topology/README.md` | how to install and run |
| `experiments/tda_topology/grid.py` | cache-only pool load, timestamp grid, aligned log-return matrix |
| `experiments/tda_topology/tda_features.py` | correlation → distance → persistence diagrams → 7 features |
| `experiments/tda_topology/tda_labels.py` | features → frozen expanding-median labels |
| `experiments/tda_topology/nulls.py` | circular block permutation + block null calibration |
| `experiments/tda_topology/run.py` | offline orchestrator, report rendering, CLI |
| `experiments/tda_topology/tests/test_grid.py` | grid + returns |
| `experiments/tda_topology/tests/test_tda_features.py` | known-topology correctness, causality, gaps |
| `experiments/tda_topology/tests/test_tda_labels.py` | burn-in, causality, label vocabulary |
| `experiments/tda_topology/tests/test_nulls.py` | permutation invariants, null verdict |
| `experiments/tda_topology/tests/test_pipeline.py` | iid self-test, determinism |

`pyproject.toml` sets `testpaths = ["tests"]`, so these tests are automatically excluded from the main suite — same as `experiments/macro_regime/`. They run only via the quarantined venv's pytest.

---

### Task 1: Quarantined venv + ripser install spike

This is the risk-retirement task. `ripser` builds from source on Python 3.12 and may fail; find out now, not after five tasks of work.

**Files:**
- Create: `experiments/tda_topology/requirements.txt`
- Create: `experiments/tda_topology/.gitignore`
- Create: `experiments/tda_topology/README.md`
- Test: `experiments/tda_topology/tests/test_install.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a working `.venv` at `experiments/tda_topology/.venv` with `numpy`, `scipy`, `pytest`, a persistent-homology backend, and the main `moonface` package installed editable.

- [ ] **Step 1: Create the directory and dependency files**

```bash
mkdir -p experiments/tda_topology/tests
```

`experiments/tda_topology/requirements.txt`:
```
numpy>=1.26
scipy>=1.11
ripser>=0.6.4
pytest>=8.0
```

`experiments/tda_topology/.gitignore`:
```
.venv/
*.csv
*.log
__pycache__/
```

- [ ] **Step 2: Build the venv and install**

```bash
cd experiments/tda_topology
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e ../..
```

Expected: all installs succeed. If `ripser` fails to build, replace the `ripser>=0.6.4` line with `gudhi>=3.9` and re-run; then use the gudhi backend in Task 3 Step 3 (the alternate implementation is given there). Record which backend was used in `README.md`.

- [ ] **Step 3: Write the failing test**

`experiments/tda_topology/tests/test_install.py`:
```python
"""The install spike: the PH backend and the main package must both import,
and the backend must find the topology of a shape we already know."""
import math

import numpy as np


def _circle(n=40, radius=1.0):
    return np.array([[radius * math.cos(2 * math.pi * i / n),
                      radius * math.sin(2 * math.pi * i / n)]
                     for i in range(n)])


def test_main_package_imports():
    from moonface.research.microscope.events import POWER_FLOOR
    assert POWER_FLOOR == 30


def test_backend_finds_one_loop_in_a_circle():
    from ripser import ripser
    dgms = ripser(_circle(), maxdim=1)["dgms"]
    h1 = [(b, d) for b, d in dgms[1] if np.isfinite(d)]
    long_lived = [(b, d) for b, d in h1 if d - b > 0.5]
    assert len(long_lived) == 1
```

- [ ] **Step 4: Run the test**

Run: `cd experiments/tda_topology && .venv/bin/pytest tests/test_install.py -v`
Expected: 2 passed. A circle has exactly one 1-dimensional hole, and the backend must say so.

- [ ] **Step 5: Write the README**

`experiments/tda_topology/README.md`:
```markdown
# tda_topology_v1 — descriptive instrument

Design: `docs/research-log/specs/2026-07-16-tda-topology-design.md`

**NOT A GATE.** No lockbox, no DSR ladder, no promotion path. This answers one
question and stops: does persistent homology of the cross-sectional correlation
matrix stratify forward-R of the frozen 1838 Donchian events, beyond a null that
preserves time structure? Microscope's 5-factor state vector did not
(effect 0.609 vs shuffle p95 0.835).

## Install

    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pip install -e ../..

Quarantined on purpose: the main tree is stdlib-only, so numpy/scipy/ripser
must not enter `src/`. PH backend in use: ripser.

## Test

    .venv/bin/pytest tests/ -v

## Run (offline, cache-only)

    .venv/bin/python run.py --cache-dir ../../cache/matrix \
        --events ../microscope/donchian_universe_events.csv \
        --out . --seed 1

Reads cached 4h candles only. Never fetches. Writes features.csv, labels.csv,
outcomes.csv, report.md, run.log.
```

- [ ] **Step 6: Commit**

```bash
git add -f experiments/tda_topology/requirements.txt \
           experiments/tda_topology/.gitignore \
           experiments/tda_topology/README.md \
           experiments/tda_topology/tests/test_install.py
git diff --cached --stat
```
Verify exactly four files are staged and nothing else, then:
```bash
git commit -m "feat(tda_topology): quarantined venv + PH backend install spike"
```

---

### Task 2: `grid.py` — cache-only pool, timestamp grid, return matrix

**Files:**
- Create: `experiments/tda_topology/grid.py`
- Test: `experiments/tda_topology/tests/test_grid.py`

**Interfaces:**
- Consumes: `moonface.foundation.data.OhlcvCache` (`.load(symbol, timeframe) -> list[Candle] | None`), `moonface.foundation.bundle.DataBundle` (field `candles`), `moonface.foundation.models.Candle` (fields `timestamp_ms`, `open`, `high`, `low`, `close`, `volume`).
- Produces:
  - `UNIVERSE: list[str]` — 17 symbols
  - `load_pool_cache_only(cache_dir: str, symbols: list[str] = UNIVERSE) -> dict[str, DataBundle]`
  - `build_grid(pool: dict[str, DataBundle]) -> list[int]`
  - `log_return_matrix(pool: dict[str, DataBundle], timestamps: list[int]) -> dict[str, list[float | None]]`

- [ ] **Step 1: Write the failing test**

`experiments/tda_topology/tests/test_grid.py`:
```python
import math

import pytest

from moonface.foundation.bundle import DataBundle
from moonface.foundation.models import Candle

from grid import build_grid, load_pool_cache_only, log_return_matrix


def _candle(ts, close):
    return Candle(timestamp_ms=ts, open=close, high=close,
                  low=close, close=close, volume=1.0)


def _bundle(pairs):
    return DataBundle(candles=[_candle(ts, c) for ts, c in pairs])


def test_grid_is_sorted_union_of_bar_timestamps():
    pool = {"A": _bundle([(300, 1.0), (100, 1.0)]),
            "B": _bundle([(200, 1.0), (100, 1.0)])}
    assert build_grid(pool) == [100, 200, 300]


def test_returns_are_log_and_aligned_to_the_grid():
    pool = {"A": _bundle([(100, 1.0), (200, 2.0), (300, 4.0)])}
    ts = build_grid(pool)
    rets = log_return_matrix(pool, ts)
    assert rets["A"][0] is None                       # no prior bar
    assert rets["A"][1] == pytest.approx(math.log(2))
    assert rets["A"][2] == pytest.approx(math.log(2))


def test_missing_bar_yields_none_not_a_silent_gap():
    # B has no bar at 200; its return there must be None, and the return at
    # 300 must also be None because the previous *B* bar is not adjacent.
    pool = {"A": _bundle([(100, 1.0), (200, 2.0), (300, 4.0)]),
            "B": _bundle([(100, 1.0), (300, 4.0)])}
    ts = build_grid(pool)
    rets = log_return_matrix(pool, ts)
    assert rets["B"][1] is None
    assert rets["B"][2] is None


def test_missing_symbol_fails_loudly(tmp_path):
    with pytest.raises(FileNotFoundError, match="NOPEUSDT"):
        load_pool_cache_only(str(tmp_path), ["NOPEUSDT"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd experiments/tda_topology && .venv/bin/pytest tests/test_grid.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'grid'`

- [ ] **Step 3: Write the implementation**

`experiments/tda_topology/grid.py`:
```python
"""Cache-only pool loading and the aligned cross-sectional return matrix.

Correlation topology needs returns and nothing else, so this lane never
touches OI, funding, or bookdepth -- that is the entire fetch cost the
microscope run paid (~8 min/asset) and this one does not."""
from __future__ import annotations

import math
import os

from moonface.foundation.bundle import DataBundle
from moonface.foundation.data import OhlcvCache

# The 16 frozen drift_screen assets plus BTCUSDT -- the universe the 1838
# Donchian events were generated on. Deliberately no ETH, no SOL (spec 3.1).
UNIVERSE = ["1000PEPEUSDT", "PEOPLEUSDT", "DOGEUSDT", "BNBUSDT",
            "1000SHIBUSDT", "1000FLOKIUSDT", "XRPUSDT", "LINKUSDT",
            "HIGHUSDT", "NEARUSDT", "JASMYUSDT", "TRBUSDT", "FILUSDT",
            "ARBUSDT", "AVAXUSDT", "ETCUSDT", "BTCUSDT"]

TIMEFRAME = "4h"


def load_pool_cache_only(cache_dir: str,
                         symbols: list[str] = UNIVERSE
                         ) -> dict[str, DataBundle]:
    """{symbol: DataBundle} from the CSV cache only -- never fetches.

    Raises on a missing symbol instead of skipping it. The microscope's first
    run silently collapsed to BTC-only because its reader returned [] for
    missing files, which made every event UNLABELED; a loud failure is the fix."""
    cache = OhlcvCache(cache_dir)
    pool: dict[str, DataBundle] = {}
    for sym in symbols:
        candles = cache.load(sym, TIMEFRAME)
        if not candles:
            raise FileNotFoundError(
                f"no cached {TIMEFRAME} candles for {sym} at "
                f"{os.path.join(cache_dir, f'{sym}_{TIMEFRAME}.csv')}")
        pool[sym] = DataBundle(candles=candles)
    return pool


def build_grid(pool: dict[str, DataBundle]) -> list[int]:
    """Sorted union of bar-open timestamps -- the shared axis, matching
    microscope.features.build_matrix so labels index the same way."""
    ts: set[int] = set()
    for bundle in pool.values():
        ts.update(c.timestamp_ms for c in bundle.candles)
    return sorted(ts)


def log_return_matrix(pool: dict[str, DataBundle],
                      timestamps: list[int]) -> dict[str, list[float | None]]:
    """{symbol: [log return at each grid bar]}, None where the asset has no
    bar or no adjacent prior bar. Adjacency is on the asset's own series, so
    a hole in one asset never fabricates a return across it."""
    index = {ts: i for i, ts in enumerate(timestamps)}
    out: dict[str, list[float | None]] = {}
    for sym, bundle in pool.items():
        series: list[float | None] = [None] * len(timestamps)
        candles = bundle.candles
        for k in range(1, len(candles)):
            prev, cur = candles[k - 1], candles[k]
            if prev.close <= 0 or cur.close <= 0:
                continue
            t = index[cur.timestamp_ms]
            if index[prev.timestamp_ms] != t - 1:
                continue          # gap on the shared axis; not a 1-bar return
            series[t] = math.log(cur.close / prev.close)
        out[sym] = series
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd experiments/tda_topology && .venv/bin/pytest tests/test_grid.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add -f experiments/tda_topology/grid.py experiments/tda_topology/tests/test_grid.py
git diff --cached --stat
git commit -m "feat(tda_topology): cache-only pool loader and aligned return matrix"
```

---

### Task 3: `tda_features.py` — correlation → distance → persistence → features

The correctness of this lane lives here, and it is testable against shapes whose topology is known before any market data is involved.

**Files:**
- Create: `experiments/tda_topology/tda_features.py`
- Test: `experiments/tda_topology/tests/test_tda_features.py`

**Interfaces:**
- Consumes: `grid.log_return_matrix` output shape (`dict[str, list[float | None]]`).
- Produces:
  - `W = 60`, `XS_MIN_ASSETS = 8`, `MAXDIM = 1`
  - `FEATURE_KEYS: tuple[str, ...]` — the seven feature names
  - `spearman_corr(mat: list[list[float]]) -> list[list[float]]`
  - `corr_distance(rho: list[list[float]]) -> list[list[float]]`
  - `persistence_diagrams(dist: list[list[float]], maxdim: int = MAXDIM) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]`
  - `persistence_entropy(dgm: list[tuple[float, float]]) -> float | None`
  - `total_persistence(dgm: list[tuple[float, float]]) -> float`
  - `landscape_norms(dgm: list[tuple[float, float]], n_grid: int = 200) -> tuple[float, float]`
  - `wasserstein1(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float`
  - `build_features(returns: dict[str, list[float | None]], n_bars: int, w: int = W, min_assets: int = XS_MIN_ASSETS) -> list[dict[str, float | None]]`

- [ ] **Step 1: Write the failing test**

`experiments/tda_topology/tests/test_tda_features.py`:
```python
import math
import random

from tda_features import (FEATURE_KEYS, W, build_features, corr_distance,
                          landscape_norms, persistence_diagrams,
                          persistence_entropy, spearman_corr,
                          total_persistence, wasserstein1)


def test_spearman_is_monotone_invariant():
    # Spearman sees rank, so a monotone transform must not move it.
    a = [1.0, 2.0, 3.0, 4.0, 5.0]
    b = [1.0, 4.0, 9.0, 16.0, 25.0]
    rho = spearman_corr([a, b])
    assert rho[0][1] == 1.0


def test_corr_distance_maps_perfect_correlation_to_zero():
    d = corr_distance([[1.0, 1.0], [1.0, 1.0]])
    assert d[0][1] == 0.0


def test_corr_distance_maps_perfect_anticorrelation_to_two():
    d = corr_distance([[1.0, -1.0], [-1.0, 1.0]])
    assert d[0][1] == 2.0


def test_two_separated_clusters_give_two_h0_classes():
    # Points at distance 0 within a cluster, 10 across: exactly two
    # components survive until the clusters merge.
    n = 6
    dist = [[0.0 if (i < 3) == (j < 3) else 10.0 for j in range(n)]
            for i in range(n)]
    h0, _ = persistence_diagrams(dist)
    long_lived = [(b, d) for b, d in h0 if d - b > 1.0]
    assert len(long_lived) == 1   # the infinite class is dropped; one finite
    assert long_lived[0][1] == 10.0


def test_circle_gives_exactly_one_persistent_loop():
    n = 40
    pts = [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n))
           for i in range(n)]
    dist = [[math.dist(p, q) for q in pts] for p in pts]
    _, h1 = persistence_diagrams(dist)
    long_lived = [(b, d) for b, d in h1 if d - b > 0.5]
    assert len(long_lived) == 1


def test_persistence_entropy_is_zero_for_one_bar_and_none_for_empty():
    assert persistence_entropy([(0.0, 1.0)]) == 0.0
    assert persistence_entropy([]) is None


def test_persistence_entropy_is_maximal_for_equal_bars():
    two_equal = persistence_entropy([(0.0, 1.0), (0.0, 1.0)])
    lopsided = persistence_entropy([(0.0, 1.0), (0.0, 0.01)])
    assert two_equal == math.log(2)
    assert lopsided < two_equal


def test_total_persistence_sums_lifetimes():
    assert total_persistence([(0.0, 1.0), (2.0, 4.5)]) == 3.5


def test_landscape_norms_scale_with_the_bar():
    small_l1, small_l2 = landscape_norms([(0.0, 1.0)])
    big_l1, big_l2 = landscape_norms([(0.0, 2.0)])
    assert big_l1 > small_l1 > 0.0
    assert big_l2 > small_l2 > 0.0
    assert landscape_norms([]) == (0.0, 0.0)


def test_wasserstein_is_zero_for_identical_diagrams():
    dgm = [(0.0, 1.0), (0.5, 2.0)]
    assert wasserstein1(dgm, dgm) == 0.0


def test_wasserstein_matches_a_point_to_the_diagonal_when_unpaired():
    # A single bar of lifetime 1.0 against an empty diagram costs its
    # diagonal projection, 0.5.
    assert wasserstein1([(0.0, 1.0)], []) == 0.5


def test_wasserstein_grows_with_a_shifted_point():
    assert wasserstein1([(0.0, 1.0)], [(0.0, 1.0)]) == 0.0
    assert wasserstein1([(0.0, 1.0)], [(0.0, 1.4)]) > 0.0


def _synthetic_returns(n_assets, n_bars, seed=0):
    rng = random.Random(seed)
    return {f"A{i}": [rng.gauss(0.0, 0.01) for _ in range(n_bars)]
            for i in range(n_assets)}


def test_below_cross_section_floor_emits_no_features():
    rets = _synthetic_returns(7, W + 5)          # 7 < XS_MIN_ASSETS = 8
    feats = build_features(rets, n_bars=W + 5)
    assert all(f["pers_entropy_h0"] is None for f in feats)


def test_at_cross_section_floor_emits_features():
    rets = _synthetic_returns(8, W + 5)
    feats = build_features(rets, n_bars=W + 5)
    assert feats[W + 4]["pers_entropy_h0"] is not None


def test_features_before_the_window_is_full_are_none():
    rets = _synthetic_returns(8, W + 5)
    feats = build_features(rets, n_bars=W + 5)
    assert all(feats[t]["pers_entropy_h0"] is None for t in range(W - 1))


def test_wasserstein_is_none_when_the_previous_bar_has_no_diagram():
    rets = _synthetic_returns(8, W + 5)
    feats = build_features(rets, n_bars=W + 5)
    # The first bar with a full window has no valid t-1, so no comparison.
    first = next(t for t, f in enumerate(feats)
                 if f["pers_entropy_h0"] is not None)
    assert feats[first]["wasserstein_dist"] is None
    assert feats[first + 1]["wasserstein_dist"] is not None


def test_features_are_causal():
    # Truncating the future must not move a past bar's features.
    full = _synthetic_returns(8, W + 40)
    cut = {k: v[:W + 10] for k, v in full.items()}
    f_full = build_features(full, n_bars=W + 40)
    f_cut = build_features(cut, n_bars=W + 10)
    for t in range(W + 10):
        for key in FEATURE_KEYS:
            assert f_full[t][key] == f_cut[t][key]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd experiments/tda_topology && .venv/bin/pytest tests/test_tda_features.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tda_features'`

- [ ] **Step 3: Write the implementation**

`experiments/tda_topology/tda_features.py`:
```python
"""Cross-sectional correlation topology.

Persistent homology reads the correlation matrix at every threshold at once,
which is the whole reason this instrument exists: the source document warns
that a graph threshold is a large degree of freedom (its 13.5) and then picks
top-k edges anyway (its 14). Persistence *is* "how many thresholds does this
structure survive", so there is no threshold to tune.

Everything here is causal: a bar's features come from its trailing window and
from the immediately preceding bar's diagram, never from the future."""
from __future__ import annotations

import math

import numpy as np
from ripser import ripser
from scipy.optimize import linear_sum_assignment

W = 60                  # trailing window in bars (10 days at 4h) -- FROZEN
XS_MIN_ASSETS = 8       # cross-section floor
MAXDIM = 1              # H0 and H1 only; H2 is costly and meaningless at 17 pts

FEATURE_KEYS = ("pers_entropy_h0", "pers_entropy_h1",
                "total_pers_h0", "total_pers_h1",
                "landscape_l1_h1", "landscape_l2_h1",
                "wasserstein_dist")


def _ranks(xs: list[float]) -> list[float]:
    """Average ranks, ties shared -- the rank transform Spearman needs."""
    n = len(xs)
    order = sorted(range(n), key=lambda i: xs[i])
    out = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0.0 or vb <= 0.0:
        return 0.0
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / math.sqrt(va * vb)


def spearman_corr(mat: list[list[float]]) -> list[list[float]]:
    """Spearman correlation across rows (rows = assets, cols = time).
    Spearman per source document 14 (`rolling Spearman correlation`)."""
    ranks = [_ranks(row) for row in mat]
    m = len(ranks)
    out = [[1.0] * m for _ in range(m)]
    for i in range(m):
        for j in range(i + 1, m):
            r = _pearson(ranks[i], ranks[j])
            out[i][j] = out[j][i] = r
    return out


def corr_distance(rho: list[list[float]]) -> list[list[float]]:
    """d_ij = sqrt(2(1 - rho_ij)) -- a true metric on correlation, mapping
    rho=1 to 0 and rho=-1 to 2."""
    m = len(rho)
    out = [[0.0] * m for _ in range(m)]
    for i in range(m):
        for j in range(m):
            r = min(1.0, max(-1.0, rho[i][j]))
            out[i][j] = math.sqrt(2.0 * (1.0 - r))
    return out


def persistence_diagrams(dist: list[list[float]], maxdim: int = MAXDIM
                         ) -> tuple[list[tuple[float, float]],
                                    list[tuple[float, float]]]:
    """Vietoris-Rips H0/H1 as finite (birth, death) pairs.

    H0's one infinite class (the component that never dies) is dropped: it is
    present in every diagram and carries no information."""
    d = np.array(dist, dtype=float)
    dgms = ripser(d, distance_matrix=True, maxdim=maxdim)["dgms"]
    h0 = [(float(b), float(x)) for b, x in dgms[0] if np.isfinite(x)]
    h1 = [(float(b), float(x)) for b, x in dgms[1] if np.isfinite(x)]
    return h0, h1


def persistence_entropy(dgm: list[tuple[float, float]]) -> float | None:
    """Shannon entropy of normalized lifetimes. None for an empty diagram or
    one with no total lifetime -- there is no distribution to measure."""
    lifetimes = [d - b for b, d in dgm if d > b]
    total = sum(lifetimes)
    if not lifetimes or total <= 0.0:
        return None
    ent = 0.0
    for x in lifetimes:
        p = x / total
        ent -= p * math.log(p)
    return ent


def total_persistence(dgm: list[tuple[float, float]]) -> float:
    return sum(d - b for b, d in dgm)


def landscape_norms(dgm: list[tuple[float, float]],
                    n_grid: int = 200) -> tuple[float, float]:
    """(L1, L2) norms of the first persistence landscape -- the Gidea-Katz
    readout. lambda_1(x) = max_i max(0, min(x - b_i, d_i - x)), integrated by
    trapezoid over the diagram's support."""
    if not dgm:
        return 0.0, 0.0
    lo = min(b for b, _ in dgm)
    hi = max(d for _, d in dgm)
    if hi <= lo:
        return 0.0, 0.0
    step = (hi - lo) / (n_grid - 1)
    vals = []
    for k in range(n_grid):
        x = lo + k * step
        vals.append(max([max(0.0, min(x - b, d - x)) for b, d in dgm]))
    l1 = 0.0
    l2sq = 0.0
    for k in range(n_grid - 1):
        l1 += 0.5 * (vals[k] + vals[k + 1]) * step
        l2sq += 0.5 * (vals[k] ** 2 + vals[k + 1] ** 2) * step
    return l1, math.sqrt(l2sq)


_UNREACHABLE = 1e12


def wasserstein1(a: list[tuple[float, float]],
                 b: list[tuple[float, float]]) -> float:
    """1-Wasserstein distance between diagrams under the L-infinity ground
    metric, solved as optimal assignment.

    Unmatched points pay their projection to the diagonal, (d - b)/2. The
    bottom-right block is diagonal-to-diagonal and free."""
    n, m = len(a), len(b)
    if n == 0 and m == 0:
        return 0.0
    size = n + m
    cost = [[0.0] * size for _ in range(size)]
    for i in range(n):
        for j in range(m):
            cost[i][j] = max(abs(a[i][0] - b[j][0]), abs(a[i][1] - b[j][1]))
        for j in range(m, size):
            cost[i][j] = (a[i][1] - a[i][0]) / 2.0 if j - m == i else _UNREACHABLE
    for i in range(n, size):
        for j in range(m):
            cost[i][j] = (b[j][1] - b[j][0]) / 2.0 if i - n == j else _UNREACHABLE
        for j in range(m, size):
            cost[i][j] = 0.0
    rows, cols = linear_sum_assignment(np.array(cost))
    return float(sum(cost[i][j] for i, j in zip(rows, cols)))


def build_features(returns: dict[str, list[float | None]], n_bars: int,
                   w: int = W, min_assets: int = XS_MIN_ASSETS
                   ) -> list[dict[str, float | None]]:
    """Seven causal topology features per bar.

    A bar with fewer than `min_assets` complete trailing windows emits all
    None and becomes UNLABELED downstream. `wasserstein_dist` needs bar t-1 to
    have a diagram; when it does not, the feature is None rather than reaching
    further back -- comparing across a gap of unknown length would make the
    same feature mean different things at different bars (spec 3.2)."""
    out = [dict.fromkeys(FEATURE_KEYS) for _ in range(n_bars)]
    prev_h1: list[tuple[float, float]] | None = None
    prev_t = -1
    for t in range(w - 1, n_bars):
        window: list[list[float]] = []
        for series in returns.values():
            chunk = series[t - w + 1:t + 1]
            if len(chunk) == w and all(v is not None for v in chunk):
                window.append([float(v) for v in chunk])
        if len(window) < min_assets:
            continue
        h0, h1 = persistence_diagrams(corr_distance(spearman_corr(window)))
        row = out[t]
        row["pers_entropy_h0"] = persistence_entropy(h0)
        row["pers_entropy_h1"] = persistence_entropy(h1)
        row["total_pers_h0"] = total_persistence(h0)
        row["total_pers_h1"] = total_persistence(h1)
        l1, l2 = landscape_norms(h1)
        row["landscape_l1_h1"] = l1
        row["landscape_l2_h1"] = l2
        if prev_h1 is not None and prev_t == t - 1:
            row["wasserstein_dist"] = wasserstein1(prev_h1, h1)
        prev_h1, prev_t = h1, t
    return out
```

If Task 1 fell back to gudhi, replace `persistence_diagrams` with:
```python
import gudhi

def persistence_diagrams(dist, maxdim=MAXDIM):
    rips = gudhi.RipsComplex(distance_matrix=dist, max_edge_length=2.0)
    tree = rips.create_simplex_tree(max_dimension=maxdim + 1)
    tree.compute_persistence()
    h0 = [(float(b), float(d)) for b, d in tree.persistence_intervals_in_dimension(0)
          if d != float("inf")]
    h1 = [(float(b), float(d)) for b, d in tree.persistence_intervals_in_dimension(1)
          if d != float("inf")]
    return h0, h1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd experiments/tda_topology && .venv/bin/pytest tests/test_tda_features.py -v`
Expected: 16 passed. If `test_circle_gives_exactly_one_persistent_loop` fails, the backend is wrong — stop and fix it before continuing; every downstream number depends on it.

- [ ] **Step 5: Commit**

```bash
git add -f experiments/tda_topology/tda_features.py \
           experiments/tda_topology/tests/test_tda_features.py
git diff --cached --stat
git commit -m "feat(tda_topology): correlation topology features (H0/H1, landscape, wasserstein)"
```

---

### Task 4: `tda_labels.py` — frozen expanding-median labels

**Files:**
- Create: `experiments/tda_topology/tda_labels.py`
- Test: `experiments/tda_topology/tests/test_tda_labels.py`

**Interfaces:**
- Consumes: `tda_features.build_features` output (`list[dict[str, float | None]]`), `moonface.research.microscope.regimes.UNLABELED`.
- Produces:
  - `BURN_IN = 250`, `LABELS: tuple[str, ...]` (the four label strings)
  - `expanding_median_flags(values: list[float | None], burn_in: int = BURN_IN) -> list[bool | None]`
  - `build_labels(features: list[dict[str, float | None]], burn_in: int = BURN_IN) -> list[str]`

- [ ] **Step 1: Write the failing test**

`experiments/tda_topology/tests/test_tda_labels.py`:
```python
from moonface.research.microscope.regimes import UNLABELED

from tda_labels import BURN_IN, LABELS, build_labels, expanding_median_flags


def test_flags_are_none_until_burn_in_is_satisfied():
    flags = expanding_median_flags([float(i) for i in range(10)], burn_in=5)
    assert flags[:5] == [None] * 5
    assert flags[5] is not None


def test_flag_compares_against_history_strictly_before_the_bar():
    # History before index 3 is [0, 1, 2], median 1. Value 5 > 1 -> True.
    flags = expanding_median_flags([0.0, 1.0, 2.0, 5.0], burn_in=3)
    assert flags[3] is True


def test_flag_is_causal_appending_the_future_cannot_change_the_past():
    base = [float(i) for i in range(20)]
    short = expanding_median_flags(base, burn_in=5)
    long = expanding_median_flags(base + [999.0] * 20, burn_in=5)
    assert short == long[:20]


def test_none_values_are_skipped_not_counted():
    flags = expanding_median_flags([0.0, None, 1.0, 2.0, 5.0], burn_in=3)
    assert flags[1] is None
    assert flags[4] is True


def test_labels_use_the_four_frozen_names_plus_unlabeled():
    feats = []
    for i in range(BURN_IN + 10):
        feats.append({"pers_entropy_h0": float(i % 7),
                      "wasserstein_dist": float(i % 5)})
    labels = build_labels(feats)
    assert labels[0] == UNLABELED
    assert set(labels[BURN_IN + 1:]) <= set(LABELS)


def test_missing_feature_yields_unlabeled():
    feats = [{"pers_entropy_h0": None, "wasserstein_dist": None}
             for _ in range(BURN_IN + 10)]
    assert build_labels(feats) == [UNLABELED] * (BURN_IN + 10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd experiments/tda_topology && .venv/bin/pytest tests/test_tda_labels.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tda_labels'`

- [ ] **Step 3: Write the implementation**

`experiments/tda_topology/tda_labels.py`:
```python
"""Frozen-threshold market-level regime labels.

Thresholds are expanding trailing medians, never global quantiles: a global
quantile over the full sample would make the label at bar t depend on bars
after t, which is look-ahead in its purest form.

These thresholds are frozen in the design spec and must never be tuned against
study outcomes -- that would turn the instrument into a fitted regime model,
which is exactly what it is not."""
from __future__ import annotations

import bisect

from moonface.research.microscope.regimes import UNLABELED

BURN_IN = 250       # bars of history before any label is emitted -- FROZEN

LABELS = ("CONCENTRATED/STABLE", "CONCENTRATED/BREAK",
          "DISPERSED/STABLE", "DISPERSED/BREAK")


def expanding_median_flags(values: list[float | None],
                           burn_in: int = BURN_IN) -> list[bool | None]:
    """flags[t] = values[t] > median(all non-None values strictly before t).

    None until `burn_in` observations have accumulated, and None wherever the
    value itself is None. The median uses history before t only, so appending
    future data can never change a past flag."""
    out: list[bool | None] = [None] * len(values)
    hist: list[float] = []
    for t, v in enumerate(values):
        if v is not None and len(hist) >= burn_in:
            n = len(hist)
            med = (hist[n // 2] if n % 2
                   else 0.5 * (hist[n // 2 - 1] + hist[n // 2]))
            out[t] = v > med
        if v is not None:
            bisect.insort(hist, v)
    return out


def build_labels(features: list[dict[str, float | None]],
                 burn_in: int = BURN_IN) -> list[str]:
    """Two frozen axes -> four buckets.

    Concentration: low pers_entropy_h0 = few dominant clusters = CONCENTRATED.
    Stability: large wasserstein_dist = the topology moved = BREAK."""
    hi_entropy = expanding_median_flags(
        [f["pers_entropy_h0"] for f in features], burn_in)
    hi_shift = expanding_median_flags(
        [f["wasserstein_dist"] for f in features], burn_in)
    out: list[str] = []
    for a, b in zip(hi_entropy, hi_shift):
        if a is None or b is None:
            out.append(UNLABELED)
            continue
        out.append(f"{'DISPERSED' if a else 'CONCENTRATED'}/"
                   f"{'BREAK' if b else 'STABLE'}")
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd experiments/tda_topology && .venv/bin/pytest tests/test_tda_labels.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add -f experiments/tda_topology/tda_labels.py \
           experiments/tda_topology/tests/test_tda_labels.py
git diff --cached --stat
git commit -m "feat(tda_topology): causal expanding-median regime labels"
```

---

### Task 5: `nulls.py` — circular block permutation

The one place this lane departs from the microscope, and the reason it can be trusted. See spec §3.5.

**Files:**
- Create: `experiments/tda_topology/nulls.py`
- Test: `experiments/tda_topology/tests/test_nulls.py`

**Interfaces:**
- Consumes: `moonface.research.microscope.events.effect_size(outcomes) -> float`.
- Produces:
  - `BLOCK = 30`, `N_SHUFFLES = 200`
  - `circular_block_permute(seq: list, block: int, rng: random.Random) -> list`
  - `block_null_calibration(outcomes: list[dict], bar_labels: list[str], timestamps: list[int], seed: int = 0, block: int = BLOCK, n_shuffles: int = N_SHUFFLES) -> dict` returning keys `real_effect`, `null_p95`, `pct_beaten`, `verdict`

- [ ] **Step 1: Write the failing test**

`experiments/tda_topology/tests/test_nulls.py`:
```python
import random

from nulls import BLOCK, block_null_calibration, circular_block_permute


def test_block_one_is_a_permutation_of_the_input():
    seq = list(range(50))
    out = circular_block_permute(seq, 1, random.Random(0))
    assert sorted(out) == seq
    assert len(out) == len(seq)


def test_block_equal_to_length_is_a_rotation():
    seq = list(range(10))
    out = circular_block_permute(seq, len(seq), random.Random(3))
    assert sorted(out) == seq
    doubled = seq + seq
    assert any(doubled[i:i + len(seq)] == out for i in range(len(seq)))


def test_permutation_preserves_the_multiset_for_any_block():
    seq = ["A"] * 17 + ["B"] * 13 + ["C"] * 20
    for block in (1, 7, 30, 50):
        out = circular_block_permute(seq, block, random.Random(block))
        assert sorted(out) == sorted(seq)


def test_block_permutation_preserves_run_structure_better_than_shuffling():
    # A label series of long runs must keep long runs under block permutation,
    # while a plain shuffle destroys them. This is the whole point of BLOCK.
    seq = (["A"] * 100) + (["B"] * 100)

    def longest_run(xs):
        best = cur = 1
        for i in range(1, len(xs)):
            cur = cur + 1 if xs[i] == xs[i - 1] else 1
            best = max(best, cur)
        return best

    blocked = circular_block_permute(seq, BLOCK, random.Random(1))
    shuffled = circular_block_permute(seq, 1, random.Random(1))
    assert longest_run(blocked) >= BLOCK
    assert longest_run(shuffled) < BLOCK


def _outcomes(labels_by_bar, timestamps):
    # One event per bar, forward R equal to a constant per label.
    payoff = {"UP": 1.0, "DOWN": -1.0}
    return [{"symbol": "X", "ts_ms": ts, "direction": 1,
             "label": labels_by_bar[i], "fwd_r_12": payoff[labels_by_bar[i]]}
            for i, ts in enumerate(timestamps)]


def test_a_perfectly_separating_label_exceeds_the_null():
    timestamps = list(range(200))
    bar_labels = ["UP"] * 100 + ["DOWN"] * 100
    outcomes = _outcomes(bar_labels, timestamps)
    res = block_null_calibration(outcomes, bar_labels, timestamps,
                                 seed=0, block=1, n_shuffles=50)
    assert res["real_effect"] == 2.0
    assert res["verdict"] == "EXCEEDS_NULL"


def test_a_label_unrelated_to_outcome_is_indistinguishable_from_null():
    timestamps = list(range(200))
    bar_labels = ["UP" if i % 2 == 0 else "DOWN" for i in range(200)]
    rng = random.Random(7)
    outcomes = [{"symbol": "X", "ts_ms": ts, "direction": 1,
                 "label": bar_labels[i], "fwd_r_12": rng.gauss(0.0, 1.0)}
                for i, ts in enumerate(timestamps)]
    res = block_null_calibration(outcomes, bar_labels, timestamps,
                                 seed=0, block=1, n_shuffles=200)
    assert res["verdict"] == "INDISTINGUISHABLE_FROM_NULL"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd experiments/tda_topology && .venv/bin/pytest tests/test_nulls.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'nulls'`

- [ ] **Step 3: Write the implementation**

`experiments/tda_topology/nulls.py`:
```python
"""Time-structure-preserving null calibration.

microscope.events.null_calibration shuffles labels row-wise. That was
defensible there: its labels were per-symbol, so each row carried its own
draw. Here the label is market-level and derived from a rolling 60-bar window,
so it is strongly autocorrelated -- labels arrive in long runs. Row-wise
shuffling destroys those runs, shrinks the null effect distribution, and makes
it too easy to beat. A null that cannot reproduce the structure of the real
thing is not a null; that is the vol_compression failure mode in a new costume.

So the primary null permutes the label *time series* in blocks, preserving run
length, and re-derives each event's label from the permuted series."""
from __future__ import annotations

import random

from moonface.research.microscope.events import effect_size

BLOCK = 30          # bars per permutation block -- FROZEN
N_SHUFFLES = 200


def circular_block_permute(seq: list, block: int,
                           rng: random.Random) -> list:
    """Rotate by a random offset, cut into `block`-sized chunks, shuffle the
    chunks, concatenate. Preserves the multiset and, for block > 1, the run
    structure inside each chunk."""
    n = len(seq)
    if n == 0:
        return []
    offset = rng.randrange(n)
    rotated = seq[offset:] + seq[:offset]
    chunks = [rotated[i:i + block] for i in range(0, n, block)]
    rng.shuffle(chunks)
    return [x for chunk in chunks for x in chunk][:n]


def block_null_calibration(outcomes: list[dict], bar_labels: list[str],
                           timestamps: list[int], seed: int = 0,
                           block: int = BLOCK,
                           n_shuffles: int = N_SHUFFLES) -> dict:
    """Re-run the effect with the bar-level label series block-permuted.

    A real conditional effect must beat this distribution. One that survives
    permutation is a selection artifact -- the vol_compression lesson made
    permanent: a valid effect must FAIL on a null."""
    index = {ts: i for i, ts in enumerate(timestamps)}
    real = effect_size(outcomes)
    rng = random.Random(seed)
    null_effects: list[float] = []
    beaten = 0
    for _ in range(n_shuffles):
        permuted = circular_block_permute(bar_labels, block, rng)
        rows = [{**r, "label": permuted[index[r["ts_ms"]]]} for r in outcomes]
        e = effect_size(rows)
        null_effects.append(e)
        if real > e:
            beaten += 1
    null_effects.sort()
    p95 = null_effects[int(0.95 * n_shuffles)] if n_shuffles else 0.0
    verdict = ("EXCEEDS_NULL" if real > p95 and real > 0.0
               else "INDISTINGUISHABLE_FROM_NULL")
    return {"real_effect": round(real, 4), "null_p95": round(p95, 4),
            "pct_beaten": round(beaten / n_shuffles, 4) if n_shuffles else 0.0,
            "verdict": verdict}
```

Note for the implementer: `effect_size` only counts buckets with `n >= POWER_FLOOR` (30) and ignores `UNLABELED` rows, so the toy tests above use 100 rows per label deliberately. Do not lower `POWER_FLOOR` to make a test pass.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd experiments/tda_topology && .venv/bin/pytest tests/test_nulls.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add -f experiments/tda_topology/nulls.py experiments/tda_topology/tests/test_nulls.py
git diff --cached --stat
git commit -m "feat(tda_topology): circular block permutation null calibration"
```

---

### Task 6: `run.py` — orchestrator, report, iid self-test

**Files:**
- Create: `experiments/tda_topology/run.py`
- Test: `experiments/tda_topology/tests/test_pipeline.py`

**Interfaces:**
- Consumes: everything above, plus `moonface.research.microscope.events.{event_outcomes, bucket_report, HORIZONS}` and `moonface.research.microscope.regimes.UNLABELED`.
- Produces:
  - `MICROSCOPE_BASELINE: dict` — the published comparison numbers
  - `run_study(pool, events, timestamps, seed) -> dict` with keys `features`, `bar_labels`, `outcomes`, `buckets`, `block_null`, `row_null`
  - `render_report(...) -> str`
  - `main(argv=None) -> int`

- [ ] **Step 1: Write the failing test**

`experiments/tda_topology/tests/test_pipeline.py`:
```python
import random

from moonface.foundation.bundle import DataBundle
from moonface.foundation.models import Candle
from moonface.research.microscope.events import Event

from run import render_report, run_study

BAR_MS = 4 * 60 * 60 * 1000


def _iid_pool(n_assets=9, n_bars=900, seed=11):
    """Constant-vol iid Gaussian returns: no effect exists by construction."""
    rng = random.Random(seed)
    pool = {}
    for a in range(n_assets):
        price = 100.0
        candles = []
        for t in range(n_bars):
            price *= (1.0 + rng.gauss(0.0, 0.01))
            candles.append(Candle(timestamp_ms=t * BAR_MS, open=price,
                                  high=price * 1.01, low=price * 0.99,
                                  close=price, volume=1.0))
        pool[f"A{a}"] = DataBundle(candles=candles)
    return pool


def _events(pool, every=1):
    out = []
    for sym, bundle in pool.items():
        for i in range(400, len(bundle.candles) - 50, every):
            out.append(Event(ts_ms=bundle.candles[i].timestamp_ms,
                             symbol=sym, direction=1))
    return out


def test_iid_null_is_indistinguishable_from_null():
    """A valid instrument must FAIL on a null. vol_compression produced this
    program's first ever PASS and it was an artifact an iid null would have
    caught; that check is a build-time requirement here."""
    pool = _iid_pool()
    timestamps = sorted({c.timestamp_ms
                         for b in pool.values() for c in b.candles})
    res = run_study(pool, _events(pool), timestamps, seed=1)
    assert res["block_null"]["verdict"] == "INDISTINGUISHABLE_FROM_NULL"


def test_run_is_deterministic_under_a_fixed_seed():
    pool = _iid_pool()
    timestamps = sorted({c.timestamp_ms
                         for b in pool.values() for c in b.candles})
    events = _events(pool)
    a = run_study(pool, events, timestamps, seed=1)
    b = run_study(pool, events, timestamps, seed=1)
    assert a["block_null"] == b["block_null"]
    assert a["buckets"] == b["buckets"]


def test_report_states_the_verdict_and_the_scope_caveat():
    pool = _iid_pool()
    timestamps = sorted({c.timestamp_ms
                         for b in pool.values() for c in b.candles})
    events = _events(pool)
    res = run_study(pool, events, timestamps, seed=1)
    text = render_report(res, n_events=len(events))
    assert "INDISTINGUISHABLE_FROM_NULL" in text
    assert "NOT A GATE" in text
    assert "long-only" in text
    assert "0.609" in text          # the microscope head-to-head baseline
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd experiments/tda_topology && .venv/bin/pytest tests/test_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'run'`

- [ ] **Step 3: Write the implementation**

`experiments/tda_topology/run.py`:
```python
"""tda_topology_v1 -- offline orchestrator.

NOT A GATE. Emits no pass/fail for any trading decision. See
docs/research-log/specs/2026-07-16-tda-topology-design.md."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from moonface.research.microscope.events import (HORIZONS, bucket_report,
                                                 event_outcomes,
                                                 null_calibration)
from moonface.research.microscope.events import Event
from moonface.research.microscope.regimes import UNLABELED

from grid import UNIVERSE, build_grid, load_pool_cache_only, log_return_matrix
from nulls import block_null_calibration
from tda_features import FEATURE_KEYS, build_features
from tda_labels import build_labels

# Published microscope result on this same 1838-event set (extended window),
# for the head-to-head. See memory: market-state-microscope-lane.
MICROSCOPE_BASELINE = {"real_effect": 0.609, "null_p95": 0.835,
                       "verdict": "INDISTINGUISHABLE_FROM_NULL"}


def parse_events_csv(path: Path) -> list[Event]:
    with path.open() as fh:
        return [Event(ts_ms=int(r["ts_ms"]), symbol=r["symbol"],
                      direction=int(r["direction"]))
                for r in csv.DictReader(fh)]


def write_csv(path: Path, rows: list[dict], header: list[str]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def run_study(pool, events: list[Event], timestamps: list[int],
              seed: int) -> dict:
    returns = log_return_matrix(pool, timestamps)
    features = build_features(returns, n_bars=len(timestamps))
    bar_labels = build_labels(features)
    # The label is market-level: one value per bar, broadcast to every symbol.
    labels = {sym: list(bar_labels) for sym in pool}
    outcomes = event_outcomes(pool, labels, timestamps, events)
    return {"features": features,
            "bar_labels": bar_labels,
            "outcomes": outcomes,
            "buckets": bucket_report(outcomes, seed=seed),
            "block_null": block_null_calibration(outcomes, bar_labels,
                                                 timestamps, seed=seed),
            "row_null": null_calibration(outcomes, seed=seed)}


def render_report(res: dict, n_events: int) -> str:
    outcomes = res["outcomes"]
    n_unlabeled = sum(1 for r in outcomes if r["label"] == UNLABELED)
    block, row = res["block_null"], res["row_null"]
    lines = [
        "# tda_topology_v1 -- correlation topology conditional study",
        "",
        "**NOT A GATE.** Descriptive instrument. No lockbox, no DSR ladder, "
        "no promotion path. A verdict here is about whether topology *sees* "
        "anything, not about whether anything is tradeable.",
        "",
        f"- events supplied: {n_events}",
        f"- events usable: {len(outcomes)}",
        f"- UNLABELED: {n_unlabeled}",
        f"- distinct bars: {len(set(r['ts_ms'] for r in outcomes))}",
        "",
        "## Verdict (primary: block-permutation null)",
        "",
        f"**{block['verdict']}** -- real effect {block['real_effect']} vs "
        f"null p95 {block['null_p95']} (beaten {block['pct_beaten']:.0%})",
        "",
        "## Secondary diagnostic: row-wise null",
        "",
        f"{row['verdict']} -- real effect {row['real_effect']} vs null p95 "
        f"{row['null_p95']}. The row null ignores the label series' "
        "autocorrelation and is therefore easier to beat; the gap between "
        "these two numbers is the reason the block null is primary.",
        "",
        "## Head-to-head: Market State Microscope, same 1838 events",
        "",
        f"| | real effect | null p95 | verdict |",
        f"|---|---:|---:|---|",
        f"| microscope 5-factor | {MICROSCOPE_BASELINE['real_effect']} | "
        f"{MICROSCOPE_BASELINE['null_p95']} | "
        f"{MICROSCOPE_BASELINE['verdict']} |",
        f"| tda block null | {block['real_effect']} | {block['null_p95']} | "
        f"{block['verdict']} |",
        "",
        "## Scope caveat",
        "",
        "All supplied events are **long-only** trend-breakout entries, so "
        "they fire mainly in UP-ish regimes: RANGE is thin and DOWN is "
        "absent. A negative verdict closes the geometric axis for long "
        "trend-breakout entries -- the same scope the microscope finding has. "
        "A long+short event source would be a different lane.",
        "",
        "## Buckets",
        "",
        "| label | n | verdict | " +
        " | ".join(f"fwd_r_{h} mean" for h in HORIZONS) + " |",
        "|---|---:|---|" + "---:|" * len(HORIZONS),
    ]
    for b in res["buckets"]:
        cells = [str(b.get(f"fwd_r_{h}_mean", "-")) for h in HORIZONS]
        lines.append(f"| {b['label']} | {b['n']} | {b['verdict']} | "
                     + " | ".join(cells) + " |")
    lines += ["",
              "Buckets below POWER_FLOOR=30 report their size and nothing "
              "else -- no direction, no CI."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tda_topology", description=__doc__)
    p.add_argument("--cache-dir", default="../../cache/matrix")
    p.add_argument("--events", required=True)
    p.add_argument("--out", default=".")
    p.add_argument("--seed", type=int, default=1)
    args = p.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    pool = load_pool_cache_only(args.cache_dir, UNIVERSE)
    timestamps = build_grid(pool)
    events = parse_events_csv(Path(args.events))
    res = run_study(pool, events, timestamps, seed=args.seed)

    write_csv(out_dir / "features.csv",
              [{"ts_ms": ts, **res["features"][t]}
               for t, ts in enumerate(timestamps)],
              ["ts_ms", *FEATURE_KEYS])
    write_csv(out_dir / "labels.csv",
              [{"ts_ms": ts, "label": res["bar_labels"][t]}
               for t, ts in enumerate(timestamps)],
              ["ts_ms", "label"])
    write_csv(out_dir / "outcomes.csv", res["outcomes"],
              ["symbol", "ts_ms", "direction", "label",
               *[f"fwd_r_{h}" for h in HORIZONS],
               "mfe_r", "mae_r", "stop_first", "fwd_vol"])
    text = render_report(res, n_events=len(events))
    (out_dir / "report.md").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd experiments/tda_topology && .venv/bin/pytest tests/test_pipeline.py -v`
Expected: 3 passed. If `test_iid_null_is_indistinguishable_from_null` fails, **stop**: the pipeline manufactures an effect from noise and every later number is void. Do not adjust the test to pass — debug the pipeline.

- [ ] **Step 5: Run the whole suite**

Run: `cd experiments/tda_topology && .venv/bin/pytest tests/ -v`
Expected: 37 passed (2 + 4 + 16 + 6 + 6 + 3).

- [ ] **Step 6: Confirm the main suite is untouched**

Run: `cd . && .venv/bin/python -m pytest -q 2>&1 | tail -3`
Expected: the pre-existing pass count, unchanged, with no collection of `experiments/` tests (`testpaths = ["tests"]` excludes them).

- [ ] **Step 7: Commit**

```bash
git add -f experiments/tda_topology/run.py experiments/tda_topology/tests/test_pipeline.py
git diff --cached --stat
git commit -m "feat(tda_topology): orchestrator, report, and iid null self-test"
```

---

### Task 7: The real run — HUMAN-GATED

Do not start this task without explicit human approval. Everything before it is code; this produces the verdict.

**Files:**
- Create: `experiments/tda_topology/report.md`, `features.csv`, `labels.csv`, `outcomes.csv`, `run.log` (all gitignored)
- Create: `experiments/tda_topology/RESULTS.md` (tracked)

**Interfaces:**
- Consumes: `run.main`.
- Produces: the verdict.

- [ ] **Step 1: Verify the inputs exist before spending time**

```bash
cd .
wc -l experiments/microscope/donchian_universe_events.csv   # expect 1839
ls cache/matrix/*_4h.csv | wc -l                            # expect >= 17
```
Expected: 1839 event rows (1838 events + header) and at least 17 cached candle files. If either is missing, stop — do not fetch, and do not run on a partial cross-section.

- [ ] **Step 2: Run it**

```bash
cd experiments/tda_topology
.venv/bin/python run.py \
    --cache-dir ../../cache/matrix \
    --events ../microscope/donchian_universe_events.csv \
    --out . --seed 1 2>&1 | tee run.log
```
Expected: minutes, not hours (Rips on a 17-point distance matrix is microseconds; `stack_path` did 16 assets in 100s). `report.md` written with a verdict.

- [ ] **Step 3: Write RESULTS.md**

Record, in this order: the verdict from the block null; the row-null number beside it; the head-to-head against the microscope's 0.609/0.835; the bucket table; the scope caveat; and the decision taken under spec §7. State the verdict once. Do not soften it, and do not add a "but if we tried W=30" paragraph — that is the parameter rescue the stop rule forbids.

- [ ] **Step 4: Commit**

```bash
git add -f experiments/tda_topology/RESULTS.md
git diff --cached --stat
git commit -m "result(tda_topology): <VERDICT> -- <one-line reason>"
```

- [ ] **Step 5: Close the loop**

If `INDISTINGUISHABLE_FROM_NULL`: add an entry to `docs/findings/BACKLOG.md` recording that the geometric axis from `docs/research-log/concepts/crypto_geometric_signal_research_ai_readable.md` is closed, with the mapping table from spec §1 so no future session reopens it under a new framing. Write the memory file. No v2, no window rescue.

If `EXCEEDS_NULL`: it is a hypothesis-generator only (spec §4.6). Stop and hand back to the human — a pre-registered lane on a fresh seal is a separate decision that also requires a ruling on the free-data terminal rule. The `euphoria-fade` precedent is the warning: the microscope's one replicated texture got its own pre-registered lane and closed negative.

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
|---|---|
| §3 architecture / quarantine | Task 1 |
| §3.1 cache-only loading, universe, loud failure | Task 2 |
| §3.2 features, W=60, causality, wasserstein gap rule | Task 3 |
| §3.3 expanding-median labels, BURN_IN, frozen thresholds | Task 4 |
| §3.4 verbatim reuse of microscope.events | Task 6 (`run_study`) |
| §3.5 block null primary + row null diagnostic | Task 5, reported in Task 6 |
| §3.6 outputs | Task 6 (`main`) |
| §4 honesty guardrails | Global Constraints; Task 6 report asserts NOT A GATE; Task 7 Step 3 |
| §5 data flow | Tasks 2→3→4→6 in order |
| §6 testing strategy | Tasks 1–6, every row of the spec's test table has a test |
| §7 stop rule | Task 7 Step 5 |
| §8 ripser risk + gudhi fallback | Task 1 Step 2, Task 3 Step 3 |
| §9 deliverable mapping | no task needed — it is a spec-level cross-reference |

**Placeholder scan:** none. Every code step carries complete code; the only free-text deliverable is `RESULTS.md` (Task 7 Step 3), which is prose by nature and has an explicit ordered content list.

**Type consistency:** `build_features(returns, n_bars, w, min_assets)` is called with `n_bars=len(timestamps)` in Task 6 and `n_bars=W+5` in Task 3 tests — consistent. `build_labels(features, burn_in)` returns `list[str]`, broadcast to `dict[str, list[str]]` in `run_study` — matching `event_outcomes(pool, labels, timestamps, events)`'s `labels[sym][t]` access. `block_null_calibration(outcomes, bar_labels, timestamps, seed, block, n_shuffles)` returns the same four keys as `null_calibration`, so `render_report` treats both uniformly. `UNLABELED` is imported from `microscope.regimes` in `tda_labels` rather than redefined, so `bucket_report`'s `row["label"] == UNLABELED` comparison matches.

**One deviation from spec §3 recorded:** the spec sketched three modules (`tda_features.py`, `tda_labels.py`, `run.py`); this plan uses five, splitting out `grid.py` and `nulls.py`. Each carries its own test cycle and a reviewer could reject one while approving its neighbour.
