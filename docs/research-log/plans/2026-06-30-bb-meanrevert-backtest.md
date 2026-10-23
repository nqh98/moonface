# Bollinger Band Mean-Reversion Backtest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a mean-reversion Bollinger Band entry signal and backtest it on BTC perp via the existing exit-free `score_variant` forward-path harness.

**Architecture:** Three small, independently testable pieces. (1) A `rolling_std` population-std indicator in the foundation indicators module. (2) A `bb_revert` entry generator in the signals module that fades band crossings (same `(index, side)` contract as every other generator). (3) A focused CLI `tools/bb_revert.py` that reuses `score_variant` / `slice_events` / `_load_candles` from `tools/smc_decompose.py`, defines a 6-variant sweep grid, and writes `results_{tf}.json` + `REPORT.md`. No existing code is refactored.

**Tech Stack:** Python 3.11, pytest, no new dependencies. Existing modules: `moonface.foundation.indicators`, `moonface.foundation.models`, `moonface.research.edge.signals`, `tools.smc_decompose`.

## Global Constraints

- Population std (ddof=0) for the Bollinger Band calculation — classic BB convention.
- `bb_revert` must NOT be added to `signals.REGISTRY` — `tests/test_edge_signals.py::RegistryTest::test_registry_covers_all_families` pins the exact key set and would break.
- Entry generators are lookahead-free: no entry index may equal the final bar; per-bar indicator windows must be bounded (`closes[max(0, i-period): i+1]`) to stay O(n) — honors the existing O(n²)→O(n) signal-generator fix.
- No edge claim / no promotion. `REPORT.md` carries a RESEARCH-ONLY banner matching `smc_decompose`.
- Commit messages carry no AI-attribution trailer (repo rule).
- Run tests with the venv interpreter: `.venv/bin/python -m pytest ...`.

---

## File Structure

- **Modify** `src/moonface/foundation/indicators.py` — add `rolling_std` next to `sma`.
- **Modify** `src/moonface/research/edge/signals.py` — add `bb_revert` generator; extend the indicators import to include `rolling_std`. `REGISTRY` untouched.
- **Create** `tools/bb_revert.py` — CLI: GRID, `cmd_run`, `print_table`, `render_report`, `main`. Reuses the scorer from `smc_decompose`.
- **Modify** `tests/test_foundation_indicators.py` — add `rolling_std` unit tests; extend the import.
- **Create** `tests/test_bb_revert.py` — `bb_revert` generator unit tests + CLI smoke tests (mirrors `tests/test_smc_decompose.py`).
- **Create** `experiments/bb_revert/results_4h.json` + `REPORT.md` — real backtest output (Task 4).

---

### Task 1: `rolling_std` population-std indicator

**Files:**
- Modify: `src/moonface/foundation/indicators.py` (add function after `sma`, ~line 9)
- Test: `tests/test_foundation_indicators.py` (extend import + append tests)

**Interfaces:**
- Consumes: nothing new (plain Python).
- Produces: `rolling_std(closes: list[float], period: int) -> float` in `moonface.foundation.indicators`. Contract: caller ensures `len(closes) >= period`. Returns population std (ddof=0) of the last `period` closes.

- [ ] **Step 1: Write the failing tests**

Edit `tests/test_foundation_indicators.py`. Change the top import (line 1) from:

```python
from moonface.foundation.indicators import donchian_channel, sma
```

to:

```python
from moonface.foundation.indicators import donchian_channel, rolling_std, sma
```

Append these tests at the end of the file:

```python
def test_rolling_std_population_of_last_n():
    # [2,4,4,4,5,5,7,9]: mean=5, population variance=4, std=2
    assert rolling_std([2.0, 4, 4, 4, 5, 5, 7, 9], 8) == 2.0


def test_rolling_std_uses_only_last_n():
    # only the last 2 values [10,12] count: mean=11, pop std=1
    assert rolling_std([0.0, 0.0, 0.0, 10.0, 12.0], 2) == 1.0


def test_rolling_std_zero_when_constant():
    assert rolling_std([5.0, 5.0, 5.0, 5.0], 4) == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_foundation_indicators.py -v`
Expected: FAIL / ERROR — `ImportError: cannot import name 'rolling_std'` (function not yet defined).

- [ ] **Step 3: Write minimal implementation**

In `src/moonface/foundation/indicators.py`, add immediately after the `sma` function (after line 9):

```python
def rolling_std(closes: list[float], period: int) -> float:
    """Population std (ddof=0) of the last `period` closes. Caller ensures len >= period."""
    window = closes[-period:]
    m = sum(window) / period
    return (sum((x - m) ** 2 for x in window) / period) ** 0.5
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_foundation_indicators.py -v`
Expected: PASS — all tests green, including the three new `rolling_std` tests.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/foundation/indicators.py tests/test_foundation_indicators.py
git commit -m "feat(indicators): rolling_std population stdev for Bollinger bands"
```

---

### Task 2: `bb_revert` mean-reversion entry generator

**Files:**
- Modify: `src/moonface/research/edge/signals.py` (extend import line 3; add generator after `reversion_in_range`, ~line 179)
- Test: `tests/test_bb_revert.py` (create)

**Interfaces:**
- Consumes: `rolling_std`, `sma` from `moonface.foundation.indicators`; `Candle` from `moonface.foundation.models`.
- Produces: `bb_revert(h1: list[Candle], params: dict) -> list[Entry]` in `moonface.research.edge.signals`, where `Entry = tuple[int, str]` (index, `"LONG"` | `"SHORT"`). `params = {"period": int, "mult": float}`. **Does not touch `REGISTRY`.**

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bb_revert.py`:

```python
from __future__ import annotations

import unittest

from moonface.foundation.models import Candle
from moonface.research.edge.signals import bb_revert


def series(closes: list[float]) -> list[Candle]:
    return [Candle(1_780_275_600_000 + i * 3_600_000, c, c + 1, c - 1, c, 1.0)
            for i, c in enumerate(closes)]


class BbRevertSignalTest(unittest.TestCase):
    def test_long_on_lower_band_cross_down(self):
        # Flat at 100 (std=0 -> bands pinned at 100), then a drop below -> LONG fade.
        closes = [100.0] * 20 + [90.0, 90.0]
        out = bb_revert(series(closes), {"period": 10, "mult": 1.0})
        self.assertIn((20, "LONG"), out)
        self.assertFalse(any(s == "SHORT" for _, s in out))

    def test_short_on_upper_band_cross_up(self):
        closes = [100.0] * 20 + [110.0, 110.0]
        out = bb_revert(series(closes), {"period": 10, "mult": 1.0})
        self.assertIn((20, "SHORT"), out)
        self.assertFalse(any(s == "LONG" for _, s in out))

    def test_no_event_while_inside_bands(self):
        # Price constant at the mean -> never crosses either band.
        closes = [100.0] * 30
        out = bb_revert(series(closes), {"period": 10, "mult": 1.0})
        self.assertEqual(out, [])

    def test_entries_never_on_final_bar(self):
        closes = [100.0] * 25 + [90.0, 110.0, 90.0, 110.0]
        out = bb_revert(series(closes), {"period": 10, "mult": 1.0})
        self.assertTrue(all(0 <= i < len(closes) - 1 for i, _ in out))
        self.assertTrue(all(s in ("LONG", "SHORT") for _, s in out))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_bb_revert.py -v`
Expected: FAIL — `ImportError: cannot import name 'bb_revert'`.

- [ ] **Step 3: Write minimal implementation**

In `src/moonface/research/edge/signals.py`, change the indicators import (line 3) from:

```python
from moonface.foundation.indicators import roc, rsi, sma
```

to:

```python
from moonface.foundation.indicators import roc, rolling_std, rsi, sma
```

Add this generator after the `reversion_in_range` function (after line 179):

```python
def bb_revert(h1: list[Candle], params: dict) -> list[Entry]:
    """Mean-reversion fade of Bollinger bands. LONG when close crosses below the
    lower band, SHORT when it crosses above the upper band. Bounded windows keep
    per-bar cost O(1) (no O(n^2) slicing); output is identical to a full prefix."""
    period = params["period"]
    mult = params["mult"]
    closes = [c.close for c in h1]
    out: list[Entry] = []
    for i in range(period + 1, len(h1) - 1):
        now = closes[max(0, i - period + 1): i + 1]      # last `period` closes incl. i
        prev = closes[max(0, i - period): i]             # prior `period` closes (.. i-1)
        mid_n, sd_n = sma(now, period), rolling_std(now, period)
        mid_p, sd_p = sma(prev, period), rolling_std(prev, period)
        lower_n, upper_n = mid_n - mult * sd_n, mid_n + mult * sd_n
        lower_p, upper_p = mid_p - mult * sd_p, mid_p + mult * sd_p
        c_prev, c_now = closes[i - 1], closes[i]
        if c_prev >= lower_p and c_now < lower_n:
            out.append((i, "LONG"))
        elif c_prev <= upper_p and c_now > upper_n:
            out.append((i, "SHORT"))
    return out
```

**Do not modify `REGISTRY`** — adding `bb_revert` there would break `test_registry_covers_all_families`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_bb_revert.py tests/test_edge_signals.py -v`
Expected: PASS — all four `bb_revert` tests green, and the existing `test_edge_signals.py` suite (incl. `RegistryTest`) still green.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/edge/signals.py tests/test_bb_revert.py
git commit -m "feat(research): bb_revert mean-reversion entry generator"
```

---

### Task 3: `tools/bb_revert.py` CLI + report renderer

**Files:**
- Create: `tools/bb_revert.py`
- Test: `tests/test_bb_revert.py` (append CLI smoke tests)

**Interfaces:**
- Consumes: `bb_revert` from `moonface.research.edge.signals`; `score_variant`, `slice_events`, `_load_candles`, `HORIZONS` from `tools.smc_decompose`; `Candle` from `moonface.foundation.models`.
- Produces: `GRID: dict[str, tuple[list[dict], object]]`, `cmd_run(args: argparse.Namespace) -> dict`, `print_table(doc: dict) -> None`, `render_report(docs: dict) -> str`, `main(argv=None) -> None` in `tools.bb_revert`. Writes `experiments/bb_revert/results_{tf}.json` + `REPORT.md`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_bb_revert.py` (before the `if __name__ == "__main__":` block). Also add imports at the top of the file. The full top-of-file import block becomes:

```python
from __future__ import annotations

import argparse
import csv
import tempfile
import unittest
from pathlib import Path

from moonface.foundation.models import Candle
from moonface.research.edge.signals import bb_revert
from tools.bb_revert import GRID, cmd_run, render_report
```

Append the cache writer and CLI tests:

```python
H1 = 3_600_000


def _write_cache(tmp: str) -> None:
    # ~130 bars: flat warmup then a rising leg -> upper-band crossings fire.
    rows = []
    for i in range(130):
        c = 100 + max(0, i - 70) * 0.5
        rows.append([i * H1, c, c + 2, c - 2, c, 1.0])
    with open(f"{tmp}/BTC_USDT:USDT_1h.csv", "w", newline="") as fh:
        csv.writer(fh).writerows(rows)


class BbRevertCliTest(unittest.TestCase):
    def _args(self, tmp, outdir):
        return argparse.Namespace(
            symbol="BTC/USDT:USDT", tf="1h",
            start_ms=0, end_ms=2_000_000_000_000,
            cache_dir=tmp, out_dir=Path(outdir), from_1h=False)

    def test_cmd_run_emits_expected_shape(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outdir:
            _write_cache(tmp)
            doc = cmd_run(self._args(tmp, outdir))
            self.assertEqual(doc["tf"], "1h")
            self.assertEqual(set(doc["variants"]), set(GRID))
            for results in doc["variants"].values():
                self.assertEqual(len(results), 6)  # period{20,50} x mult{2,2.5,3}
                for row in results:
                    for h in (6, 12, 18, 30):
                        self.assertIn(h, row["horizons"])
            self.assertTrue((Path(outdir) / "results_1h.json").exists())

    def test_render_report_mentions_research_only_and_bb(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outdir:
            _write_cache(tmp)
            doc = cmd_run(self._args(tmp, outdir))
            md = render_report({outdir: doc})
            self.assertIn("RESEARCH-ONLY", md)
            self.assertIn("bb_revert", md)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_bb_revert.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.bb_revert'`.

- [ ] **Step 3: Write minimal implementation**

Create `tools/bb_revert.py`:

```python
#!/usr/bin/env python3
"""Bollinger Band mean-reversion decomposition CLI (research-only).

Scores the bb_revert entry generator (LONG on a lower-band cross-down, SHORT on
an upper-band cross-up) over a small period x mult grid, exit-free, via the
shared score_variant path stats + bootstrap CI from tools.smc_decompose, then
writes a JSON results doc + markdown report. No promotion, no edge claim."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))                              # import smc_decompose
sys.path.insert(0, str(_HERE.parent / "src"))               # import moonface.*

from moonface.foundation.models import Candle  # noqa: E402,F401  (consistent w/ sibling tools)
from moonface.research.edge.signals import bb_revert  # noqa: E402
from smc_decompose import (  # noqa: E402
    HORIZONS, _load_candles, score_variant, slice_events,
)


# period x mult sweep = 6 variants. Long & short both scored via the slices.
GRID: dict[str, tuple[list[dict], object]] = {
    "bb_revert": (
        bb_revert,
        [{"period": p, "mult": m} for p in (20, 50) for m in (2.0, 2.5, 3.0)],
    ),
}


def cmd_run(args) -> dict:
    candles = _load_candles(args)
    variants: dict[str, list[dict]] = {}
    for name, (param_grid, gen) in GRID.items():
        variants[name] = [score_variant(candles, gen, params)
                          for params in param_grid]
    doc = {
        "symbol": args.symbol, "tf": args.tf,
        "start_ms": args.start_ms, "end_ms": args.end_ms,
        "n_bars": len(candles), "variants": variants,
        "slices": {name: [{**{"params": r["params"]}, "slices": slice_events(r["events"])}
                          for r in rows]
                   for name, rows in variants.items()},
    }
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"results_{args.tf}.json").write_text(json.dumps(doc, indent=2))
    return doc


def print_table(doc: dict) -> None:
    print(f"\n== {doc['symbol']} {doc['tf']}  bars={doc['n_bars']} ==")
    print(f"{'variant':<12}{'params':<28}{'h':<4}{'n':<6}{'win':<7}{'ret_r':<8}{'ci95'}")
    for name, rows in doc["variants"].items():
        for row in rows:
            p = json.dumps(row["params"], sort_keys=True)
            for h, b in row["horizons"].items():
                print(f"{name:<12}{p:<28}{h:<4}{b['n']:<6}{b['win_rate']:<7.2f}"
                      f"{b['mean_ret_r']:<8.3f}[{b['ci_lo']:.3f},{b['ci_hi']:.3f}]  ")


def render_report(docs: dict) -> str:
    """Markdown report from {out_dir: doc}. RESEARCH-ONLY banner; per-variant
    horizon table. No PASS/FAIL, no edge claim."""
    lines = [
        "# Bollinger Band mean-reversion decomposition — RESEARCH-ONLY", "",
        "> Diagnostic, not a strategy. No edge is claimed; the WAIT stance and",
        "> `docs/findings/PROGRAM_CONCLUSION.md` are unchanged. Exit-free forward-path",
        "> scoring (declumped events, 6/12/18/30-bar horizons) with a single-asset",
        "> bootstrap 95% CI on mean_ret_r — not a promotion gate.", "",
    ]
    for _out_dir, doc in docs.items():
        lines += [f"## {doc['symbol']} {doc['tf']}  (bars={doc['n_bars']})", "",
                  "| variant | params | h | n | win_rate | mean_ret_r | ci95 |",
                  "|---|---|---|---|---|---|---|"]
        for name, rows in doc["variants"].items():
            for row in rows:
                p = json.dumps(row["params"], sort_keys=True)
                for h, b in row["horizons"].items():
                    lines.append(
                        f"| {name} | {p} | {h} | {b['n']} | {b['win_rate']:.2f} "
                        f"| {b['mean_ret_r']:.3f} "
                        f"| [{b['ci_lo']:.3f}, {b['ci_hi']:.3f}] |")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", default="BTC/USDT:USDT")
    p.add_argument("--tf", choices=["1h", "4h", "both"], default="4h")
    p.add_argument("--start-ms", type=int, default=1_577_836_800_000)  # 2020-01-01
    p.add_argument("--end-ms", type=int, default=2_000_000_000_000)    # all cached
    p.add_argument("--cache-dir", default=".backtest_cache")
    p.add_argument("--out-dir", default="experiments/bb_revert")
    p.add_argument("--from-1h", action="store_true", default=True,
                   help="derive 4h from the 1h cache (default on)")
    args = p.parse_args(argv)
    tfs = ["1h", "4h"] if args.tf == "both" else [args.tf]
    docs: dict[str, dict] = {}
    for tf in tfs:
        args.tf = tf
        doc = cmd_run(args)
        print_table(doc)
        docs[str(Path(args.out_dir) / f"results_{tf}.json")] = doc
    report = render_report(docs)
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    (Path(args.out_dir) / "REPORT.md").write_text(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_bb_revert.py tests/test_smc_decompose.py tests/test_edge_signals.py tests/test_foundation_indicators.py -v`
Expected: PASS — all `bb_revert` tests green; `smc_decompose`, `edge_signals`, `foundation_indicators` suites still green (no regressions from the reused harness).

- [ ] **Step 5: Lint the new file**

Run: `.venv/bin/python -m ruff check tools/bb_revert.py src/moonface/research/edge/signals.py src/moonface/foundation/indicators.py`
Expected: no errors (line-length 100, py311 target). Fix any reported issues.

- [ ] **Step 6: Commit**

```bash
git add tools/bb_revert.py tests/test_bb_revert.py
git commit -m "feat(research): bb_revert CLI + report renderer (score_variant harness)"
```

---

### Task 4: Run the backtest on cached BTC data and inspect the report

**Files:**
- Create: `experiments/bb_revert/results_4h.json` (generated)
- Create: `experiments/bb_revert/REPORT.md` (generated)

**Interfaces:**
- Consumes: `tools/bb_revert.py` CLI; cached `BTC/USDT:USDT` 1h candles in `.backtest_cache/` (the same cache the SMC decomposition run used).
- Produces: scored 6-variant BB mean-reversion results over the full ~6.5y BTC 4h series.

- [ ] **Step 1: Confirm the 1h cache is present**

Run: `ls -la .backtest_cache/ | grep BTC`
Expected: a `BTC_USDT:USDT_1h.csv` (or similarly named) file exists. If missing, stop and fetch data via the existing pipeline before continuing — do not proceed without the cache.

- [ ] **Step 2: Run the backtest (4h, derived from the 1h cache, full range)**

Run: `.venv/bin/python tools/bb_revert.py`
Expected: stdout per-variant horizon table (`bb_revert` × 6 param rows × 4 horizons), then exit 0. Creates `experiments/bb_revert/results_4h.json` and `experiments/bb_revert/REPORT.md`.

- [ ] **Step 3: Sanity-check the outputs**

Run: `head -40 experiments/bb_revert/REPORT.md`
Expected: a `# Bollinger Band mean-reversion decomposition — RESEARCH-ONLY` header, the RESEARCH-ONLY caveat block, a `## BTC/USDT:USDT 4h` section, and the horizon table with 6 × 4 = 24 rows. Confirm `n > 0` for at least the `period=20` rows (events fired).

Run: `.venv/bin/python -c "import json;d=json.load(open('experiments/bb_revert/results_4h.json'));print('bars',d['n_bars']);print('variants',list(d['variants']));print('rows',len(d['variants']['bb_revert']))"`
Expected: large `n_bars` (~11k+ for ~6.5y of 4h bars), `variants ['bb_revert']`, `rows 6`.

- [ ] **Step 4: Commit the results**

```bash
git add experiments/bb_revert/results_4h.json experiments/bb_revert/REPORT.md
git commit -m "research(research): bb_revert decomposition run on 6.5y BTC 4h"
```

- [ ] **Step 5: Summarize findings to the user**

Report (do not claim edge): per-variant `mean_ret_r` with 95% CI and win rate at the reference horizon (h=12), flagged by side via the slices; note which (if any) BB config's CI excludes zero, and how the first-vs-second-half split looks. Frame as research-only, consistent with the repo's WAIT stance.

---

## Self-Review (completed)

**1. Spec coverage:** Every spec component maps to a task — `rolling_std` (Task 1), `bb_revert` generator with crossing-fade semantics + bounded windows + no-REGISTRY constraint (Task 2), `tools/bb_revert.py` CLI with the 6-variant grid, reused harness, RESEARCH-ONLY report, defaults table (Task 3), and the real backtest run + honest summary (Task 4). Reporting, testing, risks (tools→tools import, population std) all reflected. No spec section uncovered.

**2. Placeholder scan:** No TBD/TODO/"add error handling"/"similar to". Every code step contains the actual code; every run step contains the exact command and expected output.

**3. Type consistency:** `rolling_std(closes, period) -> float` (Task 1) matches its use in `bb_revert` (Task 2). `bb_revert(h1, params) -> list[Entry]` matches the `score_variant(candles, gen, params)` contract and the `GRID` value type. CLI exports `GRID`, `cmd_run`, `render_report` match the Task 3 test imports. `cmd_run` writes `results_{tf}.json` matching the smoke-test assertion. Consistent.
