from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.strategies.registry import get_strategy_module
from moonface.strategies.spec import PromotedStrategy

H = 3_600_000


def _bundle(prices):
    candles = [Candle(i * H, p, p + 0.3, p - 0.3, p, 1.0) for i, p in enumerate(prices)]
    return DataBundle(candles=candles)


def _strat(label="slope20:don20:atr_trail"):
    return PromotedStrategy(
        family="playbook",
        params={"label": label},
        exit={"name": "atr_trail", "params": {"k_trail": 3.0, "max_bars": 96, "atr_period": 14}},
        fraction=0.01,
        status="paper",
        asset={"exchange": "binance", "symbol": "BTCUSDT", "timeframe": "1h"},
        provenance={"domain": "playbook", "version": "0", "spec_hash": "test", "report": ""},
        max_drawdown_p95=0.0,
    )


def test_playbook_family_is_registered():
    assert get_strategy_module("playbook") is not None


def test_downtrend_bundle_emits_wait():
    mod = get_strategy_module("playbook")
    sig = mod.evaluate(_strat(), _bundle([300 - i * 0.2 for i in range(300)]))
    assert sig.decision == "WAIT"
