import json
from dataclasses import replace
from datetime import datetime, timezone

from moonface.core.models import Candle
from moonface.research.participation import (WORST_OBSERVED_DRAWDOWN_R,
                                             ParticipationPolicy,
                                             evaluate_participation, load_policy,
                                             policy_hash, realized_drawdown_r)

_H4_MS = 4 * 3_600_000
_START = 1_600_000_000_000

VALID_RAW = {
    "enabled": True,
    "donchian_n": 5,
    "horizon_bars": 2,
    "atr_period": 3,
    "risk_fraction": 0.0001,
    "max_account_drawdown": 0.029,
    "reconfirm_by": "2026-09-12",
    "asset": {"exchange": "binance", "symbol": "BTC/USDT:USDT",
              "timeframe": "4h"},
    "provenance": {"basis": "experiments/PROGRAM_CONCLUSION.md"},
}

NOW_FRESH = int(datetime(2026, 6, 12, tzinfo=timezone.utc).timestamp() * 1000)
NOW_STALE = int(datetime(2026, 9, 13, tzinfo=timezone.utc).timestamp() * 1000)


def _policy(**overrides) -> ParticipationPolicy:
    return replace(ParticipationPolicy(**VALID_RAW), **overrides)


def _flat(n: int, price: float = 1000.0, start_ts: int = _START) -> list[Candle]:
    return [Candle(start_ts + i * _H4_MS, price, price + 0.5, price - 0.5,
                   price, 10.0) for i in range(n)]


def _breakout(n: int = 30, jump: float = 50.0) -> list[Candle]:
    """Flat candles whose final closed bar breaks the prior donchian high."""
    cs = _flat(n)
    last = cs[-1]
    cs[-1] = Candle(last.timestamp_ms, 1000.0, 1000.0 + jump, 999.5,
                    1000.0 + jump, 10.0)
    return cs


def _breakdown(n: int = 30, drop: float = 50.0) -> list[Candle]:
    cs = _flat(n)
    last = cs[-1]
    cs[-1] = Candle(last.timestamp_ms, 1000.0, 1000.5, 1000.0 - drop,
                    1000.0 - drop, 10.0)
    return cs


# -- policy loading -----------------------------------------------------------

def test_load_policy_roundtrip(tmp_path):
    path = tmp_path / "participation.json"
    path.write_text(json.dumps(VALID_RAW))
    p = load_policy(path)
    assert p is not None
    assert p.enabled is True
    assert p.donchian_n == 5
    assert p.risk_fraction == 0.0001


def test_load_policy_is_fail_safe(tmp_path):
    assert load_policy(tmp_path / "absent.json") is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    assert load_policy(bad) is None


def test_load_policy_rejects_oversized_risk(tmp_path):
    """Layer 3 arithmetic enforced at load time: risk_fraction times the worst
    observed research drawdown must fit inside max_account_drawdown."""
    raw = dict(VALID_RAW, risk_fraction=0.001)  # 0.001 * 277 = 0.277 > 0.029
    path = tmp_path / "participation.json"
    path.write_text(json.dumps(raw))
    assert load_policy(path) is None
    assert WORST_OBSERVED_DRAWDOWN_R == 277.0


def test_load_policy_rejects_non_h4_and_bad_fields(tmp_path):
    path = tmp_path / "participation.json"
    for raw in (
        dict(VALID_RAW, asset=dict(VALID_RAW["asset"], timeframe="1h")),
        dict(VALID_RAW, horizon_bars=0),
        dict(VALID_RAW, donchian_n=-1),
        dict(VALID_RAW, reconfirm_by="not-a-date"),
        dict(VALID_RAW, max_account_drawdown=1.5),
        dict(VALID_RAW, enabled="yes"),
    ):
        path.write_text(json.dumps(raw))
        assert load_policy(path) is None, raw


def test_policy_hash_survives_reconfirmation_and_mandate_flips():
    base = _policy()
    assert policy_hash(base) == policy_hash(replace(base, enabled=False))
    assert policy_hash(base) == policy_hash(
        replace(base, reconfirm_by="2026-12-12"))
    assert policy_hash(base) != policy_hash(replace(base, risk_fraction=0.00005))


# -- decision ladder ----------------------------------------------------------

def test_default_is_wait_on_quiet_data():
    sig = evaluate_participation(_policy(), _flat(30), [], NOW_FRESH)
    assert sig.decision == "WAIT"
    assert "no donchian up-state" in sig.reason


def test_long_on_donchian_upbreak():
    policy = _policy()
    candles = _breakout()
    sig = evaluate_participation(policy, candles, [], NOW_FRESH)
    assert sig.decision == "LONG"
    assert sig.price == candles[-1].close
    assert sig.fraction == policy.risk_fraction
    assert sig.invalidation is None          # time exit, no price stop
    assert "time exit" in sig.reason


def test_short_break_is_structurally_wait():
    sig = evaluate_participation(_policy(), _breakdown(), [], NOW_FRESH)
    assert sig.decision == "WAIT"
    assert "short-side" in sig.reason


def test_disabled_mandate_waits_even_on_breakout():
    sig = evaluate_participation(_policy(enabled=False), _breakout(), [],
                                 NOW_FRESH)
    assert sig.decision == "WAIT"
    assert "not mandated" in sig.reason


def test_overdue_reconfirmation_blocks_new_entries():
    sig = evaluate_participation(_policy(), _breakout(), [], NOW_STALE)
    assert sig.decision == "WAIT"
    assert "reconfirmation overdue" in sig.reason


def test_too_few_candles_is_wait():
    sig = evaluate_participation(_policy(), _flat(3), [], NOW_FRESH)
    assert sig.decision == "WAIT"
    assert "not enough closed candles" in sig.reason


# -- position management ------------------------------------------------------

def _journal_long(policy, candles, i):
    return {"decision": "LONG", "candle_ts_ms": candles[i].timestamp_ms,
            "strategy_version": policy_hash(policy)}


def test_open_position_blocks_reentry():
    policy = _policy()                       # horizon_bars=2
    candles = _breakout()
    entries = [_journal_long(policy, candles, len(candles) - 2)]  # 1 bar ago
    sig = evaluate_participation(policy, candles, entries, NOW_FRESH)
    assert sig.decision == "WAIT"
    assert "position open" in sig.reason


def test_horizon_expiry_says_flatten():
    policy = _policy()
    candles = _flat(30)
    entries = [_journal_long(policy, candles, len(candles) - 3)]  # 2 bars ago
    sig = evaluate_participation(policy, candles, entries, NOW_FRESH)
    assert sig.decision == "WAIT"
    assert "horizon expired" in sig.reason


def test_foreign_version_entries_are_ignored():
    policy = _policy()
    candles = _flat(30)
    foreign = [{"decision": "LONG",
                "candle_ts_ms": candles[-2].timestamp_ms,
                "strategy_version": "someone-else"}]
    sig = evaluate_participation(policy, candles, foreign, NOW_FRESH)
    assert "no donchian up-state" in sig.reason


# -- kill switch --------------------------------------------------------------

def _kill_scenario():
    """Two journaled LONGs each losing ~150R under the 2-bar horizon exit:
    cumulative ~-302R, vs the policy kill threshold 0.029/0.0001 = 290R."""
    policy = _policy()
    cs = _flat(11)                                   # idx 0..10, entry 1 @ 10
    ts = cs[-1].timestamp_ms

    def bar(k, o, h, lo, c):
        return Candle(ts + k * _H4_MS, o, h, lo, c, 10.0)

    cs += [bar(1, 1000.0, 1000.5, 924.5, 925.0),
           bar(2, 925.0, 925.5, 849.5, 850.0)]       # exit 1 @ 850
    cs += [bar(3 + k, 850.0, 850.5, 849.5, 850.0) for k in range(6)]  # 13..18
    cs += [bar(9, 850.0, 850.5, 774.5, 775.0),
           bar(10, 775.0, 775.5, 699.5, 700.0)]      # exit 2 @ 700
    cs += [bar(11 + k, 700.0, 700.5, 699.5, 700.0) for k in range(4)]
    entries = [_journal_long(policy, cs, 10), _journal_long(policy, cs, 18)]
    return policy, cs, entries


def test_realized_drawdown_r_joins_journal_to_candles():
    policy, candles, entries = _kill_scenario()
    dd = realized_drawdown_r(policy, entries, candles)
    assert 295.0 < dd < 310.0


def test_kill_switch_fires_on_realized_drawdown():
    policy, candles, entries = _kill_scenario()
    sig = evaluate_participation(policy, candles, entries, NOW_FRESH)
    assert sig.decision == "WAIT"
    assert sig.kill_switch is True
    assert "kill switch" in sig.reason


def test_kill_switch_is_permanent_once_journaled():
    """A journaled kill event keeps the advisor flat even when the losing
    trades have aged out of the candle window and a fresh breakout fires."""
    policy = _policy()
    entries = [{"kill_switch": True, "strategy_version": policy_hash(policy)}]
    sig = evaluate_participation(policy, _breakout(), entries, NOW_FRESH)
    assert sig.decision == "WAIT"
    assert sig.kill_switch is True
    assert "kill switch" in sig.reason
