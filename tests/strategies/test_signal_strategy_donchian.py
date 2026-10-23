from dataclasses import replace

from moonface.core.bundle import DataBundle
from moonface.research.entries import generate_entries
from moonface.kernel.synth import make_candles
from moonface.models.evaluate import evaluate
from moonface.strategies.spec import PromotedStrategy
from moonface.strategies.impls.donchian import DONCHIAN


STRATEGY = PromotedStrategy(
    family="donchian_break",
    params={"n": 20},
    exit={
        "name": "fixed_bracket",
        "params": {"atr_period": 14, "k_stop": 1.0, "m_tp": 4.0},
    },
    fraction=0.01,
    status="paper",
    asset={
        "exchange": "binance",
        "symbol": "BTC/USDT:USDT",
        "timeframe": "4h",
    },
    provenance={},
    max_drawdown_p95=0.2,
)


def _entry_case():
    candles = make_candles(400)
    i, side = generate_entries(
        "donchian_break", STRATEGY.params, DataBundle(candles=candles)
    )[-1]
    return candles, i, side


def test_current_donchian_entry_characterization():
    candles, i, side = _entry_case()
    signal = evaluate(STRATEGY, DataBundle(candles=candles[: i + 1]))
    assert signal.decision == side
    assert signal.price == candles[i].close
    assert signal.fraction == 0.01
    assert signal.reason == f"donchian_break {{'n': 20}} fired {side}"


def test_current_donchian_quiet_bar_characterization():
    candles = make_candles(400)
    entry_indexes = {
        i for i, _ in generate_entries(
            "donchian_break", STRATEGY.params, DataBundle(candles=candles)
        )
    }
    quiet = next(i for i in range(100, 399) if i not in entry_indexes)
    signal = evaluate(STRATEGY, DataBundle(candles=candles[: quiet + 1]))
    assert signal.decision == "WAIT"
    assert signal.reason == "no donchian_break entry on the last closed candle"


def test_current_donchian_long_only_characterization():
    strategy = replace(STRATEGY, params={"n": 20, "long_only": True})
    candles = make_candles(400)
    entries = generate_entries(
        "donchian_break", strategy.params, DataBundle(candles=candles)
    )
    assert all(side == "LONG" for _, side in entries)


def test_donchian_module_accepts_current_configuration():
    assert DONCHIAN.validate(STRATEGY) is True


def test_donchian_module_rejects_invalid_parameters():
    assert DONCHIAN.validate(replace(STRATEGY, params={"n": 1})) is False
    assert DONCHIAN.validate(
        replace(
            STRATEGY,
            exit={"name": "fixed_bracket", "params": {"k_stop": 1.0}},
        )
    ) is False


def test_extracted_module_matches_characterized_entry():
    candles, i, _side = _entry_case()
    bundle = DataBundle(candles=candles[: i + 1])
    assert DONCHIAN.evaluate(STRATEGY, bundle) == evaluate(STRATEGY, bundle)
