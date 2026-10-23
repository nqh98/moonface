# Quantitative Capitulation Baseline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated numpy/pandas prototype that generates capitulation-long signals on BTC 1H data (causal Keltner + volume + funding rules), simulates 2%/1% TP-SL trades, and prints in-sample vs. sealed-OOS tear-sheets gated by a block-bootstrap CI on the forward-24H log-return.

**Architecture:** One focused module `capitulation_backtest.py` holding pure functions (loader, causal indicators, trade simulator, forward returns, block bootstrap, tear-sheet) plus an OO `CapitulationStrategy` that owns the frozen thresholds and emits signals. A thin `argparse` CLI wires them and prints both slices + the verdict. Everything is deterministic and testable from synthetic in-memory data; no network. Full frozen design in `experiments/capitulation/DESIGN.md`.

**Tech Stack:** Python 3.12, numpy, pandas (own venv at `experiments/capitulation/.venv`; quarantined from the stdlib-only main tree, not in root `pyproject.toml`, excluded from main pytest).

## Global Constraints

- Python 3.12; deps limited to **numpy + pandas only** (pinned in `experiments/capitulation/requirements.txt`).
- All code lives under `experiments/capitulation/`; **not** added to root `pyproject.toml`; own venv.
- **Zero-leakage:** every rolling input (Keltner band, volume-pct threshold, funding-pct threshold) is `.shift(1)`-aligned — computed through bar `t−1`, tested against bar `t`. Funding forward-filled onto the hourly grid never exposes a future 8H epoch at bar `t`.
- **Frozen params (do not re-tune):** EMA(20), ATR(20), Keltner mult 3.0; volume ≥95th pct of trailing 30-day (=720-bar) window, trigger bar `close < open`; funding ≤5th pct of trailing 30-day (=720-bar) window (primary), fixed variant ≤ −0.0001; cooldown 24 bars; TP +0.02 / SL −0.01, SL-first, same-bar tie = loss, timeout 48 bars → scratch-at-close.
- **Frozen split:** in-sample `2020-01-01 → 2024-06-30`; sealed OOS `2024-07-01 → present`.
- **Frozen gate:** block-bootstrap (block 24) 95% CI on mean forward-24H log-return of **sealed-OOS** signals; `PASS` iff CI lower bound > 0; `UNDERPOWERED — inconclusive` if n_OOS < 20 (seal still spent). 4H reported (not gated); win-rate descriptive only.
- Timestamps are epoch **milliseconds**, UTC; window "days" convert to bars as `days * 24`.
- Commit messages: no AI-attribution trailers.

---

### Task 1: Scaffold environment + data loader

**Files:**
- Create: `experiments/capitulation/requirements.txt`
- Create: `experiments/capitulation/README.md`
- Create: `experiments/capitulation/.gitignore`
- Create: `experiments/capitulation/capitulation_backtest.py`
- Test: `experiments/capitulation/tests/test_capitulation.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `load_data(ohlcv_path: str, funding_path: str, start: str | None = None, end: str | None = None) -> pandas.DataFrame` — UTC `DatetimeIndex`, columns `["open","high","low","close","volume","funding"]`, funding forward-filled from 8H epochs onto the hourly grid (no future epoch visible at bar `t`), sliced inclusive to `[start, end]`, rows before the first funding epoch dropped.

- [ ] **Step 1: Create the venv and pin deps**

Create `experiments/capitulation/requirements.txt`:

```
numpy==2.1.3
pandas==2.2.3
pytest==8.3.4
```

Then run:

```bash
python3 -m venv experiments/capitulation/.venv
experiments/capitulation/.venv/bin/pip install -r experiments/capitulation/requirements.txt
```

Expected: installs numpy, pandas, pytest without error.

- [ ] **Step 2: Create `.gitignore` and README**

Create `experiments/capitulation/.gitignore`:

```
.venv/
__pycache__/
data/
*.pyc
```

Create `experiments/capitulation/README.md`:

```markdown
# capitulation — Quantitative Capitulation (Mean-Reversion) Baseline

**Status:** pre-registered confirmatory study. Long-only capitulation-fade on BTC 1H.
**Not an edge claim** until the sealed-OOS bootstrap CI clears the gate. See `DESIGN.md`.

Quarantined from the stdlib-only main tree: numpy/pandas deps live only in this dir's venv.

## Setup

    python3 -m venv experiments/capitulation/.venv
    experiments/capitulation/.venv/bin/pip install -r experiments/capitulation/requirements.txt

## Run

    experiments/capitulation/.venv/bin/python experiments/capitulation/capitulation_backtest.py \
      --ohlcv .backtest_cache/BTCUSDT_1h.csv \
      --funding .backtest_cache/unifunding_BTCUSDT.csv \
      --oos-cutoff 2024-07-01 --funding-mode percentile

## Test

    experiments/capitulation/.venv/bin/pytest experiments/capitulation/tests -v
```

- [ ] **Step 3: Write the failing test for `load_data`**

Create `experiments/capitulation/tests/test_capitulation.py`:

```python
import numpy as np
import pandas as pd
import pytest

from capitulation_backtest import load_data


def _write_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, header=False, index=False)


def test_load_data_ffills_funding_without_future_leak(tmp_path):
    # Hourly OHLCV: 10 bars starting 2020-01-01 00:00 UTC.
    base = pd.Timestamp("2020-01-01", tz="UTC")
    ohlcv = [
        [int((base + pd.Timedelta(hours=h)).timestamp() * 1000),
         100.0, 101.0, 99.0, 100.0, 50.0]
        for h in range(10)
    ]
    # Funding epochs at 00:00 (=0.001) and 08:00 (=-0.002).
    funding = [
        [int(base.timestamp() * 1000), 0.001],
        [int((base + pd.Timedelta(hours=8)).timestamp() * 1000), -0.002],
    ]
    op = tmp_path / "ohlcv.csv"
    fp = tmp_path / "funding.csv"
    _write_csv(op, ohlcv)
    _write_csv(fp, funding)

    df = load_data(str(op), str(fp))

    assert list(df.columns) == ["open", "high", "low", "close", "volume", "funding"]
    assert df.index.tz is not None  # tz-aware UTC
    # Bars 0..7 carry the 00:00 epoch; bars 8..9 carry the 08:00 epoch.
    assert df.iloc[3]["funding"] == pytest.approx(0.001)
    assert df.iloc[7]["funding"] == pytest.approx(0.001)
    assert df.iloc[8]["funding"] == pytest.approx(-0.002)
    # No future epoch leaked backward.
    assert (df.iloc[:8]["funding"] == pytest.approx(0.001)).all()
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests/test_capitulation.py::test_load_data_ffills_funding_without_future_leak -v`
Expected: FAIL with `ImportError` / `cannot import name 'load_data'`.

- [ ] **Step 5: Implement `load_data`**

Create `experiments/capitulation/capitulation_backtest.py` with the module docstring and loader:

```python
"""Quantitative Capitulation (mean-reversion) baseline backtest.

Pre-registered confirmatory study — see DESIGN.md. Long-only capitulation fade on
BTC 1H. numpy/pandas only; no network; deterministic.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

_OHLCV_COLS = ["open", "high", "low", "close", "volume"]


def load_data(ohlcv_path: str, funding_path: str,
              start: str | None = None, end: str | None = None) -> pd.DataFrame:
    """Load headerless OHLCV + funding caches, align funding onto the hourly grid.

    OHLCV schema:  ts_ms, open, high, low, close, volume
    Funding schema: ts_ms, funding_rate  (8H epochs)
    Funding is forward-filled so bar t carries the most recent epoch published at
    or before t; bars before the first epoch are dropped.
    """
    ohlcv = pd.read_csv(ohlcv_path, header=None,
                        names=["ts", *_OHLCV_COLS])
    ohlcv["ts"] = pd.to_datetime(ohlcv["ts"], unit="ms", utc=True)
    ohlcv = ohlcv.set_index("ts").sort_index()

    funding = pd.read_csv(funding_path, header=None, names=["ts", "funding"])
    funding["ts"] = pd.to_datetime(funding["ts"], unit="ms", utc=True)
    funding = funding.set_index("ts").sort_index()

    # Align funding onto the hourly grid: last epoch at or before each bar.
    merged = pd.merge_asof(
        ohlcv, funding, left_index=True, right_index=True, direction="backward"
    )
    merged = merged.dropna(subset=["funding"])  # drop pre-first-epoch bars

    if start is not None:
        merged = merged[merged.index >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        merged = merged[merged.index <= pd.Timestamp(end, tz="UTC")]

    return merged[_OHLCV_COLS + ["funding"]]
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests/test_capitulation.py -v`
Expected: PASS. (Run from the `experiments/capitulation/` dir, or add a `conftest.py` — see Step 7.)

- [ ] **Step 7: Add `conftest.py` so tests import the module**

Create `experiments/capitulation/tests/conftest.py`:

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

Re-run Step 6 from repo root:
Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add experiments/capitulation/requirements.txt experiments/capitulation/README.md \
  experiments/capitulation/.gitignore experiments/capitulation/capitulation_backtest.py \
  experiments/capitulation/tests/test_capitulation.py experiments/capitulation/tests/conftest.py
git commit -m "feat(capitulation): scaffold + causal data loader with funding alignment"
```

---

### Task 2: Causal indicators (EMA, ATR, Keltner lower, rolling-pct threshold)

**Files:**
- Modify: `experiments/capitulation/capitulation_backtest.py`
- Test: `experiments/capitulation/tests/test_capitulation.py`

**Interfaces:**
- Consumes: a `pandas.DataFrame` with `open/high/low/close/volume/funding`.
- Produces:
  - `ema(series: pd.Series, n: int) -> pd.Series`
  - `atr(df: pd.DataFrame, n: int) -> pd.Series`
  - `keltner_lower(df, ema_n: int, atr_n: int, mult: float) -> pd.Series` — already `.shift(1)`; compare to `close[t]`.
  - `rolling_pct_threshold(series: pd.Series, window: int, pct: float) -> pd.Series` — `.shift(1)`; the `pct`-percentile of the trailing `window` bars ending at `t−1`.

- [ ] **Step 1: Write the failing leakage-guard test**

Add to `experiments/capitulation/tests/test_capitulation.py`:

```python
from capitulation_backtest import (
    ema, atr, keltner_lower, rolling_pct_threshold,
)


def _flat_df(n, price=100.0, vol=50.0):
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {"open": price, "high": price + 1, "low": price - 1,
         "close": price, "volume": vol, "funding": 0.0001},
        index=idx,
    )


def test_keltner_lower_is_causal_no_future_leak():
    df = _flat_df(60)
    df.loc[df.index, "close"] = np.linspace(100, 110, 60)
    band_a = keltner_lower(df, ema_n=5, atr_n=5, mult=3.0)
    df2 = df.copy()
    df2.iloc[40, df2.columns.get_loc("close")] = 999.0  # spike at t=40
    band_b = keltner_lower(df2, ema_n=5, atr_n=5, mult=3.0)
    # Bands at t<=40 must be unchanged by a spike at t=40 (band uses <= t-1).
    pd.testing.assert_series_equal(band_a.iloc[:41], band_b.iloc[:41])


def test_rolling_pct_threshold_excludes_current_bar():
    s = pd.Series([1, 2, 3, 4, 100.0])
    thr = rolling_pct_threshold(s, window=3, pct=95)
    # At index 4 the window is bars 1..3 (=[2,3,4]); the 100 at index 4 is excluded.
    assert thr.iloc[4] == pytest.approx(np.quantile([2, 3, 4], 0.95))
```

- [ ] **Step 2: Run to verify it fails**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -k "causal or threshold" -v`
Expected: FAIL with `cannot import name 'ema'`.

- [ ] **Step 3: Implement the indicators**

Add to `experiments/capitulation/capitulation_backtest.py`:

```python
def ema(series: pd.Series, n: int) -> pd.Series:
    return series.ewm(span=n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(n, min_periods=n).mean()


def keltner_lower(df: pd.DataFrame, ema_n: int, atr_n: int, mult: float) -> pd.Series:
    mid = ema(df["close"], ema_n)
    lower = mid - mult * atr(df, atr_n)
    return lower.shift(1)  # tested against close[t]; band known before t opens


def rolling_pct_threshold(series: pd.Series, window: int, pct: float) -> pd.Series:
    return series.shift(1).rolling(window, min_periods=window).quantile(pct / 100.0)
```

- [ ] **Step 4: Run to verify it passes**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -k "causal or threshold" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add experiments/capitulation/capitulation_backtest.py experiments/capitulation/tests/test_capitulation.py
git commit -m "feat(capitulation): causal indicators (EMA/ATR/Keltner/rolling-pct)"
```

---

### Task 3: `CapitulationStrategy` — three conditions + cooldown

**Files:**
- Modify: `experiments/capitulation/capitulation_backtest.py`
- Test: `experiments/capitulation/tests/test_capitulation.py`

**Interfaces:**
- Consumes: `load_data` output; the Task-2 indicators.
- Produces: `CapitulationStrategy(ema_period=20, atr_period=20, atr_mult=3.0, vol_pct=95, vol_window_days=30, funding_pct=5, funding_window_days=30, funding_mode="percentile", fixed_funding_thresh=-0.0001, cooldown_bars=24, tp=0.02, sl=0.01, timeout_bars=48)` with `.generate_signals(df) -> pd.Series` (boolean, index-aligned to `df`, cooldown applied). Window days convert to bars as `days * 24`.

- [ ] **Step 1: Write failing tests (fires-once, all-three-required, cooldown)**

Add to `experiments/capitulation/tests/test_capitulation.py`:

```python
from capitulation_backtest import CapitulationStrategy


def _capit_df(n=780, spike_idx=(760,), extreme_funding=True):
    """Flat, calm market (close==open==100, volume 100, funding +1e-4) with an
    injected capitulation bar at each spike_idx: deep down-close, volume 1000.
    Funding at the spike is -0.01 (extreme, fires cond3) when extreme_funding,
    else +0.01 (clearly NON-extreme -> cond3 false). Flat bars can never fire
    (close==open, ATR==0). Note: a flat baseline funding of 1e-4 makes the 5th-pct
    threshold exactly 1e-4, so cond3 must be killed with a POSITIVE spike, not by
    leaving funding flat (1e-4 <= 1e-4 is True)."""
    idx = pd.date_range("2020-01-01", periods=n, freq="h", tz="UTC")
    df = pd.DataFrame(
        {"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0,
         "volume": 100.0, "funding": 0.0001},
        index=idx,
    )
    for si in spike_idx:
        df.iloc[si, df.columns.get_loc("open")] = 100.0
        df.iloc[si, df.columns.get_loc("high")] = 100.0
        df.iloc[si, df.columns.get_loc("low")] = 80.0
        df.iloc[si, df.columns.get_loc("close")] = 80.0   # close < open, below band
        df.iloc[si, df.columns.get_loc("volume")] = 1000.0
        df.iloc[si, df.columns.get_loc("funding")] = -0.01 if extreme_funding else 0.01
    return df


def _fast_strategy(**kw):
    # Small windows so a ~780-bar fixture has a fully-warmed 720-bar-equivalent.
    params = dict(ema_period=5, atr_period=5, vol_window_days=1, funding_window_days=1,
                  cooldown_bars=24)
    params.update(kw)
    return CapitulationStrategy(**params)


def test_fires_exactly_once_on_capitulation_bar():
    df = _capit_df(spike_idx=(760,))
    sig = _fast_strategy().generate_signals(df)
    assert sig.sum() == 1
    assert bool(sig.iloc[760]) is True


def test_requires_all_three_conditions():
    # Kill condition 3 (funding positive, non-extreme) -> no signal.
    df = _capit_df(spike_idx=(760,), extreme_funding=False)
    sig = _fast_strategy().generate_signals(df)
    assert sig.sum() == 0


def test_cooldown_suppresses_second_fire_within_window():
    df = _capit_df(spike_idx=(760, 770))  # 10 bars apart < 24
    sig = _fast_strategy(cooldown_bars=24).generate_signals(df)
    assert sig.sum() == 1
    assert bool(sig.iloc[760]) is True
    assert bool(sig.iloc[770]) is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -k "fires or three or cooldown" -v`
Expected: FAIL with `cannot import name 'CapitulationStrategy'`.

- [ ] **Step 3: Implement `CapitulationStrategy`**

Add to `experiments/capitulation/capitulation_backtest.py`:

```python
class CapitulationStrategy:
    """Long-only capitulation-fade signal generator. All thresholds frozen in
    DESIGN.md; parameterized here only for robustness/stability checks."""

    def __init__(self, ema_period=20, atr_period=20, atr_mult=3.0,
                 vol_pct=95, vol_window_days=30,
                 funding_pct=5, funding_window_days=30,
                 funding_mode="percentile", fixed_funding_thresh=-0.0001,
                 cooldown_bars=24, tp=0.02, sl=0.01, timeout_bars=48):
        self.ema_period = ema_period
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.vol_pct = vol_pct
        self.vol_window = vol_window_days * 24
        self.funding_pct = funding_pct
        self.funding_window = funding_window_days * 24
        self.funding_mode = funding_mode
        self.fixed_funding_thresh = fixed_funding_thresh
        self.cooldown_bars = cooldown_bars
        self.tp = tp
        self.sl = sl
        self.timeout_bars = timeout_bars

    def _raw_conditions(self, df: pd.DataFrame) -> pd.Series:
        lower = keltner_lower(df, self.ema_period, self.atr_period, self.atr_mult)
        cond1 = df["close"] < lower

        vol_thr = rolling_pct_threshold(df["volume"], self.vol_window, self.vol_pct)
        cond2 = (df["volume"] >= vol_thr) & (df["close"] < df["open"])

        if self.funding_mode == "percentile":
            fund_thr = rolling_pct_threshold(df["funding"], self.funding_window,
                                             self.funding_pct)
            cond3 = df["funding"] <= fund_thr
        elif self.funding_mode == "fixed":
            cond3 = df["funding"] <= self.fixed_funding_thresh
        else:
            raise ValueError(f"unknown funding_mode: {self.funding_mode}")

        return (cond1 & cond2 & cond3).fillna(False)

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        raw = self._raw_conditions(df).to_numpy()
        accepted = np.zeros(len(raw), dtype=bool)
        last = -10**9
        for i in np.flatnonzero(raw):
            if i - last >= self.cooldown_bars:
                accepted[i] = True
                last = i
        return pd.Series(accepted, index=df.index)
```

- [ ] **Step 4: Run to verify it passes**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -k "fires or three or cooldown" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add experiments/capitulation/capitulation_backtest.py experiments/capitulation/tests/test_capitulation.py
git commit -m "feat(capitulation): CapitulationStrategy signals + cooldown"
```

---

### Task 4: Trade simulator (SL-first TP/SL/timeout)

**Files:**
- Modify: `experiments/capitulation/capitulation_backtest.py`
- Test: `experiments/capitulation/tests/test_capitulation.py`

**Interfaces:**
- Consumes: `df` (OHLCV), a boolean `signals` Series, and `tp/sl/timeout_bars`.
- Produces: `simulate_trades(df, signals, tp=0.02, sl=0.01, timeout_bars=48) -> pd.DataFrame` with columns `entry_ts, entry_price, outcome, bars_held`. `outcome` ∈ `{"win","loss","scratch_win","scratch_loss"}`. Rule: entry = signal bar close; walk `t+1…t+timeout`; SL checked before TP within a bar; same-bar TP&SL → loss; unresolved by timeout → scratch, win iff final walked close > entry.

- [ ] **Step 1: Write failing tests (SL-first, timeout scratch)**

Add to `experiments/capitulation/tests/test_capitulation.py`:

```python
from capitulation_backtest import simulate_trades


def _df_from_bars(bars):
    idx = pd.date_range("2020-01-01", periods=len(bars), freq="h", tz="UTC")
    return pd.DataFrame(bars, index=idx,
                        columns=["open", "high", "low", "close", "volume", "funding"])


def test_sl_first_same_bar_tie_is_loss():
    # entry at bar0 close=100. Bar1 spans both TP(102) and SL(99) -> loss.
    bars = [
        [100, 100, 100, 100, 1, 0.0],
        [100, 103, 98.9, 101, 1, 0.0],  # high>=102 and low<=99
    ]
    df = _df_from_bars(bars)
    sig = pd.Series([True, False], index=df.index)
    trades = simulate_trades(df, sig, tp=0.02, sl=0.01, timeout_bars=48)
    assert len(trades) == 1
    assert trades.iloc[0]["outcome"] == "loss"


def test_clean_tp_is_win():
    bars = [
        [100, 100, 100, 100, 1, 0.0],
        [100, 102.5, 99.5, 102, 1, 0.0],  # high>=102, low>99 -> TP only
    ]
    df = _df_from_bars(bars)
    sig = pd.Series([True, False], index=df.index)
    trades = simulate_trades(df, sig, tp=0.02, sl=0.01, timeout_bars=48)
    assert trades.iloc[0]["outcome"] == "win"


def test_timeout_scratch_win_and_loss():
    # No TP/SL touched within 2 bars -> scratch on final close.
    base = [100, 100.5, 99.5, 100, 1, 0.0]
    up = _df_from_bars([base, base, [100, 100.5, 99.5, 100.4, 1, 0.0]])
    down = _df_from_bars([base, base, [100, 100.5, 99.5, 99.6, 1, 0.0]])
    sig = pd.Series([True, False, False], index=up.index)
    t_up = simulate_trades(up, sig, tp=0.02, sl=0.01, timeout_bars=2)
    t_down = simulate_trades(down, sig, tp=0.02, sl=0.01, timeout_bars=2)
    assert t_up.iloc[0]["outcome"] == "scratch_win"
    assert t_down.iloc[0]["outcome"] == "scratch_loss"
```

- [ ] **Step 2: Run to verify it fails**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -k "sl_first or clean_tp or timeout_scratch" -v`
Expected: FAIL with `cannot import name 'simulate_trades'`.

- [ ] **Step 3: Implement `simulate_trades`**

Add to `experiments/capitulation/capitulation_backtest.py`:

```python
def simulate_trades(df: pd.DataFrame, signals: pd.Series,
                    tp: float = 0.02, sl: float = 0.01,
                    timeout_bars: int = 48) -> pd.DataFrame:
    """Long-only SL-first TP/SL/timeout simulation. Entry = signal bar close."""
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    closes = df["close"].to_numpy()
    n = len(df)
    sig_pos = np.flatnonzero(signals.to_numpy())

    rows = []
    for i in sig_pos:
        entry = closes[i]
        tp_price = entry * (1 + tp)
        sl_price = entry * (1 - sl)
        outcome = None
        bars_held = 0
        last_close = entry
        end = min(i + timeout_bars, n - 1)
        for j in range(i + 1, end + 1):
            bars_held = j - i
            last_close = closes[j]
            if lows[j] <= sl_price:      # SL checked before TP (tie -> loss)
                outcome = "loss"
                break
            if highs[j] >= tp_price:
                outcome = "win"
                break
        if outcome is None:
            outcome = "scratch_win" if last_close > entry else "scratch_loss"
        rows.append({
            "entry_ts": df.index[i], "entry_price": entry,
            "outcome": outcome, "bars_held": bars_held,
        })

    return pd.DataFrame(rows, columns=["entry_ts", "entry_price", "outcome", "bars_held"])
```

- [ ] **Step 4: Run to verify it passes**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -k "sl_first or clean_tp or timeout_scratch" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add experiments/capitulation/capitulation_backtest.py experiments/capitulation/tests/test_capitulation.py
git commit -m "feat(capitulation): SL-first TP/SL/timeout trade simulator"
```

---

### Task 5: Forward returns + block-bootstrap CI

**Files:**
- Modify: `experiments/capitulation/capitulation_backtest.py`
- Test: `experiments/capitulation/tests/test_capitulation.py`

**Interfaces:**
- Consumes: `df` (OHLCV) and boolean `signals`.
- Produces:
  - `forward_log_returns(df, signals, horizons=(4, 24)) -> dict[int, np.ndarray]` — per horizon `h`, the array of `ln(close[i+h]/close[i])` for each signal `i` with a full `i+h` bar (right-edge signals dropped).
  - `block_bootstrap_ci(returns, block=24, n_boot=10000, alpha=0.05, seed=0) -> tuple[float, float]` — moving-block bootstrap 95% CI on the mean; `(nan, nan)` if empty.

- [ ] **Step 1: Write failing tests**

Add to `experiments/capitulation/tests/test_capitulation.py`:

```python
from capitulation_backtest import forward_log_returns, block_bootstrap_ci


def test_forward_log_returns_values_and_right_edge_drop():
    closes = [100, 101, 102, 103, 104, 105]
    bars = [[c, c, c, c, 1, 0.0] for c in closes]
    df = _df_from_bars(bars)
    sig = pd.Series([True, False, False, False, True, False], index=df.index)
    out = forward_log_returns(df, sig, horizons=(2,))
    # Signal at idx0 -> ln(102/100); signal at idx4 has no idx6 -> dropped.
    assert len(out[2]) == 1
    assert out[2][0] == pytest.approx(np.log(102 / 100))


def test_block_bootstrap_ci_positive_constant_excludes_zero():
    r = np.full(50, 0.01)
    lo, hi = block_bootstrap_ci(r, block=24, n_boot=1000, seed=0)
    assert lo > 0
    assert hi == pytest.approx(0.01, abs=1e-9)


def test_block_bootstrap_ci_empty_is_nan():
    lo, hi = block_bootstrap_ci(np.array([]), block=24)
    assert np.isnan(lo) and np.isnan(hi)
```

- [ ] **Step 2: Run to verify it fails**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -k "forward_log or bootstrap" -v`
Expected: FAIL with `cannot import name 'forward_log_returns'`.

- [ ] **Step 3: Implement both functions**

Add to `experiments/capitulation/capitulation_backtest.py`:

```python
def forward_log_returns(df: pd.DataFrame, signals: pd.Series,
                        horizons=(4, 24)) -> dict:
    closes = df["close"].to_numpy()
    n = len(closes)
    sig_pos = np.flatnonzero(signals.to_numpy())
    out = {}
    for h in horizons:
        vals = [np.log(closes[i + h] / closes[i]) for i in sig_pos if i + h < n]
        out[h] = np.asarray(vals, dtype=float)
    return out


def block_bootstrap_ci(returns, block: int = 24, n_boot: int = 10000,
                       alpha: float = 0.05, seed: int = 0):
    r = np.asarray(returns, dtype=float)
    r = r[~np.isnan(r)]
    n = len(r)
    if n == 0:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    eff_block = min(block, n)
    n_blocks = int(np.ceil(n / eff_block))
    max_start = n - eff_block
    means = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, max_start + 1, size=n_blocks)
        sample = np.concatenate([r[s:s + eff_block] for s in starts])[:n]
        means[b] = sample.mean()
    return (float(np.quantile(means, alpha / 2)),
            float(np.quantile(means, 1 - alpha / 2)))
```

- [ ] **Step 4: Run to verify it passes**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -k "forward_log or bootstrap" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add experiments/capitulation/capitulation_backtest.py experiments/capitulation/tests/test_capitulation.py
git commit -m "feat(capitulation): forward log-returns + block-bootstrap CI"
```

---

### Task 6: Tear-sheet + verdict

**Files:**
- Modify: `experiments/capitulation/capitulation_backtest.py`
- Test: `experiments/capitulation/tests/test_capitulation.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `slice_stats(df, strategy) -> dict` — keys: `n_signals, win_rate, mean_fwd_4h, mean_fwd_24h, ci24_lo, ci24_hi, ci4_lo, ci4_hi`. `win_rate` counts `{win, scratch_win}` over all trades (nan if none).
  - `verdict(oos_stats, min_n=20) -> str` — `"PASS"` if `n_signals >= min_n and ci24_lo > 0`; `"UNDERPOWERED — inconclusive"` if `n_signals < min_n`; else `"FAIL"`.
  - `format_tear_sheet(label, stats) -> str` — human-readable block.

- [ ] **Step 1: Write failing tests**

Add to `experiments/capitulation/tests/test_capitulation.py`:

```python
from capitulation_backtest import slice_stats, verdict


def test_verdict_pass_fail_underpowered():
    assert verdict({"n_signals": 30, "ci24_lo": 0.001}, min_n=20) == "PASS"
    assert verdict({"n_signals": 30, "ci24_lo": -0.001}, min_n=20) == "FAIL"
    assert verdict({"n_signals": 5, "ci24_lo": 0.5}, min_n=20).startswith("UNDERPOWERED")


def test_slice_stats_keys_and_winrate():
    df = _capit_df(spike_idx=(760,))
    stats = slice_stats(df, _fast_strategy())
    for k in ["n_signals", "win_rate", "mean_fwd_4h", "mean_fwd_24h",
              "ci24_lo", "ci24_hi"]:
        assert k in stats
    assert stats["n_signals"] == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -k "verdict or slice_stats" -v`
Expected: FAIL with `cannot import name 'slice_stats'`.

- [ ] **Step 3: Implement the tear-sheet functions**

Add to `experiments/capitulation/capitulation_backtest.py`:

```python
def slice_stats(df: pd.DataFrame, strategy: "CapitulationStrategy") -> dict:
    sig = strategy.generate_signals(df)
    trades = simulate_trades(df, sig, strategy.tp, strategy.sl, strategy.timeout_bars)
    fwd = forward_log_returns(df, sig, horizons=(4, 24))

    n = int(sig.sum())
    if len(trades):
        wins = trades["outcome"].isin(["win", "scratch_win"]).sum()
        win_rate = wins / len(trades)
    else:
        win_rate = float("nan")

    ci4 = block_bootstrap_ci(fwd[4])
    ci24 = block_bootstrap_ci(fwd[24])
    return {
        "n_signals": n,
        "win_rate": win_rate,
        "mean_fwd_4h": float(np.mean(fwd[4])) if len(fwd[4]) else float("nan"),
        "mean_fwd_24h": float(np.mean(fwd[24])) if len(fwd[24]) else float("nan"),
        "ci4_lo": ci4[0], "ci4_hi": ci4[1],
        "ci24_lo": ci24[0], "ci24_hi": ci24[1],
    }


def verdict(oos_stats: dict, min_n: int = 20) -> str:
    if oos_stats["n_signals"] < min_n:
        return "UNDERPOWERED — inconclusive"
    return "PASS" if oos_stats["ci24_lo"] > 0 else "FAIL"


def format_tear_sheet(label: str, stats: dict) -> str:
    return (
        f"── {label} ──\n"
        f"  signals            : {stats['n_signals']}\n"
        f"  win-rate (TP/SL)   : {stats['win_rate']:.3f}   [descriptive]\n"
        f"  mean fwd  4H logret : {stats['mean_fwd_4h']:+.5f}\n"
        f"  mean fwd 24H logret : {stats['mean_fwd_24h']:+.5f}\n"
        f"  95% CI  4H         : [{stats['ci4_lo']:+.5f}, {stats['ci4_hi']:+.5f}]\n"
        f"  95% CI 24H (GATE)  : [{stats['ci24_lo']:+.5f}, {stats['ci24_hi']:+.5f}]\n"
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -k "verdict or slice_stats" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add experiments/capitulation/capitulation_backtest.py experiments/capitulation/tests/test_capitulation.py
git commit -m "feat(capitulation): slice tear-sheet stats + confirmatory verdict"
```

---

### Task 7: CLI wiring + full-suite green

**Files:**
- Modify: `experiments/capitulation/capitulation_backtest.py`
- Test: `experiments/capitulation/tests/test_capitulation.py`

**Interfaces:**
- Consumes: `load_data`, `CapitulationStrategy`, `slice_stats`, `verdict`, `format_tear_sheet`.
- Produces: `main(argv=None) -> int` and `if __name__ == "__main__"` guard. Splits loaded data at `--oos-cutoff` into in-sample (`< cutoff`) and sealed OOS (`>= cutoff`), prints both tear-sheets + the verdict line reading off the **OOS** slice.

- [ ] **Step 1: Write failing CLI smoke test**

Add to `experiments/capitulation/tests/test_capitulation.py`:

```python
from capitulation_backtest import main


def test_main_runs_and_prints_verdict(tmp_path, capsys):
    # Smoke test: one in-sample capitulation bar; OOS slice has none, so the
    # verdict is UNDERPOWERED. Only asserts the run prints both slices + verdict.
    n = 900
    base = pd.Timestamp("2020-01-01", tz="UTC")
    idx = pd.date_range(base, periods=n, freq="h", tz="UTC")
    ohlcv = [[int(idx[h].timestamp() * 1000), 100, 100, 100, 100, 100]
             for h in range(n)]
    ohlcv[760] = [int(idx[760].timestamp() * 1000), 100, 100, 80, 80, 1000]
    funding = [[int(base.timestamp() * 1000), 0.0001],
               [int(idx[760].timestamp() * 1000), -0.01]]
    op, fp = tmp_path / "o.csv", tmp_path / "f.csv"
    pd.DataFrame(ohlcv).to_csv(op, header=False, index=False)
    pd.DataFrame(funding).to_csv(fp, header=False, index=False)

    rc = main(["--ohlcv", str(op), "--funding", str(fp),
               "--oos-cutoff", "2020-02-05",
               "--ema-period", "5", "--atr-period", "5",
               "--vol-window-days", "1", "--funding-window-days", "1"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "IN-SAMPLE" in out and "SEALED OOS" in out
    assert "VERDICT" in out
```

- [ ] **Step 2: Run to verify it fails**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -k "main_runs" -v`
Expected: FAIL with `cannot import name 'main'`.

- [ ] **Step 3: Implement `main` + argparse**

Add to `experiments/capitulation/capitulation_backtest.py`:

```python
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Quantitative Capitulation backtest")
    p.add_argument("--ohlcv", default=".backtest_cache/BTCUSDT_1h.csv")
    p.add_argument("--funding", default=".backtest_cache/unifunding_BTCUSDT.csv")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--oos-cutoff", default="2024-07-01")
    p.add_argument("--funding-mode", choices=["percentile", "fixed"],
                   default="percentile")
    p.add_argument("--ema-period", type=int, default=20)
    p.add_argument("--atr-period", type=int, default=20)
    p.add_argument("--atr-mult", type=float, default=3.0)
    p.add_argument("--vol-pct", type=float, default=95)
    p.add_argument("--vol-window-days", type=int, default=30)
    p.add_argument("--funding-pct", type=float, default=5)
    p.add_argument("--funding-window-days", type=int, default=30)
    p.add_argument("--cooldown-bars", type=int, default=24)
    p.add_argument("--min-oos", type=int, default=20)
    args = p.parse_args(argv)

    df = load_data(args.ohlcv, args.funding, start=args.start)
    strat = CapitulationStrategy(
        ema_period=args.ema_period, atr_period=args.atr_period,
        atr_mult=args.atr_mult, vol_pct=args.vol_pct,
        vol_window_days=args.vol_window_days, funding_pct=args.funding_pct,
        funding_window_days=args.funding_window_days,
        funding_mode=args.funding_mode, cooldown_bars=args.cooldown_bars,
    )
    cutoff = pd.Timestamp(args.oos_cutoff, tz="UTC")
    in_df = df[df.index < cutoff]
    oos_df = df[df.index >= cutoff]

    in_stats = slice_stats(in_df, strat)
    oos_stats = slice_stats(oos_df, strat)
    v = verdict(oos_stats, min_n=args.min_oos)

    print(f"Quantitative Capitulation — funding_mode={args.funding_mode} "
          f"cutoff={args.oos_cutoff}")
    print(format_tear_sheet("IN-SAMPLE (descriptive)", in_stats))
    print(format_tear_sheet("SEALED OOS (confirmatory)", oos_stats))
    print(f"VERDICT (sealed OOS, 24H CI vs 0): {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the CLI smoke test, then the FULL suite**

Run: `experiments/capitulation/.venv/bin/python -m pytest experiments/capitulation/tests -v`
Expected: PASS (all tests, ~15).

- [ ] **Step 5: Commit**

```bash
git add experiments/capitulation/capitulation_backtest.py experiments/capitulation/tests/test_capitulation.py
git commit -m "feat(capitulation): CLI + in-sample/sealed-OOS tear-sheet run"
```

---

### Task 8: Registered run + RESULTS.md (opens the seal ONCE)

**Files:**
- Create: `experiments/capitulation/RESULTS.md`

**Interfaces:**
- Consumes: the finished CLI against the real caches.
- Produces: `RESULTS.md` — both tear-sheets, the verdict, n-counts, CIs, the `--funding-mode fixed` robustness read, and an honest interpretation per DESIGN §0.

- [ ] **Step 1: Run the registered (primary) configuration**

```bash
experiments/capitulation/.venv/bin/python experiments/capitulation/capitulation_backtest.py \
  --ohlcv .backtest_cache/BTCUSDT_1h.csv \
  --funding .backtest_cache/unifunding_BTCUSDT.csv \
  --oos-cutoff 2024-07-01 --funding-mode percentile
```

Capture the full stdout. This is the **one** sealed-OOS look — do not re-run with altered params to change the verdict.

- [ ] **Step 2: Run the robustness variant**

```bash
experiments/capitulation/.venv/bin/python experiments/capitulation/capitulation_backtest.py \
  --ohlcv .backtest_cache/BTCUSDT_1h.csv \
  --funding .backtest_cache/unifunding_BTCUSDT.csv \
  --oos-cutoff 2024-07-01 --funding-mode fixed
```

- [ ] **Step 3: Write `RESULTS.md`**

Create `experiments/capitulation/RESULTS.md` with: the primary run's two tear-sheets verbatim, the VERDICT line, n_signals for each slice, the 24H (gate) and 4H CIs, the fixed-mode robustness read, and a one-paragraph honest interpretation consistent with DESIGN §0 (candidate vs. dead; note UNDERPOWERED explicitly if n_OOS < 20; no deployment claim from this study alone).

- [ ] **Step 4: Commit**

```bash
git add experiments/capitulation/RESULTS.md
git commit -m "docs(capitulation): registered-run results + sealed-OOS verdict"
```

---

## Notes for the executor

- Run pytest from the **repo root** using the venv interpreter; `tests/conftest.py` puts the module on `sys.path`.
- Keep DESIGN.md authoritative — if any step here contradicts a frozen value there, DESIGN.md wins and the discrepancy is a plan bug to flag, not silently resolve.
- Do not add network calls, extra dependencies, or wire this into the main engine.
