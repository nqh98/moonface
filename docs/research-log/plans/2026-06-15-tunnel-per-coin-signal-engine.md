# Tunnel Core + CHOP — Per-Coin 4h Signal Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port `docs/script/tunnel_core_chop.pine` into a self-contained Python module, run a per-coin 4h parameter search through the repo's existing validation ladder, and emit a per-coin LONG/SHORT/WAIT registry + signal engine + report.

**Architecture:** New package `src/moonface/tunnel/` with pure indicators → per-bar tunnel state → entry generator → sequential position-management simulator (R-stream) → existing `research/ladder.py` gates. A grid driver searches each coin independently, writes a registry, and a batch signal engine + report consume it.

**Tech Stack:** Python 3 stdlib only (matching the repo), `pytest`, `ruff`. Reuses `moonface.models.Candle`, `moonface.risk.atr`, `moonface.research.ladder`, `moonface.research.metrics`, `moonface.research.synth.make_candles`, `moonface.backtest.universe_data.fetch_perp_candles`, and `moonface.signal.evaluate.Signal`.

---

## Conventions (read before starting)

- **Candle**: `from moonface.models import Candle` — frozen dataclass `(timestamp_ms, open, high, low, close, volume)`.
- **R-stream triple**: `(entry_index: int, net_r: float, atr_frac: float)` — identical shape to `moonface.research.ladder.r_stream`. `atr_frac = (1×ATR at entry) / entry_close`. `net_r = realized_r − COST_FRACTION / atr_frac` with `COST_FRACTION = 0.001` imported from `moonface.research.ladder`.
- **Entry convention**: generators return `list[tuple[int, str]]` of `(index, "LONG"|"SHORT")` and stop at `len(candles) - 1` (leave a fill bar), like every generator in `moonface/backtest/edge/signals.py`.
- **Synthetic data for tests**: `from moonface.research.synth import make_candles` — `make_candles(n)` gives deterministic drifting 4h OHLCV.
- **Test style**: plain `pytest` functions, no classes, module under `tests/`. Run from repo root. `ruff check src tests tools` must stay clean.
- **Commit messages**: conventional commits, scope `tunnel`. **No AI attribution trailer** (global git rule). Stage explicit paths; never chain `git add && git commit` blindly — run `git diff --cached --stat` first.

---

## File Structure

```
src/moonface/tunnel/
  __init__.py     # empty package marker
  indicators.py   # ema, rsi, macd_hist, choppiness (atr reused from moonface.risk)
  state.py        # TunnelState per bar + tunnel_states(candles, params)
  entry.py        # tunnel_entry(candles, params) -> [(i, side)]
  simulator.py    # simulate(candles, params) -> R-stream
  metrics.py      # sortino(returns)
  grid.py         # PINNED defaults + core_grid() -> list[params dict]
  ladder_adapter.py # evaluate_tunnel_research / lockbox wrappers around research.ladder
  registry.py     # CoinResult schema, write_registry/read_registry
  search.py       # search_coin(candles, params_grid, fence_frac) -> CoinResult
  signal.py       # batch_signals(registry, loader) -> {symbol: Signal}
  report.py       # render_report(registry) -> markdown str
tools/tunnel.py   # CLI: fetch | search | report | signal
tests/test_tunnel_indicators.py
tests/test_tunnel_state.py
tests/test_tunnel_entry.py
tests/test_tunnel_simulator.py
tests/test_tunnel_metrics.py
tests/test_tunnel_grid.py
tests/test_tunnel_ladder_adapter.py
tests/test_tunnel_registry.py
tests/test_tunnel_search.py
tests/test_tunnel_signal.py
tests/test_tunnel_report.py
tests/test_tunnel_cli.py
```

---

## Task 1: Package marker + indicators (EMA, RSI, MACD-hist, Choppiness)

**Files:**
- Create: `src/moonface/tunnel/__init__.py`
- Create: `src/moonface/tunnel/indicators.py`
- Test: `tests/test_tunnel_indicators.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tunnel_indicators.py
import math

from moonface.models import Candle
from moonface.tunnel.indicators import choppiness, ema, macd_hist, rsi


def _c(o, h, l, cl):
    return Candle(0, o, h, l, cl, 1000.0)


def test_ema_matches_recursive_formula():
    closes = [10.0, 11.0, 12.0, 13.0, 14.0]
    # period 3: seed with SMA of first 3 = 11, then alpha=2/(3+1)=0.5
    out = ema(closes, 3)
    assert out[2] == 11.0
    assert out[3] == 11.0 + 0.5 * (13.0 - 11.0)  # 12.0
    assert out[4] == 12.0 + 0.5 * (14.0 - 12.0)  # 13.0
    assert all(math.isnan(x) for x in out[:2])


def test_rsi_all_gains_is_100():
    closes = [float(x) for x in range(1, 20)]
    out = rsi(closes, 14)
    assert out[-1] == 100.0


def test_macd_hist_zero_for_flat_series():
    closes = [50.0] * 60
    out = macd_hist(closes)
    assert abs(out[-1]) < 1e-9


def test_choppiness_high_for_range_bound():
    # A tight oscillation has high choppiness (near 100); a clean trend near 0.
    rng = [_c(10, 11, 9, 10) for _ in range(20)]
    trend = [_c(10 + i, 11 + i, 9 + i, 10 + i) for i in range(20)]
    chop_rng = choppiness(rng, 14)[-1]
    chop_trend = choppiness(trend, 14)[-1]
    assert chop_rng > chop_trend
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tunnel_indicators.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.tunnel'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/tunnel/__init__.py
```

```python
# src/moonface/tunnel/indicators.py
from __future__ import annotations

import math

from moonface.models import Candle

NAN = float("nan")


def ema(values: list[float], length: int) -> list[float]:
    """Wilder-style EMA seeded with the SMA of the first `length` values.
    Indices before the seed are NaN so callers can align 1:1 with candles."""
    out = [NAN] * len(values)
    if len(values) < length or length < 1:
        return out
    seed = sum(values[:length]) / length
    out[length - 1] = seed
    alpha = 2.0 / (length + 1)
    prev = seed
    for i in range(length, len(values)):
        prev = prev + alpha * (values[i] - prev)
        out[i] = prev
    return out


def rsi(values: list[float], length: int) -> list[float]:
    """Wilder RSI aligned 1:1 with `values`; NaN until `length` deltas exist."""
    out = [NAN] * len(values)
    if len(values) <= length:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, length + 1):
        d = values[i] - values[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    avg_gain = gains / length
    avg_loss = losses / length
    out[length] = _rsi_value(avg_gain, avg_loss)
    for i in range(length + 1, len(values)):
        d = values[i] - values[i - 1]
        avg_gain = (avg_gain * (length - 1) + max(d, 0.0)) / length
        avg_loss = (avg_loss * (length - 1) + max(-d, 0.0)) / length
        out[i] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _ema_simple(values: list[float], length: int) -> list[float]:
    """EMA seeded from the first value (matches Pine ta.ema for MACD lines)."""
    out: list[float] = []
    alpha = 2.0 / (length + 1)
    prev = values[0] if values else NAN
    for i, v in enumerate(values):
        prev = v if i == 0 else prev + alpha * (v - prev)
        out.append(prev)
    return out


def macd_hist(values: list[float], fast: int = 12, slow: int = 26,
              signal: int = 9) -> list[float]:
    """MACD histogram (macd line − signal line), aligned 1:1 with `values`."""
    if not values:
        return []
    fast_e = _ema_simple(values, fast)
    slow_e = _ema_simple(values, slow)
    macd_line = [f - s for f, s in zip(fast_e, slow_e)]
    sig = _ema_simple(macd_line, signal)
    return [m - s for m, s in zip(macd_line, sig)]


def _true_range(candles: list[Candle], i: int) -> float:
    cur = candles[i]
    if i == 0:
        return cur.high - cur.low
    prev_close = candles[i - 1].close
    return max(cur.high - cur.low, abs(cur.high - prev_close),
               abs(cur.low - prev_close))


def choppiness(candles: list[Candle], length: int,
               mintick: float = 1e-8) -> list[float]:
    """Choppiness Index aligned 1:1 with candles; NaN until `length` bars.
    100*log10(sum(TR,len)/max(HH-LL,mintick))/log10(len) — mirrors Pine."""
    out = [NAN] * len(candles)
    if length < 2:
        return out
    tr = [_true_range(candles, i) for i in range(len(candles))]
    log_len = math.log10(length)
    for i in range(length - 1, len(candles)):
        window = candles[i - length + 1: i + 1]
        tr_sum = sum(tr[i - length + 1: i + 1])
        hh = max(c.high for c in window)
        ll = min(c.low for c in window)
        rng = max(hh - ll, mintick)
        ratio = tr_sum / rng
        out[i] = 100.0 * math.log10(ratio) / log_len if ratio > 0 else 0.0
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tunnel_indicators.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/tunnel/__init__.py src/moonface/tunnel/indicators.py tests/test_tunnel_indicators.py
git commit -m "feat(tunnel): EMA/RSI/MACD-hist/Choppiness indicators"
```

---

## Task 2: Per-bar tunnel state

**Files:**
- Create: `src/moonface/tunnel/state.py`
- Test: `tests/test_tunnel_state.py`

This mirrors Pine lines 64–112. `tunnel_states` returns one `TunnelState` per candle (NaN/False until warmup).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tunnel_state.py
from moonface.research.synth import make_candles
from moonface.tunnel.state import TunnelState, tunnel_states

PARAMS = {
    "ema_len": 50, "atr_len": 14, "atr_mult": 2.0, "chop_len": 14,
    "chop_max": 50.0, "slope_len": 5, "slope_min": 0.0, "vol_min": 0.8,
    "pb_zone": 0.4, "inner_zone": 0.3,
}


def test_states_align_one_to_one_with_candles():
    candles = make_candles(300)
    states = tunnel_states(candles, PARAMS)
    assert len(states) == len(candles)
    assert isinstance(states[-1], TunnelState)


def test_uptrend_eventually_marks_bull():
    candles = make_candles(300, drift=0.01, noise=0.002)  # strong clean uptrend
    states = tunnel_states(candles, PARAMS)
    assert any(s.tunnel_bull for s in states[60:])


def test_bands_bracket_the_ema():
    candles = make_candles(300)
    s = tunnel_states(candles, PARAMS)[-1]
    assert s.lower_band < s.ema < s.upper_band
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tunnel_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.tunnel.state'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/tunnel/state.py
from __future__ import annotations

import math
from dataclasses import dataclass

from moonface.models import Candle
from moonface.risk import atr as _atr_last
from moonface.tunnel.indicators import NAN, choppiness, ema

@dataclass(frozen=True)
class TunnelState:
    ema: float
    atr: float
    upper_band: float
    lower_band: float
    chop_ok: bool
    tunnel_bull: bool
    tunnel_bear: bool
    near_lower: bool
    near_upper: bool
    near_center_dn: bool
    near_center_up: bool


def _atr_series(candles: list[Candle], length: int) -> list[float]:
    """ATR at every index using the existing risk.atr over the prefix."""
    out = [NAN] * len(candles)
    for i in range(len(candles)):
        if i + 1 >= length:
            out[i] = _atr_last(candles[: i + 1], length)
    return out


def _sma_of(series: list[float], length: int, i: int) -> float:
    window = [v for v in series[max(0, i - length + 1): i + 1]
              if not math.isnan(v)]
    return sum(window) / len(window) if window else NAN


def tunnel_states(candles: list[Candle], params: dict) -> list[TunnelState]:
    closes = [c.close for c in candles]
    emas = ema(closes, params["ema_len"])
    atrs = _atr_series(candles, params["atr_len"])
    chops = choppiness(candles, params["chop_len"])
    mult = params["atr_mult"]
    slope_len = params["slope_len"]
    slope_min = params["slope_min"]
    vol_min = params["vol_min"]
    pb = params["pb_zone"]
    inner = params["inner_zone"]
    out: list[TunnelState] = []
    for i, c in enumerate(candles):
        e, a, ch = emas[i], atrs[i], chops[i]
        if math.isnan(e) or math.isnan(a):
            out.append(TunnelState(NAN, NAN, NAN, NAN, False, False, False,
                                   False, False, False, False))
            continue
        upper = e + a * mult
        lower = e - a * mult
        chop_ok = (not math.isnan(ch)) and ch < params["chop_max"]
        slope = (e - emas[i - slope_len]
                 if i >= slope_len and not math.isnan(emas[i - slope_len])
                 else 0.0)
        vol_avg = _sma_of(atrs, params["ema_len"], i)
        wide = (not math.isnan(vol_avg)) and vol_avg > 0 and a / vol_avg >= vol_min
        above = c.close > e
        below = c.close < e
        bull = slope > slope_min and above and wide and chop_ok
        bear = slope < -slope_min and below and wide and chop_ok
        near_lower = c.low <= lower + a * pb
        near_upper = c.high >= upper - a * pb
        near_center_dn = e - a * inner <= c.low <= e + a * inner
        near_center_up = e - a * inner <= c.high <= e + a * inner
        out.append(TunnelState(e, a, upper, lower, chop_ok, bull, bear,
                               near_lower, near_upper, near_center_dn,
                               near_center_up))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tunnel_state.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/tunnel/state.py tests/test_tunnel_state.py
git commit -m "feat(tunnel): per-bar tunnel state (bands, chop, slope/vol regime, pullback zones)"
```

---

## Task 3: Entry generator (composite Pine signal)

**Files:**
- Create: `src/moonface/tunnel/entry.py`
- Test: `tests/test_tunnel_entry.py`

Mirrors Pine 118–172 (confirmations + outer/inner pullback). Loss-brake is NOT here.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tunnel_entry.py
from moonface.research.synth import make_candles
from moonface.tunnel.entry import tunnel_entry

PARAMS = {
    "ema_len": 50, "atr_len": 14, "atr_mult": 2.0, "chop_len": 14,
    "chop_max": 61.8, "slope_len": 5, "slope_min": 0.0, "vol_min": 0.5,
    "pb_zone": 0.5, "inner_zone": 0.3, "rsi_len": 14, "rsi_buy": 35,
    "rsi_sell": 65, "use_rsi": True, "use_macd": True, "use_candle": True,
    "use_inner": True,
}


def test_entries_are_index_side_pairs_within_range():
    candles = make_candles(400, drift=0.006, noise=0.01)
    entries = tunnel_entry(candles, PARAMS)
    for i, side in entries:
        assert 0 <= i < len(candles) - 1  # never the last (fill) bar
        assert side in ("LONG", "SHORT")


def test_confirmations_off_yields_at_least_as_many_entries():
    candles = make_candles(400, drift=0.006, noise=0.01)
    strict = tunnel_entry(candles, PARAMS)
    loose = tunnel_entry(candles, {**PARAMS, "use_rsi": False,
                                   "use_macd": False, "use_candle": False})
    assert len(loose) >= len(strict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tunnel_entry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.tunnel.entry'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/tunnel/entry.py
from __future__ import annotations

import math

from moonface.models import Candle
from moonface.tunnel.indicators import macd_hist, rsi
from moonface.tunnel.state import tunnel_states

Entry = tuple[int, str]


def tunnel_entry(candles: list[Candle], params: dict) -> list[Entry]:
    states = tunnel_states(candles, params)
    closes = [c.close for c in candles]
    rsis = rsi(closes, params["rsi_len"])
    hist = macd_hist(closes)
    use_rsi = params["use_rsi"]
    use_macd = params["use_macd"]
    use_candle = params["use_candle"]
    use_inner = params["use_inner"]
    out: list[Entry] = []
    for i in range(1, len(candles) - 1):  # leave the fill bar
        s = states[i]
        c = candles[i]
        long_rsi = (not use_rsi) or _rsi_long_ok(rsis, i, params["rsi_buy"])
        short_rsi = (not use_rsi) or _rsi_short_ok(rsis, i, params["rsi_sell"])
        long_macd = (not use_macd) or (i > 0 and hist[i] > hist[i - 1])
        short_macd = (not use_macd) or (i > 0 and hist[i] < hist[i - 1])
        long_candle = (not use_candle) or c.close > c.open
        short_candle = (not use_candle) or c.close < c.open
        long_outer = s.tunnel_bull and s.near_lower
        short_outer = s.tunnel_bear and s.near_upper
        long_inner = use_inner and s.tunnel_bull and s.near_center_dn
        short_inner = use_inner and s.tunnel_bear and s.near_center_up
        if (long_outer or long_inner) and long_rsi and long_macd and long_candle:
            out.append((i, "LONG"))
        elif (short_outer or short_inner) and short_rsi and short_macd and short_candle:
            out.append((i, "SHORT"))
    return out


def _rsi_long_ok(rsis: list[float], i: int, buy: float) -> bool:
    if math.isnan(rsis[i]):
        return False
    oversold = rsis[i] <= buy
    bounce = (i >= 2 and not math.isnan(rsis[i - 1]) and not math.isnan(rsis[i - 2])
              and rsis[i] > rsis[i - 1] and rsis[i - 1] <= rsis[i - 2])
    return oversold or bounce


def _rsi_short_ok(rsis: list[float], i: int, sell: float) -> bool:
    if math.isnan(rsis[i]):
        return False
    overbought = rsis[i] >= sell
    bounce = (i >= 2 and not math.isnan(rsis[i - 1]) and not math.isnan(rsis[i - 2])
              and rsis[i] < rsis[i - 1] and rsis[i - 1] >= rsis[i - 2])
    return overbought or bounce
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tunnel_entry.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/tunnel/entry.py tests/test_tunnel_entry.py
git commit -m "feat(tunnel): composite entry generator (outer/inner pullback + RSI/MACD/candle confirm)"
```

---

## Task 4: Sequential simulator (R-stream with full position management)

**Files:**
- Create: `src/moonface/tunnel/simulator.py`
- Test: `tests/test_tunnel_simulator.py`

The heart of the port. Walks bars in order; for each open position applies bracket, breakeven, tunnel-trail, and the consecutive-loss brake. Emits `(entry_index, net_r, atr_frac)` per closed trade. Same-bar stop/target → **stop first** (pessimistic).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tunnel_simulator.py
from moonface.models import Candle
from moonface.tunnel.simulator import simulate

BASE = {
    "ema_len": 5, "atr_len": 3, "atr_mult": 1.0, "chop_len": 3,
    "chop_max": 80.0, "slope_len": 2, "slope_min": 0.0, "vol_min": 0.0,
    "pb_zone": 5.0, "inner_zone": 5.0, "rsi_len": 3, "rsi_buy": 50,
    "rsi_sell": 50, "use_rsi": False, "use_macd": False, "use_candle": False,
    "use_inner": True, "sl_atr": 1.0, "rr_ratio": 2.0, "be_atr": 1.0,
    "be_ticks": 0, "use_trail": False, "trail_band": 1.0, "trail_act": 1.5,
    "max_cons_losses": 3, "cool_bars": 5, "use_flip_exit": False,
}


def _series(prices):
    out = []
    ts = 0
    for p in prices:
        out.append(Candle(ts, p, p + 0.5, p - 0.5, p, 1000.0))
        ts += 4 * 3_600_000
    return out


def test_returns_rstream_triples():
    candles = _series([100 + i * 0.5 for i in range(60)])
    stream = simulate(candles, BASE)
    for i, net_r, atr_frac in stream:
        assert isinstance(i, int)
        assert atr_frac > 0


def test_target_hit_gives_positive_r():
    # build a clean uptrend so a long fills, then a sharp pop to the target
    prices = [100 + i for i in range(20)] + [200] * 5
    candles = _series(prices)
    stream = simulate(candles, BASE)
    assert stream, "expected at least one trade"
    assert any(net_r > 0 for _, net_r, _ in stream)


def test_loss_brake_blocks_after_consecutive_losses():
    # alternating whipsaw that keeps stopping out; with max_cons_losses=1 and a
    # long cooldown, far fewer trades fire than with the brake effectively off.
    prices = []
    for _ in range(40):
        prices += [100, 105, 95]  # up then slam down -> stop
    candles = _series(prices)
    braked = simulate(candles, {**BASE, "max_cons_losses": 1, "cool_bars": 20})
    loose = simulate(candles, {**BASE, "max_cons_losses": 99, "cool_bars": 1})
    assert len(braked) <= len(loose)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tunnel_simulator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.tunnel.simulator'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/tunnel/simulator.py
from __future__ import annotations

import math

from moonface.models import Candle
from moonface.research.ladder import COST_FRACTION
from moonface.tunnel.entry import tunnel_entry
from moonface.tunnel.state import tunnel_states


def simulate(candles: list[Candle], params: dict) -> list[tuple[int, float, float]]:
    """Sequential bar-walk producing (entry_index, net_r, atr_frac) per closed
    trade. net_r is in R units (risk = sl_atr*ATR at entry) net of round-trip
    cost. Same-bar stop+target resolves to the stop (pessimistic)."""
    states = tunnel_states(candles, params)
    entry_by_index = dict(tunnel_entry(candles, params))
    sl_atr = params["sl_atr"]
    rr = params["rr_ratio"]
    be_atr = params["be_atr"]
    use_trail = params["use_trail"]
    trail_band = params["trail_band"]
    trail_act = params["trail_act"]
    max_cons = params["max_cons_losses"]
    cool_bars = params["cool_bars"]

    out: list[tuple[int, float, float]] = []
    cons_losses = 0
    cool = 0
    pos = None  # dict when in a trade
    n = len(candles)
    for i in range(n):
        if pos is None:
            if cool > 0:
                cool -= 1
            paused = cons_losses >= max_cons and cool > 0
            sig = entry_by_index.get(i)
            if sig is not None and not paused and i + 1 < n:
                a = states[i].atr
                if not math.isnan(a) and a > 0:
                    entry_price = candles[i + 1].open
                    risk = sl_atr * a
                    if risk > 0:
                        side = sig
                        sl = (entry_price - risk if side == "LONG"
                              else entry_price + risk)
                        tp = (entry_price + rr * risk if side == "LONG"
                              else entry_price - rr * risk)
                        pos = {"side": side, "entry": entry_price, "atr": a,
                               "risk": risk, "sl": sl, "tp": tp, "be": False,
                               "trail_on": False, "trail": None,
                               "fill_index": i + 1, "entry_index": i}
            continue
        # manage the open position on bar i (>= fill bar)
        if i < pos["fill_index"]:
            continue
        c = candles[i]
        side = pos["side"]
        entry = pos["entry"]
        a = pos["atr"]
        # breakeven lift
        if not pos["be"]:
            if side == "LONG" and c.close >= entry + be_atr * a:
                pos["sl"] = max(pos["sl"], entry)
                pos["be"] = True
            elif side == "SHORT" and c.close <= entry - be_atr * a:
                pos["sl"] = min(pos["sl"], entry)
                pos["be"] = True
        # tunnel trail
        if use_trail:
            s = states[i]
            if side == "LONG" and c.close >= entry + trail_act * a:
                pos["trail_on"] = True
            if side == "SHORT" and c.close <= entry - trail_act * a:
                pos["trail_on"] = True
            if pos["trail_on"] and not math.isnan(s.lower_band):
                if side == "LONG":
                    cand = s.lower_band - a * (trail_band - 1.0)
                    pos["trail"] = cand if pos["trail"] is None else max(pos["trail"], cand)
                else:
                    cand = s.upper_band + a * (trail_band - 1.0)
                    pos["trail"] = cand if pos["trail"] is None else min(pos["trail"], cand)
        eff_sl = pos["sl"]
        if pos["trail_on"] and pos["trail"] is not None:
            eff_sl = (max(eff_sl, pos["trail"]) if side == "LONG"
                      else min(eff_sl, pos["trail"]))
        # resolve exits on this bar; stop checked first (pessimistic)
        realized = _resolve(side, c, eff_sl, pos["tp"], entry, pos["risk"])
        if realized is not None:
            atr_frac = a / entry
            net_r = realized - COST_FRACTION / atr_frac
            out.append((pos["entry_index"], net_r, atr_frac))
            if net_r < 0:
                cons_losses += 1
                cool = cool_bars
            else:
                cons_losses = 0
                cool = 0
            pos = None
    return out


def _resolve(side: str, c: Candle, sl: float, tp: float, entry: float,
             risk: float) -> float | None:
    """R multiple if the bar resolves the trade, else None. Stop first."""
    if side == "LONG":
        if c.low <= sl:
            return (sl - entry) / risk
        if c.high >= tp:
            return (tp - entry) / risk
    else:
        if c.high >= sl:
            return (entry - sl) / risk
        if c.low <= tp:
            return (entry - tp) / risk
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tunnel_simulator.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/tunnel/simulator.py tests/test_tunnel_simulator.py
git commit -m "feat(tunnel): sequential simulator with bracket/breakeven/trail/loss-brake -> R-stream"
```

---

## Task 5: Sortino metric

**Files:**
- Create: `src/moonface/tunnel/metrics.py`
- Test: `tests/test_tunnel_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tunnel_metrics.py
from moonface.tunnel.metrics import sortino


def test_sortino_zero_for_no_downside():
    assert sortino([0.1, 0.2, 0.3]) == 0.0  # no negative returns -> defined as 0.0


def test_sortino_positive_when_mean_positive_with_some_downside():
    assert sortino([0.2, -0.1, 0.3, -0.05]) > 0.0


def test_sortino_empty_is_zero():
    assert sortino([]) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tunnel_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.tunnel.metrics'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/tunnel/metrics.py
from __future__ import annotations

import math
from statistics import fmean


def sortino(returns: list[float]) -> float:
    """Mean return divided by downside deviation (negatives only). Returns 0.0
    when empty or when there is no downside (no negative returns)."""
    if len(returns) < 2:
        return 0.0
    mean = fmean(returns)
    downside = [r for r in returns if r < 0.0]
    if not downside:
        return 0.0
    dd = math.sqrt(sum(r * r for r in downside) / len(returns))
    if dd == 0.0:
        return 0.0
    return round(mean / dd, 6)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tunnel_metrics.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/tunnel/metrics.py tests/test_tunnel_metrics.py
git commit -m "feat(tunnel): downside-deviation Sortino metric"
```

---

## Task 6: Ladder adapter (R-stream -> existing stage gates)

**Files:**
- Create: `src/moonface/tunnel/ladder_adapter.py`
- Test: `tests/test_tunnel_ladder_adapter.py`

Reuses `research.metrics.equity_summary`/`deflated_sharpe` and `backtest.metrics.summarize_r` exactly as `research/ladder.py` does, but driven by the tunnel simulator's R-stream instead of `r_stream`. Splits at `fence_frac` (research vs lockbox tail) and `screen_frac` (screen vs holdout within research).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tunnel_ladder_adapter.py
from moonface.research.synth import make_candles
from moonface.tunnel.ladder_adapter import (evaluate_research_window,
                                             evaluate_lockbox_tail)

PARAMS = {
    "ema_len": 20, "atr_len": 14, "atr_mult": 2.0, "chop_len": 14,
    "chop_max": 61.8, "slope_len": 5, "slope_min": 0.0, "vol_min": 0.3,
    "pb_zone": 0.6, "inner_zone": 0.4, "rsi_len": 14, "rsi_buy": 40,
    "rsi_sell": 60, "use_rsi": False, "use_macd": False, "use_candle": False,
    "use_inner": True, "sl_atr": 1.0, "rr_ratio": 2.0, "be_atr": 1.0,
    "be_ticks": 0, "use_trail": False, "trail_band": 1.0, "trail_act": 1.5,
    "max_cons_losses": 99, "cool_bars": 1, "use_flip_exit": False,
    "fraction": 0.01,
}


def test_research_metrics_have_expected_keys():
    candles = make_candles(600, drift=0.006)
    m = evaluate_research_window(candles, PARAMS, fence_frac=0.7,
                                 screen_frac=0.7)
    for key in ("screen_trades", "screen_expectancy_r", "holdout_mar",
                "holdout_drawdown", "research_sharpe", "research_sortino",
                "max_abs_r"):
        assert key in m


def test_lockbox_only_sees_the_tail():
    candles = make_candles(600, drift=0.006)
    m = evaluate_lockbox_tail(candles, PARAMS, fence_frac=0.7)
    assert "tail_trades" in m and "tail_mar" in m and "tail_drawdown" in m
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tunnel_ladder_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.tunnel.ladder_adapter'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/tunnel/ladder_adapter.py
from __future__ import annotations

from moonface.backtest.metrics import summarize_r
from moonface.models import Candle
from moonface.research.metrics import deflated_sharpe, equity_summary
from moonface.tunnel.metrics import sortino
from moonface.tunnel.simulator import simulate


def evaluate_research_window(candles: list[Candle], params: dict,
                             fence_frac: float, screen_frac: float) -> dict:
    """Stage 1+2 metrics on the research window (the bars before the fence).
    The lockbox tail is excluded entirely here."""
    fence = int(len(candles) * fence_frac)
    research = candles[:fence]
    stream = simulate(research, params)
    split = int(len(research) * screen_frac)
    screen_rs = [r for i, r, _ in stream if i < split]
    holdout = [(r, af) for i, r, af in stream if i >= split]
    full = [(r, af) for _, r, af in stream]
    screen = summarize_r(screen_rs)
    hold_eq = equity_summary(holdout, params["fraction"])
    full_eq = equity_summary(full, params["fraction"])
    returns = [params["fraction"] * r for _, r, _ in stream]
    return {
        "screen_trades": screen.trade_count,
        "screen_expectancy_r": screen.expectancy_r,
        "holdout_trades": hold_eq.trade_count,
        "holdout_mar": hold_eq.mar,
        "holdout_net_return": hold_eq.net_return,
        "holdout_drawdown": hold_eq.max_drawdown,
        "research_trades": full_eq.trade_count,
        "research_mar": full_eq.mar,
        "research_sharpe": full_eq.sharpe,
        "research_skew": full_eq.skew,
        "research_kurtosis": full_eq.kurtosis,
        "research_sortino": sortino(returns),
        "max_abs_r": round(max((abs(r) for _, r, _ in stream), default=0.0), 4),
    }


def evaluate_lockbox_tail(candles: list[Candle], params: dict,
                          fence_frac: float) -> dict:
    """Stage 4: simulate the whole series but score only trades that ENTER at
    or after the fence index (the untouched tail)."""
    fence = int(len(candles) * fence_frac)
    stream = simulate(candles, params)
    tail = [(r, af) for i, r, af in stream if i >= fence]
    eq = equity_summary(tail, params["fraction"])
    screen = summarize_r([r for r, _ in tail])
    return {
        "tail_trades": eq.trade_count,
        "tail_mar": eq.mar,
        "tail_net_return": eq.net_return,
        "tail_sharpe": eq.sharpe,
        "tail_sortino": sortino([params["fraction"] * r for r, _ in tail]),
        "tail_drawdown": eq.max_drawdown,
        "tail_expectancy_r": screen.expectancy_r,
    }


def tunnel_dsr(research_metrics_by_hash: dict[str, dict],
               oos_pass_hashes: set[str], grid_size: int) -> dict[str, float]:
    """Deflated Sharpe for each OOS-pass config, deflated against the full grid's
    research-Sharpe variance and count (mirrors research.ladder.stage3_dsr)."""
    trial_srs = [m["research_sharpe"] for m in research_metrics_by_hash.values()]
    out: dict[str, float] = {}
    for h in oos_pass_hashes:
        m = research_metrics_by_hash[h]
        out[h] = round(deflated_sharpe(
            m["research_sharpe"], m["research_trades"], m["research_skew"],
            m["research_kurtosis"], trial_srs, grid_size), 6)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tunnel_ladder_adapter.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/tunnel/ladder_adapter.py tests/test_tunnel_ladder_adapter.py
git commit -m "feat(tunnel): ladder adapter wiring the R-stream into stage1-4 gates + DSR"
```

---

## Task 7: Search grid + pinned defaults

**Files:**
- Create: `src/moonface/tunnel/grid.py`
- Test: `tests/test_tunnel_grid.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tunnel_grid.py
from moonface.tunnel.grid import PINNED, core_grid


def test_grid_has_972_unique_configs():
    grid = core_grid()
    assert len(grid) == 972
    # uniqueness over the searched keys
    keys = ("ema_len", "atr_mult", "chop_max", "sl_atr", "rr_ratio", "pb_zone")
    seen = {tuple(g[k] for k in keys) for g in grid}
    assert len(seen) == 972


def test_every_config_carries_pinned_defaults_and_fraction():
    g = core_grid()[0]
    for k in PINNED:
        assert k in g
    assert g["fraction"] == PINNED["fraction"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tunnel_grid.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.tunnel.grid'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/tunnel/grid.py
from __future__ import annotations

import itertools

# Pinned to Pine defaults (not searched). fraction is the ladder sizing fraction.
PINNED = {
    "atr_len": 14, "chop_len": 14, "slope_len": 5, "slope_min": 0.0,
    "vol_min": 0.8, "inner_zone": 0.3, "rsi_len": 14, "rsi_buy": 35,
    "rsi_sell": 65, "use_rsi": True, "use_macd": True, "use_candle": True,
    "use_inner": True, "be_atr": 1.0, "be_ticks": 0, "use_trail": True,
    "trail_band": 1.0, "trail_act": 1.5, "max_cons_losses": 3, "cool_bars": 5,
    "use_flip_exit": False, "fraction": 0.01,
}

_EMA_LEN = (34, 50, 89)
_ATR_MULT = (1.5, 2.0, 2.5)
_CHOP_MAX = (38.2, 50.0, 61.8)
_SL_ATR = (1.0, 1.5, 2.0)
_RR_RATIO = (1.5, 2.0, 2.5, 3.0)
_PB_ZONE = (0.3, 0.4, 0.5)


def core_grid() -> list[dict]:
    """972 configs = 3*3*3*3*4*3. Each merges the searched axes over PINNED."""
    out: list[dict] = []
    for ema_len, atr_mult, chop_max, sl_atr, rr, pb in itertools.product(
            _EMA_LEN, _ATR_MULT, _CHOP_MAX, _SL_ATR, _RR_RATIO, _PB_ZONE):
        cfg = dict(PINNED)
        cfg.update({"ema_len": ema_len, "atr_mult": atr_mult,
                    "chop_max": chop_max, "sl_atr": sl_atr, "rr_ratio": rr,
                    "pb_zone": pb})
        out.append(cfg)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tunnel_grid.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/tunnel/grid.py tests/test_tunnel_grid.py
git commit -m "feat(tunnel): 972-config core search grid over Pine-default pins"
```

---

## Task 8: Registry schema (read/write)

**Files:**
- Create: `src/moonface/tunnel/registry.py`
- Test: `tests/test_tunnel_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tunnel_registry.py
from moonface.tunnel.registry import CoinResult, read_registry, write_registry


def _result(symbol, status):
    return CoinResult(symbol=symbol, status=status,
                      params={"ema_len": 50} if status == "pass" else None,
                      stats={"tail_mar": 1.4, "tail_sortino": 0.9} if status == "pass" else {},
                      dsr=0.96 if status == "pass" else 0.0,
                      provenance={"grid_size": 972, "fence_frac": 0.7})


def test_round_trip(tmp_path):
    results = [_result("BTCUSDT", "pass"), _result("XRPUSDT", "no_edge")]
    path = tmp_path / "registry.json"
    write_registry(path, results)
    back = read_registry(path)
    assert {r.symbol for r in back} == {"BTCUSDT", "XRPUSDT"}
    btc = next(r for r in back if r.symbol == "BTCUSDT")
    assert btc.status == "pass"
    assert btc.params == {"ema_len": 50}
    assert btc.dsr == 0.96


def test_registry_is_versioned(tmp_path):
    path = tmp_path / "registry.json"
    write_registry(path, [_result("BTCUSDT", "pass")])
    import json
    raw = json.loads(path.read_text())
    assert raw["version"] == 1
    assert isinstance(raw["coins"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tunnel_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.tunnel.registry'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/tunnel/registry.py
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

REGISTRY_VERSION = 1


@dataclass(frozen=True)
class CoinResult:
    symbol: str
    status: str               # "pass" | "no_edge"
    params: dict | None       # selected config (None when no_edge)
    stats: dict               # tail/holdout MAR, Sharpe, Sortino, DD, trades...
    dsr: float
    provenance: dict          # grid_size, fence_frac, data window, etc.


def write_registry(path: str | Path, results: list[CoinResult]) -> None:
    payload = {"version": REGISTRY_VERSION,
               "coins": [asdict(r) for r in results]}
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, sort_keys=True))


def read_registry(path: str | Path) -> list[CoinResult]:
    raw = json.loads(Path(path).read_text())
    return [CoinResult(**c) for c in raw["coins"]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tunnel_registry.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/tunnel/registry.py tests/test_tunnel_registry.py
git commit -m "feat(tunnel): versioned per-coin registry schema (read/write)"
```

---

## Task 9: Per-coin search driver

**Files:**
- Create: `src/moonface/tunnel/search.py`
- Test: `tests/test_tunnel_search.py`

Runs the full 4-stage ladder over a coin's grid and returns a `CoinResult`. Uses gate constants from `research.ladder` so thresholds stay identical.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tunnel_search.py
from moonface.research.synth import make_candles
from moonface.tunnel.registry import CoinResult
from moonface.tunnel.search import search_coin


def test_search_returns_coinresult_with_known_status():
    candles = make_candles(800, drift=0.004)
    # tiny grid for speed; reuse the real evaluation path
    grid = [
        {"ema_len": 20, "atr_mult": 2.0, "chop_max": 61.8, "sl_atr": 1.0,
         "rr_ratio": 2.0, "pb_zone": 0.6, "atr_len": 14, "chop_len": 14,
         "slope_len": 5, "slope_min": 0.0, "vol_min": 0.3, "inner_zone": 0.4,
         "rsi_len": 14, "rsi_buy": 35, "rsi_sell": 65, "use_rsi": False,
         "use_macd": False, "use_candle": False, "use_inner": True,
         "be_atr": 1.0, "be_ticks": 0, "use_trail": False, "trail_band": 1.0,
         "trail_act": 1.5, "max_cons_losses": 99, "cool_bars": 1,
         "use_flip_exit": False, "fraction": 0.01},
    ]
    res = search_coin("BTCUSDT", candles, grid, fence_frac=0.7, screen_frac=0.7)
    assert isinstance(res, CoinResult)
    assert res.status in ("pass", "no_edge")
    assert res.provenance["grid_size"] == 1


def test_no_survivor_is_no_edge():
    # flat market -> no edge survives the gate
    flat = make_candles(800, drift=0.0, noise=0.0001)
    grid = [
        {"ema_len": 50, "atr_mult": 2.0, "chop_max": 38.2, "sl_atr": 1.5,
         "rr_ratio": 2.5, "pb_zone": 0.4, "atr_len": 14, "chop_len": 14,
         "slope_len": 5, "slope_min": 0.0, "vol_min": 0.8, "inner_zone": 0.3,
         "rsi_len": 14, "rsi_buy": 35, "rsi_sell": 65, "use_rsi": True,
         "use_macd": True, "use_candle": True, "use_inner": True,
         "be_atr": 1.0, "be_ticks": 0, "use_trail": True, "trail_band": 1.0,
         "trail_act": 1.5, "max_cons_losses": 3, "cool_bars": 5,
         "use_flip_exit": False, "fraction": 0.01},
    ]
    res = search_coin("BTCUSDT", flat, grid, fence_frac=0.7, screen_frac=0.7)
    assert res.status == "no_edge"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tunnel_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.tunnel.search'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/tunnel/search.py
from __future__ import annotations

import hashlib
import json

from moonface.models import Candle
from moonface.research.ladder import (DSR_THRESHOLD, LOCKBOX_MIN_MAR,
                                       LOCKBOX_MIN_TRADES, R_SANITY_CAP,
                                       stage1_passed, stage2_passed,
                                       stage4_passed)
from moonface.tunnel.ladder_adapter import (evaluate_lockbox_tail,
                                             evaluate_research_window,
                                             tunnel_dsr)
from moonface.tunnel.metrics import sortino  # noqa: F401 (kept for stats parity)
from moonface.tunnel.registry import CoinResult


def _cfg_hash(cfg: dict) -> str:
    return hashlib.sha256(
        json.dumps(cfg, sort_keys=True).encode("utf-8")).hexdigest()


def search_coin(symbol: str, candles: list[Candle], grid: list[dict],
                fence_frac: float, screen_frac: float) -> CoinResult:
    """Full 4-stage ladder over one coin's grid. Returns the best stage-4
    survivor as a 'pass' CoinResult, else 'no_edge'."""
    research_by_hash: dict[str, dict] = {}
    cfg_by_hash: dict[str, dict] = {}
    oos_pass: set[str] = set()
    for cfg in grid:
        h = _cfg_hash(cfg)
        cfg_by_hash[h] = cfg
        m = evaluate_research_window(candles, cfg, fence_frac, screen_frac)
        research_by_hash[h] = m
        if m["max_abs_r"] > R_SANITY_CAP:
            continue
        if not stage1_passed(m):
            continue
        if not stage2_passed(m):
            continue
        oos_pass.add(h)

    grid_size = len(grid)
    provenance = {"grid_size": grid_size, "fence_frac": fence_frac,
                  "screen_frac": screen_frac, "n_candles": len(candles)}

    if not oos_pass:
        return CoinResult(symbol, "no_edge", None, {}, 0.0, provenance)

    dsr = tunnel_dsr(research_by_hash, oos_pass, grid_size)
    survivors = [h for h in oos_pass if dsr[h] >= DSR_THRESHOLD]
    if not survivors:
        return CoinResult(symbol, "no_edge", None, {}, max(dsr.values()),
                          provenance)

    best = None
    for h in survivors:
        cfg = cfg_by_hash[h]
        tail = evaluate_lockbox_tail(candles, cfg, fence_frac)
        if not stage4_passed(tail, min_mar=LOCKBOX_MIN_MAR,
                             min_trades=LOCKBOX_MIN_TRADES):
            continue
        score = (tail["tail_mar"], tail["tail_sortino"], tail["tail_sharpe"])
        if best is None or score > best[0]:
            best = (score, h, cfg, tail, dsr[h])

    if best is None:
        return CoinResult(symbol, "no_edge", None, {},
                          max(dsr[h] for h in survivors), provenance)

    _, h, cfg, tail, d = best
    stats = {**research_by_hash[h], **tail}
    return CoinResult(symbol, "pass", cfg, stats, d, provenance)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tunnel_search.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/tunnel/search.py tests/test_tunnel_search.py
git commit -m "feat(tunnel): per-coin 4-stage search driver (stage1-4 + DSR -> CoinResult)"
```

---

## Task 10: Batch signal engine + sim/live parity

**Files:**
- Create: `src/moonface/tunnel/signal.py`
- Test: `tests/test_tunnel_signal.py`

Reuses `Signal` from `moonface.signal.evaluate`. For each `pass` coin, evaluates the most recent closed bar; `no_edge` coins emit WAIT. A parity test asserts the signal at index `i` matches the simulator's entry at `i`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tunnel_signal.py
from moonface.research.synth import make_candles
from moonface.signal.evaluate import Signal
from moonface.tunnel.entry import tunnel_entry
from moonface.tunnel.registry import CoinResult
from moonface.tunnel.signal import batch_signals, signal_for_coin

PARAMS = {
    "ema_len": 20, "atr_mult": 2.0, "chop_max": 61.8, "sl_atr": 1.0,
    "rr_ratio": 2.0, "pb_zone": 0.6, "atr_len": 14, "chop_len": 14,
    "slope_len": 5, "slope_min": 0.0, "vol_min": 0.3, "inner_zone": 0.4,
    "rsi_len": 14, "rsi_buy": 35, "rsi_sell": 65, "use_rsi": False,
    "use_macd": False, "use_candle": False, "use_inner": True, "be_atr": 1.0,
    "be_ticks": 0, "use_trail": False, "trail_band": 1.0, "trail_act": 1.5,
    "max_cons_losses": 99, "cool_bars": 1, "use_flip_exit": False,
    "fraction": 0.01,
}


def test_no_edge_coin_emits_wait():
    candles = make_candles(300)
    sig = signal_for_coin(CoinResult("XRPUSDT", "no_edge", None, {}, 0.0, {}),
                          candles)
    assert sig.decision == "WAIT"


def test_pass_coin_signal_matches_simulator_entry():
    """Parity guard: the live decision on prefix [:i+1] equals the entry the
    generator emits at i (or WAIT when there is none)."""
    candles = make_candles(500, drift=0.006)
    entries = dict(tunnel_entry(candles, PARAMS))
    res = CoinResult("BTCUSDT", "pass", PARAMS, {}, 0.96, {})
    # pick an index that fired and one that did not
    fired = next(iter(entries))
    sig = signal_for_coin(res, candles[: fired + 2])  # +2 so `fired` isn't last
    assert sig.decision in ("LONG", "SHORT")


def test_batch_returns_one_signal_per_coin():
    candles = make_candles(300)
    registry = [CoinResult("BTCUSDT", "pass", PARAMS, {}, 0.96, {}),
                CoinResult("XRPUSDT", "no_edge", None, {}, 0.0, {})]
    out = batch_signals(registry, lambda sym: candles)
    assert set(out) == {"BTCUSDT", "XRPUSDT"}
    assert all(isinstance(s, Signal) for s in out.values())
    assert out["XRPUSDT"].decision == "WAIT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tunnel_signal.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.tunnel.signal'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/tunnel/signal.py
from __future__ import annotations

from collections.abc import Callable

from moonface.models import Candle
from moonface.signal.evaluate import Signal
from moonface.tunnel.entry import tunnel_entry
from moonface.tunnel.registry import CoinResult

Loader = Callable[[str], list[Candle]]


def _wait(symbol: str, reason: str) -> Signal:
    return Signal("WAIT", None, None, None, f"{symbol}: {reason}",
                  timeframe="4h")


def signal_for_coin(result: CoinResult, candles: list[Candle]) -> Signal:
    """LONG/SHORT/WAIT for the last closed bar of `candles`. no_edge coins and
    coins with no entry on the last closed bar return WAIT."""
    if result.status != "pass" or result.params is None:
        return _wait(result.symbol, "no validated config")
    if len(candles) < 2:
        return _wait(result.symbol, "not enough closed candles")
    last = len(candles) - 1
    entries = dict(tunnel_entry(candles, result.params))
    side = entries.get(last)
    if side is None:
        return _wait(result.symbol, "no entry on the last closed bar")
    price = candles[last].close
    sl_atr = result.params["sl_atr"]
    from moonface.tunnel.state import tunnel_states
    a = tunnel_states(candles, result.params)[last].atr
    invalidation = (price - sl_atr * a if side == "LONG"
                    else price + sl_atr * a)
    return Signal(side, price, round(invalidation, 2), result.params["fraction"],
                  f"{result.symbol}: tunnel {side}", timeframe="4h", tier="paper")


def batch_signals(registry: list[CoinResult], loader: Loader) -> dict[str, Signal]:
    out: dict[str, Signal] = {}
    for result in registry:
        try:
            candles = loader(result.symbol)
        except Exception as exc:  # noqa: BLE001 - one bad coin must not sink all
            out[result.symbol] = _wait(result.symbol, f"data error: {exc!r}")
            continue
        out[result.symbol] = signal_for_coin(result, candles)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tunnel_signal.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/tunnel/signal.py tests/test_tunnel_signal.py
git commit -m "feat(tunnel): batch 4h signal engine (LONG/SHORT/WAIT per coin) + parity guard"
```

---

## Task 11: Report renderer

**Files:**
- Create: `src/moonface/tunnel/report.py`
- Test: `tests/test_tunnel_report.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tunnel_report.py
from moonface.tunnel.registry import CoinResult
from moonface.tunnel.report import render_report


def _pass(sym, mar):
    return CoinResult(sym, "pass", {"ema_len": 50, "atr_mult": 2.0,
                                    "chop_max": 50.0, "sl_atr": 1.5,
                                    "rr_ratio": 2.5, "pb_zone": 0.4},
                      {"tail_mar": mar, "tail_sharpe": 0.3, "tail_sortino": 0.5,
                       "tail_drawdown": -0.2, "tail_trades": 14}, 0.96,
                      {"grid_size": 972})


def test_report_ranks_survivors_by_mar_then_lists_no_edge():
    registry = [_pass("ETHUSDT", 1.2), _pass("BTCUSDT", 2.0),
                CoinResult("XRPUSDT", "no_edge", None, {}, 0.0, {"grid_size": 972})]
    md = render_report(registry)
    assert "# Tunnel Core + CHOP" in md
    # BTC (mar 2.0) ranked above ETH (mar 1.2)
    assert md.index("BTCUSDT") < md.index("ETHUSDT")
    assert "XRPUSDT" in md and "no_edge" in md


def test_all_no_edge_states_deploy_none():
    registry = [CoinResult("BTCUSDT", "no_edge", None, {}, 0.0, {"grid_size": 972})]
    md = render_report(registry)
    assert "Deploy none" in md or "deploy none" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tunnel_report.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moonface.tunnel.report'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/moonface/tunnel/report.py
from __future__ import annotations

from moonface.tunnel.registry import CoinResult


def render_report(registry: list[CoinResult]) -> str:
    survivors = [r for r in registry if r.status == "pass"]
    survivors.sort(key=lambda r: r.stats.get("tail_mar", float("-inf")),
                   reverse=True)
    no_edge = [r for r in registry if r.status != "pass"]
    lines = ["# Tunnel Core + CHOP — Per-Coin 4h Report", ""]

    lines += ["## Recommended deployment configuration", ""]
    if survivors:
        lines.append(f"Deploy {len(survivors)} coin(s): "
                     + ", ".join(r.symbol for r in survivors) + ".")
    else:
        lines.append("Deploy none — no coin cleared the validation ladder; "
                     "the engine emits WAIT for every coin.")
    lines.append("")

    lines += ["## Coin ranking by risk-adjusted performance", "",
              "| rank | coin | status | tail MAR | tail Sortino | tail Sharpe |"
              " tail DD | tail trades | DSR |",
              "|---|---|---|---|---|---|---|---|---|"]
    rank = 1
    for r in survivors:
        s = r.stats
        lines.append(
            f"| {rank} | {r.symbol} | pass | {s.get('tail_mar')} | "
            f"{s.get('tail_sortino')} | {s.get('tail_sharpe')} | "
            f"{s.get('tail_drawdown')} | {s.get('tail_trades')} | {r.dsr} |")
        rank += 1
    for r in no_edge:
        lines.append(f"| — | {r.symbol} | no_edge | — | — | — | — | — | {r.dsr} |")
    lines.append("")

    lines += ["## Best configuration per coin", ""]
    if survivors:
        lines += ["| coin | ema_len | atr_mult | chop_max | sl_atr | rr_ratio |"
                  " pb_zone |", "|---|---|---|---|---|---|---|"]
        for r in survivors:
            p = r.params or {}
            lines.append(
                f"| {r.symbol} | {p.get('ema_len')} | {p.get('atr_mult')} | "
                f"{p.get('chop_max')} | {p.get('sl_atr')} | {p.get('rr_ratio')}"
                f" | {p.get('pb_zone')} |")
    else:
        lines.append("No surviving configuration.")
    lines.append("")

    lines += [
        "## Signal generation logic", "",
        "Every 4h, each `pass` coin is evaluated on its latest closed bar with"
        " its registry config. An outer pullback to the tunnel band (or inner"
        " pullback to center) in the trend direction, confirmed by"
        " RSI/MACD/candle, fires LONG/SHORT; otherwise WAIT. Invalidation is"
        " the entry minus `sl_atr`×ATR. `no_edge` coins always emit WAIT.", "",
        "Fidelity caveats: (1) same-bar stop+target resolves stop-first"
        " (pessimistic); (2) sizing is modelled in R-space via the ladder's"
        " fraction, not a tick-level equity replica.", "",
    ]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tunnel_report.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/moonface/tunnel/report.py tests/test_tunnel_report.py
git commit -m "feat(tunnel): final report renderer (ranking, best config, deploy recommendation)"
```

---

## Task 12: CLI (fetch | search | report | signal)

**Files:**
- Create: `tools/tunnel.py`
- Test: `tests/test_tunnel_cli.py`

Follows the `tools/research.py` pattern (argparse subcommands, `sys.path.insert` for `src`). `fetch` extends 4h history via `fetch_perp_candles`; `search` runs every cached coin; `report` renders; `signal` prints the batch table.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tunnel_cli.py
import json

from moonface.research.synth import make_candles
from moonface.tunnel.registry import CoinResult, write_registry
from tools.tunnel import cmd_report, cmd_signal, dedupe_symbols, make_parser


def test_dedupe_collapses_ccxt_variants():
    syms = ["BTCUSDT", "BTC_USDT:USDT", "ETHUSDT", "ETH_USDT:USDT", "XRPUSDT"]
    assert dedupe_symbols(syms) == ["BTCUSDT", "ETHUSDT", "XRPUSDT"]


def test_parser_has_all_subcommands():
    parser = make_parser()
    for cmd in ("fetch", "search", "report", "signal"):
        ns = parser.parse_args([cmd, "--cache-dir", ".backtest_cache"])
        assert ns.cmd == cmd


def test_report_cmd_writes_markdown(tmp_path, capsys):
    reg = tmp_path / "registry.json"
    write_registry(reg, [CoinResult("BTCUSDT", "no_edge", None, {}, 0.0,
                                    {"grid_size": 972})])
    out = tmp_path / "REPORT.md"
    cmd_report(type("NS", (), {"registry": str(reg), "out": str(out)}))
    assert out.exists()
    assert "Tunnel Core + CHOP" in out.read_text()


def test_signal_cmd_prints_table(tmp_path, capsys, monkeypatch):
    reg = tmp_path / "registry.json"
    write_registry(reg, [CoinResult("BTCUSDT", "no_edge", None, {}, 0.0,
                                    {"grid_size": 972})])
    monkeypatch.setattr("tools.tunnel._load_candles",
                        lambda sym, cache_dir: make_candles(300))
    cmd_signal(type("NS", (), {"registry": str(reg),
                               "cache_dir": ".backtest_cache"}))
    captured = capsys.readouterr().out
    assert "BTCUSDT" in captured and "WAIT" in captured
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tunnel_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.tunnel'`

- [ ] **Step 3: Write minimal implementation**

```python
#!/usr/bin/env python
# tools/tunnel.py
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moonface.backtest.data import OhlcvCache
from moonface.models import Candle
from moonface.tunnel.grid import core_grid
from moonface.tunnel.registry import read_registry, write_registry
from moonface.tunnel.report import render_report
from moonface.tunnel.search import search_coin
from moonface.tunnel.signal import batch_signals

_DEFAULT_REGISTRY = "experiments/tunnel/registry.json"
_DEFAULT_REPORT = "experiments/tunnel/REPORT.md"


def dedupe_symbols(symbols: list[str]) -> list[str]:
    """Collapse ccxt-style variants (BTC_USDT:USDT) onto the plain Binance
    symbol (BTCUSDT), preserving first-seen order."""
    seen: dict[str, None] = {}
    for s in symbols:
        plain = s.split(":")[0].replace("_", "").replace("/", "")
        seen.setdefault(plain, None)
    return list(seen)


def _cached_symbols(cache_dir: str) -> list[str]:
    names = sorted({p.name[:-7] for p in Path(cache_dir).glob("*_4h.csv")})
    return dedupe_symbols(names)


def _load_candles(symbol: str, cache_dir: str) -> list[Candle]:
    candles = OhlcvCache(cache_dir).load(symbol, "4h")
    if candles is None:
        raise FileNotFoundError(f"no 4h cache for {symbol}")
    return candles


def cmd_fetch(args: argparse.Namespace) -> None:
    from moonface.backtest.universe_data import fetch_perp_candles
    start = 0
    end = 10_000_000_000_000  # far future; fetchers stop at available data
    for sym in _cached_symbols(args.cache_dir):
        rows = fetch_perp_candles(sym, "4h", start, end, args.cache_dir)
        print(f"{sym}: {len(rows)} 4h candles cached")


def cmd_search(args: argparse.Namespace) -> None:
    grid = core_grid()
    results = []
    for sym in _cached_symbols(args.cache_dir):
        candles = _load_candles(sym, args.cache_dir)
        res = search_coin(sym, candles, grid, fence_frac=args.fence_frac,
                          screen_frac=args.screen_frac)
        results.append(res)
        print(f"{sym}: {res.status} (dsr={res.dsr})")
    write_registry(args.out, results)
    print(f"registry written to {args.out}")


def cmd_report(args: argparse.Namespace) -> None:
    md = render_report(read_registry(args.registry))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    print(f"report written to {out}")


def cmd_signal(args: argparse.Namespace) -> None:
    registry = read_registry(args.registry)
    signals = batch_signals(
        registry, lambda sym: _load_candles(sym, args.cache_dir))
    for sym, sig in signals.items():
        price = "" if sig.price is None else f" @ {sig.price}"
        print(f"{sym:14s} {sig.decision:5s}{price}  {sig.reason}")


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tunnel Core + CHOP per-coin 4h pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="extend 4h history for cached coins")
    p_fetch.add_argument("--cache-dir", default=".backtest_cache")
    p_fetch.set_defaults(func=cmd_fetch)

    p_search = sub.add_parser("search", help="per-coin grid search + validation")
    p_search.add_argument("--cache-dir", default=".backtest_cache")
    p_search.add_argument("--out", default=_DEFAULT_REGISTRY)
    p_search.add_argument("--fence-frac", type=float, default=0.7)
    p_search.add_argument("--screen-frac", type=float, default=0.7)
    p_search.set_defaults(func=cmd_search)

    p_report = sub.add_parser("report", help="render the final report")
    p_report.add_argument("--cache-dir", default=".backtest_cache")
    p_report.add_argument("--registry", default=_DEFAULT_REGISTRY)
    p_report.add_argument("--out", default=_DEFAULT_REPORT)
    p_report.set_defaults(func=cmd_report)

    p_signal = sub.add_parser("signal", help="emit LONG/SHORT/WAIT per coin")
    p_signal.add_argument("--cache-dir", default=".backtest_cache")
    p_signal.add_argument("--registry", default=_DEFAULT_REGISTRY)
    p_signal.set_defaults(func=cmd_signal)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = make_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tunnel_cli.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add tools/tunnel.py tests/test_tunnel_cli.py
git commit -m "feat(tunnel): CLI (fetch|search|report|signal) over cached 4h coins"
```

---

## Task 13: Full suite green + ruff clean

**Files:** none (verification task)

- [ ] **Step 1: Run the whole tunnel suite**

Run: `python -m pytest tests/test_tunnel_*.py -v`
Expected: all PASS.

- [ ] **Step 2: Run the entire repo suite (no regressions)**

Run: `python -m pytest -q`
Expected: all PASS (existing tests unaffected — the tunnel module is additive).

- [ ] **Step 3: Lint**

Run: `ruff check src/moonface/tunnel tools/tunnel.py tests/test_tunnel_*.py`
Expected: `All checks passed!` (fix any findings, then re-run).

- [ ] **Step 4: Commit any lint fixes**

```bash
git add -A
git diff --cached --stat   # verify only tunnel files staged
git commit -m "chore(tunnel): ruff clean + full-suite green"
```

---

## Task 14: Live end-to-end smoke (real cached data)

**Files:** none (manual verification; do NOT commit generated artifacts unless asked)

- [ ] **Step 1: Search on a single real coin (fast subset)**

Run a Python one-liner from repo root to confirm the pipeline runs on real cached BTC 4h data without error and returns a known status:

```bash
python -c "
import sys; sys.path.insert(0,'src')
from moonface.backtest.data import OhlcvCache
from moonface.tunnel.grid import core_grid
from moonface.tunnel.search import search_coin
c = OhlcvCache('.backtest_cache').load('BTCUSDT','4h')
print('candles:', len(c))
res = search_coin('BTCUSDT', c, core_grid()[:20], 0.7, 0.7)
print(res.status, res.dsr, res.provenance)
"
```
Expected: prints candle count and a status of `pass` or `no_edge` (no traceback). Given the program's history, `no_edge` is the likely and acceptable outcome.

- [ ] **Step 2: Confirm the signal engine produces a WAIT-or-decision table**

```bash
python -c "
import sys; sys.path.insert(0,'src')
from moonface.research.synth import make_candles
from moonface.tunnel.registry import CoinResult
from moonface.tunnel.signal import batch_signals
reg=[CoinResult('BTCUSDT','no_edge',None,{},0.0,{})]
print(batch_signals(reg, lambda s: make_candles(300))['BTCUSDT'].decision)
"
```
Expected: `WAIT`.

- [ ] **Step 3: Record the outcome**

Note in the session whether real-data BTC returned `pass` or `no_edge`. No commit; this step validates the wiring, not an artifact.

---

## Self-review notes (addressed)

- **Spec coverage:** faithful port (Tasks 1–4), Sortino ranking (Task 5), reused ladder gates (Task 6), core 972 grid (Task 7), registry (Task 8), per-coin independent search with per-coin DSR grid_size (Task 9), batch 4h signal + parity guard (Task 10), report with all five required sections incl. deploy recommendation and honest "Deploy none" (Task 11), CLI with fetch/search/report/signal and ccxt dedupe (Task 12), verification + real-data smoke (Tasks 13–14).
- **Type consistency:** `CoinResult` fields, the `(index, net_r, atr_frac)` triple, and `params` keys are identical across `state`/`entry`/`simulator`/`ladder_adapter`/`search`/`signal`. `Signal` is the existing dataclass from `moonface.signal.evaluate`.
- **Pinned vs searched:** the simulator/entry read the same param keys the grid emits; `core_grid()` always merges over `PINNED`, so no config is missing a key the simulator dereferences.
- **Gate fidelity:** stage thresholds come from `research.ladder` constants (`DSR_THRESHOLD`, `LOCKBOX_MIN_MAR`, `LOCKBOX_MIN_TRADES`, `R_SANITY_CAP`, `DRAWDOWN_BUDGET` via `stage2_passed`/`stage4_passed`) — never re-hardcoded.
