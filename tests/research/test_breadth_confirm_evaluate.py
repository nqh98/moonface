from moonface.core.models import Candle
from moonface.research.universe_data import DailyRow
from moonface.research.breadth_internal.signals import net_new_highs_state
from moonface.research.breadth_internal.overlap import overlapping_entries_from_state
from moonface.research.breadth.signals import entries_from_state
from moonface.research.breadth_confirm.evaluate import evaluate_slice_overlap
from moonface.research.breadth_confirm.grid import net_new_highs_spec

_DAY = 86_400_000
_4H = 4 * 60 * 60 * 1000


def _daily_breakout_universe():
    # Two non-BTC coins that both ramp to fresh highs over the window, so the
    # net-new-highs aggregate hits the +0.30 LONG band on the ramp days.
    def ramp(start_close):
        rows = []
        for i in range(40):
            close = start_close + i  # strictly increasing -> rolling-max highs
            rows.append(DailyRow(ts_ms=i * _DAY, close=close, quote_volume=1000.0))
        return rows

    return {"AUSDT": ramp(10.0), "BUSDT": ramp(20.0)}


def _btc_candles():
    # One 4h candle at each day boundary + a few intraday bars, spanning the window.
    # Spans one day past the 40-day daily ramp so the final active state-day has a
    # following bar to map its overlapping entry onto (otherwise the last event,
    # which has no next-day bar, is silently dropped).
    candles = []
    for i in range(41):
        base = i * _DAY
        for j in range(6):  # 6 x 4h = 24h
            ts = base + j * _4H
            candles.append(Candle(timestamp_ms=ts, open=100.0, high=101.0, low=99.0,
                                   close=100.0, volume=1.0))
    return candles


def test_state_emits_long_on_broad_new_highs():
    daily = _daily_breakout_universe()
    spec = net_new_highs_spec()
    state = net_new_highs_state(daily, int(spec.params["n"]), spec.params["long_thr"],
                                spec.params["short_thr"])
    sides = {side for _, side in state}
    assert "LONG" in sides  # broad fresh-highs expansion -> LONG


def test_overlap_yields_one_entry_per_active_day_after_the_state_day():
    daily = _daily_breakout_universe()
    btc = _btc_candles()
    spec = net_new_highs_spec()
    state = net_new_highs_state(daily, int(spec.params["n"]), spec.params["long_thr"],
                                spec.params["short_thr"])
    active_days = [ts for ts, side in state if side in ("LONG", "SHORT")]
    entries = overlapping_entries_from_state(btc, state, spec.h)
    assert len(entries) == len(active_days)  # one entry per active day
    # Each entry's bar timestamp is strictly after its source state-day boundary.
    for (bar_idx, _side), day_ts in zip(entries, active_days):
        assert btc[bar_idx].timestamp_ms >= day_ts + _DAY


def test_overlap_count_ge_nonoverlap_count():
    daily = _daily_breakout_universe()
    btc = _btc_candles()
    spec = net_new_highs_spec()
    state = net_new_highs_state(daily, int(spec.params["n"]), spec.params["long_thr"],
                                spec.params["short_thr"])
    overlap = overlapping_entries_from_state(btc, state, spec.h)
    nonoverlap = entries_from_state(btc, state, spec.h)
    assert len(overlap) >= len(nonoverlap)


def test_evaluate_slice_overlap_shape():
    daily = _daily_breakout_universe()
    btc = _btc_candles()
    out = evaluate_slice_overlap(daily, btc, net_new_highs_spec())
    assert set(out) == {"key", "metrics", "records"}
    assert out["key"] == "net_new_highs"
    assert out["metrics"]["trade_count"] == len(out["records"])


def test_evaluate_slice_overlap_empty_inputs():
    out = evaluate_slice_overlap({}, [], net_new_highs_spec())
    assert out["records"] == []
    assert out["metrics"]["trade_count"] == 0


# --- appended: CLI-helper unit tests (no network) ---
import importlib.util  # noqa: E402
from pathlib import Path  # noqa: E402

_CLI_PATH = Path(__file__).resolve().parents[2] / "tools" / "breadth_confirm" / "breadth_confirm.py"


def _load_cli():
    import sys

    import tools.breadth.breadth as _tools_breadth

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    # The CLI does `from breadth import ...`. Pytest's prepend collection can cache
    # the bare name `breadth` as a different module; point it at tools/breadth.py
    # for the CLI load, then restore the prior binding (matches the sibling
    # tools-CLI tests' hermeticity guard).
    _saved = sys.modules.get("breadth")
    sys.modules["breadth"] = _tools_breadth
    try:
        spec = importlib.util.spec_from_file_location("breadth_confirm_cli", _CLI_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        if _saved is not None:
            sys.modules["breadth"] = _saved
        else:
            sys.modules.pop("breadth", None)
    return mod


def test_cli_xcheck_matches_discovery_constants():
    cli = _load_cli()
    good_validate = {"metrics": {"expectancy_r": 0.5323, "trade_count": 34}}
    good_sealed = {"metrics": {"expectancy_r": 0.2588, "trade_count": 32}}
    assert cli._xcheck_ok(good_validate, good_sealed) is True
    bad = {"metrics": {"expectancy_r": 0.10, "trade_count": 34}}
    assert cli._xcheck_ok(bad, good_sealed) is False


def test_cli_lane_verdict_confirmed_when_any_slice_confirmed():
    cli = _load_cli()
    assert cli._lane_verdict([{"status": "confirmed"}, {"status": "mechanism_unconfirmed"}]) == "confirmed"
    assert cli._lane_verdict([{"status": "mechanism_unconfirmed"}, {"status": "infeasible"}]) == "mechanism_unconfirmed"
    assert cli._lane_verdict([{"status": "infeasible"}]) == "mechanism_unconfirmed"
