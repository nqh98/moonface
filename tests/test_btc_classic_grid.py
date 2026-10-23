import importlib.util
import sys
from pathlib import Path
from types import MappingProxyType

import pytest
from moonface.core.models import Candle
from moonface.research.btc_classic.evaluate import cell_entries, evaluate_spec
from moonface.research.btc_classic.grid import SignalSpec, all_specs, EXIT_NAME, EXIT_PARAMS
from moonface.kernel.power_harness import bonferroni_level


def test_grid_is_exactly_six_frozen_specs():
    specs = all_specs()
    assert [s.key for s in specs] == [
        "trend", "breakout", "momentum", "channel", "meanrev", "funding_fade",
    ]
    # one a-priori config per family -> K = 6
    assert len(specs) == 6
    assert abs(bonferroni_level(len(specs)) - 0.05 / 6) < 1e-12


def test_specs_carry_expected_builders_and_kinds():
    by_key = {s.key: s for s in all_specs()}
    assert by_key["trend"].kind == "price" and by_key["trend"].builder == "ma_cross"
    assert by_key["breakout"].builder == "donchian_break"
    assert by_key["momentum"].builder == "roc_sign"
    assert by_key["channel"].builder == "atr_channel_break"
    assert by_key["meanrev"].builder == "reversion_in_range"
    assert by_key["funding_fade"].kind == "funding"
    assert by_key["funding_fade"].builder == "funding_fade"


def test_params_and_exit_are_frozen_and_shared():
    for s in all_specs():
        assert isinstance(s.params, MappingProxyType)
        assert isinstance(s.exit_params, MappingProxyType)
        assert s.exit_name == EXIT_NAME == "atr_trail"
        assert dict(s.exit_params) == EXIT_PARAMS == {
            "k_trail": 2.0, "max_bars": 120, "atr_period": 14,
        }
        with pytest.raises(TypeError):
            s.params["x"] = 1  # MappingProxyType is read-only


def test_frozen_configs_have_expected_values():
    by_key = {s.key: dict(s.params) for s in all_specs()}
    assert by_key["trend"] == {"fast": 20, "slow": 100}
    assert by_key["breakout"] == {"n": 55}
    assert by_key["momentum"] == {"period": 24}
    assert by_key["channel"] == {"k": 1.5, "atr_period": 14}
    assert by_key["meanrev"] == {"period": 14, "low": 30, "high": 70}
    assert by_key["funding_fade"] == {"window": 180, "z_thr": 2.0}


def _candles(closes):
    out = []
    for i, c in enumerate(closes):
        out.append(Candle(
            timestamp_ms=i * 14_400_000,  # 4h bars
            open=float(c), high=float(c), low=float(c) - 1.0,
            close=float(c), volume=1.0,
        ))
    return out


def _spec(kind, builder, params):
    return SignalSpec(
        key="t", kind=kind, builder=builder,
        params=MappingProxyType(dict(params)), exit_name=EXIT_NAME,
        exit_params=MappingProxyType(dict(EXIT_PARAMS)),
    )


def test_price_routing_emits_long_breakouts_no_lookahead():
    candles = _candles(list(range(100, 140)))  # strictly rising
    spec = _spec("price", "donchian_break", {"n": 2})
    entries = cell_entries(candles, None, spec)
    assert entries, "rising series should break the donchian channel up"
    assert all(side == "LONG" for _, side in entries)
    # no-lookahead: entry index is within range and after the warmup window
    assert all(2 <= i < len(candles) for i, _ in entries)


def test_funding_routing_uses_make_funding_fade():
    # window=3, z_thr=1.0: a single large positive spike -> crowded long -> SHORT
    funding = [0.0, 0.0, 0.0, 0.0, 0.0, 0.01, 0.0, 0.0, 0.0]
    candles = _candles([100.0] * len(funding))
    spec = _spec("funding", "funding_fade", {"window": 3, "z_thr": 1.0})
    entries = cell_entries(candles, funding, spec)
    assert any(side == "SHORT" for _, side in entries)


def test_evaluate_spec_returns_records_structure():
    # rise then fall so an atr_trail long both enters and resolves
    closes = list(range(100, 160)) + list(range(158, 98, -2))
    candles = _candles(closes)
    spec = _spec("price", "donchian_break", {"n": 2})
    out = evaluate_spec(candles, None, spec)
    assert set(out.keys()) == {"key", "metrics", "records"}
    assert out["key"] == "t"
    assert isinstance(out["records"], list) and len(out["records"]) >= 1
    for rec in out["records"]:
        assert set(rec.keys()) >= {"i", "side", "net_r", "atr_frac"}
    assert "expectancy_r" in out["metrics"] and "max_drawdown_r" in out["metrics"]


def test_unknown_kind_raises():
    spec = _spec("bogus", "ma_cross", {"fast": 2, "slow": 4})
    with pytest.raises(ValueError):
        cell_entries(_candles([1, 2, 3, 4, 5]), None, spec)


def _load_cli():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "tools"))
    import tools.breadth.breadth as _tools_breadth
    # The CLI does `from breadth import ...`; pytest's prepend collection can
    # cache the bare name `breadth` as a test package, so force `breadth` at
    # tools/breadth.py for the CLI load, then restore (matches sibling CLIs).
    _saved = sys.modules.get("breadth")
    sys.modules["breadth"] = _tools_breadth
    try:
        spec = importlib.util.spec_from_file_location(
            "btc_classic_cli", root / "tools" / "btc_classic" / "btc_classic.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if _saved is not None:
            sys.modules["breadth"] = _saved
        else:
            sys.modules.pop("breadth", None)


def test_cli_split_parallel_aligns_funding_to_candles():
    cli = _load_cli()
    candles = _candles(list(range(0, 100)))
    funding = [float(i) for i in range(100)]
    (tr_c, tr_f), (va_c, va_f), (se_c, se_f) = cli._split_parallel(candles, funding)
    # same boundaries as split_60_20_20: a=60, b=80
    assert len(tr_c) == len(tr_f) == 60
    assert len(va_c) == len(va_f) == 20
    assert len(se_c) == len(se_f) == 20
    # funding stays index-aligned to its candle slice
    assert tr_f[0] == 0.0 and va_f[0] == 60.0 and se_f[0] == 80.0


def test_cli_spec_doc_is_json_safe():
    cli = _load_cli()
    from moonface.research.btc_classic.grid import all_specs
    doc = cli._spec_doc(all_specs()[0])
    assert doc["key"] == "trend"
    assert doc["params"] == {"fast": 20, "slow": 100}
    assert doc["exit_name"] == "atr_trail"
    import json
    json.dumps(doc)  # must not raise


def test_cli_parser_requires_a_mode():
    cli = _load_cli()
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["--start-ms", "1", "--end-ms", "2",
                                       "--out-dir", "x"])
