# tests/test_engine_backtest_cli.py
import tools.engine.engine_backtest as eb
from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig
from tools.engine.engine_backtest import replay

H = 3_600_000

# v2 needs real multi-timeframe history: a confirmed 1W macro bias (>=~32 weeks
# = ~5500 1h bars), a 4h Donchian/MA window (DONCHIAN_N=40, TREND_MA=50), and a
# non-vanishing 4h ROC. A GEOMETRIC uptrend keeps ROC strong at high prices
# (a linear ramp's fractional ROC decays to ~0), and confirmed BULL macro lets
# the trend book clear the 60-pt gate (macro 20 + breakout 20 + ma_align 10 +
# roc 20 = 70, tier B). The tail crash trails the WT stop out -> EXIT.
UPTREND_N = 5500          # multiple of 4 so the last 4h bar is complete
CRASH_N = 12
_R = 1.002                # per-1h geometric step


def _cfg(**kw):
    base = dict(enabled=True, regime_ma_fast=10, regime_ma_slow=20,
                vol_window=8, atr_period=10)
    base.update(kw)
    return EngineConfig(**base)


def _uptrend_then_crash(up=UPTREND_N, down=CRASH_N):
    out, prev = [], 100.0
    for i in range(up):
        close = 100.0 * (_R ** i)
        open_ = prev
        out.append(Candle(i * H, open_, max(open_, close) * 1.0005,
                          min(open_, close) * 0.9995, close, 1.0))
        prev = close
    for j in range(down):
        close = prev * 0.97
        out.append(Candle((up + j) * H, prev, prev * 1.0005, close * 0.9995,
                          close, 1.0))
        prev = close
    return out


def test_replay_produces_trade_lifecycle():
    cfg = _cfg()
    # start the replay at the breakout top so it OPENs, then the crash EXITs;
    # a small window keeps the resample cost bounded.
    entries = replay(cfg, _uptrend_then_crash(), warmup=UPTREND_N - 1)
    actions = [e["action"] for e in entries]
    assert "OPEN" in actions
    assert "EXIT" in actions          # the crash trails out the long
    # every entry is a well-formed engine journal record
    assert all(e["status"] == "engine" for e in entries)


def test_replay_is_deterministic():
    cfg = _cfg()
    candles = _uptrend_then_crash()
    a = replay(cfg, candles, warmup=UPTREND_N - 1)
    b = replay(cfg, candles, warmup=UPTREND_N - 1)
    assert [e["action"] for e in a] == [e["action"] for e in b]


def test_replay_feeds_at_most_lookback_bars(monkeypatch):
    """Live feeds evaluate_engine exactly lookback_bars candles (cli.py:86,
    start_ms = end_ms - lookback*tf_ms). The backtest replay must match: it must
    NEVER feed a window longer than lookback_bars, or it overstates (the
    expanding vol_ratio baseline live never has). Regression for the full-slice
    bug recorded in experiments/engine/FORWARD_FAITHFUL_BACKTEST_2026-06-24.md."""
    cfg = _cfg(lookback_bars=50)
    candles = _uptrend_then_crash()       # thousands of candles >> lookback_bars
    seen = []
    real = eb.evaluate_engine

    def spy(cfg_, bundle, entries, now_ms, deriv=None):
        seen.append(len(bundle.candles))
        return real(cfg_, bundle, entries, now_ms=now_ms, deriv=deriv)

    monkeypatch.setattr(eb, "evaluate_engine", spy)
    replay(cfg, candles, warmup=len(candles) - 20)
    assert seen, "replay never evaluated the engine"
    assert max(seen) <= cfg.lookback_bars, (
        f"replay fed {max(seen)} candles, exceeds lookback_bars="
        f"{cfg.lookback_bars}; not live-faithful (full-slice overstatement)")
