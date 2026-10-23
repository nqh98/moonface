# vrp_measure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `vrp_measure` measurement lane — fix the broken DVOL fetcher, then implement a run-once pipeline that measures whether BTC 30-day implied variance (Deribit DVOL) sits persistently above subsequent realized variance, calibrated against two synthetic nulls.

**Architecture:** Mirrors `carry_measure` exactly. Pure functions in `src/moonface/research/vrp_measure.py` (no network, no I/O beyond pinned CSVs); a thin run-once CLI in `tools/vrp_measure.py` that hash-freezes inputs and refuses to run if `RESULTS.md` exists; a separate one-time network script `tools/vrp_fetch_dvol.py`. Realized variance over ~3790 overlapping windows is computed via prefix sums so the 1000 null runs stay tractable in pure Python.

**Tech Stack:** Python 3.11+, stdlib only (`csv`, `math`, `random`, `urllib`, `hashlib`, `json`). pytest + ruff for dev.

**Spec:** `experiments/vrp_measure/SPEC.md` (committed `cb93088`). The spec is authoritative. Where this plan and the spec disagree, stop and ask.

## Global Constraints

- **numpy is NOT available.** `pyproject.toml` marks it an optional extra for `pathsig` only: "the core library does not need it". Everything here is stdlib. Do not add a dependency.
- **No network in any test, ever.** Hermetic tests are a repo convention (the `confluence-engine` non-hermetic test gotcha). `fetch_dvol` and the fetch script take an injectable `get_json` — tests always inject a fake.
- **Never interpolate, never zero-fill.** Missing data raises. This is repo-wide (`carry_measure` §4, `load_bars_1h`).
- **This lane is descriptive.** No forecasting, no optimization, no verdict, no trading recommendation in any output string. SPEC §0.1.
- **Do NOT run the pipeline and do NOT run the fetch script.** Both are human-gated. This plan builds and tests them only. Task 8 ends with the CLI implemented and unit-tested against fixtures — never against the real pinned inputs.
- Line length 100 (`[tool.ruff]`). Target py311.
- Tests use `unittest.TestCase` executed via pytest, matching `tests/test_carry_measure.py`.
- Commit after every task. Never chain `git add && git commit` — stage, verify `git diff --cached --stat`, then commit.
- **No AI attribution trailers in commit messages** (global rule).

### Frozen constants (SPEC §3.1, §4, §5 — copy verbatim)

```python
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
DVOL_INTERVAL_MS = 43_200_000          # 12h
RV_HORIZON_HOURS = 720                 # 30 days
ANNUALIZATION_HOURS = 8760.0           # 24/7/365

WINDOW_START_MS = 1_616_544_000_000    # 2021-03-24 00:00 UTC
WINDOW_END_MS = 1_780_228_800_000      # 2026-05-31 12:00 UTC

BLOCK_LEN = 60                         # 60 DVOL points = 30 days
N_RESAMPLES = 2000
BOOTSTRAP_SEED = 20260717
NULL_SEED_GAUSS = 20270101
NULL_SEED_T = 20280101
N_NULL_SEEDS = 500
T_DF = 4
DISJOINT_STRIDE_MS = 30 * DAY_MS
```

### File structure

| File | Responsibility |
|---|---|
| `src/moonface/research/exogenous/deribit_dvol.py` | **modify** — backward pagination + seconds/ms unit fix |
| `tests/research/exogenous/test_deribit_dvol.py` | **rewrite** — fake mimics Deribit's real most-recent-N behavior |
| `tools/vrp_fetch_dvol.py` | **create** — one-time network script (built, not run) |
| `src/moonface/research/vrp_measure.py` | **create** — all pure functions |
| `tools/vrp_measure.py` | **create** — run-once CLI, hash freeze |
| `tests/test_vrp_measure.py` | **create** — all lane tests |
| `tests/fixtures/vrp_measure/` | **create** — synthetic fixture CSVs |

---

### Task 1: Fix `fetch_dvol` — backward pagination

**Files:**
- Modify: `src/moonface/research/exogenous/deribit_dvol.py:37-60`
- Test: `tests/research/exogenous/test_deribit_dvol.py` (rewrite)

**Interfaces:**
- Consumes: nothing.
- Produces: `fetch_dvol(currency: str, start_ms: int, end_ms: int, cache_dir: str, resolution: int = 43200, get_json=_get_json) -> list[DvolPoint]` — signature unchanged, behavior fixed. `DvolPoint(ts_ms: int, open: float, high: float, low: float, close: float)` unchanged.

**Background (SPEC §2.1):** Deribit's `get_volatility_index_data` returns **the most recent 1000 points** inside the requested window, not the earliest. The current loop pages *forward* from `start`, so page 1 already lands at the end of history and the loop exits with only the last 1000 points (= 500 days at 12h). The existing test's fake returns pages ascending from `start`, encoding the same wrong model as the code — which is why the bug survived. Fix: page **backward** on `end_timestamp`.

- [ ] **Step 1: Write the failing test**

Replace the entire contents of `tests/research/exogenous/test_deribit_dvol.py`:

```python
"""Tests for the Deribit DVOL fetcher.

The fake here mimics Deribit's ACTUAL behavior: get_volatility_index_data
returns the MOST RECENT `page_size` points inside [start, end], not the
earliest. The previous version of this test returned pages ascending from
`start`, which encoded the same wrong model as the bug it was meant to catch
(SPEC vrp_measure section 2.1).
"""
from __future__ import annotations

import urllib.parse

from moonface.research.exogenous.deribit_dvol import (
    DvolPoint,
    fetch_dvol,
    parse_dvol_payload,
)

RES = 43200
RES_MS = RES * 1000


class FakeDeribit:
    """Serves from a fixed universe of 12h bars, most-recent-N first."""

    def __init__(self, first_ts: int, n_bars: int, page_size: int = 1000):
        self.bars = [
            [first_ts + i * RES_MS, float(i), float(i), float(i), float(i)]
            for i in range(n_bars)
        ]
        self.page_size = page_size
        self.calls = 0

    def __call__(self, url: str) -> dict:
        self.calls += 1
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        start = int(q["start_timestamp"][0])
        end = int(q["end_timestamp"][0])
        window = [b for b in self.bars if start <= b[0] <= end]
        return {"result": {"data": window[-self.page_size:]}}


def test_parse_payload():
    payload = {"result": {"data": [
        [1739232000000, 52.4, 54.67, 52.08, 53.23],
        [1739275200000, 53.23, 54.0, 52.9, 53.8],
    ]}}
    pts = parse_dvol_payload(payload)
    assert pts[0] == DvolPoint(1739232000000, 52.4, 54.67, 52.08, 53.23)
    assert len(pts) == 2


def test_fetch_walks_back_past_one_page(tmp_path):
    """The bug: a single page is the LAST 1000 bars, so forward paging stops
    there. 2500 bars must require 3 backward pages and return all of them."""
    fake = FakeDeribit(first_ts=1_000_000_000_000, n_bars=2500, page_size=1000)
    pts = fetch_dvol("BTC", 1_000_000_000_000, 1_000_000_000_000 + 2500 * RES_MS,
                     str(tmp_path), resolution=RES, get_json=fake)
    assert len(pts) == 2500, f"got {len(pts)} bars (forward-paging bug returns 1000)"
    assert [p.ts_ms for p in pts] == sorted(p.ts_ms for p in pts)
    assert pts[0].ts_ms == 1_000_000_000_000
    assert fake.calls >= 3


def test_fetch_dedups_overlapping_pages(tmp_path):
    fake = FakeDeribit(first_ts=1_000_000_000_000, n_bars=1500, page_size=1000)
    pts = fetch_dvol("BTC", 1_000_000_000_000, 1_000_000_000_000 + 1500 * RES_MS,
                     str(tmp_path), resolution=RES, get_json=fake)
    ts = [p.ts_ms for p in pts]
    assert len(ts) == len(set(ts)) == 1500


def test_fetch_single_page_terminates(tmp_path):
    fake = FakeDeribit(first_ts=1_000_000_000_000, n_bars=10, page_size=1000)
    pts = fetch_dvol("BTC", 1_000_000_000_000, 1_000_000_000_000 + 10 * RES_MS,
                     str(tmp_path), resolution=RES, get_json=fake)
    assert len(pts) == 10
    assert fake.calls == 2  # one full page, one empty page proving exhaustion


def test_fetch_uses_cache_and_skips_network(tmp_path):
    fake = FakeDeribit(first_ts=1_000_000_000_000, n_bars=10)
    fetch_dvol("BTC", 1_000_000_000_000, 1_000_000_000_000 + 10 * RES_MS,
               str(tmp_path), resolution=RES, get_json=fake)
    before = fake.calls

    def boom(url):
        raise AssertionError("network hit despite cache")

    pts = fetch_dvol("BTC", 1_000_000_000_000, 1_000_000_000_000 + 10 * RES_MS,
                     str(tmp_path), resolution=RES, get_json=boom)
    assert len(pts) == 10
    assert fake.calls == before
```

- [ ] **Step 2: Run the test and confirm it fails against the CURRENT code**

Run: `.venv/bin/python -m pytest tests/research/exogenous/test_deribit_dvol.py -v`

Expected: `test_fetch_walks_back_past_one_page` **FAILS** with `got 1000 bars (forward-paging bug returns 1000)`. This failure is the whole point of the task — it is the proof the bug is real and the old test was blind to it. Do not proceed until you have seen it.

- [ ] **Step 3: Implement the fix**

Replace `fetch_dvol` in `src/moonface/research/exogenous/deribit_dvol.py` (lines 37-60) with:

```python
def fetch_dvol(currency: str, start_ms: int, end_ms: int, cache_dir: str,
               resolution: int = 43200, get_json=_get_json) -> list[DvolPoint]:
    """All DVOL bars in [start_ms, end_ms], ascending, cached permanently.

    Paginates BACKWARD on end_timestamp: the API returns the most RECENT
    ~1000 points inside the requested window, so paging forward from
    `start_ms` lands on the final page immediately and terminates having seen
    only the tail (SPEC vrp_measure section 2.1). `resolution` is in SECONDS;
    timestamps are in MILLISECONDS.
    """
    path = _cache_path(cache_dir, currency, resolution)
    if path.exists():
        with path.open(newline="") as fh:
            return [DvolPoint(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]))
                    for r in csv.reader(fh)]
    resolution_ms = resolution * 1000
    seen: dict[int, DvolPoint] = {}
    cursor = end_ms
    while cursor >= start_ms:
        page = parse_dvol_payload(get_json(
            DVOL_URL.format(cur=currency, start=start_ms, end=cursor, res=resolution)))
        if not page:
            break
        fresh = [p for p in page if p.ts_ms not in seen]
        for p in page:
            seen[p.ts_ms] = p
        if not fresh:  # page is entirely re-served data: no backward progress
            break
        cursor = min(p.ts_ms for p in page) - resolution_ms
    pts = [seen[k] for k in sorted(seen)]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        for p in pts:
            w.writerow([p.ts_ms, p.open, p.high, p.low, p.close])
    return pts
```

Note `cursor = min(...) - resolution_ms` rather than `- 1`: it steps a whole bar back, so a page whose earliest bar is re-served cannot loop. The `fresh` guard is the belt-and-braces termination check.

- [ ] **Step 4: Run the tests and verify they pass**

Run: `.venv/bin/python -m pytest tests/research/exogenous/test_deribit_dvol.py -v`
Expected: 5 passed.

- [ ] **Step 5: Verify nothing else broke**

Run: `.venv/bin/python -m pytest tests/research/ -q && .venv/bin/ruff check src/moonface/research/exogenous/deribit_dvol.py`

Expected: all pass, no lint errors. `tools/exogenous_btc.py:86` is the only other caller; `experiments/exogenous/STAGE01_RESULT.md:30-34` confirms DVOL is not screened in v1, so its frozen Stage-1 result does not depend on this data. Do **not** retro-edit `STAGE01_RESULT.md`.

- [ ] **Step 6: Commit**

```bash
git add src/moonface/research/exogenous/deribit_dvol.py tests/research/exogenous/test_deribit_dvol.py
git diff --cached --stat
git commit -m "fix(deribit_dvol): paginate backward; the API returns most-recent-N

get_volatility_index_data returns the most recent ~1000 points inside the
requested window, not the earliest, so paging forward from start_ms landed on
the final page immediately and returned only the tail (499 days of a real
1918). Also fixes resolution being in seconds while timestamps are in ms.

The old test's fake served pages ascending from start, encoding the same wrong
model as the code -- both agreed and the bug was invisible. The new fake serves
most-recent-N like the real API and fails against the old implementation."
```

---

### Task 2: `tools/vrp_fetch_dvol.py` — one-time fetch script

**Files:**
- Create: `tools/vrp_fetch_dvol.py`
- Test: `tests/test_vrp_measure.py` (create; fetch-script tests only in this task)

**Interfaces:**
- Consumes: `fetch_dvol` from Task 1.
- Produces: `drop_incomplete_tail(points: list[DvolPoint], now_ms: int, interval_ms: int) -> list[DvolPoint]`; `check_cadence(points: list[DvolPoint], interval_ms: int) -> None` (raises `GapError`); `main(argv: list[str] | None = None) -> int`.

**Background (SPEC §3.2, §4.1.1):** The API returns the currently-forming bar; a bar stamped `t` is complete only once wall-clock `>= t + 12h`. Without dropping it the fetch is not reproducible. Expected output: 3837 points, 2021-03-24 → 2026-06-24.

- [ ] **Step 1: Write the failing test**

Create `tests/test_vrp_measure.py`:

```python
"""Tests for the vrp_measure measurement lane.

See experiments/vrp_measure/SPEC.md. Descriptive accounting: no forecasting,
no optimization. All fixtures synthetic. No network anywhere.
"""
from __future__ import annotations

import unittest

from moonface.research.exogenous.deribit_dvol import DvolPoint
from tools.vrp_fetch_dvol import check_cadence, drop_incomplete_tail

RES_MS = 43_200_000


def _pts(first_ts: int, n: int) -> list[DvolPoint]:
    return [DvolPoint(first_ts + i * RES_MS, 50.0, 51.0, 49.0, 50.5) for i in range(n)]


class TestDropIncompleteTail(unittest.TestCase):
    def test_drops_bar_still_forming(self):
        pts = _pts(1_000_000_000_000, 3)
        last = pts[-1].ts_ms
        kept = drop_incomplete_tail(pts, now_ms=last + RES_MS - 1, interval_ms=RES_MS)
        self.assertEqual(len(kept), 2)
        self.assertEqual(kept[-1].ts_ms, last - RES_MS)

    def test_keeps_bar_exactly_complete(self):
        pts = _pts(1_000_000_000_000, 3)
        last = pts[-1].ts_ms
        kept = drop_incomplete_tail(pts, now_ms=last + RES_MS, interval_ms=RES_MS)
        self.assertEqual(len(kept), 3)

    def test_empty_input(self):
        self.assertEqual(drop_incomplete_tail([], now_ms=1, interval_ms=RES_MS), [])


class TestCheckCadence(unittest.TestCase):
    def test_contiguous_passes(self):
        check_cadence(_pts(1_000_000_000_000, 5), RES_MS)  # must not raise

    def test_gap_raises(self):
        pts = _pts(1_000_000_000_000, 5)
        del pts[2]
        with self.assertRaises(Exception) as ctx:
            check_cadence(pts, RES_MS)
        self.assertIn("step", str(ctx.exception))

    def test_too_few_points_raises(self):
        with self.assertRaises(Exception):
            check_cadence(_pts(1_000_000_000_000, 1), RES_MS)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.vrp_fetch_dvol'`

- [ ] **Step 3: Write the implementation**

Create `tools/vrp_fetch_dvol.py`:

```python
#!/usr/bin/env python
"""vrp_measure one-time DVOL fetch. RUN ONCE, BY HAND.

Fetches the full Deribit BTC DVOL history to
cache/exogenous/dvol_BTC_43200_full.csv. Does NOT touch
cache/exogenous/dvol_BTC_43200.csv -- that is a frozen `exogenous` lane
artifact (SPEC vrp_measure section 3).

Expected: 3837 points, 2021-03-24 -> 2026-06-24. Hard-fails on any cadence
gap or a span under 1900 days -- stop and ask, do not work around it.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from moonface.research.exogenous.deribit_dvol import DvolPoint, fetch_dvol

RESOLUTION = 43200
RESOLUTION_MS = RESOLUTION * 1000
DAY_MS = 86_400_000
MIN_SPAN_DAYS = 1900
OUT_DIR = REPO / "cache/exogenous"
OUT_NAME = "dvol_BTC_43200_full.csv"
FETCH_START_MS = 1_483_228_800_000   # 2017-01-01, safely before DVOL inception
FETCH_END_MS = 1_782_259_200_000     # 2026-06-24 00:00 UTC (SPEC section 3.2)


class GapError(ValueError):
    """The fetched DVOL series is not a contiguous 12h cadence."""


def drop_incomplete_tail(points: list[DvolPoint], now_ms: int,
                         interval_ms: int = RESOLUTION_MS) -> list[DvolPoint]:
    """Drop trailing bars still forming. A bar stamped t is complete only once
    now >= t + interval (the API serves the current, partial bar)."""
    return [p for p in points if p.ts_ms + interval_ms <= now_ms]


def check_cadence(points: list[DvolPoint], interval_ms: int = RESOLUTION_MS) -> None:
    """Strict `interval_ms` spacing, ascending. Raises GapError otherwise."""
    if len(points) < 2:
        raise GapError(f"need >= 2 points, got {len(points)}")
    for prev, cur in zip(points, points[1:]):
        step = cur.ts_ms - prev.ts_ms
        if step != interval_ms:
            raise GapError(f"{step} ms step after {prev.ts_ms} (want {interval_ms})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", default=str(OUT_DIR))
    parser.add_argument("--start-ms", type=int, default=FETCH_START_MS)
    parser.add_argument("--end-ms", type=int, default=FETCH_END_MS)
    args = parser.parse_args(argv)

    out = Path(args.cache_dir) / OUT_NAME
    if out.exists():
        print(f"REFUSING: {out} exists (one-time fetch; delete deliberately to redo)")
        return 1

    tmp_dir = Path(args.cache_dir) / "_vrp_fetch_tmp"
    points = fetch_dvol("BTC", args.start_ms, args.end_ms, str(tmp_dir),
                        resolution=RESOLUTION)
    points = drop_incomplete_tail(points, now_ms=int(time.time() * 1000))
    check_cadence(points)

    span_days = (points[-1].ts_ms - points[0].ts_ms) / DAY_MS
    if span_days < MIN_SPAN_DAYS:
        print(f"STOP-AND-ASK: span {span_days:.1f}d < {MIN_SPAN_DAYS}d "
              f"({len(points)} points). Do not proceed.")
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as fh:
        for p in points:
            fh.write(f"{p.ts_ms},{p.open},{p.high},{p.low},{p.close}\n")
    print(f"wrote {out}: {len(points)} points, span {span_days:.1f}d")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/vrp_fetch_dvol.py tests/test_vrp_measure.py
git diff --cached --stat
git commit -m "feat(vrp_measure): one-time DVOL fetch script (SPEC 3.2)

Writes the corrected full DVOL history to a new path; never touches the frozen
exogenous lane's truncated cache. Drops the still-forming trailing bar (the API
serves it) so the fetch is reproducible, and hard-fails on any cadence gap or a
span under 1900 days.

Built, not run: the fetch is human-gated."
```

---

### Task 3: Loaders — `load_dvol`, `load_spot_closes`

**Files:**
- Create: `src/moonface/research/vrp_measure.py`
- Create: `tests/fixtures/vrp_measure/` (fixture written by the test itself into tmp)
- Modify: `tests/test_vrp_measure.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `GapError(ValueError)`
  - `load_dvol(path: str, start_ms: int, end_ms: int) -> list[tuple[int, float]]` — `(ts_ms, open)` pairs, strict 12h cadence, first == `start_ms`, last == `end_ms`.
  - `load_spot_closes(path: str, first_ms: int, last_ms: int) -> dict[int, float]` — `bar_open_ts -> close`, contiguous 1h, first == `first_ms`, last == `last_ms`.

**Background:** `load_dvol` returns the bar **open**, not close — SPEC §4.1.1: Deribit stamps bars at their start, so `close(t)` is not observable until `t+12h` and using it would be a 12h look-ahead. `open(t) == close(t-12h)` so this costs nothing.

Spot CSV row format (`.backtest_cache/BTC_USDT_1h.csv`): `ts_ms,open,high,low,close,volume` — close is `row[4]`. DVOL CSV row format: `ts_ms,open,high,low,close` — open is `row[1]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_vrp_measure.py`:

```python
import csv as _csv
from pathlib import Path as _Path
from tempfile import TemporaryDirectory

from moonface.research.vrp_measure import (
    DVOL_INTERVAL_MS,
    HOUR_MS,
    GapError as VrpGapError,
    load_dvol,
    load_spot_closes,
)


def _write_dvol(path, first_ts, n, step=DVOL_INTERVAL_MS, skip=()):
    with open(path, "w", newline="") as fh:
        w = _csv.writer(fh)
        for i in range(n):
            if i in skip:
                continue
            ts = first_ts + i * step
            w.writerow([ts, 50.0 + i, 52.0, 48.0, 50.0 + i + 1])


def _write_spot(path, first_ts, n, skip=()):
    with open(path, "w", newline="") as fh:
        w = _csv.writer(fh)
        for i in range(n):
            if i in skip:
                continue
            ts = first_ts + i * HOUR_MS
            w.writerow([ts, 100.0 + i, 101.0, 99.0, 100.0 + i + 0.5, 1.0])


class TestLoadDvol(unittest.TestCase):
    def test_returns_open_not_close(self):
        with TemporaryDirectory() as d:
            p = str(_Path(d) / "dvol.csv")
            _write_dvol(p, 1_000_000_000_000, 4)
            got = load_dvol(p, 1_000_000_000_000,
                            1_000_000_000_000 + 3 * DVOL_INTERVAL_MS)
            self.assertEqual([v for _, v in got], [50.0, 51.0, 52.0, 53.0])

    def test_gap_raises(self):
        with TemporaryDirectory() as d:
            p = str(_Path(d) / "dvol.csv")
            _write_dvol(p, 1_000_000_000_000, 5, skip=(2,))
            with self.assertRaises(VrpGapError):
                load_dvol(p, 1_000_000_000_000,
                          1_000_000_000_000 + 4 * DVOL_INTERVAL_MS)

    def test_wrong_first_raises(self):
        with TemporaryDirectory() as d:
            p = str(_Path(d) / "dvol.csv")
            _write_dvol(p, 1_000_000_000_000, 4)
            with self.assertRaises(VrpGapError):
                load_dvol(p, 1_000_000_000_000 - DVOL_INTERVAL_MS,
                          1_000_000_000_000 + 3 * DVOL_INTERVAL_MS)


class TestLoadSpotCloses(unittest.TestCase):
    def test_reads_close_column(self):
        with TemporaryDirectory() as d:
            p = str(_Path(d) / "spot.csv")
            _write_spot(p, 1_000_000_000_000, 3)
            got = load_spot_closes(p, 1_000_000_000_000,
                                   1_000_000_000_000 + 2 * HOUR_MS)
            self.assertEqual(got[1_000_000_000_000], 100.5)
            self.assertEqual(len(got), 3)

    def test_gap_raises(self):
        with TemporaryDirectory() as d:
            p = str(_Path(d) / "spot.csv")
            _write_spot(p, 1_000_000_000_000, 5, skip=(2,))
            with self.assertRaises(VrpGapError):
                load_spot_closes(p, 1_000_000_000_000,
                                 1_000_000_000_000 + 4 * HOUR_MS)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.research.vrp_measure'`

- [ ] **Step 3: Write the implementation**

Create `src/moonface/research/vrp_measure.py`:

```python
"""vrp_measure: BTC variance risk premium, measurement lane.

Descriptive accounting over pinned historical data (experiments/vrp_measure/
SPEC.md). Nothing is predicted; there is no verdict and no trading rule here.

Pure functions only: no network imports, no I/O beyond reading the pinned
CSVs. stdlib only -- numpy is an optional pathsig extra and is NOT available.
"""
from __future__ import annotations

import csv

HOUR_MS = 3_600_000
DAY_MS = 86_400_000
DVOL_INTERVAL_MS = 43_200_000          # 12h
RV_HORIZON_HOURS = 720                 # 30 days
ANNUALIZATION_HOURS = 8760.0           # BTC trades 24/7/365

WINDOW_START_MS = 1_616_544_000_000    # 2021-03-24 00:00 UTC
WINDOW_END_MS = 1_780_228_800_000      # 2026-05-31 12:00 UTC

BLOCK_LEN = 60                         # 60 DVOL points = 30 days
N_RESAMPLES = 2000
BOOTSTRAP_SEED = 20260717
NULL_SEED_GAUSS = 20270101
NULL_SEED_T = 20280101
N_NULL_SEEDS = 500
T_DF = 4
DISJOINT_STRIDE_MS = 30 * DAY_MS

# Binance BTC/USDT spot 1h bars inside this lane's window that are NOT Binance
# data: they are Coinbase BTC/USD candles spliced in under the human-approved
# 2026-07-16 resolution of a real exchange-side gap. Source of truth is
# SPOT_GAP_SUBSTITUTIONS_UTC in tools/carry_measure.py -- duplicated here as
# ms, restricted to this window, because src/ must not import tools/ and
# carry_measure is a frozen run-once lane whose list can no longer change.
# SPEC section 3.3.
SPLICED_BAR_TS_MS = frozenset((
    1618884000000,  # 2021-04-20 02:00
    1618887600000,  # 2021-04-20 03:00
    1619326800000,  # 2021-04-25 05:00
    1619330400000,  # 2021-04-25 06:00
    1619334000000,  # 2021-04-25 07:00
    1628820000000,  # 2021-08-13 02:00
    1628823600000,  # 2021-08-13 03:00
    1628827200000,  # 2021-08-13 04:00
    1628830800000,  # 2021-08-13 05:00
    1632898800000,  # 2021-09-29 07:00
    1632902400000,  # 2021-09-29 08:00
    1679662800000,  # 2023-03-24 13:00
))


class GapError(ValueError):
    """A pinned input series is missing points inside the window."""


def load_dvol(path: str, start_ms: int, end_ms: int) -> list[tuple[int, float]]:
    """(ts_ms, dvol_open) at strict 12h cadence covering [start_ms, end_ms].

    Returns the bar OPEN, not the close: Deribit stamps bars at their start,
    so close(t) is not observable until t+12h and using it would look ahead
    into rv_var(t)'s own window (SPEC section 4.1.1). open(t) == close(t-12h),
    so this costs nothing.
    """
    points: list[tuple[int, float]] = []
    with open(path, newline="") as handle:
        for row in csv.reader(handle):
            ts = int(float(row[0]))
            if start_ms <= ts <= end_ms:
                points.append((ts, float(row[1])))
    if not points:
        raise GapError(f"{path}: no DVOL points in window")
    for prev, cur in zip(points, points[1:]):
        step = cur[0] - prev[0]
        if step != DVOL_INTERVAL_MS:
            raise GapError(f"{path}: {step} ms step after {prev[0]} (want 12h)")
    if points[0][0] != start_ms:
        raise GapError(f"{path}: first point {points[0][0]} != {start_ms}")
    if points[-1][0] != end_ms:
        raise GapError(f"{path}: last point {points[-1][0]} != {end_ms}")
    return points


def load_spot_closes(path: str, first_ms: int, last_ms: int) -> dict[int, float]:
    """bar-open ts -> close, contiguous 1h bars covering [first_ms, last_ms].

    Missing bars are a GapError -- never interpolated (repo convention).
    """
    closes: dict[int, float] = {}
    prev: int | None = None
    with open(path, newline="") as handle:
        for row in csv.reader(handle):
            ts = int(float(row[0]))
            if ts < first_ms or ts > last_ms:
                continue
            if prev is not None and ts - prev != HOUR_MS:
                raise GapError(f"{path}: {ts - prev} ms step after {prev} (want 1h)")
            prev = ts
            closes[ts] = float(row[4])
    if not closes:
        raise GapError(f"{path}: no bars in window")
    first, last = min(closes), max(closes)
    if first != first_ms:
        raise GapError(f"{path}: first bar {first} != {first_ms}")
    if last != last_ms:
        raise GapError(f"{path}: last bar {last} != {last_ms}")
    return closes
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/vrp_measure.py tests/test_vrp_measure.py
git diff --cached --stat
git commit -m "feat(vrp_measure): pinned-input loaders with gap validation

load_dvol returns the bar OPEN, not close: Deribit stamps bars at their start,
so close(t) is unobservable until t+12h and would look ahead into rv_var(t)'s
own window (SPEC 4.1.1). open(t) == close(t-12h), so it costs nothing.

Freezes the window constants and the 12 spliced spot bars inside the window."
```

---

### Task 4: Splice-aware return series and `rv_var` via prefix sums

**Files:**
- Modify: `src/moonface/research/vrp_measure.py`
- Modify: `tests/test_vrp_measure.py`

**Interfaces:**
- Consumes: `GapError`, `SPLICED_BAR_TS_MS`, `HOUR_MS`, `RV_HORIZON_HOURS`, `ANNUALIZATION_HOURS` (Task 3).
- Produces:
  - `ReturnSeries` — frozen dataclass with fields `first_ts: int`, `r2_prefix: tuple[float, ...]`, `cnt_prefix: tuple[int, ...]`; method `index_of(ts: int) -> int`.
  - `build_return_series(closes: dict[int, float], first_ret_ts: int, last_ret_ts: int, spliced: frozenset[int] = SPLICED_BAR_TS_MS) -> ReturnSeries`
  - `build_return_series_from_returns(returns: list[float], first_ret_ts: int, usable: list[bool]) -> ReturnSeries`
  - `usable_mask(first_ret_ts: int, n: int, spliced: frozenset[int]) -> list[bool]`
  - `rv_var(series: ReturnSeries, t: int, horizon: int = RV_HORIZON_HOURS) -> float`

**Background — indexing (derive it once, get it right):** the return stamped `ts` is `ln(close(ts) / close(ts - 1h))` and covers the interval `(ts, ts + 1h]`. So `rv_var(t)` over `(t, t + 720h]` uses the 720 returns stamped `t .. t + 719h`, which need closes from bar `t - 1h` through bar `t + 719h`. Prefix arrays have length `n + 1` with `prefix[k] = sum over returns 0..k-1`, so a window is `prefix[i0 + 720] - prefix[i0]` where `i0 = index_of(t)`.

**Background — splice (SPEC §3.3):** return `ts` uses bars `ts` and `ts - 1h`. It straddles a splice boundary iff exactly one of them is substituted, i.e. `usable(ts) = (spliced(ts) == spliced(ts - 1h))`. Both-substituted is Coinbase-to-Coinbase and is kept. Excluded returns contribute 0 to `r2_prefix` and 0 to `cnt_prefix`; RV divides by the actual usable count, not by an assumed 720.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_vrp_measure.py`:

```python
import math

from moonface.research.vrp_measure import (
    ANNUALIZATION_HOURS,
    RV_HORIZON_HOURS,
    build_return_series,
    build_return_series_from_returns,
    rv_var,
    usable_mask,
)


class TestUsableMask(unittest.TestCase):
    def test_no_splices_all_usable(self):
        m = usable_mask(1_000_000_000_000, 5, frozenset())
        self.assertEqual(m, [True] * 5)

    def test_straddling_return_excluded(self):
        base = 1_000_000_000_000
        # bar at base+2h is spliced; returns stamped base+2h (uses base+1h,
        # base+2h) and base+3h (uses base+2h, base+3h) both straddle.
        spliced = frozenset({base + 2 * HOUR_MS})
        m = usable_mask(base, 5, spliced)
        self.assertEqual(m, [True, True, False, False, True])

    def test_interior_of_spliced_run_is_usable(self):
        base = 1_000_000_000_000
        spliced = frozenset({base + 2 * HOUR_MS, base + 3 * HOUR_MS})
        m = usable_mask(base, 5, spliced)
        # stamped base+3h uses two spliced bars -> Coinbase-to-Coinbase -> kept
        self.assertEqual(m, [True, True, False, True, False])


class TestRvVar(unittest.TestCase):
    def test_known_answer_constant_vol(self):
        """A path with a constant |log return| per hour must round-trip to
        the variance that generated it. This is the annualization guard."""
        base = 1_000_000_000_000
        step = 0.001  # |r| per hour
        n = RV_HORIZON_HOURS
        closes = {}
        price = 100.0
        closes[base - HOUR_MS] = price
        for i in range(n):
            price *= math.exp(step if i % 2 == 0 else -step)
            closes[base + i * HOUR_MS] = price
        series = build_return_series(closes, base, base + (n - 1) * HOUR_MS,
                                     spliced=frozenset())
        got = rv_var(series, base)
        self.assertAlmostEqual(got, step * step * ANNUALIZATION_HOURS, places=9)

    def test_excluded_returns_do_not_shrink_the_average(self):
        """Excluding a return divides by the true usable count, not by 720."""
        base = 1_000_000_000_000
        n = 4
        usable = [True, False, True, True]
        returns = [0.01, 99.0, 0.01, 0.01]  # 99.0 is the fake splice jump
        series = build_return_series_from_returns(returns, base, usable)
        got = rv_var(series, base, horizon=n)
        self.assertAlmostEqual(got, 0.0001 * ANNUALIZATION_HOURS, places=9)

    def test_window_is_exclusive_of_t_and_inclusive_of_t_plus_horizon(self):
        base = 1_000_000_000_000
        returns = [1.0, 2.0, 3.0, 4.0]
        series = build_return_series_from_returns(returns, base, [True] * 4)
        # horizon=2 from base must use returns stamped base and base+1h only
        got = rv_var(series, base, horizon=2)
        self.assertAlmostEqual(got, ((1.0 + 4.0) / 2) * ANNUALIZATION_HOURS, places=9)

    def test_reads_past_end_raises(self):
        base = 1_000_000_000_000
        series = build_return_series_from_returns([1.0, 2.0], base, [True] * 2)
        with self.assertRaises(VrpGapError):
            rv_var(series, base, horizon=5)

    def test_all_returns_excluded_raises(self):
        base = 1_000_000_000_000
        series = build_return_series_from_returns([1.0, 2.0], base, [False, False])
        with self.assertRaises(VrpGapError):
            rv_var(series, base, horizon=2)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: FAIL — `ImportError: cannot import name 'ReturnSeries'`

- [ ] **Step 3: Write the implementation**

Add to `src/moonface/research/vrp_measure.py` (after the loaders; add `import math` and `from dataclasses import dataclass` to the imports):

```python
@dataclass(frozen=True)
class ReturnSeries:
    """Prefix-summed hourly log returns, splice-aware.

    r2_prefix[k] / cnt_prefix[k] cover returns 0..k-1, so any window is one
    subtraction. Excluded returns contribute 0 to both -- rv_var divides by
    the actual usable count, never by an assumed horizon.
    """

    first_ts: int
    r2_prefix: tuple[float, ...]
    cnt_prefix: tuple[int, ...]

    def index_of(self, ts: int) -> int:
        return (ts - self.first_ts) // HOUR_MS


def usable_mask(first_ret_ts: int, n: int,
                spliced: frozenset[int] = SPLICED_BAR_TS_MS) -> list[bool]:
    """A return stamped `ts` is ln(close(ts)/close(ts-1h)), spanning bars
    ts-1h and ts. It straddles a splice boundary iff exactly one of them is a
    substituted (Coinbase) bar; both-substituted is Coinbase-to-Coinbase and
    is kept (SPEC section 3.3)."""
    out: list[bool] = []
    for i in range(n):
        ts = first_ret_ts + i * HOUR_MS
        out.append((ts in spliced) == ((ts - HOUR_MS) in spliced))
    return out


def build_return_series_from_returns(returns: list[float], first_ret_ts: int,
                                     usable: list[bool]) -> ReturnSeries:
    if len(returns) != len(usable):
        raise ValueError(f"{len(returns)} returns vs {len(usable)} mask entries")
    r2 = [0.0]
    cnt = [0]
    for r, ok in zip(returns, usable):
        r2.append(r2[-1] + (r * r if ok else 0.0))
        cnt.append(cnt[-1] + (1 if ok else 0))
    return ReturnSeries(first_ret_ts, tuple(r2), tuple(cnt))


def build_return_series(closes: dict[int, float], first_ret_ts: int,
                        last_ret_ts: int,
                        spliced: frozenset[int] = SPLICED_BAR_TS_MS) -> ReturnSeries:
    """Hourly log returns stamped first_ret_ts..last_ret_ts inclusive.

    The return stamped `ts` is ln(close(ts)/close(ts-1h)) and covers
    (ts, ts+1h], so close(first_ret_ts - 1h) must be present.
    """
    n = (last_ret_ts - first_ret_ts) // HOUR_MS + 1
    returns: list[float] = []
    for i in range(n):
        ts = first_ret_ts + i * HOUR_MS
        try:
            cur, prev = closes[ts], closes[ts - HOUR_MS]
        except KeyError as exc:
            raise GapError(f"missing spot close at {exc.args[0]}") from exc
        if cur <= 0.0 or prev <= 0.0:
            raise GapError(f"non-positive close at {ts}")
        returns.append(math.log(cur / prev))
    return build_return_series_from_returns(returns, first_ret_ts,
                                            usable_mask(first_ret_ts, n, spliced))


def rv_var(series: ReturnSeries, t: int, horizon: int = RV_HORIZON_HOURS) -> float:
    """Annualized realized variance over (t, t + horizon*1h].

    Uses the `horizon` returns stamped t .. t+(horizon-1)h. Divides by the
    usable count, not by `horizon` (SPEC section 3.3).
    """
    i0 = series.index_of(t)
    i1 = i0 + horizon
    if i0 < 0 or i1 > len(series.r2_prefix) - 1:
        raise GapError(f"window [{i0}, {i1}) outside series of "
                       f"{len(series.r2_prefix) - 1} returns")
    count = series.cnt_prefix[i1] - series.cnt_prefix[i0]
    if count == 0:
        raise GapError(f"no usable returns in window at {t}")
    total = series.r2_prefix[i1] - series.r2_prefix[i0]
    return (total / count) * ANNUALIZATION_HOURS
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: 19 passed.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check src/moonface/research/vrp_measure.py
git add src/moonface/research/vrp_measure.py tests/test_vrp_measure.py
git diff --cached --stat
git commit -m "feat(vrp_measure): splice-aware realized variance via prefix sums

rv_var(t) covers (t, t+720h] from the 720 returns stamped t..t+719h. Prefix
sums make each of ~3790 overlapping windows one subtraction, which is what
keeps 1000 null runs tractable without numpy.

Returns straddling a Binance->Coinbase splice boundary are excluded and the
window divides by its actual usable count; returns interior to a spliced run
are kept (SPEC 3.3). Known-answer test pins the 8760 annualization."
```

---

### Task 5: Spread series and interval statistics

**Files:**
- Modify: `src/moonface/research/vrp_measure.py`
- Modify: `tests/test_vrp_measure.py`

**Interfaces:**
- Consumes: `ReturnSeries`, `rv_var` (Task 4).
- Produces:
  - `iv_var(dvol_open: float) -> float`
  - `spread_series(dvol: list[tuple[int, float]], series: ReturnSeries) -> list[tuple[int, float]]`
  - `mean(values: list[float]) -> float`
  - `percentile(values: list[float], q: float) -> float`
  - `block_bootstrap_mean_ci(values: list[float], block_len: int = BLOCK_LEN, n_resamples: int = N_RESAMPLES, seed: int = BOOTSTRAP_SEED) -> tuple[float, float]`
  - `disjoint_spreads(spread: list[tuple[int, float]], stride_ms: int = DISJOINT_STRIDE_MS) -> list[float]`
  - `plain_mean_ci(values: list[float]) -> tuple[float, float]`
  - `year_buckets(spread: list[tuple[int, float]]) -> dict[int, list[float]]`

**Background (SPEC §4.3):** `mean_spread` is the mean of the **overlapping** series. Overlap does not bias a point estimate, only the apparent precision of one — so the point estimate uses every window and every interval claim is made by a method that accounts for overlap. **Never compute a naive SE or t-statistic on the overlapping series**; it would be wrong by roughly √60.

`plain_mean_ci` uses the normal approximation `mean ± 1.96 * s / √n` on the *disjoint* series (n=64), where `s` is the sample standard deviation with `n-1` denominator. Year bucket membership is by the calendar year of `t`, not `t + 30d` (SPEC §6 clause 3).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_vrp_measure.py`:

```python
from moonface.research.vrp_measure import (
    DISJOINT_STRIDE_MS,
    block_bootstrap_mean_ci,
    disjoint_spreads,
    iv_var,
    mean,
    percentile,
    plain_mean_ci,
    spread_series,
    year_buckets,
)


class TestIvVar(unittest.TestCase):
    def test_vol_points_to_annualized_variance(self):
        self.assertAlmostEqual(iv_var(50.0), 0.25, places=12)
        self.assertAlmostEqual(iv_var(100.0), 1.0, places=12)


class TestSpreadSeries(unittest.TestCase):
    def test_spread_is_iv_minus_rv(self):
        base = 1_000_000_000_000
        dvol = [(base, 50.0), (base + DVOL_INTERVAL_MS, 60.0)]
        # spread_series always uses the real 720h horizon, and the last DVOL
        # point is 12h in, so the series needs 720 + 12 returns.
        n = RV_HORIZON_HOURS + 12
        series = build_return_series_from_returns([0.0] * n, base, [True] * n)
        got = spread_series(dvol, series)
        self.assertEqual(len(got), 2)
        self.assertAlmostEqual(got[0][1], 0.25, places=12)   # rv is 0
        self.assertAlmostEqual(got[1][1], 0.36, places=12)


class TestPercentile(unittest.TestCase):
    def test_linear_interpolation(self):
        v = [1.0, 2.0, 3.0, 4.0]
        self.assertAlmostEqual(percentile(v, 0.0), 1.0)
        self.assertAlmostEqual(percentile(v, 100.0), 4.0)
        self.assertAlmostEqual(percentile(v, 50.0), 2.5)

    def test_single_value(self):
        self.assertAlmostEqual(percentile([7.0], 97.5), 7.0)


class TestBlockBootstrap(unittest.TestCase):
    def test_deterministic_for_a_seed(self):
        v = [float(i % 7) for i in range(600)]
        a = block_bootstrap_mean_ci(v, block_len=60, n_resamples=200, seed=1)
        b = block_bootstrap_mean_ci(v, block_len=60, n_resamples=200, seed=1)
        self.assertEqual(a, b)

    def test_different_seeds_differ(self):
        v = [float(i % 7) for i in range(600)]
        a = block_bootstrap_mean_ci(v, block_len=60, n_resamples=200, seed=1)
        b = block_bootstrap_mean_ci(v, block_len=60, n_resamples=200, seed=2)
        self.assertNotEqual(a, b)

    def test_ci_brackets_the_mean(self):
        v = [float(i % 7) for i in range(600)]
        lo, hi = block_bootstrap_mean_ci(v, block_len=60, n_resamples=500, seed=1)
        self.assertLess(lo, mean(v))
        self.assertGreater(hi, mean(v))

    def test_series_shorter_than_block_raises(self):
        with self.assertRaises(ValueError):
            block_bootstrap_mean_ci([1.0] * 10, block_len=60, n_resamples=10, seed=1)


class TestDisjointSpreads(unittest.TestCase):
    def test_strides_by_30_days(self):
        base = 1_000_000_000_000
        spread = [(base + i * DVOL_INTERVAL_MS, float(i)) for i in range(200)]
        got = disjoint_spreads(spread, stride_ms=DISJOINT_STRIDE_MS)
        # 60 DVOL points per 30d stride: indices 0, 60, 120, 180
        self.assertEqual(got, [0.0, 60.0, 120.0, 180.0])


class TestPlainMeanCi(unittest.TestCase):
    def test_known_values(self):
        v = [1.0, 2.0, 3.0, 4.0, 5.0]
        lo, hi = plain_mean_ci(v)
        self.assertAlmostEqual((lo + hi) / 2, 3.0, places=12)
        self.assertLess(lo, 3.0)
        self.assertGreater(hi, 3.0)

    def test_too_few_raises(self):
        with self.assertRaises(ValueError):
            plain_mean_ci([1.0])


class TestYearBuckets(unittest.TestCase):
    def test_buckets_by_year_of_t(self):
        # 2021-12-31 12:00 UTC and 2022-01-01 00:00 UTC
        spread = [(1640953800000 - 1800000, 1.0), (1640995200000, 2.0)]
        got = year_buckets(spread)
        self.assertEqual(sorted(got), [2021, 2022])
        self.assertEqual(got[2021], [1.0])
        self.assertEqual(got[2022], [2.0])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: FAIL — `ImportError: cannot import name 'iv_var'`

- [ ] **Step 3: Write the implementation**

Add to `src/moonface/research/vrp_measure.py` (add `import datetime as dt` and `import random` to the imports):

```python
def iv_var(dvol_open: float) -> float:
    """Annualized implied variance from a DVOL vol-point quote."""
    return (dvol_open / 100.0) ** 2


def spread_series(dvol: list[tuple[int, float]],
                  series: ReturnSeries) -> list[tuple[int, float]]:
    """[(t, iv_var(t) - rv_var(t))] over every DVOL point supplied."""
    return [(t, iv_var(v) - rv_var(series, t)) for t, v in dvol]


def mean(values: list[float]) -> float:
    if not values:
        raise ValueError("mean of empty series")
    return sum(values) / len(values)


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile, q in [0, 100]."""
    if not values:
        raise ValueError("percentile of empty series")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (q / 100.0) * (len(ordered) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def block_bootstrap_mean_ci(values: list[float], block_len: int = BLOCK_LEN,
                            n_resamples: int = N_RESAMPLES,
                            seed: int = BOOTSTRAP_SEED) -> tuple[float, float]:
    """(p2.5, p97.5) of the mean over moving-block bootstrap resamples.

    Block length matches the 30-day overlap horizon, so the resample preserves
    the autocorrelation the overlap induces (SPEC section 4.3). Never compute a
    naive SE on the overlapping series -- it is wrong by roughly sqrt(60).
    """
    n = len(values)
    if n <= block_len:
        raise ValueError(f"series of {n} shorter than bootstrap block {block_len}")
    rng = random.Random(seed)
    n_blocks = -(-n // block_len)  # ceil
    max_start = n - block_len
    means: list[float] = []
    for _ in range(n_resamples):
        total = 0.0
        count = 0
        for _ in range(n_blocks):
            start = rng.randint(0, max_start)
            for j in range(start, start + block_len):
                total += values[j]
                count += 1
        means.append(total / count)
    return percentile(means, 2.5), percentile(means, 97.5)


def disjoint_spreads(spread: list[tuple[int, float]],
                     stride_ms: int = DISJOINT_STRIDE_MS) -> list[float]:
    """Non-overlapping windows at phase 0: the value at t0, t0+30d, t0+60d, …"""
    if not spread:
        raise ValueError("disjoint_spreads of empty series")
    by_ts = dict(spread)
    t0 = spread[0][0]
    t_last = spread[-1][0]
    out: list[float] = []
    t = t0
    while t <= t_last:
        if t in by_ts:
            out.append(by_ts[t])
        t += stride_ms
    return out


def plain_mean_ci(values: list[float]) -> tuple[float, float]:
    """Normal-approximation 95% CI on the mean. For the DISJOINT series only."""
    n = len(values)
    if n < 2:
        raise ValueError(f"need >= 2 values, got {n}")
    m = mean(values)
    var = sum((v - m) ** 2 for v in values) / (n - 1)
    half = 1.96 * math.sqrt(var / n)
    return m - half, m + half


def year_buckets(spread: list[tuple[int, float]]) -> dict[int, list[float]]:
    """Calendar-year buckets keyed by the year of t, never of t + 30d
    (SPEC section 6 clause 3)."""
    out: dict[int, list[float]] = {}
    for t, v in spread:
        year = dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).year
        out.setdefault(year, []).append(v)
    return out
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: 31 passed.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check src/moonface/research/vrp_measure.py
git add src/moonface/research/vrp_measure.py tests/test_vrp_measure.py
git diff --cached --stat
git commit -m "feat(vrp_measure): spread series and overlap-aware interval stats

mean_spread is the mean of the overlapping series -- overlap biases precision,
not the point estimate -- so every interval claim goes through a moving-block
bootstrap at the 30-day overlap horizon, and a disjoint n=64 series gives the
cross-check CI. No naive SE is ever computed on the overlapping series."
```

---

### Task 6: Null generators

**Files:**
- Modify: `src/moonface/research/vrp_measure.py`
- Modify: `tests/test_vrp_measure.py`

**Interfaces:**
- Consumes: everything from Tasks 3-5.
- Produces:
  - `sigma_path(dvol: list[tuple[int, float]], first_ret_ts: int, n: int) -> list[float]`
  - `draw_gaussian(rng: random.Random) -> float`
  - `draw_student_t(rng: random.Random, df: int = T_DF) -> float`
  - `synthetic_returns(sigmas: list[float], rng: random.Random, draw) -> list[float]`
  - `null_mean_spread(dvol, first_ret_ts, usable, sigmas, seed, draw) -> float`
  - `null_distribution(dvol, first_ret_ts, usable, sigmas, base_seed, draw, n_seeds=N_NULL_SEEDS) -> list[float]`

**Background (SPEC §5.2):** the null is *"DVOL is a correct, unbiased statement of BTC's instantaneous volatility, and no variance risk premium exists."* Build `σ(h) = dvol_open(t(h)) / 100 / √8760` where `t(h)` is the most recent DVOL bar stamped at or before `h`; generate returns from it; run the identical pipeline against the **real** DVOL series. Any spread it reports is mechanical (Jensen, the 12h-step-vs-30d-window smoothing mismatch, annualization, the 64-window sample).

**Student-t (SPEC §5.3):** `t(df)` has variance `df/(df-2)` = 2 at `df=4`, so divide by `√2` for unit variance before scaling by `σ`. `df=4` is a pre-committed convention — not estimated, not swept.

**Performance:** each null run is ~46k draws + ~46k prefix adds + 3790 subtractions. 500 seeds × 2 nulls ≈ 1000 runs. Budget a few minutes. Do not "optimize" by reducing `N_NULL_SEEDS` — it is a frozen constant.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_vrp_measure.py`:

```python
import random as _random
import statistics as _stats

from moonface.research.vrp_measure import (
    N_NULL_SEEDS,
    T_DF,
    draw_gaussian,
    draw_student_t,
    null_distribution,
    null_mean_spread,
    sigma_path,
    synthetic_returns,
)


class TestSigmaPath(unittest.TestCase):
    def test_step_function_holds_dvol_across_its_bar(self):
        base = 1_000_000_000_000
        dvol = [(base, 50.0), (base + DVOL_INTERVAL_MS, 100.0)]
        sig = sigma_path(dvol, base, 13)
        expected_first = 0.5 / math.sqrt(ANNUALIZATION_HOURS)
        expected_last = 1.0 / math.sqrt(ANNUALIZATION_HOURS)
        for i in range(12):
            self.assertAlmostEqual(sig[i], expected_first, places=12)
        self.assertAlmostEqual(sig[12], expected_last, places=12)

    def test_before_first_bar_raises(self):
        base = 1_000_000_000_000
        with self.assertRaises(VrpGapError):
            sigma_path([(base, 50.0)], base - HOUR_MS, 2)


class TestDraws(unittest.TestCase):
    def test_gaussian_is_unit_variance(self):
        rng = _random.Random(7)
        xs = [draw_gaussian(rng) for _ in range(200_000)]
        self.assertAlmostEqual(_stats.pstdev(xs), 1.0, places=2)

    def test_student_t_rescaled_to_unit_variance(self):
        rng = _random.Random(7)
        xs = [draw_student_t(rng, df=T_DF) for _ in range(200_000)]
        self.assertAlmostEqual(_stats.pstdev(xs), 1.0, delta=0.05)

    def test_student_t_is_fatter_tailed_than_gaussian(self):
        rng = _random.Random(7)
        g = sorted(abs(draw_gaussian(rng)) for _ in range(100_000))
        t = sorted(abs(draw_student_t(rng, df=T_DF)) for _ in range(100_000))
        self.assertGreater(t[-100], g[-100])


class TestSyntheticReturns(unittest.TestCase):
    def test_scales_by_sigma(self):
        rng = _random.Random(3)
        sigmas = [0.01] * 50_000
        rs = synthetic_returns(sigmas, rng, draw_gaussian)
        self.assertEqual(len(rs), 50_000)
        self.assertAlmostEqual(_stats.pstdev(rs), 0.01, places=3)


class TestNull(unittest.TestCase):
    def _fixture(self, n_bars=200):
        base = 1_000_000_000_000
        dvol = [(base + i * DVOL_INTERVAL_MS, 60.0) for i in range(n_bars)]
        n_ret = (n_bars - 1) * 12 + RV_HORIZON_HOURS
        return base, dvol, n_ret

    def test_deterministic_for_a_seed(self):
        base, dvol, n_ret = self._fixture()
        sig = sigma_path(dvol, base, n_ret)
        usable = [True] * n_ret
        a = null_mean_spread(dvol, base, usable, sig, seed=5, draw=draw_gaussian)
        b = null_mean_spread(dvol, base, usable, sig, seed=5, draw=draw_gaussian)
        self.assertEqual(a, b)

    def test_null_spread_is_small_relative_to_iv(self):
        """Under the null there is no premium, so the mean spread must sit near
        zero -- far below iv_var itself. Catches a sign error or a
        squared/unsquared mixup."""
        base, dvol, n_ret = self._fixture()
        sig = sigma_path(dvol, base, n_ret)
        usable = [True] * n_ret
        got = null_mean_spread(dvol, base, usable, sig, seed=5, draw=draw_gaussian)
        self.assertLess(abs(got), 0.1 * iv_var(60.0))

    def test_distribution_length_and_determinism(self):
        base, dvol, n_ret = self._fixture(n_bars=70)
        sig = sigma_path(dvol, base, n_ret)
        usable = [True] * n_ret
        a = null_distribution(dvol, base, usable, sig, base_seed=11,
                              draw=draw_gaussian, n_seeds=5)
        b = null_distribution(dvol, base, usable, sig, base_seed=11,
                              draw=draw_gaussian, n_seeds=5)
        self.assertEqual(len(a), 5)
        self.assertEqual(a, b)

    def test_default_seed_count_is_frozen(self):
        self.assertEqual(N_NULL_SEEDS, 500)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: FAIL — `ImportError: cannot import name 'sigma_path'`

- [ ] **Step 3: Write the implementation**

Add to `src/moonface/research/vrp_measure.py`:

```python
def sigma_path(dvol: list[tuple[int, float]], first_ret_ts: int,
               n: int) -> list[float]:
    """Hourly instantaneous vol implied by DVOL, held piecewise-constant across
    each 12h bar (SPEC section 5.2). sigma(h) = dvol_open(t(h))/100/sqrt(8760),
    t(h) = the most recent DVOL bar stamped at or before h. No interpolation.
    """
    if not dvol:
        raise GapError("sigma_path: empty DVOL series")
    if first_ret_ts < dvol[0][0]:
        raise GapError(f"sigma_path: {first_ret_ts} precedes first DVOL bar "
                       f"{dvol[0][0]}")
    out: list[float] = []
    idx = 0
    for i in range(n):
        h = first_ret_ts + i * HOUR_MS
        while idx + 1 < len(dvol) and dvol[idx + 1][0] <= h:
            idx += 1
        out.append(dvol[idx][1] / 100.0 / math.sqrt(ANNUALIZATION_HOURS))
    return out


def draw_gaussian(rng: random.Random) -> float:
    """Unit-variance normal innovation."""
    return rng.gauss(0.0, 1.0)


def draw_student_t(rng: random.Random, df: int = T_DF) -> float:
    """Student-t(df) innovation rescaled to UNIT VARIANCE.

    t(df) has variance df/(df-2) -- 2.0 at df=4 -- so divide by sqrt of that.
    df is a pre-committed convention (SPEC section 5.3): not estimated from the
    data, not swept.
    """
    if df <= 2:
        raise ValueError(f"df must exceed 2 for finite variance, got {df}")
    # t = Z / sqrt(V/df), V ~ chi-square(df) = sum of df squared normals.
    z = rng.gauss(0.0, 1.0)
    v = sum(rng.gauss(0.0, 1.0) ** 2 for _ in range(df))
    raw = z / math.sqrt(v / df)
    return raw / math.sqrt(df / (df - 2.0))


def synthetic_returns(sigmas: list[float], rng: random.Random, draw) -> list[float]:
    """Hourly log returns with true instantaneous vol `sigmas`, iid given sigma."""
    return [s * draw(rng) for s in sigmas]


def null_mean_spread(dvol: list[tuple[int, float]], first_ret_ts: int,
                     usable: list[bool], sigmas: list[float], seed: int,
                     draw) -> float:
    """mean_spread from one synthetic path, measured against the REAL DVOL
    series through the identical pipeline (SPEC section 5.2 step 4)."""
    rng = random.Random(seed)
    returns = synthetic_returns(sigmas, rng, draw)
    series = build_return_series_from_returns(returns, first_ret_ts, usable)
    return mean([v for _, v in spread_series(dvol, series)])


def null_distribution(dvol: list[tuple[int, float]], first_ret_ts: int,
                      usable: list[bool], sigmas: list[float], base_seed: int,
                      draw, n_seeds: int = N_NULL_SEEDS) -> list[float]:
    """The distribution of mean_spread in a world where the premium is exactly
    zero by construction."""
    return [null_mean_spread(dvol, first_ret_ts, usable, sigmas, base_seed + i, draw)
            for i in range(n_seeds)]
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: 41 passed. The draw-statistics tests take a few seconds; that is expected.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check src/moonface/research/vrp_measure.py
git add src/moonface/research/vrp_measure.py tests/test_vrp_measure.py
git diff --cached --stat
git commit -m "feat(vrp_measure): DVOL-calibrated null generators (SPEC 5)

The null is 'DVOL is unbiased instantaneous vol and no premium exists': build
sigma from DVOL, generate paths, run the identical pipeline against the real
DVOL series. Any spread reported is mechanical -- Jensen, the 12h-step vs 30d
smoothing mismatch, annualization, the 64-window sample.

An iid constant-vol null would be vacuous here: DVOL is an exogenous market
price, not a selected trailing estimator as in vol_compression, so such a null
measures whatever gap was baked in (SPEC 5.1).

The Student-t(df=4) null is required because a Gaussian null is narrower than
reality and therefore generous to the lane."
```

---

### Task 7: `assemble_results`, threshold evaluation, and rendering

**Files:**
- Modify: `src/moonface/research/vrp_measure.py`
- Modify: `tests/test_vrp_measure.py`

**Interfaces:**
- Consumes: everything from Tasks 3-6.
- Produces:
  - `tail_windows(spread: list[tuple[int, float]], series: ReturnSeries, k: int = 5) -> list[dict]`
  - `vol_point_spreads(dvol, series) -> list[tuple[int, float]]`
  - `evaluate_threshold(results: dict) -> dict` — returns `{"null_clears": bool, "interval_clears": bool, "stability_clears": bool, "continue_recommended": bool}`
  - `assemble_results(dvol, series) -> dict`
  - `render_results_md(results: dict, meta: dict) -> str`

**Background — the threshold (SPEC §6), all three required:**
1. `mean_spread` > 97.5th percentile of **both** null distributions.
2. Block-bootstrap CI **and** disjoint CI both strictly above zero.
3. `mean_spread` positive within-bucket in **≥5 of 6** calendar buckets.

`continue_recommended` is `all three`. This is a **continuation** recommendation — whether a Stage-1 spec gets written — not a verdict and not a trading signal (SPEC §0.2). Q5 tail behavior is **descriptive and deliberately not part of the threshold** (SPEC §7): making it one would be designing an exit rule, which voids the measurement classification.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_vrp_measure.py`:

```python
from moonface.research.vrp_measure import (
    assemble_results,
    evaluate_threshold,
    render_results_md,
    tail_windows,
)


def _threshold_results(mean_spread, null_g_p975, null_t_p975, boot, disj,
                       buckets_positive):
    buckets = {}
    for i, positive in enumerate(buckets_positive):
        buckets[2021 + i] = {"mean": 1.0 if positive else -1.0, "n": 10}
    return {
        "mean_spread": mean_spread,
        "null_gaussian": {"p97_5": null_g_p975},
        "null_student_t": {"p97_5": null_t_p975},
        "bootstrap_ci": boot,
        "disjoint_ci": disj,
        "year_buckets": buckets,
    }


class TestEvaluateThreshold(unittest.TestCase):
    def test_all_three_clear(self):
        r = _threshold_results(0.05, 0.01, 0.02, (0.01, 0.09), (0.005, 0.095),
                               [True] * 6)
        got = evaluate_threshold(r)
        self.assertTrue(got["continue_recommended"])

    def test_fails_when_below_either_null(self):
        r = _threshold_results(0.05, 0.01, 0.09, (0.01, 0.09), (0.005, 0.095),
                               [True] * 6)
        got = evaluate_threshold(r)
        self.assertFalse(got["null_clears"])
        self.assertFalse(got["continue_recommended"])

    def test_fails_when_a_ci_straddles_zero(self):
        r = _threshold_results(0.05, 0.01, 0.02, (-0.01, 0.09), (0.005, 0.095),
                               [True] * 6)
        got = evaluate_threshold(r)
        self.assertFalse(got["interval_clears"])
        self.assertFalse(got["continue_recommended"])

    def test_fails_when_only_four_buckets_positive(self):
        r = _threshold_results(0.05, 0.01, 0.02, (0.01, 0.09), (0.005, 0.095),
                               [True, True, True, True, False, False])
        got = evaluate_threshold(r)
        self.assertFalse(got["stability_clears"])
        self.assertFalse(got["continue_recommended"])

    def test_five_of_six_buckets_is_enough(self):
        r = _threshold_results(0.05, 0.01, 0.02, (0.01, 0.09), (0.005, 0.095),
                               [True, True, True, True, True, False])
        got = evaluate_threshold(r)
        self.assertTrue(got["stability_clears"])
        self.assertTrue(got["continue_recommended"])


class TestTailWindows(unittest.TestCase):
    def test_returns_k_highest_rv_windows(self):
        base = 1_000_000_000_000
        n_ret = 12 * 5 + RV_HORIZON_HOURS
        returns = [0.001] * n_ret
        # make the window starting at the 3rd DVOL bar the most volatile
        for i in range(24, 24 + RV_HORIZON_HOURS):
            returns[i] = 0.02
        series = build_return_series_from_returns(returns, base, [True] * n_ret)
        dvol = [(base + i * DVOL_INTERVAL_MS, 60.0) for i in range(5)]
        spread = spread_series(dvol, series)
        got = tail_windows(spread, series, k=2)
        self.assertEqual(len(got), 2)
        self.assertGreaterEqual(got[0]["rv_var"], got[1]["rv_var"])
        self.assertIn("date_utc", got[0])
        self.assertIn("spread", got[0])


class TestRender(unittest.TestCase):
    def test_renders_without_verdict_language(self):
        base = 1_000_000_000_000
        n_ret = 12 * 70 + RV_HORIZON_HOURS
        series = build_return_series_from_returns([0.001] * n_ret, base,
                                                 [True] * n_ret)
        dvol = [(base + i * DVOL_INTERVAL_MS, 60.0) for i in range(71)]
        results = assemble_results(dvol, series, n_null_seeds=3)
        md = render_results_md(results, {"commit": "abc123", "inputs_sha256": {}})
        self.assertIn("Q1", md)
        self.assertIn("Q4", md)
        lowered = md.lower()
        for banned in ("edge found", "kill", "buy", "sell", "recommend trading"):
            self.assertNotIn(banned, lowered)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: FAIL — `ImportError: cannot import name 'assemble_results'`

- [ ] **Step 3: Write the implementation**

Add to `src/moonface/research/vrp_measure.py`:

```python
def vol_point_spreads(dvol: list[tuple[int, float]],
                      series: ReturnSeries) -> list[tuple[int, float]]:
    """DESCRIPTIVE ONLY (SPEC section 4.4): dvol_open(t) - 100*sqrt(rv_var(t)).
    Jensen-biased relative to the variance claim; never part of a threshold."""
    return [(t, v - 100.0 * math.sqrt(rv_var(series, t))) for t, v in dvol]


def _utc_date(ts_ms: int) -> str:
    return dt.datetime.fromtimestamp(ts_ms / 1000, dt.timezone.utc).strftime(
        "%Y-%m-%d %H:%M")


def tail_windows(spread: list[tuple[int, float]], series: ReturnSeries,
                 k: int = 5) -> list[dict]:
    """The k windows with the highest realized variance, and the spread in each.

    DESCRIPTIVE (SPEC section 7 Q5). A short-vol premium's entire risk is that
    it is collected in calm and repaid in spikes. Deliberately NOT part of the
    section 6 threshold: making it one would be designing an exit rule.
    """
    rows = [{"t": t, "date_utc": _utc_date(t), "rv_var": rv_var(series, t),
             "spread": s} for t, s in spread]
    rows.sort(key=lambda r: r["rv_var"], reverse=True)
    return rows[:k]


def evaluate_threshold(results: dict) -> dict:
    """The section 6 continuation threshold. All three clauses required.

    This decides whether a Stage-1 spec gets written -- NOT whether anything
    trades. It is not a verdict (SPEC section 0.2).
    """
    m = results["mean_spread"]
    null_clears = (m > results["null_gaussian"]["p97_5"]
                   and m > results["null_student_t"]["p97_5"])
    interval_clears = (results["bootstrap_ci"][0] > 0.0
                       and results["disjoint_ci"][0] > 0.0)
    positive = sum(1 for b in results["year_buckets"].values() if b["mean"] > 0.0)
    stability_clears = positive >= 5
    return {"null_clears": null_clears,
            "interval_clears": interval_clears,
            "stability_clears": stability_clears,
            "buckets_positive": positive,
            "continue_recommended": bool(null_clears and interval_clears
                                         and stability_clears)}


def assemble_results(dvol: list[tuple[int, float]], series: ReturnSeries,
                     n_null_seeds: int = N_NULL_SEEDS) -> dict:
    """Every frozen question (SPEC section 7) in one pass."""
    spread = spread_series(dvol, series)
    values = [v for _, v in spread]
    m = mean(values)
    disjoint = disjoint_spreads(spread)
    buckets = {year: {"mean": mean(vs), "n": len(vs)}
               for year, vs in sorted(year_buckets(spread).items())}

    n_ret = len(series.r2_prefix) - 1
    sigmas = sigma_path(dvol, series.first_ts, n_ret)
    usable = [series.cnt_prefix[i + 1] - series.cnt_prefix[i] == 1
              for i in range(n_ret)]

    nulls = {}
    for name, base_seed, draw in (("null_gaussian", NULL_SEED_GAUSS, draw_gaussian),
                                  ("null_student_t", NULL_SEED_T, draw_student_t)):
        dist = null_distribution(dvol, series.first_ts, usable, sigmas,
                                 base_seed, draw, n_seeds=n_null_seeds)
        nulls[name] = {"n_seeds": len(dist), "mean": mean(dist),
                       "p2_5": percentile(dist, 2.5),
                       "p50": percentile(dist, 50.0),
                       "p97_5": percentile(dist, 97.5)}

    results = {
        "window": {"start_ms": dvol[0][0], "end_ms": dvol[-1][0],
                   "start_utc": _utc_date(dvol[0][0]),
                   "end_utc": _utc_date(dvol[-1][0]),
                   "n_dvol_bars": len(dvol), "n_returns": n_ret,
                   "n_excluded_returns": n_ret - series.cnt_prefix[-1]},
        "mean_spread": m,
        "median_spread": percentile(values, 50.0),
        "frac_positive": sum(1 for v in values if v > 0.0) / len(values),
        "bootstrap_ci": block_bootstrap_mean_ci(values),
        "disjoint_n": len(disjoint),
        "disjoint_mean": mean(disjoint),
        "disjoint_ci": plain_mean_ci(disjoint),
        "year_buckets": buckets,
        "tail_windows": tail_windows(spread, series),
        "vol_point_mean": mean([v for _, v in vol_point_spreads(dvol, series)]),
    }
    results.update(nulls)
    results["bias_corrected_spread"] = m - nulls["null_gaussian"]["mean"]
    results["threshold"] = evaluate_threshold(results)
    return results


def render_results_md(results: dict, meta: dict) -> str:
    """RESULTS.md. Descriptive throughout: no verdict, no recommendation to
    trade (SPEC section 0.1)."""
    out: list[str] = []
    add = out.append
    w = results["window"]
    add("# vrp_measure — BTC Variance Risk Premium (frozen measurement run)")
    add("")
    add("Measurement lane: descriptive accounting over pinned data. Nothing is")
    add("predicted. There is no verdict here and no trading rule. See")
    add("`experiments/vrp_measure/SPEC.md`.")
    add("")
    add(f"- commit: `{meta.get('commit', '')}`")
    for name, info in sorted(meta.get("inputs_sha256", {}).items()):
        add(f"- {name}: `{info['path']}` sha256 `{info['sha256']}`")
    add("")
    add("## Q1 — data integrity")
    add("")
    add(f"- window: {w['start_utc']} → {w['end_utc']} UTC")
    add(f"- DVOL bars: {w['n_dvol_bars']}")
    add(f"- hourly returns: {w['n_returns']}")
    add(f"- returns excluded at splice boundaries: {w['n_excluded_returns']}")
    add("")
    add("## Q2 — the spread, full window (annualized variance)")
    add("")
    add(f"- mean (overlapping, primary): {results['mean_spread']:+.6f}")
    add(f"- median: {results['median_spread']:+.6f}")
    add(f"- fraction of windows positive: {results['frac_positive']:.4f}")
    add(f"- block-bootstrap 95% CI: [{results['bootstrap_ci'][0]:+.6f}, "
        f"{results['bootstrap_ci'][1]:+.6f}]")
    add(f"- disjoint cross-check (n={results['disjoint_n']}): "
        f"mean {results['disjoint_mean']:+.6f}, CI "
        f"[{results['disjoint_ci'][0]:+.6f}, {results['disjoint_ci'][1]:+.6f}]")
    add("")
    add("## Q3 — year by year")
    add("")
    add("| year | mean spread | n |")
    add("|---|---|---|")
    for year, b in results["year_buckets"].items():
        add(f"| {year} | {b['mean']:+.6f} | {b['n']} |")
    add("")
    add("## Q4 — null calibration (the gate)")
    add("")
    add("| null | seeds | mean | p2.5 | p50 | p97.5 |")
    add("|---|---|---|---|---|---|")
    for name in ("null_gaussian", "null_student_t"):
        n = results[name]
        add(f"| {name} | {n['n_seeds']} | {n['mean']:+.6f} | {n['p2_5']:+.6f} "
            f"| {n['p50']:+.6f} | {n['p97_5']:+.6f} |")
    add("")
    add(f"- real mean − gaussian null mean: {results['bias_corrected_spread']:+.6f}")
    t = results["threshold"]
    add(f"- clause 1 (above both null p97.5): {t['null_clears']}")
    add(f"- clause 2 (both CIs above zero): {t['interval_clears']}")
    add(f"- clause 3 (≥5 of 6 buckets positive): {t['stability_clears']} "
        f"({t['buckets_positive']} of {len(results['year_buckets'])})")
    add("")
    add(f"**Continuation (SPEC §6): {t['continue_recommended']}** — this decides")
    add("only whether a Stage-1 spec is written. It is not a verdict.")
    add("")
    add("## Q5 — tail behavior (descriptive, not part of §6)")
    add("")
    add("| window start (UTC) | realized variance | spread |")
    add("|---|---|---|")
    for row in results["tail_windows"]:
        add(f"| {row['date_utc']} | {row['rv_var']:.6f} | {row['spread']:+.6f} |")
    add("")
    add("## Q6 — vol-point spread (descriptive secondary)")
    add("")
    add(f"- mean DVOL − realized vol: {results['vol_point_mean']:+.4f} vol points")
    add("")
    add("Jensen caveat: E[σ]² ≠ E[σ²], so this is biased relative to the")
    add("variance-space claim in Q2. It is reported because vol points are how")
    add("volatility is read, and is not part of any threshold.")
    add("")
    return "\n".join(out)
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: 48 passed.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check src/moonface/research/vrp_measure.py
git add src/moonface/research/vrp_measure.py tests/test_vrp_measure.py
git diff --cached --stat
git commit -m "feat(vrp_measure): assemble Q1-Q6, threshold evaluation, rendering

evaluate_threshold implements the three pre-committed SPEC 6 clauses; it
decides whether a Stage-1 spec is written, not whether anything trades. Q5 tail
behavior is reported and deliberately excluded from the threshold -- gating on
it would be designing an exit rule, which voids the measurement classification.

A render test asserts no verdict or trading language reaches RESULTS.md."
```

---

### Task 8: `tools/vrp_measure.py` — run-once CLI

**Files:**
- Create: `tools/vrp_measure.py`
- Modify: `tests/test_vrp_measure.py`

**Interfaces:**
- Consumes: everything from `moonface.research.vrp_measure`.
- Produces: `sha256_of(path: str) -> str`; `main(argv: list[str] | None = None) -> int`.

**Background (SPEC §3.4, §11):** run-once is enforced mechanically — the CLI refuses if `RESULTS.md` exists. Inputs are hash-frozen into both outputs alongside the pipeline commit. **Do not run this against the real pinned inputs.** The run is human-gated (SPEC §11 step 2-3).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_vrp_measure.py`:

```python
import json as _json

from tools.vrp_measure import main as vrp_main
from tools.vrp_measure import sha256_of


class TestCliRunOnce(unittest.TestCase):
    def _inputs(self, d):
        """A small but structurally real fixture: 70 DVOL bars + enough spot."""
        base = 1_000_000_000_000
        n_bars = 70
        dvol_p = str(_Path(d) / "dvol.csv")
        with open(dvol_p, "w", newline="") as fh:
            w = _csv.writer(fh)
            for i in range(n_bars):
                w.writerow([base + i * DVOL_INTERVAL_MS, 60.0, 61.0, 59.0, 60.0])
        n_ret = (n_bars - 1) * 12 + RV_HORIZON_HOURS
        spot_p = str(_Path(d) / "spot.csv")
        price = 100.0
        with open(spot_p, "w", newline="") as fh:
            w = _csv.writer(fh)
            for i in range(n_ret + 1):
                ts = base - HOUR_MS + i * HOUR_MS
                price *= math.exp(0.001 if i % 2 == 0 else -0.001)
                w.writerow([ts, price, price, price, price, 1.0])
        return dvol_p, spot_p, base, n_bars

    def test_sha256_is_stable(self):
        with TemporaryDirectory() as d:
            p = _Path(d) / "x.txt"
            p.write_text("hello")
            self.assertEqual(sha256_of(str(p)), sha256_of(str(p)))
            self.assertEqual(len(sha256_of(str(p))), 64)

    def test_writes_outputs_then_refuses_second_run(self):
        with TemporaryDirectory() as d:
            dvol_p, spot_p, base, n_bars = self._inputs(d)
            outdir = str(_Path(d) / "out")
            argv = ["--dvol", dvol_p, "--spot", spot_p, "--outdir", outdir,
                    "--start-ms", str(base),
                    "--end-ms", str(base + (n_bars - 1) * DVOL_INTERVAL_MS),
                    "--null-seeds", "2"]
            self.assertEqual(vrp_main(argv), 0)
            self.assertTrue((_Path(outdir) / "RESULTS.md").exists())
            payload = _json.loads((_Path(outdir) / "results.json").read_text())
            self.assertIn("mean_spread", payload["results"])
            self.assertIn("dvol", payload["meta"]["inputs_sha256"])
            # second run must refuse
            self.assertEqual(vrp_main(argv), 1)

    def test_gap_in_input_is_a_hard_failure(self):
        with TemporaryDirectory() as d:
            dvol_p, spot_p, base, n_bars = self._inputs(d)
            rows = list(_csv.reader(open(spot_p)))
            del rows[50]
            with open(spot_p, "w", newline="") as fh:
                _csv.writer(fh).writerows(rows)
            argv = ["--dvol", dvol_p, "--spot", spot_p,
                    "--outdir", str(_Path(d) / "out2"),
                    "--start-ms", str(base),
                    "--end-ms", str(base + (n_bars - 1) * DVOL_INTERVAL_MS),
                    "--null-seeds", "2"]
            with self.assertRaises(VrpGapError):
                vrp_main(argv)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.vrp_measure'`

- [ ] **Step 3: Write the implementation**

Create `tools/vrp_measure.py`:

```python
#!/usr/bin/env python
"""vrp_measure frozen measurement run. RUN ONCE.

Measurement lane: descriptive accounting, no forecasting, no verdict. Pinned
inputs, frozen window and conventions: experiments/vrp_measure/SPEC.md.
Refuses to run if RESULTS.md already exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from moonface.research.vrp_measure import (HOUR_MS, N_NULL_SEEDS,
                                           RV_HORIZON_HOURS, WINDOW_END_MS,
                                           WINDOW_START_MS, assemble_results,
                                           build_return_series, load_dvol,
                                           load_spot_closes, render_results_md)

PINNED = {"dvol": REPO / "cache/exogenous/dvol_BTC_43200_full.csv",
          "spot": REPO / ".backtest_cache/BTC_USDT_1h.csv"}
OUTDIR = REPO / "experiments/vrp_measure"

SPLICE_NOTE = (
    "Realized variance is measured on Binance BTC/USDT spot 1h closes. Twelve "
    "bars inside this window are not Binance data: they are Coinbase BTC/USD "
    "candles spliced in by carry_measure under the human-approved 2026-07-16 "
    "resolution of a real exchange-side gap (2021-04-20, 2021-04-25, "
    "2021-08-13, 2021-09-29, 2023-03-24). Each splice boundary creates an "
    "artificial cross-exchange price step, so log returns straddling a boundary "
    "are excluded from the sum of squares and each window divides by its actual "
    "usable return count. Returns interior to a spliced run are kept. Nothing "
    "is interpolated (SPEC section 3.3).")


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dvol", default=str(PINNED["dvol"]))
    parser.add_argument("--spot", default=str(PINNED["spot"]))
    parser.add_argument("--outdir", default=str(OUTDIR))
    parser.add_argument("--start-ms", type=int, default=WINDOW_START_MS)
    parser.add_argument("--end-ms", type=int, default=WINDOW_END_MS)
    parser.add_argument("--null-seeds", type=int, default=N_NULL_SEEDS,
                        help="testing hook only; the frozen run uses the default")
    args = parser.parse_args(argv)

    outdir = Path(args.outdir)
    results_md = outdir / "RESULTS.md"
    if results_md.exists():
        print(f"REFUSING to run: {results_md} exists "
              "(run-once lane, SPEC section 3.4; re-runs need a written amendment)")
        return 1

    dvol = load_dvol(args.dvol, args.start_ms, args.end_ms)
    last_ret_ts = args.end_ms + (RV_HORIZON_HOURS - 1) * HOUR_MS
    closes = load_spot_closes(args.spot, args.start_ms - HOUR_MS, last_ret_ts)
    series = build_return_series(closes, args.start_ms, last_ret_ts)
    results = assemble_results(dvol, series, n_null_seeds=args.null_seeds)

    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                            capture_output=True, text=True).stdout.strip()
    meta = {"commit": commit, "notes": [SPLICE_NOTE],
            "inputs_sha256": {name: {"path": getattr(args, name),
                                     "sha256": sha256_of(getattr(args, name))}
                              for name in ("dvol", "spot")}}

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "results.json").write_text(
        json.dumps({"meta": meta, "results": results}, indent=2) + "\n")
    results_md.write_text(render_results_md(results, meta))
    print(f"wrote {results_md} and results.json (commit {commit[:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `.venv/bin/python -m pytest tests/test_vrp_measure.py -v`
Expected: 51 passed.

- [ ] **Step 5: Run the whole suite and lint**

Run: `.venv/bin/python -m pytest -q && .venv/bin/ruff check src/ tools/ tests/`
Expected: full suite passes, no lint errors. Report the actual counts — do not claim success without the output in front of you.

- [ ] **Step 6: Confirm no run artifacts exist**

Run: `ls experiments/vrp_measure/`
Expected: `SPEC.md` only. If `RESULTS.md` or `results.json` exist, the pipeline was run — that is human-gated and must not have happened. Delete them and report.

- [ ] **Step 7: Commit**

```bash
git add tools/vrp_measure.py tests/test_vrp_measure.py
git diff --cached --stat
git commit -m "feat(vrp_measure): run-once CLI with hash freeze (SPEC 3.4)

Refuses to run if RESULTS.md exists; records SHA-256 of both pinned inputs and
the pipeline commit in RESULTS.md and results.json. Gaps hard-fail rather than
degrade.

Built, not run: the frozen run is human-gated (SPEC 11)."
```

---

## After the plan

The lane is implemented but **not run**. SPEC §11 governs what happens next, and every step of it is a human decision:

1. Run `tools/vrp_fetch_dvol.py` once, by hand. Expect 3837 points, 2021-03-24 → 2026-06-24. Any cadence gap or a span under 1900 days is a stop-and-ask.
2. Single pipeline run.
3. `gitnexus_detect_changes()`, then one commit: one run, one commit.
4. Re-runs only via a written `AMENDMENTS.md` note.

Open question carried from SPEC §12, unresolved: whether Lane B (passive execution alpha) belongs in MoonFace at all, given the repo has no exchange account to check maker economics against.
