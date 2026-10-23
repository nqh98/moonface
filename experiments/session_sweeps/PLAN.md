# Session-Sweep Fade Baseline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated numpy/pandas prototype that fades prior-session high/low liquidity sweeps on BTC 15m data (3×8h UTC sessions), computes signed forward log-returns, and prints in-sample vs. sealed-OOS tear-sheets gated by a hardened block-bootstrap CI (`min_n=30 > block=20`, so the CI can never degenerate).

**Architecture:** One focused module `session_sweeps_backtest.py` with pure functions (loader, session tagger, signed forward returns, block bootstrap, tear-sheet) plus an OO `SessionSweepStrategy` owning the frozen signal logic. A thin `argparse` CLI wires them and prints both slices + the verdict. Deterministic, no network. Full frozen design in `experiments/session_sweeps/DESIGN.md`.

**Tech Stack:** Python 3.12, numpy, pandas (own venv at `experiments/session_sweeps/.venv`; quarantined from the stdlib-only main tree, not in root `pyproject.toml`, excluded from main pytest).

## Global Constraints

- Python 3.12; deps limited to **numpy + pandas only** (pinned in `experiments/session_sweeps/requirements.txt`).
- All code under `experiments/session_sweeps/`; **not** in root `pyproject.toml`; own venv.
- **Sessions:** 3 fixed non-overlapping 8h UTC blocks — Asia `00:00–08:00`, EU `08:00–16:00`, US `16:00–24:00`. `session_id = (floor-to-8h hour) // 8`. "Prior level" = the immediately preceding 8h block's high/low.
- **Zero-leakage:** prior-session high/low uses only the *completed* previous block (known at current block open); entry = signal bar close; only the forward-return outcome looks ahead.
- **Signal (frozen, reversal mode):** first bar in a session where `high > prior_high AND close < prior_high` → fade SHORT (`direction=-1`), or `low < prior_low AND close > prior_low` → fade LONG (`direction=+1`). A bar qualifying BOTH ways is skipped (ambiguous). **One signal per session** (earliest qualifying bar). Continuation mode (`close > prior_high` → +1 / `close < prior_low` → -1) is a robustness variant only.
- **Primary metric:** signed forward **16-bar (4h)** log-return (`direction * ln(close[t+16]/entry)`); secondary **8-bar (2h)** reported not gated.
- **Win-rate:** directional hit-rate (fraction with signed 4h return > 0) — descriptive only. No TP/SL bracket.
- **Frozen split:** in-sample `2020-01-01 → 2024-06-30`; sealed OOS `2024-07-01 → present`.
- **Frozen gate:** moving-block bootstrap (block 20, 10,000 resamples, `seed=0`) 95% CI on mean signed 4h return of **sealed-OOS** signals; `PASS` iff CI lower bound > 0; `UNDERPOWERED — inconclusive` iff n_OOS < 30 (`min_n=30 > block=20`).
- Timestamps are epoch **milliseconds**, UTC.
- Commit messages: no AI-attribution trailers.

---

### Task 1: Scaffold environment + 15m data loader

**Files:**
- Create: `experiments/session_sweeps/requirements.txt`
- Create: `experiments/session_sweeps/README.md`
- Create: `experiments/session_sweeps/.gitignore`
- Create: `experiments/session_sweeps/session_sweeps_backtest.py`
- Create: `experiments/session_sweeps/tests/conftest.py`
- Test: `experiments/session_sweeps/tests/test_session_sweeps.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `load_data(ohlcv_path: str, start: str | None = None, end: str | None = None) -> pandas.DataFrame` — UTC `DatetimeIndex`, columns `["open","high","low","close","volume"]`, sorted ascending, sliced inclusive to `[start, end]`.

- [ ] **Step 1: Create the venv and pin deps**

Create `experiments/session_sweeps/requirements.txt`:

```
numpy==2.1.3
pandas==2.2.3
pytest==8.3.4
```

Then run:

```bash
python3 -m venv experiments/session_sweeps/.venv
experiments/session_sweeps/.venv/bin/pip install -r experiments/session_sweeps/requirements.txt
```

Expected: installs numpy, pandas, pytest without error.

- [ ] **Step 2: Create `.gitignore` and README**

Create `experiments/session_sweeps/.gitignore`:

```
.venv/
__pycache__/
*.pyc
```

Create `experiments/session_sweeps/README.md`:

```markdown
# session_sweeps — Time-of-Day / Session Sweep (Fade) Baseline

**Status:** pre-registered confirmatory study. Fade prior-session high/low liquidity
sweeps on BTC 15m (3×8h UTC sessions). **Not an edge claim** until the sealed-OOS
bootstrap CI clears the gate. See `DESIGN.md`.

Quarantined from the stdlib-only main tree: numpy/pandas deps live only in this dir's venv.

## Setup

    python3 -m venv experiments/session_sweeps/.venv
    experiments/session_sweeps/.venv/bin/pip install -r experiments/session_sweeps/requirements.txt

## Run

    experiments/session_sweeps/.venv/bin/python experiments/session_sweeps/session_sweeps_backtest.py \
      --ohlcv .backtest_cache/BTCUSDT_15m.csv --oos-cutoff 2024-07-01 --mode reversal

## Test

    experiments/session_sweeps/.venv/bin/pytest experiments/session_sweeps/tests -v
```

- [ ] **Step 3: Create `conftest.py` so tests import the module**

Create `experiments/session_sweeps/tests/conftest.py`:

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

- [ ] **Step 4: Write the failing test for `load_data`**

Create `experiments/session_sweeps/tests/test_session_sweeps.py`:

```python
import numpy as np
import pandas as pd
import pytest

from session_sweeps_backtest import load_data


def test_load_data_parses_utc_and_slices(tmp_path):
    base = pd.Timestamp("2020-01-01", tz="UTC")
    rows = [[int((base + pd.Timedelta(minutes=15 * h)).timestamp() * 1000),
             100.0, 101.0, 99.0, 100.0, 5.0] for h in range(10)]
    p = tmp_path / "ohlcv.csv"
    pd.DataFrame(rows).to_csv(p, header=False, index=False)

    df = load_data(str(p))
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.tz is not None
    assert len(df) == 10
    assert df.index.is_monotonic_increasing
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `experiments/session_sweeps/.venv/bin/python -m pytest experiments/session_sweeps/tests -k load_data -v`
Expected: FAIL with `cannot import name 'load_data'`.

- [ ] **Step 6: Implement `load_data`**

Create `experiments/session_sweeps/session_sweeps_backtest.py`:

```python
"""Time-of-Day / Session-Sweep (fade) baseline backtest.

Pre-registered confirmatory study — see DESIGN.md. Fade prior-session high/low
liquidity sweeps on BTC 15m. numpy/pandas only; no network; deterministic.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

_OHLCV_COLS = ["open", "high", "low", "close", "volume"]


def load_data(ohlcv_path: str, start: str | None = None,
              end: str | None = None) -> pd.DataFrame:
    """Load headerless 15m OHLCV cache: ts_ms, open, high, low, close, volume."""
    df = pd.read_csv(ohlcv_path, header=None, names=["ts", *_OHLCV_COLS])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("ts").sort_index()
    if start is not None:
        df = df[df.index >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        df = df[df.index <= pd.Timestamp(end, tz="UTC")]
    return df[_OHLCV_COLS]
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `experiments/session_sweeps/.venv/bin/python -m pytest experiments/session_sweeps/tests -k load_data -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add experiments/session_sweeps/requirements.txt experiments/session_sweeps/README.md \
  experiments/session_sweeps/.gitignore experiments/session_sweeps/session_sweeps_backtest.py \
  experiments/session_sweeps/tests/test_session_sweeps.py experiments/session_sweeps/tests/conftest.py
git commit -m "feat(session_sweeps): scaffold + 15m data loader"
```

---

### Task 2: Session tagging + prior-block high/low

**Files:**
- Modify: `experiments/session_sweeps/session_sweeps_backtest.py`
- Test: `experiments/session_sweeps/tests/test_session_sweeps.py`

**Interfaces:**
- Consumes: `load_data` output.
- Produces: `tag_sessions(df) -> pd.DataFrame` — returns a copy with added columns `session_id` (`0`=Asia/`1`=EU/`2`=US, from `floor('8h').hour // 8`), `session_key` (contiguous integer per 8h block in time order), `prior_high`, `prior_low` (previous block's high/low broadcast to every bar of the current block; `NaN` for the first block).

- [ ] **Step 1: Write failing tests (tagging, prior-level, leakage)**

Add to `experiments/session_sweeps/tests/test_session_sweeps.py`:

```python
from session_sweeps_backtest import tag_sessions


def _df(idx, ohlc):
    return pd.DataFrame(ohlc, index=idx,
                        columns=["open", "high", "low", "close", "volume"])


def test_session_ids_and_keys():
    idx = pd.DatetimeIndex([
        pd.Timestamp("2020-01-01 03:00", tz="UTC"),
        pd.Timestamp("2020-01-01 10:00", tz="UTC"),
        pd.Timestamp("2020-01-01 18:00", tz="UTC"),
        pd.Timestamp("2020-01-02 01:00", tz="UTC"),
    ])
    df = _df(idx, [[1, 1, 1, 1, 1]] * 4)
    t = tag_sessions(df)
    assert list(t["session_id"]) == [0, 1, 2, 0]
    assert list(t["session_key"]) == [0, 1, 2, 3]


def test_prior_level_from_previous_block():
    idx = pd.DatetimeIndex([
        pd.Timestamp("2020-01-01 00:00", tz="UTC"),
        pd.Timestamp("2020-01-01 04:00", tz="UTC"),
        pd.Timestamp("2020-01-01 08:00", tz="UTC"),  # next block
    ])
    df = _df(idx, [[100, 105, 97, 100, 1],
                   [100, 103, 95, 100, 1],
                   [100, 101, 99, 100, 1]])
    t = tag_sessions(df)
    assert np.isnan(t.iloc[0]["prior_high"])       # first block: no predecessor
    assert t.iloc[2]["prior_high"] == 105          # prev block max high
    assert t.iloc[2]["prior_low"] == 95            # prev block min low


def test_prior_level_no_future_leak():
    idx = pd.DatetimeIndex([
        pd.Timestamp("2020-01-01 00:00", tz="UTC"),  # block0
        pd.Timestamp("2020-01-01 08:00", tz="UTC"),  # block1
        pd.Timestamp("2020-01-01 16:00", tz="UTC"),  # block2 (future)
    ])
    base = [[100, 110, 90, 100, 1], [100, 101, 85, 95, 1], [100, 200, 50, 100, 1]]
    t1 = tag_sessions(_df(idx, base))
    mutated = [r[:] for r in base]
    mutated[2] = [100, 999, 1, 100, 1]  # mutate the FUTURE block
    t2 = tag_sessions(_df(idx, mutated))
    assert t1.iloc[1]["prior_high"] == t2.iloc[1]["prior_high"]
    assert t1.iloc[1]["prior_low"] == t2.iloc[1]["prior_low"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `experiments/session_sweeps/.venv/bin/python -m pytest experiments/session_sweeps/tests -k "session_ids or prior_level or future_leak" -v`
Expected: FAIL with `cannot import name 'tag_sessions'`.

- [ ] **Step 3: Implement `tag_sessions`**

Add to `experiments/session_sweeps/session_sweeps_backtest.py`:

```python
def tag_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Tag each bar with its 8h UTC session and the prior block's high/low."""
    df = df.copy()
    block_start = df.index.floor("8h")
    codes, _ = pd.factorize(block_start)  # contiguous ints in time order
    df["session_id"] = (block_start.hour // 8).to_numpy()
    df["session_key"] = codes
    block_high = df.groupby("session_key")["high"].max()
    block_low = df.groupby("session_key")["low"].min()
    df["prior_high"] = df["session_key"].map(block_high.shift(1))
    df["prior_low"] = df["session_key"].map(block_low.shift(1))
    return df
```

- [ ] **Step 4: Run to verify it passes**

Run: `experiments/session_sweeps/.venv/bin/python -m pytest experiments/session_sweeps/tests -k "session_ids or prior_level or future_leak" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add experiments/session_sweeps/session_sweeps_backtest.py experiments/session_sweeps/tests/test_session_sweeps.py
git commit -m "feat(session_sweeps): 8h session tagging + causal prior-block levels"
```

---

### Task 3: `SessionSweepStrategy` — sweep-reject signals

**Files:**
- Modify: `experiments/session_sweeps/session_sweeps_backtest.py`
- Test: `experiments/session_sweeps/tests/test_session_sweeps.py`

**Interfaces:**
- Consumes: `tag_sessions` output.
- Produces: `SessionSweepStrategy(mode="reversal", fwd_horizon=16, secondary_horizon=8)` with `.generate_signals(df_tagged) -> pd.DataFrame` (columns `entry_ts, entry_price, direction`; `direction` ∈ `{+1,-1}`; one row per accepted signal, first qualifying bar per session).

- [ ] **Step 1: Write failing tests (long, short, clean-breakout/continuation, dedup)**

Add to `experiments/session_sweeps/tests/test_session_sweeps.py`:

```python
from session_sweeps_backtest import SessionSweepStrategy


def _two_block_df(trigger, filler=None):
    """Block0 (00:00) sets prior_high=110, prior_low=90. Block1 (08:00) holds the
    trigger bar (+ optional filler bar at 08:15)."""
    rows = [[100, 110, 90, 100, 1], trigger]
    times = [pd.Timestamp("2020-01-01 00:00", tz="UTC"),
             pd.Timestamp("2020-01-01 08:00", tz="UTC")]
    if filler is not None:
        rows.append(filler)
        times.append(pd.Timestamp("2020-01-01 08:15", tz="UTC"))
    return tag_sessions(_df(pd.DatetimeIndex(times), rows))


def test_reversal_fires_long():
    df = _two_block_df([100, 101, 85, 95, 1])  # low 85<90, close 95>90 -> LONG
    sig = SessionSweepStrategy().generate_signals(df)
    assert len(sig) == 1
    assert sig.iloc[0]["direction"] == 1
    assert sig.iloc[0]["entry_price"] == 95


def test_reversal_fires_short():
    df = _two_block_df([100, 115, 99, 105, 1])  # high 115>110, close 105<110 -> SHORT
    sig = SessionSweepStrategy().generate_signals(df)
    assert len(sig) == 1
    assert sig.iloc[0]["direction"] == -1


def test_clean_breakout_no_reversal_but_continuation():
    df = _two_block_df([100, 116, 100, 113, 1])  # closes 113 ABOVE 110: no rejection
    assert len(SessionSweepStrategy(mode="reversal").generate_signals(df)) == 0
    csig = SessionSweepStrategy(mode="continuation").generate_signals(df)
    assert len(csig) == 1
    assert csig.iloc[0]["direction"] == 1


def test_first_per_session_dedup():
    # two low-sweep-reject bars in block1 -> only the earlier (08:00) fires
    df = _two_block_df([100, 101, 85, 95, 1], filler=[100, 101, 80, 96, 1])
    sig = SessionSweepStrategy().generate_signals(df)
    assert len(sig) == 1
    assert sig.iloc[0]["entry_ts"] == pd.Timestamp("2020-01-01 08:00", tz="UTC")
```

- [ ] **Step 2: Run to verify it fails**

Run: `experiments/session_sweeps/.venv/bin/python -m pytest experiments/session_sweeps/tests -k "reversal_fires or breakout or dedup" -v`
Expected: FAIL with `cannot import name 'SessionSweepStrategy'`.

- [ ] **Step 3: Implement `SessionSweepStrategy`**

Add to `experiments/session_sweeps/session_sweeps_backtest.py`:

```python
class SessionSweepStrategy:
    """Fade (or, in continuation mode, follow) prior-session high/low sweeps.
    Frozen logic per DESIGN.md; parameterized only for robustness checks."""

    def __init__(self, mode="reversal", fwd_horizon=16, secondary_horizon=8):
        self.mode = mode
        self.fwd_horizon = fwd_horizon
        self.secondary_horizon = secondary_horizon

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        ph = df["prior_high"].to_numpy()
        pl = df["prior_low"].to_numpy()
        high = df["high"].to_numpy()
        low = df["low"].to_numpy()
        close = df["close"].to_numpy()

        with np.errstate(invalid="ignore"):  # NaN prior levels compare False cleanly
            if self.mode == "reversal":
                short_c = (high > ph) & (close < ph)   # swept high, rejected
                long_c = (low < pl) & (close > pl)     # swept low, rejected
            elif self.mode == "continuation":
                long_c = close > ph                    # broke and held above
                short_c = close < pl                   # broke and held below
            else:
                raise ValueError(f"unknown mode: {self.mode}")

        # First block has NaN prior levels -> invalid; drop ambiguous both-sided bars.
        valid = ~(np.isnan(ph) | np.isnan(pl))
        short_c = short_c & valid
        long_c = long_c & valid
        ambiguous = short_c & long_c
        short_c = short_c & ~ambiguous
        long_c = long_c & ~ambiguous
        direction = np.where(long_c, 1, np.where(short_c, -1, 0))

        keys = df["session_key"].to_numpy()
        seen = set()
        rows = []
        for i in np.flatnonzero(direction != 0):  # ascending -> earliest first
            k = keys[i]
            if k in seen:
                continue
            seen.add(k)
            rows.append({"entry_ts": df.index[i], "entry_price": float(close[i]),
                         "direction": int(direction[i])})
        return pd.DataFrame(rows, columns=["entry_ts", "entry_price", "direction"])
```

- [ ] **Step 4: Run to verify it passes**

Run: `experiments/session_sweeps/.venv/bin/python -m pytest experiments/session_sweeps/tests -k "reversal_fires or breakout or dedup" -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add experiments/session_sweeps/session_sweeps_backtest.py experiments/session_sweeps/tests/test_session_sweeps.py
git commit -m "feat(session_sweeps): SessionSweepStrategy sweep-reject signals"
```

---

### Task 4: Signed forward returns + block-bootstrap CI

**Files:**
- Modify: `experiments/session_sweeps/session_sweeps_backtest.py`
- Test: `experiments/session_sweeps/tests/test_session_sweeps.py`

**Interfaces:**
- Consumes: `df` (with `close`) and a signals DataFrame (`entry_ts, direction`).
- Produces:
  - `signed_forward_returns(df, signals, horizons=(8, 16)) -> dict[int, np.ndarray]` — per horizon `h`, `direction * ln(close[i+h]/close[i])` for each signal at position `i` with a full `i+h` bar (right-edge dropped).
  - `block_bootstrap_ci(returns, block=20, n_boot=10000, alpha=0.05, seed=0) -> tuple[float, float]` — moving-block bootstrap 95% CI on the mean; `(nan, nan)` if empty.

- [ ] **Step 1: Write failing tests**

Add to `experiments/session_sweeps/tests/test_session_sweeps.py`:

```python
from session_sweeps_backtest import signed_forward_returns, block_bootstrap_ci


def test_signed_forward_returns_sign_and_right_edge():
    idx = pd.date_range("2020-01-01", periods=5, freq="15min", tz="UTC")
    df = _df(idx, [[100, 100, 100, c, 1] for c in [100, 101, 102, 103, 104]])
    long_sig = pd.DataFrame([{"entry_ts": idx[0], "entry_price": 100, "direction": 1},
                             {"entry_ts": idx[4], "entry_price": 104, "direction": 1}])
    out = signed_forward_returns(df, long_sig, horizons=(2,))
    # idx0 -> +ln(102/100); idx4 has no idx6 -> dropped.
    assert len(out[2]) == 1
    assert out[2][0] == pytest.approx(np.log(102 / 100))

    short_sig = pd.DataFrame([{"entry_ts": idx[0], "entry_price": 100, "direction": -1}])
    outs = signed_forward_returns(df, short_sig, horizons=(2,))
    assert outs[2][0] == pytest.approx(-np.log(102 / 100))


def test_block_bootstrap_ci_non_degenerate_when_n_gt_block():
    rng = np.random.default_rng(1)
    r = rng.normal(0.001, 0.01, size=50)  # n=50 > block=20, varied
    lo, hi = block_bootstrap_ci(r, block=20, n_boot=500, seed=0)
    assert hi > lo  # degeneracy fix: real resampling variability


def test_block_bootstrap_ci_empty_is_nan():
    lo, hi = block_bootstrap_ci(np.array([]), block=20)
    assert np.isnan(lo) and np.isnan(hi)
```

- [ ] **Step 2: Run to verify it fails**

Run: `experiments/session_sweeps/.venv/bin/python -m pytest experiments/session_sweeps/tests -k "signed_forward or bootstrap" -v`
Expected: FAIL with `cannot import name 'signed_forward_returns'`.

- [ ] **Step 3: Implement both functions**

Add to `experiments/session_sweeps/session_sweeps_backtest.py`:

```python
def signed_forward_returns(df: pd.DataFrame, signals: pd.DataFrame,
                           horizons=(8, 16)) -> dict:
    closes = df["close"].to_numpy()
    n = len(closes)
    if len(signals) == 0:
        return {h: np.asarray([], dtype=float) for h in horizons}
    ipos = df.index.get_indexer(pd.DatetimeIndex(signals["entry_ts"]))
    dirs = signals["direction"].to_numpy()
    out = {}
    for h in horizons:
        ok = (ipos >= 0) & (ipos + h < n)
        ii = ipos[ok]
        out[h] = dirs[ok] * np.log(closes[ii + h] / closes[ii])
    return out


def block_bootstrap_ci(returns, block: int = 20, n_boot: int = 10000,
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

Run: `experiments/session_sweeps/.venv/bin/python -m pytest experiments/session_sweeps/tests -k "signed_forward or bootstrap" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add experiments/session_sweeps/session_sweeps_backtest.py experiments/session_sweeps/tests/test_session_sweeps.py
git commit -m "feat(session_sweeps): signed forward returns + hardened block-bootstrap CI"
```

---

### Task 5: Tear-sheet stats + verdict

**Files:**
- Modify: `experiments/session_sweeps/session_sweeps_backtest.py`
- Test: `experiments/session_sweeps/tests/test_session_sweeps.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `slice_stats(df_tagged, strategy) -> dict` — keys `n_signals, win_rate, mean_fwd_2h, mean_fwd_4h, ci2_lo, ci2_hi, ci4_lo, ci4_hi`. `win_rate` = fraction of signed 4h returns > 0 (nan if none).
  - `verdict(oos_stats, min_n=30) -> str` — `"PASS"` iff `n_signals >= min_n and ci4_lo > 0`; `"UNDERPOWERED — inconclusive"` iff `n_signals < min_n`; else `"FAIL"`.
  - `format_tear_sheet(label, stats) -> str`.

- [ ] **Step 1: Write failing tests**

Add to `experiments/session_sweeps/tests/test_session_sweeps.py`:

```python
from session_sweeps_backtest import slice_stats, verdict


def test_verdict_branches():
    assert verdict({"n_signals": 40, "ci4_lo": 0.001}, min_n=30) == "PASS"
    assert verdict({"n_signals": 40, "ci4_lo": -0.001}, min_n=30) == "FAIL"
    assert verdict({"n_signals": 10, "ci4_lo": 0.5}, min_n=30).startswith("UNDERPOWERED")


def test_slice_stats_keys_and_count():
    df = _two_block_df([100, 101, 85, 95, 1])  # one LONG signal
    stats = slice_stats(df, SessionSweepStrategy())
    for k in ["n_signals", "win_rate", "mean_fwd_2h", "mean_fwd_4h",
              "ci2_lo", "ci2_hi", "ci4_lo", "ci4_hi"]:
        assert k in stats
    assert stats["n_signals"] == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `experiments/session_sweeps/.venv/bin/python -m pytest experiments/session_sweeps/tests -k "verdict_branches or slice_stats" -v`
Expected: FAIL with `cannot import name 'slice_stats'`.

- [ ] **Step 3: Implement the tear-sheet functions**

Add to `experiments/session_sweeps/session_sweeps_backtest.py`:

```python
def slice_stats(df_tagged: pd.DataFrame, strategy: "SessionSweepStrategy") -> dict:
    sig = strategy.generate_signals(df_tagged)
    h2, h4 = strategy.secondary_horizon, strategy.fwd_horizon
    fwd = signed_forward_returns(df_tagged, sig, horizons=(h2, h4))
    r2, r4 = fwd[h2], fwd[h4]
    return {
        "n_signals": int(len(sig)),
        "win_rate": float(np.mean(r4 > 0)) if len(r4) else float("nan"),
        "mean_fwd_2h": float(np.mean(r2)) if len(r2) else float("nan"),
        "mean_fwd_4h": float(np.mean(r4)) if len(r4) else float("nan"),
        "ci2_lo": block_bootstrap_ci(r2)[0], "ci2_hi": block_bootstrap_ci(r2)[1],
        "ci4_lo": block_bootstrap_ci(r4)[0], "ci4_hi": block_bootstrap_ci(r4)[1],
    }


def verdict(oos_stats: dict, min_n: int = 30) -> str:
    if oos_stats["n_signals"] < min_n:
        return "UNDERPOWERED — inconclusive"
    return "PASS" if oos_stats["ci4_lo"] > 0 else "FAIL"


def format_tear_sheet(label: str, stats: dict) -> str:
    return (
        f"── {label} ──\n"
        f"  signals            : {stats['n_signals']}\n"
        f"  hit-rate (4H>0)    : {stats['win_rate']:.3f}   [descriptive]\n"
        f"  mean signed  2H    : {stats['mean_fwd_2h']:+.5f}\n"
        f"  mean signed  4H    : {stats['mean_fwd_4h']:+.5f}\n"
        f"  95% CI  2H         : [{stats['ci2_lo']:+.5f}, {stats['ci2_hi']:+.5f}]\n"
        f"  95% CI  4H (GATE)  : [{stats['ci4_lo']:+.5f}, {stats['ci4_hi']:+.5f}]\n"
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `experiments/session_sweeps/.venv/bin/python -m pytest experiments/session_sweeps/tests -k "verdict_branches or slice_stats" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add experiments/session_sweeps/session_sweeps_backtest.py experiments/session_sweeps/tests/test_session_sweeps.py
git commit -m "feat(session_sweeps): slice tear-sheet stats + confirmatory verdict"
```

---

### Task 6: CLI wiring + full-suite green

**Files:**
- Modify: `experiments/session_sweeps/session_sweeps_backtest.py`
- Test: `experiments/session_sweeps/tests/test_session_sweeps.py`

**Interfaces:**
- Consumes: `load_data`, `tag_sessions`, `SessionSweepStrategy`, `slice_stats`, `verdict`, `format_tear_sheet`.
- Produces: `main(argv=None) -> int` and a `__main__` guard. Loads, tags on the FULL series (so the first OOS block's prior level comes legitimately from the last in-sample block), splits at `--oos-cutoff` (in-sample `< cutoff`, OOS `>= cutoff`), prints both tear-sheets + the verdict off the OOS 4h CI.

- [ ] **Step 1: Write failing CLI smoke test**

Add to `experiments/session_sweeps/tests/test_session_sweeps.py`:

```python
from session_sweeps_backtest import main


def test_main_runs_and_prints_verdict(tmp_path, capsys):
    # 200 flat 15m bars across 2 days -> no sweeps -> underpowered, but must print.
    n = 200
    base = pd.Timestamp("2020-01-01", tz="UTC")
    idx = pd.date_range(base, periods=n, freq="15min", tz="UTC")
    rows = [[int(idx[i].timestamp() * 1000), 100, 100, 100, 100, 1] for i in range(n)]
    p = tmp_path / "o.csv"
    pd.DataFrame(rows).to_csv(p, header=False, index=False)

    rc = main(["--ohlcv", str(p), "--start", "2020-01-01",
               "--oos-cutoff", "2020-01-02"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "IN-SAMPLE" in out and "SEALED OOS" in out and "VERDICT" in out
```

- [ ] **Step 2: Run to verify it fails**

Run: `experiments/session_sweeps/.venv/bin/python -m pytest experiments/session_sweeps/tests -k "main_runs" -v`
Expected: FAIL with `cannot import name 'main'`.

- [ ] **Step 3: Implement `main` + argparse**

Add to `experiments/session_sweeps/session_sweeps_backtest.py`:

```python
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Session-Sweep fade backtest")
    p.add_argument("--ohlcv", default=".backtest_cache/BTCUSDT_15m.csv")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--oos-cutoff", default="2024-07-01")
    p.add_argument("--mode", choices=["reversal", "continuation"], default="reversal")
    p.add_argument("--fwd-horizon", type=int, default=16)
    p.add_argument("--secondary-horizon", type=int, default=8)
    p.add_argument("--min-oos", type=int, default=30)
    args = p.parse_args(argv)

    df = load_data(args.ohlcv, start=args.start)
    tagged = tag_sessions(df)  # tag on full series (prior level crosses split legitimately)
    strat = SessionSweepStrategy(mode=args.mode, fwd_horizon=args.fwd_horizon,
                                 secondary_horizon=args.secondary_horizon)
    cutoff = pd.Timestamp(args.oos_cutoff, tz="UTC")
    in_stats = slice_stats(tagged[tagged.index < cutoff], strat)
    oos_stats = slice_stats(tagged[tagged.index >= cutoff], strat)
    v = verdict(oos_stats, min_n=args.min_oos)

    print(f"Session Sweeps — mode={args.mode} cutoff={args.oos_cutoff}")
    print(format_tear_sheet("IN-SAMPLE (descriptive)", in_stats))
    print(format_tear_sheet("SEALED OOS (confirmatory)", oos_stats))
    print(f"VERDICT (sealed OOS, 4H CI vs 0): {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the CLI smoke test, then the FULL suite**

Run: `experiments/session_sweeps/.venv/bin/python -m pytest experiments/session_sweeps/tests -v`
Expected: PASS (all ~14 tests).

- [ ] **Step 5: Commit**

```bash
git add experiments/session_sweeps/session_sweeps_backtest.py experiments/session_sweeps/tests/test_session_sweeps.py
git commit -m "feat(session_sweeps): CLI + in-sample/sealed-OOS tear-sheet run"
```

---

### Task 7: Registered run + RESULTS.md (opens the seal ONCE)

**Files:**
- Create: `experiments/session_sweeps/RESULTS.md`

**Interfaces:**
- Consumes: the finished CLI against the real cache.
- Produces: `RESULTS.md` — both tear-sheets, the verdict, n-counts, CIs, the `--mode continuation` robustness read, and an honest interpretation per DESIGN §0.

- [ ] **Step 1: Run the registered (primary) configuration**

```bash
experiments/session_sweeps/.venv/bin/python experiments/session_sweeps/session_sweeps_backtest.py \
  --ohlcv .backtest_cache/BTCUSDT_15m.csv \
  --oos-cutoff 2024-07-01 --mode reversal
```

Capture the full stdout. This is the **one** sealed-OOS look — do not re-run with altered params to change the verdict.

- [ ] **Step 2: Run the robustness variant**

```bash
experiments/session_sweeps/.venv/bin/python experiments/session_sweeps/session_sweeps_backtest.py \
  --ohlcv .backtest_cache/BTCUSDT_15m.csv \
  --oos-cutoff 2024-07-01 --mode continuation
```

- [ ] **Step 3: Write `RESULTS.md`**

Create `experiments/session_sweeps/RESULTS.md` with: the primary run's two tear-sheets verbatim, the VERDICT line, n_signals for each slice, the 4H (gate) and 2H CIs, the continuation-mode robustness read, and a one-paragraph honest interpretation consistent with DESIGN §0 (candidate vs. dead; note UNDERPOWERED explicitly if n_OOS < 30; no deployment claim from this study alone).

- [ ] **Step 4: Commit**

```bash
git add experiments/session_sweeps/RESULTS.md
git commit -m "docs(session_sweeps): registered-run results + sealed-OOS verdict"
```

---

## Notes for the executor

- Run pytest from the **repo root** using the venv interpreter; `tests/conftest.py` puts the module on `sys.path`.
- Keep DESIGN.md authoritative — if any step here contradicts a frozen value there, DESIGN.md wins and the discrepancy is a plan bug to flag, not silently resolve.
- Do not add network calls, extra dependencies, or wire this into the main engine.
