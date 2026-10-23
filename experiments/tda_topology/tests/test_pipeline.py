import random

from moonface.foundation.bundle import DataBundle
from moonface.foundation.models import Candle
from moonface.research.microscope.events import Event

from run import render_report, run_study

BAR_MS = 4 * 60 * 60 * 1000


def _iid_pool(n_assets=9, n_bars=900, seed=11):
    """Constant-vol iid Gaussian returns: no effect exists by construction."""
    rng = random.Random(seed)
    pool = {}
    for a in range(n_assets):
        price = 100.0
        candles = []
        for t in range(n_bars):
            price *= (1.0 + rng.gauss(0.0, 0.01))
            candles.append(Candle(timestamp_ms=t * BAR_MS, open=price,
                                  high=price * 1.01, low=price * 0.99,
                                  close=price, volume=1.0))
        pool[f"A{a}"] = DataBundle(candles=candles)
    return pool


def _events(pool, every=1):
    out = []
    for sym, bundle in pool.items():
        for i in range(400, len(bundle.candles) - 50, every):
            out.append(Event(ts_ms=bundle.candles[i].timestamp_ms,
                             symbol=sym, direction=1))
    return out


def test_iid_null_is_indistinguishable_from_null():
    """A valid instrument must FAIL on a null. vol_compression produced this
    program's first ever PASS and it was an artifact an iid null would have
    caught; that check is a build-time requirement here."""
    pool = _iid_pool()
    timestamps = sorted({c.timestamp_ms
                         for b in pool.values() for c in b.candles})
    res = run_study(pool, _events(pool), timestamps, seed=1)
    assert res["block_null"]["verdict"] == "INDISTINGUISHABLE_FROM_NULL"


def test_run_is_deterministic_under_a_fixed_seed():
    pool = _iid_pool()
    timestamps = sorted({c.timestamp_ms
                         for b in pool.values() for c in b.candles})
    events = _events(pool)
    a = run_study(pool, events, timestamps, seed=1)
    b = run_study(pool, events, timestamps, seed=1)
    assert a["block_null"] == b["block_null"]
    assert a["buckets"] == b["buckets"]


def test_report_states_the_verdict_and_the_scope_caveat():
    pool = _iid_pool()
    timestamps = sorted({c.timestamp_ms
                         for b in pool.values() for c in b.candles})
    events = _events(pool)
    res = run_study(pool, events, timestamps, seed=1)
    text = render_report(res, n_events=len(events))
    assert "INDISTINGUISHABLE_FROM_NULL" in text
    assert "NOT A GATE" in text
    assert "long-only" in text
    assert "0.609" in text          # the microscope head-to-head baseline
