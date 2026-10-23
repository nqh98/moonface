# tests/test_engine_discipline.py
from moonface.models.engine.config import EngineConfig
from moonface.models.engine.discipline import (bars_since_last_exit,
                                               closed_trades, hard_breaker_tripped,
                                               in_cooldown, is_paused,
                                               last_trade_was_loss,
                                               realized_drawdown_r,
                                               tier_size_fraction,
                                               windowed_drawdown_r)

V = "v1"
DAY_MS = 86_400_000


def _entry(action, realized_r=None, atr_frac=0.01, fraction=0.005, version=V,
           ts_ms=0):
    return {"strategy_version": version, "status": "engine", "action": action,
            "realized_r": realized_r, "atr_frac": atr_frac, "fraction": fraction,
            "ts_ms": ts_ms}


def test_closed_trades_only_exits():
    entries = [_entry("OPEN"), _entry("HOLD"),
               _entry("EXIT", realized_r=1.5), _entry("WAIT")]
    ct = closed_trades(entries, V)
    assert ct == [(1.5, 0.01, 0.005)]


def test_realized_drawdown_and_pause():
    entries = [_entry("EXIT", realized_r=-10.0), _entry("EXIT", realized_r=-8.0)]
    assert realized_drawdown_r(entries, V) <= -18.0
    assert is_paused(entries, EngineConfig(drawdown_budget_r=15.0), V) is True
    assert is_paused(entries, EngineConfig(drawdown_budget_r=50.0), V) is False


def test_windowed_drawdown_only_counts_recent_trades():
    cfg = EngineConfig(drawdown_window_days=90.0)
    now = 1000 * DAY_MS
    entries = [_entry("EXIT", realized_r=-10.0, ts_ms=now - 200 * DAY_MS),
               _entry("EXIT", realized_r=-5.0, ts_ms=now - 10 * DAY_MS)]
    # only the -5 is inside the trailing 90-day window
    assert windowed_drawdown_r(entries, cfg, V, now) == -5.0


def test_trailing_window_pauses_recent_drawdown():
    cfg = EngineConfig(drawdown_budget_r=15.0, drawdown_window_days=90.0,
                       hard_drawdown_budget_r=30.0)
    now = 1000 * DAY_MS
    recent = now - 10 * DAY_MS
    entries = [_entry("EXIT", realized_r=-10.0, ts_ms=recent),
               _entry("EXIT", realized_r=-10.0, ts_ms=recent),
               _entry("WAIT", ts_ms=now)]
    assert is_paused(entries, cfg, V, now) is True


def test_trailing_window_auto_resumes_when_drawdown_ages_out():
    cfg = EngineConfig(drawdown_budget_r=15.0, drawdown_window_days=90.0,
                       hard_drawdown_budget_r=30.0)
    now = 1000 * DAY_MS
    old = now - 200 * DAY_MS                 # -20R cluster older than the window
    entries = [_entry("EXIT", realized_r=-10.0, ts_ms=old),
               _entry("EXIT", realized_r=-10.0, ts_ms=old),
               _entry("WAIT", ts_ms=now)]
    assert is_paused(entries, cfg, V, now) is False


def test_hard_breaker_latches_even_after_window_clears():
    cfg = EngineConfig(drawdown_budget_r=15.0, drawdown_window_days=90.0,
                       hard_drawdown_budget_r=30.0)
    now = 1000 * DAY_MS
    old = now - 200 * DAY_MS                 # -35R all-time, but window is clear
    entries = [_entry("EXIT", realized_r=-20.0, ts_ms=old),
               _entry("EXIT", realized_r=-15.0, ts_ms=old),
               _entry("WAIT", ts_ms=now)]
    assert hard_breaker_tripped(entries, cfg, V) is True
    assert is_paused(entries, cfg, V, now) is True   # latch overrides aging


def test_hard_breaker_not_tripped_below_budget():
    cfg = EngineConfig(hard_drawdown_budget_r=30.0)
    now = 1000 * DAY_MS
    entries = [_entry("EXIT", realized_r=-20.0, ts_ms=now)]
    assert hard_breaker_tripped(entries, cfg, V) is False


def test_window_disabled_falls_back_to_all_time_latch():
    cfg = EngineConfig(drawdown_budget_r=15.0, drawdown_window_days=0.0)
    now = 1000 * DAY_MS
    old = now - 999 * DAY_MS
    entries = [_entry("EXIT", realized_r=-10.0, ts_ms=old),
               _entry("EXIT", realized_r=-10.0, ts_ms=old),
               _entry("WAIT", ts_ms=now)]
    # window disabled -> legacy all-time latch -> still paused despite age
    assert is_paused(entries, cfg, V, now) is True


def test_is_paused_derives_now_from_entries_when_omitted():
    cfg = EngineConfig(drawdown_budget_r=15.0, drawdown_window_days=90.0)
    now = 1000 * DAY_MS
    entries = [_entry("EXIT", realized_r=-10.0, ts_ms=now - 200 * DAY_MS),
               _entry("EXIT", realized_r=-10.0, ts_ms=now - 200 * DAY_MS),
               _entry("WAIT", ts_ms=now)]
    # no now_ms passed -> uses latest entry ts -> old cluster aged out
    assert is_paused(entries, cfg, V) is False


def test_cooldown_after_loss():
    cfg = EngineConfig(cooldown_bars=3)
    entries = [_entry("EXIT", realized_r=-1.0), _entry("WAIT"), _entry("WAIT")]
    assert last_trade_was_loss(entries, V) is True
    assert bars_since_last_exit(entries, V) == 2
    assert in_cooldown(entries, cfg, V) is True
    entries += [_entry("WAIT")]  # now 3 bars since exit -> cooldown over
    assert in_cooldown(entries, cfg, V) is False


def test_no_cooldown_after_win():
    cfg = EngineConfig(cooldown_bars=3)
    entries = [_entry("EXIT", realized_r=2.0), _entry("WAIT")]
    assert in_cooldown(entries, cfg, V) is False


def test_version_isolation():
    entries = [_entry("EXIT", realized_r=-99.0, version="other")]
    assert closed_trades(entries, V) == []


def test_tier_size_fraction_flattened_to_one_cell():
    cfg = EngineConfig(max_fraction=0.02)
    assert tier_size_fraction("B", "WT", "normal", cfg) == 0.005
    assert tier_size_fraction("A", "WT", "normal", cfg) == 0.0
    assert tier_size_fraction("A", "CT", "normal", cfg) == 0.0
    assert tier_size_fraction("B", "CT", "normal", cfg) == 0.0


def test_tier_size_fraction_high_vol_halves_the_surviving_cell():
    cfg = EngineConfig(max_fraction=0.02)
    assert tier_size_fraction("B", "WT", "high", cfg) == 0.0025
    assert tier_size_fraction("A", "WT", "high", cfg) == 0.0
    assert tier_size_fraction("A", "CT", "high", cfg) == 0.0
    assert tier_size_fraction("B", "CT", "high", cfg) == 0.0


def test_tier_size_fraction_caps_at_max_fraction():
    cfg = EngineConfig(max_fraction=0.006)
    assert tier_size_fraction("B", "WT", "normal", cfg) == 0.005
    capped = EngineConfig(max_fraction=0.004)
    assert tier_size_fraction("B", "WT", "normal", capped) == 0.004


def test_tier_size_fraction_unknown_tier_profile_is_zero():
    cfg = EngineConfig(max_fraction=0.02)
    assert tier_size_fraction("C", "WT", "normal", cfg) == 0.0
