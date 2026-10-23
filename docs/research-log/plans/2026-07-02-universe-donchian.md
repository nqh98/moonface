# universe_donchian Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build + run the pre-registered `universe_donchian` domain — the frozen Donchian engine on a dynamic top-5 altcoin-perp universe selected by abnormal 24h quote-volume expansion — to a `closed_positive`/`closed_negative` verdict against a static-basket control.

**Architecture:** A bespoke research domain (mirrors `orderflow_microstructure` / `funding_fade_voltarget`). The frozen `trend_sim.simulate_donchian` engine runs per-symbol on 4h candles; a new point-in-time screener (`universe_data` daily klines) picks the top-5 eligible alts weekly; a new bar-by-bar mark-to-market portfolio simulator blends open positions into one daily return series; the ladder gates (reused, unmutated) + a static-basket dominance control + one-touch lockbox decide the verdict. The generic `runner.run` skips this domain (`config.runner = "universe_donchian"`).

**Tech Stack:** Python 3.11 stdlib only (no new deps). Reuses `moonface.research.{trend_sim, universe_data, ladder, store, spec, lockbox}`, `moonface.foundation.metrics`, `tools/research.py`.

## Global Constraints

Copied verbatim from the frozen spec (`docs/research-log/specs/2026-07-02-universe-donchian-design.md`) + repo rules. Every task's requirements implicitly include these.

- **Engine (FROZEN — do not modify entries/exits):** `trend_sim.simulate_donchian(candles, TrendParams(entry_n=40, trail_n=20, atr_period=14, k_stop=2.0, long_only=False, fee_rate=0.00045, slippage=0.0005, funding_enabled=True, exit_mode="trail"), funding_points)`.
- **Universe:** Binance USDⓈ-M perps; `universe_data.list_um_perp_symbols()` (survivorship-clean, delisted included); exclude BTC/ETH/fiat-stables. Daily 24h quote volume from `fetch_daily_klines` `DailyRow.quote_volume` (NOT the OHLCV `Candle.volume`, which is base-coin). Listing age = first daily bar.
- **Screener (frozen):** rank qualifiers by `ratio = quote_volume_t / median(trailing 30d)` (or z-score variant); liquidity floor trailing-mean ≥ USD 20M; listing-age ≥ 90 days; top_n=5; weekly rebuild; signals at day t earn from t+1; membership gates NEW entries, open positions run to the engine exit.
- **Cost:** `COST_FRACTION = 0.001` round-trip (foundation/metrics.py:211); applied per trade (one-way 0.0005 at entry, 0.0005 at exit). Funding applied per held day (long pays +rate, short receives).
- **Sizing:** fixed total gross `G = 1.0`; `f_slot = G / book_size` (treatment `G/top_n`, control `G/N_qualifiers`); `MAX_LEVERAGE=5.0` respected.
- **Window:** `START = 1_609_459_200_000` (2021-01-01 UTC) → run date; `LOCKBOX_FRACTION = 0.2` → fence ≈ 2025-05.
- **Gates (ladder constants UNMUTATED):** Stage1 pooled trades ≥ `SCREEN_MIN_TRADES`(30) AND expectancy_R > 0; Stage2 portfolio MAR > 0 AND maxDD ≥ `DRAWDOWN_BUDGET`(-0.30); Stage3 DSR ≥ `DSR_THRESHOLD`(0.95), `grid_size = n_trials = 4`; Stage3.5 folds ≥ 1, aggregate MAR > 0, dominance; Stage4 tail MAR ≥ `LOCKBOX_MIN_MAR`(1.0), tail trades ≥ `LOCKBOX_MIN_TRADES`(10), tail maxDD ≥ −0.30, dominance. Dominance = treatment > control on MAR AND Sharpe.
- **Kill rule (no rescue):** closed-negative → no v2 universe rule, no filter relaxation, no long-only flip, no exit change, no top-N re-tuning. Lever terminal. `n_trials = 4`.
- **Git:** local trunk-based `main`, never push to origin; `docs/` and `experiments/` are gitignored — force-add (`git add -f`) `docs/research-log/**` and any new tracked `experiments/**`; NEVER include AI attribution trailers in commit messages.

---

## File Map

**Create:**
- `src/moonface/research/universe_donchian.py` — screener + portfolio simulator + specs + evaluators + stage fns (Tasks 1–3).
- `src/moonface/research/universe_donchian_wf.py` — rolling walk-forward on the portfolio curve (Task 4).
- `src/moonface/research/universe_donchian_runner.py` — bespoke runner: `register`, `run_domain`, `_write_verdict` (Task 5).
- `tests/test_universe_donchian.py` — screener + portfolio + evaluators tests (Tasks 1–3).
- `tests/test_universe_donchian_wf.py` — walk-forward tests (Task 4).
- `tests/test_universe_donchian_runner.py` — runner tests with monkeypatched data layer (Task 5).

**Modify:**
- `tools/research.py` — add `cmd_universe_donchian` + `universe-donchian` subparser (Task 6).
- `tests/test_research_cli.py` — append `TestUniverseDonchianCli` (Task 6).
- `experiments/universe_donchian/PREREGISTRATION.md` — already created + committed in the spec step; no change.

---

## Task 1: Universe screener (point-in-time, no look-ahead)

**Files:**
- Create: `src/moonface/research/universe_donchian.py`
- Test: `tests/test_universe_donchian.py`

**Interfaces:**
- Consumes: `moonface.research.universe_data.DailyRow` (`ts_ms: int, close: float, quote_volume: float`).
- Produces: `is_alt_perp(symbol)->bool`, `expansion_ratio(rows, asof, lookback_days)->float|None`, `expansion_zscore(...)`, `screen_universe(daily, asof, cfg)->list[str]`, `build_membership(daily, calendar, cfg, rebalance_days=7)->tuple[dict[int,frozenset[str]], dict[int,int]]`, plus constants `DOMAIN`, `N_TRIALS`, `GROSS`, `REBALANCE_DAYS`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_universe_donchian.py
import unittest

from moonface.research.universe_data import DailyRow
from moonface.research import universe_donchian as ud


def _row(day, qv, close=10.0):
    # day is an integer day-offset; ts_ms = 2021-01-01 + day days
    return DailyRow(ts_ms=1_609_459_200_000 + day * 86_400_000, close=close, quote_volume=qv)


class TestScreener(unittest.TestCase):
    def test_is_alt_perp_excludes_majors_and_stables(self):
        self.assertTrue(ud.is_alt_perp("SOLUSDT"))
        self.assertFalse(ud.is_alt_perp("BTCUSDT"))
        self.assertFalse(ud.is_alt_perp("ETHUSDT"))
        self.assertFalse(ud.is_alt_perp("USDCUSDT"))
        self.assertFalse(ud.is_alt_perp("BTCUSDT_230929"))  # dated future
        self.assertFalse(ud.is_alt_perp("SOLBUSD"))         # non-USDT quote

    def test_expansion_ratio_median_of_prior_window(self):
        rows = [_row(d, qv) for d, qv in
                enumerate([10, 10, 10, 10, 40])]  # last day spikes 4x
        # asof = day 4; prior window (day 0..3) median = 10; ratio = 40/10
        self.assertAlmostEqual(
            ud.expansion_ratio(rows, rows[-1].ts_ms, lookback_days=30), 4.0)

    def test_expansion_ratio_none_when_short_history(self):
        rows = [_row(0, 10.0), _row(1, 20.0)]  # only 1 prior day
        self.assertIsNone(ud.expansion_ratio(rows, rows[-1].ts_ms, 30))

    def test_screen_universe_top_n_by_ratio_with_filters(self):
        # SYMA: high expansion, qualifies; SYMB: low expansion, qualifies;
        # SYMC: fails liquidity floor; SYMD: fails listing-age floor.
        daily = {
            "SYMAUSDT": [_row(d, q) for d, q in
                         enumerate([5e6] * 100 + [5e7])],      # old + liquid + spike
            "SYMBUSDT": [_row(d, q) for d, q in
                         enumerate([5e6] * 100 + [1e7])],      # old + liquid, small spike
            "SYMCUSDT": [_row(d, 1e3) for d in range(101)],     # old but illiquid
            "SYMDUSDT": [_row(d, 5e7) for d in range(5)],       # liquid but too young
        }
        asof = 1_609_459_200_000 + 100 * 86_400_000
        cfg = {"top_n": 5, "lookback_days": 30, "metric": "ratio",
               "min_liquidity_usd": 20e6, "min_age_days": 90, "rank": "expansion"}
        got = ud.screen_universe(daily, asof, cfg)
        self.assertEqual(got, ["SYMAUSDT", "SYMBUSDT"])  # C illiquid, D too young

    def test_screen_universe_static_returns_all_qualifiers(self):
        daily = {"AUSDT": [_row(d, 5e7) for d in range(101)],
                 "BUSDT": [_row(d, 5e7) for d in range(101)]}
        asof = 1_609_459_200_000 + 100 * 86_400_000
        cfg = {"top_n": 5, "lookback_days": 30, "metric": "ratio",
               "min_liquidity_usd": 20e6, "min_age_days": 90, "rank": "static"}
        self.assertEqual(ud.screen_universe(daily, asof, cfg), ["AUSDT", "BUSDT"])

    def test_build_membership_weekly_hold_and_one_day_lag(self):
        # Two symbols alternate which has the bigger spike; membership should
        # hold a set for 7 days then switch, and day-i membership reflects a
        # screen computed strictly before i (no same-day lookahead).
        daily = {
            "AUSDT": [_row(d, (1e8 if d % 14 < 7 else 1e6)) for d in range(30)],
            "BUSDT": [_row(d, (1e6 if d % 14 < 7 else 1e8)) for d in range(30)],
        }
        cal = sorted({r.ts_ms for rs in daily.values() for r in rs})
        cfg = {"top_n": 1, "lookback_days": 30, "metric": "ratio",
               "min_liquidity_usd": 0.0, "min_age_days": 0, "rank": "expansion"}
        membership, book = ud.build_membership(daily, cal, cfg, rebalance_days=7)
        self.assertEqual(set(membership.keys()), set(cal))
        self.assertTrue(all(v == 1 for v in book.values()))  # top_n=1 throughout
        # Membership is constant within each 7-day block (held between rebuilds).
        block0 = {membership[t] for t in cal[:7]}
        self.assertEqual(len(block0), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_universe_donchian.py -v`
Expected: FAIL (ModuleNotFoundError / AttributeError — `universe_donchian` not present).

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/research/universe_donchian.py
"""Universe-expansion Donchian domain (spec 2026-07-02).

The frozen trend_sim.simulate_donchian engine run on a dynamic top-5 altcoin
universe selected by abnormal 24h quote-volume expansion. The engine is byte-
frozen; the only new code is (a) a point-in-time screener [this task], (b) a
mark-to-market portfolio simulator [Task 2], and (c) dominance evaluators that
drive the ladder against a static-basket control [Task 3]. Pure functions only;
network IO + the Store live in universe_donchian_runner."""
from __future__ import annotations

from statistics import median

from moonface.research.universe_data import DailyRow

DOMAIN = "universe_donchian"
_DAY_MS = 86_400_000
N_TRIALS = 4
GROSS = 1.0
REBALANCE_DAYS = 7

# Excluded from the alt universe: the efficient majors + fiat/stable quote bases.
_EXCLUDE_BASES = {"BTC", "ETH", "USDC", "BUSD", "FDUSD", "TUSD", "EUR", "GBP",
                  "AEUR", "EURI", "XUSD", "USD1"}


def is_alt_perp(symbol: str) -> bool:
    """A genuine USDT alt perp: ends in USDT, base is not a major/stable, and it
    is not a dated future (those carry an underscore)."""
    if not symbol.endswith("USDT") or "_" in symbol:
        return False
    base = symbol[:-4]
    return len(base) >= 1 and base not in _EXCLUDE_BASES


def _window(rows, asof, lookback_days, include_asof):
    hi = asof if include_asof else asof - 1
    return [r.quote_volume for r in rows
            if asof - lookback_days * _DAY_MS < r.ts_ms <= hi]


def expansion_ratio(rows: list[DailyRow], asof: int,
                    lookback_days: int) -> float | None:
    """quote_volume[asof] / median(quote_volume over the trailing lookback window,
    excluding asof). None when the asof day or <2 prior days are absent."""
    prior = _window(rows, asof, lookback_days, include_asof=False)
    today = [r.quote_volume for r in rows if r.ts_ms == asof]
    if len(prior) < 2 or not today:
        return None
    m = median(prior)
    return None if m <= 0 else today[0] / m


def expansion_zscore(rows: list[DailyRow], asof: int,
                     lookback_days: int) -> float | None:
    """z-score of today's quote volume vs the trailing window (excluding asof)."""
    prior = _window(rows, asof, lookback_days, include_asof=False)
    today = [r.quote_volume for r in rows if r.ts_ms == asof]
    if len(prior) < 2 or not today:
        return None
    mean = sum(prior) / len(prior)
    var = sum((v - mean) ** 2 for v in prior) / (len(prior) - 1)
    return None if var <= 0 else (today[0] - mean) / var ** 0.5


def _qualifies(rows, asof, min_liquidity_usd, min_age_days, lookback_days):
    """Liquidity + listing-age floor (point-in-time: only data up to and including asof)."""
    if not rows or rows[0].ts_ms > asof - min_age_days * _DAY_MS:
        return False
    vols = _window(rows, asof, lookback_days, include_asof=True)
    return bool(vols) and sum(vols) / len(vols) >= min_liquidity_usd


def screen_universe(daily: dict[str, list[DailyRow]], asof: int,
                    cfg: dict) -> list[str]:
    """Eligible symbols at asof per cfg.
    cfg: top_n, lookback_days, metric ('ratio'|'zscore'), min_liquidity_usd,
    min_age_days, rank ('expansion'|'static'). rank='static' returns ALL
    qualifiers sorted (the control): no expansion ranking, no top_n cut."""
    metric_fn = (expansion_ratio if cfg.get("metric", "ratio") == "ratio"
                 else expansion_zscore)
    qualifiers = [s for s, rows in daily.items()
                  if _qualifies(rows, asof, cfg["min_liquidity_usd"],
                                cfg["min_age_days"], cfg["lookback_days"])]
    if cfg.get("rank", "expansion") == "static":
        return sorted(qualifiers)
    scored = []
    for s in qualifiers:
        score = metric_fn(daily[s], asof, cfg["lookback_days"])
        if score is not None:
            scored.append((score, s))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [s for _, s in scored[: cfg["top_n"]]]


def _screen_at(daily, asof, cfg):
    members = screen_universe(daily, asof, cfg)
    n = len(members) if cfg.get("rank", "expansion") == "static" else cfg["top_n"]
    return members, n


def build_membership(daily: dict[str, list[DailyRow]], calendar: list[int],
                     cfg: dict, rebalance_days: int = REBALANCE_DAYS
                     ) -> tuple[dict[int, frozenset[str]], dict[int, int]]:
    """Weekly membership + intended book-size schedule, keyed by every day in
    calendar. A screen computed at boundary day b is applied to days STRICTLY
    AFTER b (so day-i membership reflects a screen built on or before day i-1:
    no same-day look-ahead), mirroring xsection.simulate's 'signals at t earn
    from t+1' rule. Returns (membership, book_size) dicts over the calendar."""
    if not calendar:
        return {}, {}
    step = max(1, rebalance_days)
    screens: dict[int, tuple[list[str], int]] = {}
    for boundary in range(0, len(calendar), step):
        screens[boundary] = _screen_at(daily, calendar[boundary], cfg)
    membership: dict[int, frozenset[str]] = {}
    book_size: dict[int, int] = {}
    for i, ts in enumerate(calendar):
        # most recent boundary strictly before i (day 0's own screen only at i==0)
        b = 0 if i == 0 else ((i - 1) // step) * step
        members, n = screens[b]
        membership[ts] = frozenset(members)
        book_size[ts] = n
    return membership, book_size
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_universe_donchian.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/universe_donchian.py tests/test_universe_donchian.py
git commit -m "feat(research): universe_donchian point-in-time alt screener"
```

---

## Task 2: Mark-to-market portfolio simulator

**Files:**
- Modify: `src/moonface/research/universe_donchian.py` (append)
- Test: `tests/test_universe_donchian.py` (append)

**Interfaces:**
- Consumes: Task 1's `build_membership`; `moonface.foundation.metrics.COST_FRACTION`.
- Produces: `Position` dataclass `(side, entry_day, exit_day, r_multiple)`; `simulate_portfolio(calendar, membership, book_size, positions, daily_close, daily_funding, gross=GROSS, cost=COST_FRACTION) -> list[float]` — daily portfolio returns aligned to `calendar` (`returns[0] == 0.0`, `returns[i]` is the return INTO day `calendar[i]`). Only positions whose symbol was eligible at entry (`sym ∈ membership[entry_day]`) deploy capital.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_universe_donchian.py
from moonface.foundation.metrics import COST_FRACTION
from moonface.research.universe_donchian import (GROSS, Position,
                                                  simulate_portfolio)


class TestPortfolioSim(unittest.TestCase):
    def _days(self, n, base=1_609_459_200_000):
        return [base + i * 86_400_000 for i in range(n)]

    def test_flat_portfolio_is_zero(self):
        cal = self._days(5)
        membership = {t: frozenset() for t in cal}
        book = {t: 5 for t in cal}
        r = simulate_portfolio(cal, membership, book, {}, {}, {}, GROSS)
        self.assertEqual(r, [0.0, 0.0, 0.0, 0.0, 0.0])

    def test_single_long_earns_price_move_minus_costs_and_funding(self):
        # ALTS: eligible every day (top_n=1, f_slot=G/1=1.0). One long position
        # entered on day 0 (earns from day 1), exited on day 3. Closes step +10%
        # per day. Daily funding sum 0.001 (long pays).
        cal = self._days(5)
        closes = {10.0, 11.0, 12.1, 13.31, 14.641}  # +10% daily
        daily_close = {"ALTSUSDT": dict(zip(cal, closes))}
        daily_funding = {"ALTSUSDT": {t: 0.001 for t in cal}}
        membership = {t: frozenset({"ALTSUSDT"}) for t in cal}
        book = {t: 1 for t in cal}                    # f_slot = 1.0
        positions = {"ALTSUSDT": [Position("BUY", cal[0], cal[3], 1.0)]}
        r = simulate_portfolio(cal, membership, book, positions,
                               daily_close, daily_funding, GROSS)
        # Position earns days 1,2,3 (entry_day < d <= exit_day). Each = +10% price
        # return - funding 0.001. Entry cost on day1 + exit cost on day3,
        # each one-way = COST_FRACTION/2.
        one_way = COST_FRACTION / 2
        exp1 = (11.0 / 10.0 - 1.0) - 0.001 - one_way   # day1: price - fund - entry cost
        exp2 = (12.1 / 11.0 - 1.0) - 0.001             # day2: price - fund
        exp3 = (13.31 / 12.1 - 1.0) - 0.001 - one_way  # day3: price - fund - exit cost
        self.assertAlmostEqual(r[1], exp1)
        self.assertAlmostEqual(r[2], exp2)
        self.assertAlmostEqual(r[3], exp3)
        self.assertEqual(r[4], 0.0)                    # closed after day3

    def test_position_not_held_when_symbol_ineligible_at_entry(self):
        cal = self._days(4)
        daily_close = {"ALTSUSDT": {cal[0]: 10.0, cal[1]: 11.0, cal[2]: 12.1, cal[3]: 13.31}}
        # NOT eligible at entry day 0 -> capital never deployed.
        membership = {t: frozenset() for t in cal}
        book = {t: 1 for t in cal}
        positions = {"ALTSUSDT": [Position("BUY", cal[0], cal[3], 1.0)]}
        r = simulate_portfolio(cal, membership, book, positions,
                               daily_close, {}, GROSS)
        self.assertEqual(r[1:], [0.0, 0.0, 0.0])

    def test_short_pays_negative_funding(self):
        cal = self._days(3)
        daily_close = {"XUSDT": {cal[0]: 10.0, cal[1]: 9.0, cal[2]: 8.1}}  # -10%/day
        daily_funding = {"XUSDT": {t: 0.001 for t in cal}}
        membership = {t: frozenset({"XUSDT"}) for t in cal}
        book = {t: 1 for t in cal}
        positions = {"XUSDT": [Position("SELL", cal[0], cal[2], 1.0)]}
        r = simulate_portfolio(cal, membership, book, positions,
                               daily_close, daily_funding, GROSS)
        # short on a falling day is a gain; short RECEIVES +funding -> +0.001
        exp1 = -(9.0 / 10.0 - 1.0) + 0.001 - COST_FRACTION / 2
        self.assertAlmostEqual(r[1], exp1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_universe_donchian.py::TestPortfolioSim -v`
Expected: FAIL (ImportError: cannot import `Position` / `simulate_portfolio`).

- [ ] **Step 3: Write minimal implementation**

Append to `src/moonface/research/universe_donchian.py`:

```python
from dataclasses import dataclass

from moonface.foundation.metrics import COST_FRACTION  # add to imports at top


@dataclass(frozen=True)
class Position:
    """A held Donchian position in daily-day space (engine trade mapped to UTC
    midnight entry/exit days). side is 'BUY' (long) or 'SELL' (short)."""
    side: str
    entry_day: int
    exit_day: int
    r_multiple: float


def _is_long(side: str) -> bool:
    return side == "BUY"


def simulate_portfolio(calendar: list[int],
                       membership: dict[int, frozenset[str]],
                       book_size: dict[int, int],
                       positions: dict[str, list[Position]],
                       daily_close: dict[str, dict[int, float]],
                       daily_funding: dict[str, dict[int, float]],
                       gross: float = GROSS,
                       cost: float = COST_FRACTION) -> list[float]:
    """Daily mark-to-market portfolio returns aligned to `calendar`
    (returns[0] == 0.0; returns[i] is the return INTO calendar[i]).

    A position deploys capital only if its symbol was eligible for a NEW entry
    on its entry day (sym in membership[entry_day]). It then earns the symbol's
    daily close-to-close return over (entry_day, exit_day] (entry day's move is
    not claimed — no look-ahead), minus funding (long pays +rate, short
    receives) and minus a one-way cost (cost/2) on the first held day (entry)
    and on the exit day. f_slot = gross / book_size[entry_day], fixed at entry."""
    one_way = cost / 2.0
    idx = {t: i for i, t in enumerate(calendar)}
    returns = [0.0] * len(calendar)
    for i in range(1, len(calendar)):
        prev_t, cur_t = calendar[i - 1], calendar[i]
        ret = 0.0
        # positions open over (entry, exit]: held on day i iff entry_index < i <= exit_index
        for sym, trades in positions.items():
            closes = daily_close.get(sym, {})
            fund = daily_funding.get(sym, {})
            c_prev, c_cur = closes.get(prev_t), closes.get(cur_t)
            if c_prev is None or c_prev == 0 or c_cur is None:
                continue
            price_ret = c_cur / c_prev - 1.0
            for pos in trades:
                ei = idx.get(pos.entry_day)
                xi = idx.get(pos.exit_day)
                if ei is None or xi is None or not (ei < i <= xi):
                    continue
                if sym not in membership.get(pos.entry_day, frozenset()):
                    continue
                n = book_size.get(pos.entry_day, 1)
                f_slot = gross / n if n > 0 else 0.0
                signed = price_ret if _is_long(pos.side) else -price_ret
                ret += f_slot * signed
                ret -= f_slot * fund.get(cur_t, 0.0) * (1 if _is_long(pos.side) else -1)
                if i == ei + 1:                 # entry cost on first held day
                    ret -= f_slot * one_way
                if i == xi:                     # exit cost on exit day
                    ret -= f_slot * one_way
        returns[i] = ret
    return returns
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_universe_donchian.py -v`
Expected: PASS (all screener + portfolio tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/universe_donchian.py tests/test_universe_donchian.py
git commit -m "feat(research): universe_donchian mark-to-market portfolio simulator"
```

---

## Task 3: Specs + dominance evaluators + stage functions

**Files:**
- Modify: `src/moonface/research/universe_donchian.py` (append)
- Test: `tests/test_universe_donchian.py` (append)

**Interfaces:**
- Consumes: Tasks 1–2; `moonface.research.spec.HypothesisSpec`; `moonface.research.ladder.{SCREEN_FRACTION, SCREEN_MIN_TRADES, DRAWDOWN_BUDGET, LOCKBOX_MIN_MAR, LOCKBOX_MIN_TRADES}`; `moonface.foundation.metrics.{equity_summary_from_returns, summarize_r}`.
- Produces: `ENTRY_FAMILY = "volexp_donchian"`, `ENGINE_PARAMS` (frozen), the 4 `universe_donchian_specs()`, `control_for(spec)`, `btc_reference_spec()`, `dominates(t_mar,t_sharpe,c_mar,c_sharpe)`, `evaluate_dominant(t_returns, c_returns, pooled_trades, fence_idx, screen_fraction)`, `lockbox_dominant(t_returns, c_returns, pooled_trades_tail)`, `stage1_of`, `stage2_of`, `stage4_of`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_universe_donchian.py
from moonface.research import universe_donchian as ud
from moonface.research.universe_donchian import (
    control_for, dominates, evaluate_dominant, lockbox_dominant,
    stage1_of, stage2_of, stage4_of, universe_donchian_specs, N_TRIALS,
)


class TestSpecsEvaluators(unittest.TestCase):
    def test_four_treatment_specs_share_frozen_engine(self):
        specs = universe_donchian_specs()
        self.assertEqual(len(specs), N_TRIALS)
        for s in specs:
            self.assertEqual(s.domain, "universe_donchian")
            self.assertEqual(s.entry["family"], "volexp_donchian")
            self.assertEqual(s.exit["name"], "donchian_trail")
            self.assertEqual(s.exit["params"],
                             {"entry_n": 40, "trail_n": 20, "atr_period": 14, "k_stop": 2.0})
            self.assertEqual(s.fraction, 1.0)

    def test_control_is_static_basket_same_filters(self):
        spec = universe_donchian_specs()[0]
        ctrl = control_for(spec)
        self.assertEqual(ctrl.entry["params"]["rank"], "static")
        # same filters, same engine, same fraction; only rank differs
        for k in ("min_liquidity_usd", "min_age_days", "lookback_days"):
            self.assertEqual(ctrl.entry["params"][k], spec.entry["params"][k])

    def test_dominance_strict_both_metrics(self):
        self.assertTrue(dominates(1.5, 1.1, 1.0, 1.0))
        self.assertFalse(dominates(1.5, 0.9, 1.0, 1.0))   # Sharpe loses
        self.assertFalse(dominates(0.5, 1.1, 1.0, 1.0))   # MAR loses

    def test_stage1_uses_pooled_trades(self):
        m = {"screen_trades": 30, "screen_expectancy_r": 0.01}
        self.assertTrue(stage1_of(m))
        m2 = {"screen_trades": 29, "screen_expectancy_r": 0.5}
        self.assertFalse(stage1_of(m2))                   # too few trades
        m3 = {"screen_trades": 100, "screen_expectancy_r": -0.01}
        self.assertFalse(stage1_of(m3))                   # negative expectancy

    def test_evaluate_dominant_splits_at_fence(self):
        # 10 daily returns (idx 0..9); fence at 8 -> holdout = research[5:8].
        # Treatment returns VARY (so Sharpe>0) and are positive; control flat.
        t_ret = [0.0, 0.010, 0.020, 0.015, 0.025, 0.010, 0.020, 0.015, 0.012, 0.018]
        c_ret = [0.0] * 10
        pooled = [0.5] * 50             # >= 30 trades, positive expectancy
        m = evaluate_dominant(t_ret, c_ret, pooled, fence_idx=8, screen_fraction=0.7)
        self.assertTrue(m["holdout_dominance"])
        self.assertGreater(m["holdout_treatment_mar"], m["holdout_control_mar"])
        self.assertEqual(m["screen_trades"], 50)
        self.assertGreater(m["screen_expectancy_r"], 0.0)
        self.assertIn("research_sharpe", m)

    def test_stage4_lockbox_gate(self):
        tail = {"tail_trades": 10, "tail_treatment_mar": 1.0,
                "tail_treatment_dd": -0.1, "tail_dominance": True}
        self.assertTrue(stage4_of(tail))
        bad = dict(tail, tail_treatment_mar=0.5)
        self.assertFalse(stage4_of(bad))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_universe_donchian.py::TestSpecsEvaluators -v`
Expected: FAIL (ImportError: `universe_donchian_specs` / `evaluate_dominant` etc. absent).

- [ ] **Step 3: Write minimal implementation**

Append to `src/moonface/research/universe_donchian.py`. (Update the top import block to also pull ladder constants + metrics.)

```python
from moonface.research.ladder import (DRAWDOWN_BUDGET, LOCKBOX_MIN_MAR,
                                       LOCKBOX_MIN_TRADES, SCREEN_FRACTION,
                                       SCREEN_MIN_TRADES)
from moonface.research.spec import HypothesisSpec
from moonface.foundation.metrics import equity_summary_from_returns, summarize_r

ENTRY_FAMILY = "volexp_donchian"
ENGINE_PARAMS = {"entry_n": 40, "trail_n": 20, "atr_period": 14, "k_stop": 2.0}
EXIT_NAME = "donchian_trail"

# Shared asset descriptor (universe, not a single symbol) + frozen filters.
_ASSET = {"exchange": "binanceusdm",
          "universe": "alt_perps_excl_btc_eth_stables", "timeframe": "4h"}
_BASE_FILTERS = {"min_liquidity_usd": 20e6, "min_age_days": 90, "lookback_days": 30}

# The 4 pre-registered treatment grids (spec §3). Only the screener varies.
_TREATMENT_GRIDS = [
    {"top_n": 5,  "lookback_days": 30, "metric": "ratio"},
    {"top_n": 5,  "lookback_days": 60, "metric": "ratio"},
    {"top_n": 10, "lookback_days": 30, "metric": "ratio"},
    {"top_n": 5,  "lookback_days": 30, "metric": "zscore"},
]


def _spec(params: dict) -> HypothesisSpec:
    cfg = {**_BASE_FILTERS, **params, "rank": "expansion", "long_only": False}
    return HypothesisSpec(
        domain=DOMAIN, version=1, asset=_ASSET,
        entry={"family": ENTRY_FAMILY, "params": cfg},
        exit={"name": EXIT_NAME, "params": ENGINE_PARAMS},
        fraction=GROSS)


def universe_donchian_specs() -> list[HypothesisSpec]:
    return [_spec(grid) for grid in _TREATMENT_GRIDS]


def control_for(spec: HypothesisSpec) -> HypothesisSpec:
    """The static broad-basket control: same filters + engine + fraction, but
    rank='static' (all qualifiers equal-weight, no expansion ranking)."""
    p = {**spec.entry["params"], "rank": "static"}
    return HypothesisSpec(
        domain=DOMAIN, version=1, asset=_ASSET,
        entry={"family": ENTRY_FAMILY, "params": p},
        exit={"name": EXIT_NAME, "params": ENGINE_PARAMS},
        fraction=GROSS)


def btc_reference_spec() -> HypothesisSpec:
    """Non-gating reference: the byte-identical deployed engine on BTC (long-only)."""
    return HypothesisSpec(
        domain=DOMAIN, version=1,
        asset={"exchange": "binanceusdm", "symbol": "BTCUSDT", "timeframe": "4h"},
        entry={"family": ENTRY_FAMILY,
               "params": {**_BASE_FILTERS, "rank": "static", "long_only": True}},
        exit={"name": EXIT_NAME, "params": ENGINE_PARAMS},
        fraction=GROSS)


def dominates(t_mar: float, t_sharpe: float,
              c_mar: float, c_sharpe: float) -> bool:
    return t_mar > c_mar and t_sharpe > c_sharpe


def _splits(returns: list[float], fence_idx: int, screen_fraction: float):
    research = returns[:fence_idx]
    cut = int(len(research) * screen_fraction)
    return research[:cut], research[cut:], returns[fence_idx:]


def evaluate_dominant(t_returns: list[float], c_returns: list[float],
                      pooled_trades: list[float], fence_idx: int,
                      screen_fraction: float = SCREEN_FRACTION) -> dict:
    """Stage-1/2 metrics for the treatment portfolio vs its control, all on the
    daily return series. Stage-1 trade stats come from `pooled_trades` (the
    engine's per-trade net R-multiples in the screen window)."""
    t_screen_ret, t_hold_ret, _ = _splits(t_returns, fence_idx, screen_fraction)
    _, c_hold_ret, _ = _splits(c_returns, fence_idx, screen_fraction)
    pooled = summarize_r(pooled_trades)
    t_hold = equity_summary_from_returns(t_hold_ret)
    c_hold = equity_summary_from_returns(c_hold_ret)
    t_full = equity_summary_from_returns(t_returns[:fence_idx])
    return {
        "screen_trades": pooled.trade_count,
        "screen_expectancy_r": pooled.expectancy_r,
        "holdout_treatment_mar": t_hold.mar,
        "holdout_treatment_dd": t_hold.max_drawdown,
        "holdout_treatment_sharpe": t_hold.sharpe,
        "holdout_control_mar": c_hold.mar,
        "holdout_control_sharpe": c_hold.sharpe,
        "holdout_dominance": dominates(t_hold.mar, t_hold.sharpe,
                                       c_hold.mar, c_hold.sharpe),
        "research_sharpe": t_full.sharpe,
        "research_skew": t_full.skew,
        "research_kurtosis": t_full.kurtosis,
        "research_trades": len(t_returns[:fence_idx]),
    }


def lockbox_dominant(t_returns: list[float], c_returns: list[float],
                     pooled_trades_tail: list[float]) -> dict:
    t_tail = equity_summary_from_returns(t_returns)
    c_tail = equity_summary_from_returns(c_returns)
    pooled = summarize_r(pooled_trades_tail)
    return {
        "tail_trades": pooled.trade_count,
        "tail_treatment_mar": t_tail.mar,
        "tail_treatment_dd": t_tail.max_drawdown,
        "tail_treatment_sharpe": t_tail.sharpe,
        "tail_control_mar": c_tail.mar,
        "tail_control_sharpe": c_tail.sharpe,
        "tail_dominance": dominates(t_tail.mar, t_tail.sharpe,
                                    c_tail.mar, c_tail.sharpe),
    }


def stage1_of(m: dict, min_trades: int = SCREEN_MIN_TRADES) -> bool:
    return m["screen_trades"] >= min_trades and m["screen_expectancy_r"] > 0.0


def stage2_of(m: dict) -> bool:
    return (m["holdout_treatment_mar"] > 0.0
            and m["holdout_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["holdout_dominance"])


def stage4_of(m: dict, min_trades: int = LOCKBOX_MIN_TRADES) -> bool:
    return (m["tail_treatment_mar"] >= LOCKBOX_MIN_MAR
            and m["tail_treatment_dd"] >= DRAWDOWN_BUDGET
            and m["tail_trades"] >= min_trades
            and m["tail_dominance"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_universe_donchian.py -v`
Expected: PASS (all screener + portfolio + evaluator tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/universe_donchian.py tests/test_universe_donchian.py
git commit -m "feat(research): universe_donchian specs + dominance evaluators + stage gates"
```

---

## Task 4: Rolling walk-forward on the portfolio curve

**Files:**
- Create: `src/moonface/research/universe_donchian_wf.py`
- Test: `tests/test_universe_donchian_wf.py`

**Interfaces:**
- Consumes: Task 3's `dominates`; `moonface.foundation.metrics.equity_summary_from_returns`.
- Produces: `TRAIN_DAYS=365`, `TEST_DAYS=182` (~6mo), `STEP_DAYS=182`; `walk_forward(t_returns, c_returns, train_days=365, test_days=182, step_days=182)->dict`; `stage35_of(wf)->bool`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_universe_donchian_wf.py
import unittest

from moonface.research.universe_donchian_wf import walk_forward, stage35_of


class TestWalkForward(unittest.TestCase):
    def test_two_non_overlapping_folds_and_dominance(self):
        # 365 warm-up + 182 + 182 = 729 daily returns. Treatment alternates
        # (varies -> Sharpe>0) with positive mean; control flat.
        t = [0.002 if i % 2 == 0 else 0.001 for i in range(729)]
        c = [0.0] * 729
        wf = walk_forward(t, c)
        self.assertEqual(wf["folds"], 2)
        self.assertGreater(wf["aggregate_treatment_mar"], 0.0)
        self.assertTrue(wf["dominance"])

    def test_too_short_for_any_fold(self):
        wf = walk_forward([0.001] * 400, [0.0] * 400)
        self.assertEqual(wf["folds"], 0)
        self.assertFalse(stage35_of(wf))

    def test_stage35_requires_dominance(self):
        # Both vary; control has the higher mean -> control dominates, so the
        # treatment does NOT pass stage35 (needs treatment dominance).
        t = [0.001 if i % 2 == 0 else 0.0005 for i in range(729)]
        c = [0.004 if i % 2 == 0 else 0.003 for i in range(729)]
        wf = walk_forward(t, c)
        self.assertFalse(stage35_of(wf))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_universe_donchian_wf.py -v`
Expected: FAIL (ModuleNotFoundError: `universe_donchian_wf`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/research/universe_donchian_wf.py
"""Rolling walk-forward for universe_donchian (spec §4, stage 3.5).

The construction is frozen (no param selection), so TRAIN_DAYS is only the
warm-up offset before the first test window. The portfolio daily-return series
is precomputed and point-in-time causal, so each contiguous test slice is a
valid OOS window. Pools test-window daily returns, then checks dominance vs the
static-basket control."""
from __future__ import annotations

from moonface.foundation.metrics import equity_summary_from_returns
from moonface.research.universe_donchian import dominates

TRAIN_DAYS = 365          # ~1yr warm-up offset
TEST_DAYS = 182           # ~6mo test window
STEP_DAYS = TEST_DAYS     # non-overlapping


def walk_forward(t_returns: list[float], c_returns: list[float],
                 train_days: int = TRAIN_DAYS, test_days: int = TEST_DAYS,
                 step_days: int = STEP_DAYS) -> dict:
    n = min(len(t_returns), len(c_returns))
    t_pool: list[float] = []
    c_pool: list[float] = []
    folds = 0
    start = train_days
    while start + test_days <= n:
        t_pool.extend(t_returns[start:start + test_days])
        c_pool.extend(c_returns[start:start + test_days])
        folds += 1
        start += step_days
    t = equity_summary_from_returns(t_pool)
    c = equity_summary_from_returns(c_pool)
    return {
        "folds": folds,
        "aggregate_treatment_mar": t.mar,
        "aggregate_treatment_sharpe": t.sharpe,
        "aggregate_control_mar": c.mar,
        "aggregate_trades": t.trade_count,
        "dominance": dominates(t.mar, t.sharpe, c.mar, c.sharpe),
    }


def stage35_of(wf: dict) -> bool:
    return (wf["folds"] >= 1 and wf["aggregate_treatment_mar"] > 0.0
            and wf["dominance"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_universe_donchian_wf.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/universe_donchian_wf.py tests/test_universe_donchian_wf.py
git commit -m "feat(research): universe_donchian rolling walk-forward"
```

---

## Task 5: Bespoke runner — register, run_domain, verdict writer

**Files:**
- Create: `src/moonface/research/universe_donchian_runner.py`
- Test: `tests/test_universe_donchian_runner.py`

**Interfaces:**
- Consumes: Tasks 1–4; `moonface.research.store.Store`; `moonface.research.spec.{spec_from_json, spec_hash}`; `moonface.research.ladder.{DSR_THRESHOLD, SCREEN_FRACTION}`; `moonface.foundation.metrics.deflated_sharpe`; `moonface.research.trend_sim.{simulate_donchian, TrendParams}`; `moonface.research.universe_data.{list_um_perp_symbols, fetch_daily_klines, fetch_perp_candles, fetch_funding_rates}`; `moonface.research.funding_cost.held_funding_rates`.
- Produces: `UNIVERSE_DONCHIAN_DOMAIN`, `UNIVERSE_DONCHIAN_START_MS = 1_609_459_200_000`, `LOCKBOX_FRACTION = 0.2`, `register(store, now_ms)->None`, `run_domain(store, cache_dir, out_root)->str`, `_write_verdict(out_root, verdict, rows, dsr, reference)->None`.

- [ ] **Step 1: Write the failing tests**

The runner touches the network via `universe_data`; tests inject fake fetchers by monkeypatching the four `universe_data` functions + `list_um_perp_symbols`, and use a temp `Store` + temp `out_root`. The fake returns a tiny synthetic universe where the treatment beats the control.

```python
# tests/test_universe_donchian_runner.py
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from moonface.foundation.models import Candle
from moonface.research.store import Store
from moonface.research.universe_data import DailyRow
from moonface.research import universe_donchian_runner as r


def _candles(start_ms, n, drift):
    """n 4h candles, close drifting by `drift` per bar (alt) or 0 (control)."""
    out = []
    ts = start_ms
    for i in range(n):
        out.append(Candle(ts, 100, 100, 100, 100 * (1 + drift) ** i, 1.0))
        ts += 4 * 3_600_000
    return out


class TestRunner(unittest.TestCase):
    def test_register_freezes_window_fence_and_grid(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            now = 1_609_459_200_000 + 400 * 86_400_000
            r.register(store, now)
            d = store.domain(r.UNIVERSE_DONCHIAN_DOMAIN, 1)
            self.assertEqual(d["status"], "active")
            self.assertEqual(d["config"], {"runner": "universe_donchian"})
            self.assertEqual(d["start_ms"], r.UNIVERSE_DONCHIAN_START_MS)
            self.assertEqual(len(store.rows(r.UNIVERSE_DONCHIAN_DOMAIN, 1)), 4)
            # fence = now - 0.2*(now - start)
            self.assertEqual(d["fence_ts"],
                             now - int((now - r.UNIVERSE_DONCHIAN_START_MS) * 0.2))
            r.register(store, now)   # idempotent
            self.assertEqual(len(store.rows(r.UNIVERSE_DONCHIAN_DOMAIN, 1)), 4)

    def test_register_is_idempotent_and_does_not_mutate_grid(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            now = 1_609_459_200_000 + 400 * 86_400_000
            r.register(store, now)
            with self.assertRaises(Exception):
                # second insert_grid path is guarded by the domain-absent check;
                # re-calling register is a no-op, but a direct re-insert raises.
                from moonface.research.universe_donchian import universe_donchian_specs
                store.insert_grid(r.UNIVERSE_DONCHIAN_DOMAIN, 1, universe_donchian_specs())

    def test_run_domain_writes_verdict_and_sets_status(self):
        with tempfile.TemporaryDirectory() as td:
            store = Store(Path(td) / "s.db")
            start = r.UNIVERSE_DONCHIAN_START_MS
            now = start + 500 * 86_400_000
            r.register(store, now)
            d = store.domain(r.UNIVERSE_DONCHIAN_DOMAIN, 1)

            # Fakes: one alt (trending) + BTC (flat). Enough days + 4h bars.
            sym = "ALTSUSDT"
            days = 500
            daily = {sym: [DailyRow(start + i * 86_400_000, 100.0, 30e6)
                           for i in range(days)]}
            candles = {sym: _candles(start, days * 6, drift=0.0)}
            funding = {sym: []}

            with mock.patch.object(r, "list_um_perp_symbols", return_value=[sym]), \
                 mock.patch.object(r, "fetch_daily_klines",
                                   side_effect=lambda s, a, b, c: daily.get(s, [])), \
                 mock.patch.object(r, "fetch_perp_candles",
                                   side_effect=lambda s, iv, a, b, c: candles.get(s, [])), \
                 mock.patch.object(r, "fetch_funding_rates",
                                   side_effect=lambda s, a, b, c: funding.get(s, [])):
                verdict = r.run_domain(store, cache_dir=td,
                                       out_root=Path(td))
            self.assertIn(verdict, ("closed_positive", "closed_negative"))
            self.assertEqual(store.domain(r.UNIVERSE_DONCHIAN_DOMAIN, 1)["status"],
                             "closed_" + verdict.split("_")[1])
            vpath = Path(td) / "universe_donchian" / "verdict.md"
            self.assertTrue(vpath.exists())
            self.assertIn("Status:", vpath.read_text())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_universe_donchian_runner.py -v`
Expected: FAIL (ModuleNotFoundError: `universe_donchian_runner`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/research/universe_donchian_runner.py
"""Bespoke runner for the universe_donchian domain (spec 2026-07-02).

Reuses Store (registration + one-touch lockbox) but drives the
universe-expansion dominance ladder + walk-forward itself: the generic
runner.run cannot express the dynamic-universe portfolio + static-basket
control-dominance gate. The generic runner skips any domain whose config.runner
is neither None nor 'generic'."""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import replace
from pathlib import Path

from moonface.foundation.metrics import deflated_sharpe
from moonface.research.ladder import DSR_THRESHOLD, SCREEN_FRACTION
from moonface.research.spec import spec_from_json, spec_hash
from moonface.research.store import Store
from moonface.research.trend_sim import TrendParams, simulate_donchian
from moonface.research.universe_data import (fetch_daily_klines,
                                             fetch_funding_rates,
                                             fetch_perp_candles,
                                             list_um_perp_symbols)
from moonface.research.universe_donchian import (
    _BASE_FILTERS, DOMAIN, GROSS, Position, _qualifies, build_membership,
    btc_reference_spec, control_for, evaluate_dominant, is_alt_perp,
    lockbox_dominant, simulate_portfolio, stage1_of, stage2_of, stage4_of,
    universe_donchian_specs)
from moonface.research.universe_donchian_wf import stage35_of, walk_forward

UNIVERSE_DONCHIAN_DOMAIN = DOMAIN
UNIVERSE_DONCHIAN_START_MS = 1_609_459_200_000   # 2021-01-01 UTC
LOCKBOX_FRACTION = 0.2
_DAY_MS = 86_400_000

_LS_ENGINE = TrendParams(entry_n=40, trail_n=20, atr_period=14, k_stop=2.0,
                         long_only=False, fee_rate=0.00045, slippage=0.0005,
                         funding_enabled=True, exit_mode="trail")
_LONG_ONLY_ENGINE = replace(_LS_ENGINE, long_only=True)


def register(store: Store, now_ms: int) -> None:
    """Freeze the window + fence and insert the 4-spec grid. Idempotent."""
    fence_ts = now_ms - int((now_ms - UNIVERSE_DONCHIAN_START_MS) * LOCKBOX_FRACTION)
    if store.domain(UNIVERSE_DONCHIAN_DOMAIN, 1) is None:
        store.register_domain(UNIVERSE_DONCHIAN_DOMAIN, 1, "active",
                              {"runner": "universe_donchian"},
                              UNIVERSE_DONCHIAN_START_MS, now_ms, fence_ts)
        store.insert_grid(UNIVERSE_DONCHIAN_DOMAIN, 1, universe_donchian_specs())


def _utc_midnight(ts_ms: int) -> int:
    return ts_ms - (ts_ms % _DAY_MS)


def _daily_funding_map(points, start_ms, end_ms):
    """{utc_midnight(funding_time): sum(rate)} over the window."""
    out: dict[int, float] = {}
    for t, rate in points:
        if start_ms <= t < end_ms:
            out[_utc_midnight(t)] = out.get(_utc_midnight(t), 0.0) + rate
    return out


def _load_engine_trades(symbols, start_ms, end_ms, cache_dir, engine):
    """For each symbol: 4h candles + funding -> simulate_donchian -> Position list
    in day-space (entry_day/exit_day floored to UTC midnight). Returns
    {symbol: list[Position]} and {symbol: {day_ts: close}}."""
    positions: dict[str, list[Position]] = {}
    closes: dict[str, dict[int, float]] = {}
    for sym in symbols:
        candles = fetch_perp_candles(sym, "4h", start_ms, end_ms, cache_dir)
        if len(candles) < engine.entry_n + 2:
            continue
        funding = fetch_funding_rates(sym, start_ms, end_ms, cache_dir)
        trades = simulate_donchian(candles, engine, funding)
        positions[sym] = [Position(t.side, _utc_midnight(candles[t.entry_index].timestamp_ms),
                                   _utc_midnight(candles[t.exit_index].timestamp_ms),
                                   t.r_multiple) for t in trades]
        closes[sym] = {_utc_midnight(c.timestamp_ms): c.close for c in candles}
    return positions, closes


def _simulate_cfg(cfg, daily, calendar, positions, closes, funding_daily, fence_idx):
    membership, book = build_membership(daily, calendar, cfg)
    returns = simulate_portfolio(calendar, membership, book, positions, closes,
                                 funding_daily, gross=GROSS)
    return returns


def run_domain(store: Store, cache_dir: str, out_root: Path) -> str:
    d = store.domain(UNIVERSE_DONCHIAN_DOMAIN, 1)
    start_ms, end_ms, fence_ts = d["start_ms"], d["end_ms"], d["fence_ts"]
    specs = [spec_from_json(r["spec_json"])
             for r in store.rows(UNIVERSE_DONCHIAN_DOMAIN, 1)]
    grid_size = len(specs)                       # == N_TRIALS == 4

    # 1. Universe + daily klines (quote volume), alt-only.
    all_symbols = [s for s in list_um_perp_symbols() if is_alt_perp(s)]
    daily = {s: fetch_daily_klines(s, start_ms, end_ms, cache_dir)
             for s in all_symbols}
    daily = {s: rows for s, rows in daily.items() if rows}

    # 2. Unified daily calendar + fence index.
    calendar = sorted({r.ts_ms for rows in daily.values() for r in rows
                       if start_ms <= r.ts_ms < end_ms})
    fence_idx = bisect_left(calendar, fence_ts)

    # 3. Candidate set: symbols that ever clear the liquidity+age floor (bounds
    #    the expensive 4h+funding+engine fetches to liquid alts only).
    min_liq = _BASE_FILTERS["min_liquidity_usd"]
    min_age = _BASE_FILTERS["min_age_days"]
    lookback = _BASE_FILTERS["lookback_days"]
    candidates = [s for s, rows in daily.items()
                  if any(_qualifies(rows, t, min_liq, min_age, lookback)
                         for t in calendar)]

    positions, closes = _load_engine_trades(candidates, start_ms, end_ms,
                                            cache_dir, _LS_ENGINE)
    # Per-symbol daily funding (sum of 8h prints per UTC day).
    funding_daily = {s: _daily_funding_map(fetch_funding_rates(s, start_ms, end_ms, cache_dir),
                                           start_ms, end_ms) for s in candidates}

    # 4. BTC reference (non-gating), routed through the same simulator as a
    #    single-symbol static book with the long-only deployed engine.
    btc_positions, btc_closes = _load_engine_trades(["BTCUSDT"], start_ms, end_ms,
                                                    cache_dir, _LONG_ONLY_ENGINE)
    btc_membership, btc_book = build_membership(
        {"BTCUSDT": fetch_daily_klines("BTCUSDT", start_ms, end_ms, cache_dir)},
        calendar, {**{k: v for k, v in _BASE_FILTERS.items()},
                   "rank": "static", "top_n": 1})
    btc_returns = simulate_portfolio(calendar, btc_membership, btc_book,
                                     btc_positions, btc_closes, {}, gross=GROSS)

    # 5. Per-spec: build treatment + control curves, evaluate stages 1/2/3.5.
    rows: list[dict] = []
    for spec in specs:
        cfg = spec.entry["params"]
        t_ret = _simulate_cfg(cfg, daily, calendar, positions, closes,
                              funding_daily, fence_idx)
        c_ret = _simulate_cfg({**cfg, "rank": "static"}, daily, calendar,
                              positions, closes, funding_daily, fence_idx)
        screen_trades = _screen_pooled_trades(daily, positions, calendar, fence_idx, cfg)
        m = evaluate_dominant(t_ret, c_ret, screen_trades, fence_idx, SCREEN_FRACTION)
        rows.append({"spec_hash": spec_hash(spec), "spec": spec, "m": m,
                     "wf": None, "stage": "research", "t_ret": t_ret, "c_ret": c_ret})
        if not stage1_of(m):
            rows[-1]["stage"] = "rejected_stage1"
            continue
        if not stage2_of(m):
            rows[-1]["stage"] = "rejected_stage2"
            continue
        wf = walk_forward(t_ret[:fence_idx], c_ret[:fence_idx])
        rows[-1]["wf"] = wf
        rows[-1]["stage"] = "wf_pass" if stage35_of(wf) else "rejected_wf"

    # 6. DSR (stage 3) across survivors; trial variance from ALL specs.
    all_sharpes = [r["m"]["research_sharpe"] for r in rows]
    dsr: dict[str, float] = {}
    for r in rows:
        if r["stage"] != "wf_pass":
            continue
        m = r["m"]
        value = deflated_sharpe(m["research_sharpe"], m["research_trades"],
                                m["research_skew"], m["research_kurtosis"],
                                all_sharpes, grid_size)
        r["dsr"] = round(value, 6)
        if r["dsr"] >= DSR_THRESHOLD:
            dsr[r["spec_hash"]] = r["dsr"]
        else:
            r["stage"] = "rejected_dsr"

    # 7. One-touch lockbox (stage 4) for every DSR survivor.
    survivors = [r for r in rows if r["stage"] == "wf_pass"]
    if survivors:
        store.touch_lockbox(UNIVERSE_DONCHIAN_DOMAIN, 1)   # set-once for the domain
        for r in survivors:
            cfg = r["spec"].entry["params"]
            t_tail = r["t_ret"][fence_idx:]
            c_tail = r["c_ret"][fence_idx:]
            tail_trades = _screen_pooled_trades(daily, positions, calendar, fence_idx,
                                                cfg, tail_only=True)
            tail = lockbox_dominant(t_tail, c_tail, tail_trades)
            r["tail"] = tail
            r["stage"] = "lockbox_pass" if stage4_of(tail) else "lockbox_fail"

    promoted = any(r["stage"] == "lockbox_pass" for r in rows)
    verdict = "closed_positive" if promoted else "closed_negative"
    store.set_domain_status(UNIVERSE_DONCHIAN_DOMAIN, 1, verdict)
    reference = _reference_metrics(btc_returns, fence_idx)
    _write_verdict(out_root, verdict, rows, dsr, reference)
    return verdict


def _screen_pooled_trades(daily, positions, calendar, fence_idx, cfg, tail_only=False):
    """Engine r_multiples for trades whose symbol was eligible per the treatment
    cfg at the trade's entry day, with the entry day in the screen window
    (research[:fence]) — or the lockbox tail (research[fence:]) when tail_only.
    Eligibility is read from the weekly membership (rebuilt once here) so it
    matches what the portfolio simulator actually traded."""
    membership, _ = build_membership(daily, calendar, cfg)
    lo = fence_idx if tail_only else 0
    hi = fence_idx if not tail_only else len(calendar)
    out: list[float] = []
    for day_idx in range(lo, hi):
        ts = calendar[day_idx]
        elig = membership.get(ts, frozenset())
        for sym, trades in positions.items():
            if sym not in elig:
                continue
            for pos in trades:
                if pos.entry_day == ts:
                    out.append(pos.r_multiple)
    return out
```

Finally, append the reference + verdict helpers:

```python
def _reference_metrics(btc_returns, fence_idx):
    from moonface.foundation.metrics import equity_summary_from_returns
    full = equity_summary_from_returns(btc_returns)
    tail = equity_summary_from_returns(btc_returns[fence_idx:])
    return {"full_mar": full.mar, "full_sharpe": full.sharpe,
            "full_dd": full.max_drawdown, "tail_mar": tail.mar,
            "tail_sharpe": tail.sharpe, "tail_dd": tail.max_drawdown}


def _write_verdict(out_root: Path, verdict: str, rows: list[dict],
                   dsr: dict[str, float], reference: dict) -> None:
    lines = [
        "# universe_donchian v1 — verdict",
        "",
        f"- **Status:** {verdict.upper()}",
        f"- **Domain:** {UNIVERSE_DONCHIAN_DOMAIN} (frozen Donchian engine on a"
        " dynamic top-5 alt universe by abnormal 24h quote-volume expansion, vs"
        " a static broad-basket control)",
        "- **Construction:** simulate_donchian(entry_n=40, trail_n=20 @ 4h,"
        " long_only=False) on universe_data alt perps; COST_FRACTION=0.001"
        " round-trip + funding; top-5/30d-ratio screener default.",
        "- **Promotion requires >=1 treatment spec to clear stages 1, 2, 3.5,"
        " DSR(>=0.95, n_trials=4), and 4 AND strictly dominate its static-basket"
        " control on portfolio MAR & Sharpe at holdout, WF aggregate, and lockbox"
        " tail.",
        f"- **BTC/USDT deployed reference (non-gating):** full MAR"
        f" {reference['full_mar']:.3f}, tail MAR {reference['tail_mar']:.3f},"
        f" tail DD {reference['tail_dd']:.3f}.",
        "",
        "| screener | final stage | screen n | holdout trt MAR | WF folds |"
        " DSR | tail trt MAR |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        m = r["m"]
        label = (f"{r['spec'].entry['params'].get('top_n')}x"
                 f"{r['spec'].entry['params'].get('lookback_days')}d"
                 f"-{r['spec'].entry['params'].get('metric')}")
        wf_folds = r["wf"]["folds"] if r.get("wf") else "-"
        dsr_v = f"{r['dsr']:.4f}" if isinstance(r.get("dsr"), float) else "-"
        tail_mar = (f"{r['tail']['tail_treatment_mar']:.3f}"
                    if r.get("tail") else "-")
        lines.append(f"| {label} | {r['stage']} | {m['screen_trades']} | "
                     f"{m['holdout_treatment_mar']:.3f} | {wf_folds} | "
                     f"{dsr_v} | {tail_mar} |")
    lines += ["",
              "Closed by the pre-committed kill rule if negative: no v2 universe"
              " rule, no filter relaxation, no long-only flip, no exit change, no"
              " top-N re-tuning. The universe-expansion lever is terminal for the"
              " frozen Donchian engine on a closed-negative verdict."]
    d = out_root / UNIVERSE_DONCHIAN_DOMAIN
    d.mkdir(parents=True, exist_ok=True)
    (d / "verdict.md").write_text("\n".join(lines))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_universe_donchian_runner.py -v`
Expected: PASS (3 tests). The synthetic universe is too small/flat to promote, so the verdict is `closed_negative` with a written `verdict.md` — the test asserts the path + status mechanics, not the sign.

- [ ] **Step 5: Commit**

```bash
git add src/moonface/research/universe_donchian_runner.py tests/test_universe_donchian_runner.py
git commit -m "feat(research): universe_donchian bespoke runner + verdict writer"
```

---

## Task 6: CLI subcommand

**Files:**
- Modify: `tools/research.py` (add import + `cmd_universe_donchian` + subparser)
- Modify: `tests/test_research_cli.py` (append `TestUniverseDonchianCli`)

**Interfaces:**
- Consumes: Task 5's `universe_donchian_runner.{UNIVERSE_DONCHIAN_DOMAIN, register, run_domain}`.
- Produces: a `universe-donchian` subcommand mirroring `orderflow`.

- [ ] **Step 1: Write the failing test**

Read the existing `tests/test_research_cli.py` to copy its style (argparse `parse_args` + captured stdout, no network). Append:

```python
# append to tests/test_research_cli.py
import unittest
from unittest import mock

import tools.research as research


class TestUniverseDonchianCli(unittest.TestCase):
    def test_subcommand_registers_and_runs(self):
        with mock.patch.object(research, "register_universe_donchian") as reg, \
             mock.patch.object(research, "run_universe_donchian",
                               return_value="closed_negative") as run:
            args = research.build_parser().parse_args(
                ["universe-donchian", "--cache-dir", ".backtest_cache"])
            self.assertEqual(args.fn.__name__, "cmd_universe_donchian")
            args.fn(args)
            reg.assert_called_once()
            run.assert_called_once()

    def test_subparser_attached(self):
        args = research.build_parser().parse_args(["universe-donchian"])
        self.assertEqual(args.fn.__name__, "cmd_universe_donchian")
        self.assertEqual(args.cache_dir, ".backtest_cache")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_research_cli.py::TestUniverseDonchianCli -v`
Expected: FAIL (`register_universe_donchian` / `run_universe_donchian` not importable; subcommand unknown).

- [ ] **Step 3: Write minimal implementation**

In `tools/research.py`, add to the import block (after the `orderflow_runner` import):

```python
from moonface.research.universe_donchian_runner import (
    UNIVERSE_DONCHIAN_DOMAIN,
    register as register_universe_donchian,
    run_domain as run_universe_donchian)
```

Add the command function after `cmd_orderflow`:

```python
def cmd_universe_donchian(args: argparse.Namespace) -> None:
    """Register + run the universe_donchian domain and print the verdict.
    Drives the frozen Donchian engine over a dynamic top-5 alt universe
    selected by abnormal 24h quote-volume expansion, against a static-basket
    control, with a one-touch lockbox."""
    store = _store(args)
    now_ms = int(time.time() * 1000)
    register_universe_donchian(store, now_ms)
    verdict = run_universe_donchian(store, args.cache_dir, Path(args.out_root))
    print(f"{UNIVERSE_DONCHIAN_DOMAIN} v1: {verdict}")
    print(f"verdict: {Path(args.out_root) / UNIVERSE_DONCHIAN_DOMAIN / 'verdict.md'}")
```

In `build_parser`, after the `orderflow` subparser block:

```python
    ud = sub.add_parser("universe-donchian",
                        help="register + run universe_donchian (frozen Donchian"
                             " on a dynamic top-5 alt universe by quote-volume"
                             " expansion, vs static-basket control)")
    ud.add_argument("--cache-dir", default=".backtest_cache")
    ud.set_defaults(fn=cmd_universe_donchian)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_research_cli.py -v`
Expected: PASS (whole CLI test file green, including existing orderflow/voltarget cases).

- [ ] **Step 5: Commit**

```bash
git add tools/research.py tests/test_research_cli.py
git commit -m "feat(research): universe-donchian CLI subcommand"
```

---

## Task 7: Execute on real data, write verdict, update memory

**Files:**
- Run: `python tools/research.py universe-donchian` (produces `experiments/research/universe_donchian/verdict.md`).
- Modify (force-add): `experiments/universe_donchian/verdict.md` (copy of the run output, committed for the record).
- Update: the `universe-donchian-preregistration` memory file + MEMORY.md index line with the verdict.

**Interfaces:** none (execution + record-keeping).

- [ ] **Step 1: Run the full suite green before the real run**

Run: `python -m pytest tests/test_universe_donchian.py tests/test_universe_donchian_wf.py tests/test_universe_donchian_runner.py tests/test_research_cli.py -v`
Expected: all PASS. Also run the import-boundary guard: `python -m pytest tests/test_import_boundaries.py -v` → PASS (no layer violation from the new modules; `research` importing `foundation` is allowed).

- [ ] **Step 2: Execute the program on real data**

Run: `python tools/research.py universe-donchian`
Expected: prints `universe_donchian v1: closed_positive` or `closed_negative` and the verdict path. First run fetches 4h candles + funding for the candidate alt set (cached under `.backtest_cache/`); expect significant runtime on a cold cache. If a wide-window partial-cache returns suspiciously few candles for a symbol (per the OHLCV-cache no-tail-backfill memory), rename the partial `uni1d_`/4h cache file aside and re-run to force a full network backfill.

- [ ] **Step 3: Record the verdict + sanity-check the numbers**

Read `experiments/research/universe_donchian/verdict.md`. Verify the BTC reference tail MAR is negative or near-zero (sanity: it should resemble the documented 2025-26 decay). Copy it into the force-tracked record:

```bash
mkdir -p experiments/universe_donchian
cp experiments/research/universe_donchian/verdict.md experiments/universe_donchian/VERDICT_v1.md
git add -f experiments/universe_donchian/VERDICT_v1.md
```

Commit:

```bash
git commit -m "docs(research): universe_donchian v1 verdict - <closed_positive|closed_negative>"
```

- [ ] **Step 4: Update memory**

Edit the author's private notes (`universe-donchian-preregistration.md`, not published): change status from "OPEN / awaiting review" to the verdict (e.g. "CLOSED NEGATIVE 2026-07-02" or "PAPER-LIVE WATCHING 2026-07-02"), record the headline metrics (per-spec final stages, BTC reference tail MAR), and note the kill-rule consequence. Update the MEMORY.md index line to match.

- [ ] **Step 5: Final full-suite green**

Run: `python -m pytest -q`
Expected: all green.

---

## Self-Review

**1. Spec coverage:**
- §1 Hypothesis (frozen engine on dynamic top-5 universe, L/S, beat static basket) → Tasks 1–3 (screener + specs `long_only=False` + `control_for` static).
- §2 Construction (engine params, exclusions, expansion ratio, liquidity $20M, age 90d, top_n=5, weekly rebuild, cost, sizing G=1.0) → Task 1 `_EXCLUDE_BASES`/`expansion_ratio`/`screen_universe`/`build_membership`; Task 3 `ENGINE_PARAMS`/`_BASE_FILTERS`/`GROSS`; Task 2 cost + f_slot.
- §3 Treatment vs control (static basket dominance) → Task 3 `control_for`/`dominates`/`evaluate_dominant`/`lockbox_dominant`.
- §4 Evaluation ladder (stages 1–4 + WF + dominance, ladder constants unmutated) → Task 3 `stage1/2/4_of` (read ladder constants), Task 4 WF, Task 5 runner drives DSR + lockbox.
- §5 Decision + kill rule → Task 5 `run_domain` promotion logic + `_write_verdict` footer.
- §6 Data (Vision S3, `uni1d_` quote volume, listing age from first bar, delisting) → Task 5 `_load_engine_trades`/`run_domain` via `universe_data`.
- §7 Runner architecture (bespoke pattern, `config.runner`, one-touch lockbox) → Task 5.
- §8 Run (`python tools/research.py universe-donchian`) → Task 6 + Task 7.
- Coverage gate (≥ lookback history) → Task 1 `_qualifies`. 2× cost-stress: reported via `equity_summary_from_returns` on a doubled-cost re-run is NOT auto-wired; **accepted gap** — the spec marks 2× as REPORTED non-gating, so the verdict's headline uses the base cost only. (If desired, add a one-line extra call in Task 7 Step 3.)

**2. Placeholder scan:** No TBD/TODO/"add error handling"/"implement later" anywhere. All code blocks are complete and final, including the Task 5 `_screen_pooled_trades` helper (single clean definition; eligibility read from the weekly `membership` so it matches the simulator). All test code is complete.

**3. Type consistency:** `Position(side, entry_day, exit_day, r_multiple)` is defined in Task 2 and consumed identically in Task 2 sim, Task 3 (no), Task 5 `_load_engine_trades` (builds `Position`) and `_screen_pooled_trades` (reads `pos.entry_day/.r_multiple`). `simulate_portfolio(calendar, membership, book_size, positions, daily_close, daily_funding, gross, cost)` signature matches across Task 2 def, Task 3 evaluators (indirect), and Task 5 call sites. `build_membership` returns `(membership, book_size)` consumed as such in Task 5. `evaluate_dominant(t_returns, c_returns, pooled_trades, fence_idx, screen_fraction)` matches Task 3 def + Task 5 call. `walk_forward(t_returns, c_returns, …)` matches Task 4 def + Task 5 call (`t_ret[:fence_idx]`). `dominates` imported in both `universe_donchian_wf.py` and used in `universe_donchian.py`. `_BASE_FILTERS`/`_qualifies` imported from `universe_donchian` in the runner. All consistent.
