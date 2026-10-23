import os
from unittest import mock

from moonface.config import Settings


def test_defaults_are_perp_research_settings():
    with mock.patch.dict(os.environ, {}, clear=True):
        s = Settings.from_env()
    assert s.exchange == "binance"
    assert s.symbol == "BTC/USDT:USDT"
    assert s.sandbox is False
    assert s.atr_period == 14
    assert s.n_periods == 5


def test_env_overrides():
    env = {"MOONFACE_EXCHANGE": "Bybit", "MOONFACE_SYMBOL": "BTC/USDT:USDT",
           "MOONFACE_ATR_PERIOD": "21", "MOONFACE_SANDBOX": "true"}
    with mock.patch.dict(os.environ, env, clear=True):
        s = Settings.from_env()
    assert s.exchange == "bybit"
    assert s.atr_period == 21
    assert s.sandbox is True


def test_settings_have_no_llm_or_telegram_fields():
    fields = set(Settings.__dataclass_fields__)
    assert not any(f.startswith(("llm_", "telegram_", "champion_")) for f in fields)
    assert "advisor_mode" not in fields
