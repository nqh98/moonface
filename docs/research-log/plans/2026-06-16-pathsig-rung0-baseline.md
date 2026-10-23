# Path Signal Rung-0 Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replay the ~16 already-screened signal families through the path-signal harness on real BTCUSDT 4h data, producing a per-signal dual-frame baseline table (the rung-0 floor) over purged/embargoed walk-forward folds with the lockbox tail sealed.

**Architecture:** Two new pure-consumer modules in `src/moonface/research/pathsig/`. `data.py` assembles the real BTC `Sample` grid through the existing (unchanged) `build_dataset` — sourcing HTF blocks by closed-bar resampling of the 4h series and the two cross-sectional rank features by point-in-time ranking against the 16-asset pool. `baseline.py` is the rung-0 driver: per fold it fits an empirical signal-frame `Distribution` from train-fold labels only, emits decisions on fired test bars via the existing `decide()`, and scores them with the existing dual-frame `evaluate_strategy()`. A `baseline` subcommand in `tools/path_signal.py` wires the real CSV readers and writes the results JSON.

**Tech Stack:** Python 3.11, standard library only (`statistics`, `math`, `bisect`, `time`), `pytest`, `ruff`. Reuses `moonface.research.pathsig.{dataset,features,htf,walkforward,policy,evaluate}`, `moonface.research.entries.generate_entries`, `moonface.research.bundle.DataBundle`, `moonface.research.multifamily_loader.default_readers`.

Design spec: `docs/research-log/specs/2026-06-16-pathsig-rung0-baseline-design.md`

---

## File Structure

- Create: `src/moonface/research/pathsig/data.py` — `resample_ohlc`, `cross_sectional_ranks`, internal `_trailing_return`/`_align_to_grid`, `build_btc_dataset`. Real-data → `Sample` grid.
- Create: `src/moonface/research/pathsig/baseline.py` — `_mirror`, `fit_distribution`, `replay_fired`, `replay_signal`, `run_baseline_to_doc`, frozen `SIGNALS`/`POOL_SYMBOLS`/`_METRICS_FIELD` + policy constants. The rung-0 driver.
- Modify: `tools/path_signal.py` — add the `baseline` subcommand.
- Test: `tests/test_pathsig_data.py`, `tests/test_pathsig_baseline.py`, `tests/test_pathsig_baseline_cli.py`.
- Generated (force-add, gitignore convention): `experiments/path_signal/rung0_baseline.json`.

Tests are flat (repo convention) and read in isolation; the synthetic-reader helper is defined inline in each test file that needs it.

---

## Task 1: HTF closed-bar resampling

**Files:**
- Create: `src/moonface/research/pathsig/data.py`
- Test: `tests/test_pathsig_data.py`

`resample_ohlc` aggregates a fine series (4h) into a coarse series (1d/1w). Only **complete** groups are emitted: a group with fewer than `group_dur_ms // base_dur_ms` sub-bars is still forming and is dropped, so a resampled bar's `timestamp_ms + group_dur_ms` close time is real (no lookahead when later consumed by `align_htf_index`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_data.py
from moonface.models import Candle
from moonface.research.pathsig.data import resample_ohlc

H4 = 14_400_000
D1 = 86_400_000


def _bars(n, dur, start=0, base=100.0):
    return [Candle(timestamp_ms=start + i * dur, open=base + i,
                   high=base + i + 0.5, low=base + i - 0.5,
                   close=base + i, volume=1.0) for i in range(n)]


def test_resample_aggregates_complete_groups_only():
    base = _bars(13, H4)          # 13 4h bars: 2 full days (12) + 1 leftover
    daily = resample_ohlc(base, D1, H4)
    assert len(daily) == 2                      # the 13th bar's group is incomplete
    assert daily[0].timestamp_ms == 0
    assert daily[1].timestamp_ms == D1
    # closed-bar OHLC over the first 6 4h bars (indices 0..5)
    assert daily[0].open == base[0].open
    assert daily[0].close == base[5].close
    assert daily[0].high == max(b.high for b in base[:6])
    assert daily[0].low == min(b.low for b in base[:6])
    assert daily[0].volume == sum(b.volume for b in base[:6])


def test_resample_empty_input_returns_empty():
    assert resample_ohlc([], D1, H4) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_data.py -v`
Expected: FAIL (module `data` not found).

- [ ] **Step 3: Write the implementation**

Create `src/moonface/research/pathsig/data.py`:

```python
"""Real-data assembly for the path-signal rung-0 baseline.

Builds the BTC Sample grid through the existing build_dataset: HTF (1d/1w)
blocks come from closed-bar resampling of the 4h series, and the two
cross-sectional rank features come from point-in-time ranking against the
16-asset pool. Readers are injectable so tests run with no network or disk."""
from __future__ import annotations

from moonface.models import Candle
from moonface.research.bundle import DataBundle
from moonface.research.pathsig.dataset import build_dataset

H4_MS = 14_400_000
D1_MS = 86_400_000
W1_MS = 604_800_000


def resample_ohlc(candles: list[Candle], group_dur_ms: int,
                  base_dur_ms: int) -> list[Candle]:
    """Aggregate fine bars into coarse bars. Only complete groups (with the
    full expected sub-bar count) are emitted, so the coarse bar is truly
    closed at group start + group_dur_ms."""
    if not candles or group_dur_ms <= 0 or base_dur_ms <= 0:
        return []
    expected = group_dur_ms // base_dur_ms
    groups: dict[int, list[Candle]] = {}
    for c in candles:
        key = (c.timestamp_ms // group_dur_ms) * group_dur_ms
        groups.setdefault(key, []).append(c)
    out: list[Candle] = []
    for key in sorted(groups):
        bars = groups[key]
        if len(bars) < expected:
            continue
        out.append(Candle(
            timestamp_ms=key,
            open=bars[0].open,
            high=max(b.high for b in bars),
            low=min(b.low for b in bars),
            close=bars[-1].close,
            volume=sum(b.volume for b in bars)))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_data.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/data.py tests/test_pathsig_data.py
git commit -m "feat(pathsig): closed-bar HTF resampling"
```

---

## Task 2: Cross-sectional ranks

**Files:**
- Modify: `src/moonface/research/pathsig/data.py`
- Test: `tests/test_pathsig_data.py`

`cross_sectional_ranks` computes, per bar, BTC's percentile rank within the pool peers present at that bar. `_trailing_return` and `_align_to_grid` are the point-in-time helpers that feed it.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pathsig_data.py`:

```python
from moonface.research.pathsig.data import (cross_sectional_ranks,
                                            _trailing_return, _align_to_grid)


def test_trailing_return_is_point_in_time():
    bars = _bars(5, H4, base=100.0)   # closes 100,101,102,103,104
    rets = _trailing_return(bars, 1)
    assert rets[0] is None
    assert rets[1] == 101.0 / 100.0 - 1.0


def test_align_to_grid_maps_by_timestamp():
    grid = [0, H4, 2 * H4]
    series = _bars(2, H4)             # timestamps 0, H4
    vals = [10.0, 20.0]
    aligned = _align_to_grid(grid, series, vals)
    assert aligned == [10.0, 20.0, None]


def test_rank_position_and_degenerate_bar():
    # bar 0: BTC=5 beats both peers -> 1.0 ; bar 1: BTC below both -> 0.0
    btc = [5.0, 1.0]
    peers = [[1.0, 9.0], [2.0, 8.0]]
    ranks = cross_sectional_ranks(btc, peers)
    assert ranks == [1.0, 0.0]


def test_rank_is_half_with_no_peers_or_missing_value():
    assert cross_sectional_ranks([5.0], [[None]]) == [0.5]   # no peers present
    assert cross_sectional_ranks([None], [[1.0]]) == [0.5]   # BTC value missing
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_data.py -v`
Expected: FAIL (`cross_sectional_ranks` not defined).

- [ ] **Step 3: Write the implementation**

Append to `src/moonface/research/pathsig/data.py`:

```python
def _trailing_return(candles: list[Candle], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(candles)
    for i in range(len(candles)):
        if i - n >= 0 and candles[i - n].close > 0:
            out[i] = candles[i].close / candles[i - n].close - 1.0
    return out


def _align_to_grid(grid_ts: list[int], series: list[Candle],
                   values: list[float | None]) -> list[float | None]:
    by_ts = {c.timestamp_ms: v for c, v in zip(series, values)}
    return [by_ts.get(ts) for ts in grid_ts]


def cross_sectional_ranks(btc_values: list[float | None],
                          pool_values: list[list[float | None]]
                          ) -> list[float]:
    """Per-bar percentile rank of BTC's value among the peers present at that
    bar (fraction of peers strictly below BTC). 0.5 when BTC's value is missing
    or no peer is present, so the feature is never None for a price-complete
    bar."""
    out: list[float] = []
    for i in range(len(btc_values)):
        b = btc_values[i]
        peers = [pv[i] for pv in pool_values if pv[i] is not None]
        if b is None or not peers:
            out.append(0.5)
            continue
        out.append(sum(1 for v in peers if v < b) / len(peers))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_data.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/data.py tests/test_pathsig_data.py
git commit -m "feat(pathsig): point-in-time cross-sectional ranks"
```

---

## Task 3: Real BTC dataset assembler

**Files:**
- Modify: `src/moonface/research/pathsig/data.py`
- Test: `tests/test_pathsig_data.py`

`build_btc_dataset` ties Tasks 1–2 to the existing `build_dataset`: it loads BTC's bundle and the pool via injectable readers, derives HTF by resampling, computes the two rank series, and returns the BTC `DataBundle` plus the `Sample` list.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pathsig_data.py`:

```python
from moonface.research.pathsig.data import build_btc_dataset
from moonface.research.pathsig.features import FEATURE_NAMES


def _synthetic_readers(n=500):
    # BTC + two peers, all on the same 4h grid; rising metrics so oi_z is defined.
    def candles(sym, tf):
        base = {"BTCUSDT": 100.0, "ETHUSDT": 50.0, "SOLUSDT": 20.0}.get(sym)
        if base is None:
            return []
        return [Candle(timestamp_ms=i * H4, open=base + i * 0.5,
                       high=(base + i * 0.5) * 1.01, low=(base + i * 0.5) * 0.99,
                       close=base + i * 0.5, volume=1.0) for i in range(n)]

    def funding(sym):
        return [0.0001] * n if candles(sym, "4h") else None

    def metrics(sym, field):
        return [1000.0 + i for i in range(n)] if sym == "BTCUSDT" else None

    def bookdepth(sym):
        return None

    return {"candles": candles, "funding": funding,
            "metrics": metrics, "bookdepth": bookdepth}


def test_build_btc_dataset_yields_complete_samples():
    readers = _synthetic_readers(500)
    bundle, samples = build_btc_dataset(readers, h=6, atr_period=14,
                                        pool_symbols=["ETHUSDT", "SOLUSDT"])
    assert len(bundle.candles) == 500
    assert len(samples) > 50
    s = samples[0]
    assert len(s.x) == len(FEATURE_NAMES)
    assert all(v is not None for v in s.x)
    assert max(t.index for t in samples) < 500 - 6   # horizon excluded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_data.py -v`
Expected: FAIL (`build_btc_dataset` not defined).

- [ ] **Step 3: Write the implementation**

Append to `src/moonface/research/pathsig/data.py` (the `Sample` type comes from `build_dataset`'s return; no new import needed beyond what is shown):

```python
def build_btc_dataset(readers: dict, h: int, atr_period: int,
                      pool_symbols: list[str], *, deploy: str = "BTCUSDT",
                      metrics_field: str = "sum_open_interest",
                      xs_lookback: int = 24):
    """Assemble the real BTC Sample grid. `readers` is a dict of
    candles/funding/metrics/bookdepth callables (see
    multifamily_loader.default_readers). Returns (btc_bundle, samples)."""
    candles_r = readers["candles"]
    funding_r = readers["funding"]
    metrics_r = readers["metrics"]
    bookdepth_r = readers["bookdepth"]

    btc = candles_r(deploy, "4h")
    if not btc:
        raise ValueError(f"no candles for {deploy}")
    bundle = DataBundle(candles=btc, funding=funding_r(deploy),
                        feature=metrics_r(deploy, metrics_field),
                        bookdepth=bookdepth_r(deploy))

    d1 = resample_ohlc(btc, D1_MS, H4_MS)
    w1 = resample_ohlc(btc, W1_MS, H4_MS)

    grid = [c.timestamp_ms for c in btc]
    peer_ret: list[list[float | None]] = []
    peer_fund: list[list[float | None]] = []
    for sym in pool_symbols:
        pc = candles_r(sym, "4h")
        if not pc:
            continue
        peer_ret.append(_align_to_grid(grid, pc, _trailing_return(pc, xs_lookback)))
        pf = funding_r(sym)
        if pf is not None:
            peer_fund.append(_align_to_grid(grid, pc, pf))

    xs_ret_rank = cross_sectional_ranks(_trailing_return(btc, xs_lookback), peer_ret)
    btc_fund = bundle.funding or [None] * len(btc)
    xs_funding_rank = cross_sectional_ranks(btc_fund, peer_fund)

    samples = build_dataset(bundle, h=h, atr_period=atr_period,
                            xs_ret_rank=xs_ret_rank,
                            xs_funding_rank=xs_funding_rank,
                            d1_candles=d1, w1_candles=w1)
    return bundle, samples
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_data.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/data.py tests/test_pathsig_data.py
git commit -m "feat(pathsig): real BTC dataset assembler"
```

---

## Task 4: Empirical signal-frame distribution fit

**Files:**
- Create: `src/moonface/research/pathsig/baseline.py`
- Test: `tests/test_pathsig_baseline.py`

`_mirror` reframes a stored LONG-frame label into the signal's own direction; `fit_distribution` averages the mirrored labels over the fired training samples into a `Distribution`. This is the only "learning" at rung 0, and it touches train-fold labels only.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_baseline.py
from moonface.research.pathsig.baseline import _mirror, fit_distribution
from moonface.research.pathsig.dataset import Sample
from moonface.research.pathsig.labels import PathLabel


def _sample(index, label):
    return Sample(index=index, timestamp_ms=index, x=[0.0] * 16, label=label)


def test_mirror_short_flips_frame():
    lbl = PathLabel(ret_r=1.5, mae_r=-0.8, mfe_r=2.0)
    assert _mirror(lbl, "LONG") == lbl
    m = _mirror(lbl, "SHORT")
    assert m.ret_r == -1.5
    assert m.mae_r == -2.0   # was mfe (>=0) -> negated
    assert m.mfe_r == 0.8    # was mae (<=0) -> negated


def test_fit_distribution_is_train_mean():
    samples = [_sample(0, PathLabel(2.0, -1.0, 3.0)),
               _sample(1, PathLabel(-1.0, -2.0, 1.0)),
               _sample(2, PathLabel(0.0, 0.0, 0.0))]   # not fired
    fire = {0: "LONG", 1: "LONG"}
    dist = fit_distribution(samples, fire, [0, 1, 2], min_events=2)
    assert dist.exp_ret_r == 0.5            # mean of 2.0, -1.0
    assert dist.exp_mae_r == -1.5
    assert dist.exp_mfe_r == 2.0
    assert dist.p_up == 0.5                 # one of two has ret_r > 0


def test_fit_distribution_too_few_returns_none():
    samples = [_sample(0, PathLabel(2.0, -1.0, 3.0))]
    assert fit_distribution(samples, {0: "LONG"}, [0], min_events=2) is None


def test_fit_distribution_ignores_non_train_labels():
    # changing a label outside the train positions must not change the fit
    samples = [_sample(0, PathLabel(2.0, -1.0, 3.0)),
               _sample(1, PathLabel(99.0, -99.0, 99.0))]
    fire = {0: "LONG", 1: "LONG"}
    dist = fit_distribution(samples, fire, [0], min_events=1)
    assert dist.exp_ret_r == 2.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_baseline.py -v`
Expected: FAIL (module `baseline` not found).

- [ ] **Step 3: Write the implementation**

Create `src/moonface/research/pathsig/baseline.py`:

```python
"""Rung-0 baseline: replay existing signal families through the path-signal
harness on the real BTC Sample grid.

Per fold, an empirical signal-frame Distribution is fitted from train-fold
labels only, then applied to fired test bars via the shared decide() policy and
scored by the shared dual-frame evaluate_strategy(). Everything is kept in the
signal's own direction by mirroring SHORT labels, so decide()'s LONG means
"go with the signal" and the LONG-frame realized R stays correct. Design frozen
in docs/research-log/specs/2026-06-16-pathsig-rung0-baseline-design.md."""
from __future__ import annotations

from statistics import fmean

from moonface.research.entries import UnknownEntryFamily, generate_entries
from moonface.research.pathsig.dataset import Sample
from moonface.research.pathsig.evaluate import evaluate_strategy
from moonface.research.pathsig.features import FEATURE_NAMES
from moonface.research.pathsig.labels import PathLabel
from moonface.research.pathsig.policy import Distribution, decide
from moonface.research.pathsig.walkforward import Fold


def _mirror(label: PathLabel, side: str) -> PathLabel:
    """Reframe a LONG-frame label into the signal's own direction. For SHORT
    the adverse/favourable excursions swap and negate (mae stays <=0, mfe >=0)."""
    if side == "SHORT":
        return PathLabel(ret_r=-label.ret_r, mae_r=-label.mfe_r,
                         mfe_r=-label.mae_r)
    return label


def fit_distribution(samples: list[Sample], fire: dict[int, str],
                     positions: list[int], min_events: int
                     ) -> Distribution | None:
    """Mean signal-frame distribution over fired samples at `positions`
    (sample positions, not candle indices). None if fewer than min_events."""
    obs: list[PathLabel] = []
    for pos in positions:
        s = samples[pos]
        side = fire.get(s.index)
        if side is not None:
            obs.append(_mirror(s.label, side))
    if len(obs) < min_events:
        return None
    n = len(obs)
    return Distribution(
        p_up=sum(1 for lbl in obs if lbl.ret_r > 0) / n,
        exp_ret_r=fmean(lbl.ret_r for lbl in obs),
        exp_mae_r=fmean(lbl.mae_r for lbl in obs),
        exp_mfe_r=fmean(lbl.mfe_r for lbl in obs))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_baseline.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/baseline.py tests/test_pathsig_baseline.py
git commit -m "feat(pathsig): empirical signal-frame distribution fit"
```

---

## Task 5: Per-signal replay driver

**Files:**
- Modify: `src/moonface/research/pathsig/baseline.py`
- Test: `tests/test_pathsig_baseline.py`

`replay_fired` runs the fold loop over a known fire-map and returns a dual-frame result; `replay_signal` resolves the fire-map from a family via `generate_entries` (reporting `no_data` when the bundle lacks the family's series). The frozen `SIGNALS`/`POOL_SYMBOLS`/`_METRICS_FIELD` lists and policy constants are added here.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pathsig_baseline.py`:

```python
from moonface.research.bundle import DataBundle
from moonface.research.pathsig.baseline import replay_fired, replay_signal
from moonface.research.pathsig.walkforward import Fold


def _wall_samples(n=60):
    # positive drift but large adverse excursion -> the structural wall
    out = []
    for i in range(n):
        x = [0.0] * 16
        x[FEATURE_NAMES.index("atr_frac")] = 0.02
        out.append(_sample(i, PathLabel(ret_r=0.3, mae_r=-2.0, mfe_r=0.5)))
        out[-1] = Sample(index=i, timestamp_ms=i, x=x, label=out[-1].label)
    return out


def test_replay_fired_reports_both_frames():
    samples = _wall_samples(60)
    fire = {i: "LONG" for i in range(60)}
    folds = [Fold(train_idx=list(range(0, 30)), test_idx=list(range(30, 48)))]
    res = replay_fired(fire, samples, folds, h=6, edge_threshold=0.05,
                       kelly_scale=0.02, max_fraction=0.02, taker_bps=5.0,
                       slippage_bps=2.0, min_events=10, n_trials=16,
                       drawdown_cap_r=15.0)
    assert res["status"] == "ok"
    assert "risk_adjusted" in res and "fixed_cap" in res
    assert res["n_trades"] >= 0
    assert isinstance(res["fixed_cap"]["within_cap"], bool)


def test_replay_fired_too_few_events():
    samples = _wall_samples(60)
    fire = {0: "LONG"}   # only one fired bar, below min_events
    folds = [Fold(train_idx=list(range(0, 30)), test_idx=list(range(30, 48)))]
    res = replay_fired(fire, samples, folds, h=6, edge_threshold=0.05,
                       kelly_scale=0.02, max_fraction=0.02, taker_bps=5.0,
                       slippage_bps=2.0, min_events=10, n_trials=16,
                       drawdown_cap_r=15.0)
    assert res["status"] == "too_few_events"


def test_replay_signal_reports_no_data_when_series_missing():
    samples = _wall_samples(60)
    folds = [Fold(train_idx=list(range(0, 30)), test_idx=list(range(30, 48)))]
    bundle = DataBundle(candles=[], funding=None)   # funding_fade needs funding
    res = replay_signal("funding_fade", {"window": 60, "z_thr": 1.5}, bundle,
                        samples, folds, h=6, edge_threshold=0.05,
                        kelly_scale=0.02, max_fraction=0.02, taker_bps=5.0,
                        slippage_bps=2.0, min_events=10, n_trials=16,
                        drawdown_cap_r=15.0)
    assert res["status"] == "no_data"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_baseline.py -v`
Expected: FAIL (`replay_fired`/`replay_signal` not defined).

- [ ] **Step 3: Write the implementation**

Append to `src/moonface/research/pathsig/baseline.py`:

```python
# Uniform rung-0 policy constants (no per-signal tuning — that is rung 2's job).
EDGE_THRESHOLD = 0.15
KELLY_SCALE = 0.02
MAX_FRACTION = 0.02
TAKER_BPS = 5.0
SLIPPAGE_BPS = 2.0
MIN_FIT_EVENTS = 10
DRAWDOWN_CAP_R = 15.0

# The 16-asset 4h pool (cross-sectional inputs only; BTC is the deploy target).
POOL_SYMBOLS = ["1000PEPEUSDT", "PEOPLEUSDT", "DOGEUSDT", "BNBUSDT",
                "1000SHIBUSDT", "1000FLOKIUSDT", "XRPUSDT", "LINKUSDT",
                "HIGHUSDT", "NEARUSDT", "JASMYUSDT", "TRBUSDT", "FILUSDT",
                "ARBUSDT", "AVAXUSDT", "ETCUSDT"]

# Metrics field each positioning family needs on the bundle for generate_entries.
_METRICS_FIELD = {
    "oi_build_momentum": "sum_open_interest",
    "oi_flush_reversal": "sum_open_interest",
    "toptrader_follow": "sum_toptrader_long_short_ratio",
    "taker_flow_momentum": "sum_taker_long_short_vol_ratio",
}

# The frozen signal/param set replayed as the baseline (price + funding +
# positioning + orderbook). Horizon-independent; the label horizon is set per run.
SIGNALS = [
    {"family": "donchian_break", "params": {"n": 100}},
    {"family": "donchian_break", "params": {"n": 55}},
    {"family": "atr_channel_break", "params": {"k": 1.5, "atr_period": 14}},
    {"family": "atr_channel_break", "params": {"k": 2.0, "atr_period": 14}},
    {"family": "ma_cross", "params": {"fast": 50, "slow": 200}},
    {"family": "roc_sign", "params": {"period": 24}},
    {"family": "price_vs_ma", "params": {"period": 100}},
    {"family": "funding_fade", "params": {"window": 60, "z_thr": 1.5}},
    {"family": "funding_confirm", "params": {"persist": 6, "lvl": 0.0003}},
    {"family": "funding_flip", "params": {"debounce": 6}},
    {"family": "oi_build_momentum", "params": {"window": 180, "lookback": 6, "z_thr": 1.5}},
    {"family": "oi_flush_reversal", "params": {"window": 180, "lookback": 6, "z_thr": 1.5}},
    {"family": "toptrader_follow", "params": {"window": 180, "z_thr": 1.5}},
    {"family": "taker_flow_momentum", "params": {"window": 180, "z_thr": 1.5}},
    {"family": "ob_imbalance_follow", "params": {"window": 180, "z_thr": 1.5}},
    {"family": "ob_imbalance_follow", "params": {"window": 180, "z_thr": 2.0}},
]


def replay_fired(fire: dict[int, str], samples: list[Sample],
                 folds: list[Fold], *, h: int, edge_threshold: float,
                 kelly_scale: float, max_fraction: float, taker_bps: float,
                 slippage_bps: float, min_events: int, n_trials: int,
                 drawdown_cap_r: float) -> dict:
    """Fold loop over a known fire-map. Per fold: fit on train, decide on fired
    test bars, then score the concatenated stream under both risk frames."""
    atr_idx = FEATURE_NAMES.index("atr_frac")
    decisions, labels, atr_fracs, fundings = [], [], [], []
    used_folds = 0
    for fold in folds:
        dist = fit_distribution(samples, fire, fold.train_idx, min_events)
        if dist is None:
            continue
        used_folds += 1
        for pos in fold.test_idx:
            s = samples[pos]
            side = fire.get(s.index)
            if side is None:
                continue
            decisions.append(decide(dist, edge_threshold, kelly_scale,
                                    max_fraction))
            labels.append(_mirror(s.label, side))
            atr_fracs.append(s.x[atr_idx])
            fundings.append(0.0)

    if not decisions:
        return {"status": "too_few_events", "n_events": len(fire),
                "used_folds": used_folds}
    res = evaluate_strategy(decisions, labels, atr_fracs, fundings,
                            taker_bps=taker_bps, slippage_bps=slippage_bps,
                            n_trials=n_trials, trial_srs=[],
                            drawdown_cap_r=drawdown_cap_r)
    n_trades = sum(1 for d in decisions if d.action != "WAIT")
    return {"status": "ok", "n_events": len(fire), "n_trades": n_trades,
            "used_folds": used_folds, **res}


def replay_signal(family: str, params: dict, bundle, samples: list[Sample],
                  folds: list[Fold], *, h: int, **kw) -> dict:
    """Resolve the fire-map from the family, then replay it. Reports no_data
    when the bundle lacks the family's required series."""
    head = {"family": family, "params": params, "h": h}
    try:
        events = generate_entries(family, params, bundle)
    except (ValueError, UnknownEntryFamily):
        return {**head, "status": "no_data"}
    fire = {i: side for i, side in events}
    return {**head, **replay_fired(fire, samples, folds, h=h, **kw)}
```

Note: `replay_fired` sets `fundings` to `0.0` because the funding accrual over the hold is not part of the rung-0 R label (kept comparable to the original screens, which scored gross-of-funding path R); taker + slippage costs are still applied. The cost model's `funding_r` argument therefore receives 0.0.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_baseline.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/baseline.py tests/test_pathsig_baseline.py
git commit -m "feat(pathsig): per-signal rung-0 replay driver"
```

---

## Task 6: Baseline run document

**Files:**
- Modify: `src/moonface/research/pathsig/baseline.py`
- Test: `tests/test_pathsig_baseline.py`

`run_baseline_to_doc` is the offline-testable entry point: given readers, it builds the BTC Sample grid + folds per horizon, replays every signal (swapping in each positioning family's metrics field), and returns the full results document (config + sorted rows).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pathsig_baseline.py`:

```python
from moonface.models import Candle
from moonface.research.pathsig.baseline import run_baseline_to_doc

H4 = 14_400_000


def _readers(n=500):
    def candles(sym, tf):
        base = {"BTCUSDT": 100.0, "ETHUSDT": 50.0, "SOLUSDT": 20.0}.get(sym)
        if base is None:
            return []
        return [Candle(timestamp_ms=i * H4, open=base + i * 0.5,
                       high=(base + i * 0.5) * 1.01, low=(base + i * 0.5) * 0.99,
                       close=base + i * 0.5, volume=1.0) for i in range(n)]

    def funding(sym):
        return [0.0001] * n if candles(sym, "4h") else None

    def metrics(sym, field):
        return [1000.0 + i for i in range(n)] if sym == "BTCUSDT" else None

    def bookdepth(sym):
        return None

    return {"candles": candles, "funding": funding,
            "metrics": metrics, "bookdepth": bookdepth}


def test_run_baseline_to_doc_schema_and_statuses():
    doc = run_baseline_to_doc(_readers(500), n_folds=2, horizons=[6],
                              pool_symbols=["ETHUSDT", "SOLUSDT"])
    assert doc["config"]["horizons"] == [6]
    assert doc["config"]["n_trials"] == len(doc["rows"])
    statuses = {r["status"] for r in doc["rows"]}
    assert statuses <= {"ok", "no_data", "too_few_events"}
    # bookdepth is None -> the two ob_imbalance_follow rows must be no_data
    ob = [r for r in doc["rows"] if r["family"] == "ob_imbalance_follow"]
    assert ob and all(r["status"] == "no_data" for r in ob)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_baseline.py -v`
Expected: FAIL (`run_baseline_to_doc` not defined).

- [ ] **Step 3: Write the implementation**

Append to `src/moonface/research/pathsig/baseline.py` (add `from moonface.research.bundle import DataBundle`, `from moonface.research.pathsig.data import build_btc_dataset`, and `from moonface.research.pathsig.walkforward import walk_forward_folds` to the imports at the top of the file):

```python
LOCKBOX_FRACTION = 0.2
ATR_PERIOD = 14


def run_baseline_to_doc(readers: dict, *, n_folds: int, horizons: list[int],
                        pool_symbols: list[str] = POOL_SYMBOLS,
                        deploy: str = "BTCUSDT") -> dict:
    """Build the full rung-0 results document from injectable readers (offline
    testable). One row per signal x horizon, sorted by fixed-cap total_r."""
    n_trials = len(SIGNALS) * len(horizons)
    policy = dict(edge_threshold=EDGE_THRESHOLD, kelly_scale=KELLY_SCALE,
                  max_fraction=MAX_FRACTION, taker_bps=TAKER_BPS,
                  slippage_bps=SLIPPAGE_BPS, min_events=MIN_FIT_EVENTS,
                  n_trials=n_trials, drawdown_cap_r=DRAWDOWN_CAP_R)
    rows: list[dict] = []
    for h in horizons:
        base, samples = build_btc_dataset(readers, h=h, atr_period=ATR_PERIOD,
                                          pool_symbols=pool_symbols,
                                          deploy=deploy)
        folds = walk_forward_folds(len(samples), n_folds=n_folds, embargo=h,
                                   lockbox_fraction=LOCKBOX_FRACTION)
        for spec in SIGNALS:
            family, params = spec["family"], spec["params"]
            field = _METRICS_FIELD.get(family, "sum_open_interest")
            bundle = DataBundle(candles=base.candles, funding=base.funding,
                                feature=readers["metrics"](deploy, field),
                                bookdepth=base.bookdepth)
            rows.append(replay_signal(family, params, bundle, samples, folds,
                                      h=h, **policy))

    rows.sort(key=lambda r: r.get("fixed_cap", {}).get("total_r", float("-inf")),
              reverse=True)
    return {
        "config": {
            "deploy": deploy, "horizons": horizons, "n_folds": n_folds,
            "lockbox_fraction": LOCKBOX_FRACTION, "atr_period": ATR_PERIOD,
            "n_trials": n_trials, "edge_threshold": EDGE_THRESHOLD,
            "kelly_scale": KELLY_SCALE, "max_fraction": MAX_FRACTION,
            "taker_bps": TAKER_BPS, "slippage_bps": SLIPPAGE_BPS,
            "min_fit_events": MIN_FIT_EVENTS, "drawdown_cap_r": DRAWDOWN_CAP_R,
            "pool_symbols": pool_symbols,
        },
        "rows": rows,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_baseline.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/pathsig/baseline.py tests/test_pathsig_baseline.py
git commit -m "feat(pathsig): rung-0 baseline run document"
```

---

## Task 7: `baseline` CLI subcommand

**Files:**
- Modify: `tools/path_signal.py`
- Test: `tests/test_pathsig_baseline_cli.py`

The subcommand wires the real CSV readers and writes the document. A `readers` injection point keeps the test offline.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pathsig_baseline_cli.py
import json
import sys
from pathlib import Path

from moonface.models import Candle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import path_signal  # noqa: E402

H4 = 14_400_000


def _readers(n=500):
    def candles(sym, tf):
        base = {"BTCUSDT": 100.0, "ETHUSDT": 50.0}.get(sym)
        if base is None:
            return []
        return [Candle(timestamp_ms=i * H4, open=base + i * 0.5,
                       high=(base + i * 0.5) * 1.01, low=(base + i * 0.5) * 0.99,
                       close=base + i * 0.5, volume=1.0) for i in range(n)]

    def funding(sym):
        return [0.0001] * n if candles(sym, "4h") else None

    def metrics(sym, field):
        return [1000.0 + i for i in range(n)] if sym == "BTCUSDT" else None

    def bookdepth(sym):
        return None

    return {"candles": candles, "funding": funding,
            "metrics": metrics, "bookdepth": bookdepth}


def test_baseline_writes_results_json(tmp_path):
    out = tmp_path / "rung0.json"
    path_signal.baseline(str(out), cache_dir=".backtest_cache", n_folds=2,
                         horizons=[6], readers=_readers(500),
                         pool_symbols=["ETHUSDT"])
    doc = json.loads(out.read_text())
    assert doc["config"]["horizons"] == [6]
    assert doc["rows"]
    assert {"family", "params", "h", "status"} <= set(doc["rows"][0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pathsig_baseline_cli.py -v`
Expected: FAIL (`path_signal.baseline` not defined).

- [ ] **Step 3: Write the implementation**

In `tools/path_signal.py`, add the `baseline` function after `register` and wire its subparser in `main`. Insert this function:

```python
def baseline(out_path: str, cache_dir: str, n_folds: int,
             horizons: list[int], readers=None,
             pool_symbols=None) -> None:
    import time

    from moonface.research.pathsig.baseline import (POOL_SYMBOLS,
                                                    run_baseline_to_doc)

    if readers is None:
        from moonface.research.multifamily_loader import default_readers
        end_ms = int(time.time() * 1000)
        start_ms = end_ms - int(3 * 365 * 86_400_000)
        readers = default_readers(cache_dir, start_ms, end_ms)
    doc = run_baseline_to_doc(readers, n_folds=n_folds, horizons=horizons,
                              pool_symbols=pool_symbols or POOL_SYMBOLS)
    Path(out_path).write_text(json.dumps(doc, indent=2))
    ok = [r for r in doc["rows"] if r["status"] == "ok"]
    print(f"wrote {out_path}: {len(doc['rows'])} rows, {len(ok)} scored")
    for r in sorted(ok, key=lambda r: r["fixed_cap"]["total_r"],
                    reverse=True)[:5]:
        fc = r["fixed_cap"]
        print(f"  {r['family']:<20} h={r['h']} total_r={fc['total_r']:+.2f} "
              f"maxdd_r={fc['max_drawdown_r']:+.2f} cap_ok={fc['within_cap']}")
```

Then update `main` to register the subcommand and dispatch it. Replace the body of `main` with:

```python
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    reg = sub.add_parser("register", help="freeze the design")
    reg.add_argument("--out", default="experiments/path_signal/registration.json")
    bl = sub.add_parser("baseline", help="run the rung-0 signal replay")
    bl.add_argument("--out", default="experiments/path_signal/rung0_baseline.json")
    bl.add_argument("--cache-dir", default=".backtest_cache")
    bl.add_argument("--n-folds", type=int, default=5)
    bl.add_argument("--horizons", type=int, nargs="+", default=[6, 12])
    args = parser.parse_args(argv)
    if args.cmd == "register":
        register(args.out)
        return 0
    if args.cmd == "baseline":
        baseline(args.out, args.cache_dir, args.n_folds, args.horizons)
        return 0
    return 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pathsig_baseline_cli.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add tools/path_signal.py tests/test_pathsig_baseline_cli.py
git commit -m "feat(pathsig): baseline CLI subcommand"
```

---

## Task 8: Generate the artifact + full verification

**Files:**
- Generated: `experiments/path_signal/rung0_baseline.json`

- [ ] **Step 1: Run the whole suite + lint**

Run: `python -m pytest tests/ -q && ruff check src/moonface/research/pathsig tools/path_signal.py`
Expected: all tests PASS, ruff reports no issues.

- [ ] **Step 2: Generate the real baseline over the cached data**

Run: `python tools/path_signal.py baseline --out experiments/path_signal/rung0_baseline.json --n-folds 5 --horizons 6 12`
Expected: writes the JSON and prints a top-5 table. Sanity-read the output against the spec's §0/§9 premise — drift-bearing signals (e.g. `funding_fade`, `donchian_break`) should show positive `total_r` paired with a large adverse `max_drawdown_r` and/or `within_cap=false` (the structural wall reproduced). **Any signal clearing the −15R cap with a high DSR is a red flag to investigate before trusting the harness, not a result.**

- [ ] **Step 3: Commit the artifact (force-add — experiments specs are tracked despite global gitignore)**

```bash
git add -f experiments/path_signal/rung0_baseline.json
git commit -m "chore(pathsig): rung-0 baseline results artifact"
```

---

## Self-Review

**Spec coverage** (against `docs/research-log/specs/2026-06-16-pathsig-rung0-baseline-design.md`):
- §2 frozen 16-signal set + program horizons {6,12} → Task 5 `SIGNALS`, Task 6/7 horizon loop. ✅
- §3 two pure-consumer modules, no frozen interface changed → Tasks 1–6 only consume `build_dataset`/`decide`/`evaluate_strategy`/`walk_forward_folds`. ✅
- §4 real-data loader: injectable readers, HTF by resampling, point-in-time xs ranks, Sample-grid drops → Tasks 1–3. ✅
- §5 per-fold empirical fit (train-only), SHORT mirroring, decide→evaluate, uniform policy constants, metrics-field swap, n_trials = signals×horizons → Tasks 4–6. ✅
- §6 `baseline` CLI + JSON schema (config + rows w/ status) + stdout table → Task 7. ✅
- §7 leakage controls (purge/embargo via folds, train-only fit, lockbox excluded by `walk_forward_folds`, costs on sized strategy) → Tasks 5–6 + leak-guard test in Task 4. ✅
- §9 descriptive interpretation + red-flag check → Task 8 Step 2. ✅
- §10 out of scope (no ensemble/model/lockbox-open/tuning) → none of the tasks add these. ✅

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command states expected output. ✅

**Type consistency:** `Distribution`/`Decision`/`PathLabel`/`Sample`/`Fold` used exactly as defined by the foundations modules; `fit_distribution`→`replay_fired`→`replay_signal`→`run_baseline_to_doc`→`baseline` form a consistent call chain; `_METRICS_FIELD`/`SIGNALS`/`POOL_SYMBOLS` referenced after definition in Task 5 and consumed in Task 6; `readers` dict shape (`candles/funding/metrics/bundle`) matches `multifamily_loader.default_readers` and Task 3's consumer. `atr_frac` read via `FEATURE_NAMES.index("atr_frac")` (no hard-coded index). ✅

**Note on funding in R:** Task 5 passes `funding_r=0.0` to the cost model deliberately (rung-0 path R is gross-of-funding for comparability with the original screens); funding *level/slope* still enter as features and `funding_fade`/`funding_confirm`/`funding_flip` still consume the funding series for entries. This is intentional, not a gap.
