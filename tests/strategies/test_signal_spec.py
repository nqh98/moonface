import json
from pathlib import Path

from moonface.strategies.spec import PromotedStrategy, load_strategy, strategy_hash

VALID = {
    "family": "donchian_break",
    "params": {"n": 20},
    "exit": {"name": "fixed_bracket",
             "params": {"atr_period": 14, "k_stop": 1.0, "m_tp": 4.0}},
    "fraction": 0.01,
    "status": "paper",
    "asset": {"exchange": "binance", "symbol": "BTC/USDT:USDT", "timeframe": "4h"},
    "provenance": {"domain": "new_families.lead_lag", "version": 1,
                   "spec_hash": "abc"},
    "max_drawdown_p95": 0.18,
}


def _write(tmp_path, payload):
    p = tmp_path / "strategy.json"
    p.write_text(json.dumps(payload) if isinstance(payload, dict) else payload)
    return p


def test_loads_valid_strategy(tmp_path):
    s = load_strategy(_write(tmp_path, VALID))
    assert isinstance(s, PromotedStrategy)
    assert s.family == "donchian_break"
    assert s.status == "paper"


def test_missing_file_is_none(tmp_path):
    assert load_strategy(tmp_path / "absent.json") is None


def test_corrupt_json_is_none(tmp_path):
    assert load_strategy(_write(tmp_path, "{not json")) is None


def test_unknown_family_is_none(tmp_path):
    assert load_strategy(_write(tmp_path, {**VALID, "family": "astrology"})) is None


def test_unknown_exit_is_none(tmp_path):
    bad = {**VALID, "exit": {"name": "psychic", "params": {"atr_period": 14}}}
    assert load_strategy(_write(tmp_path, bad)) is None


def test_bad_status_is_none(tmp_path):
    assert load_strategy(_write(tmp_path, {**VALID, "status": "live!!"})) is None


def test_nonpositive_fraction_is_none(tmp_path):
    assert load_strategy(_write(tmp_path, {**VALID, "fraction": 0})) is None


def test_strategy_hash_is_stable_and_ignores_status(tmp_path):
    a = load_strategy(_write(tmp_path, VALID))
    b = load_strategy(_write(tmp_path, {**VALID, "status": "live"}))
    assert strategy_hash(a) == strategy_hash(b)
    c = load_strategy(_write(tmp_path, {**VALID, "params": {"n": 55}}))
    assert strategy_hash(a) != strategy_hash(c)


def test_invalid_donchian_params_are_none(tmp_path):
    assert load_strategy(
        _write(tmp_path, {**VALID, "params": {"n": 1}})
    ) is None


def test_repository_archived_strategy_still_loads():
    path = (Path(__file__).parents[2] / "promotion" / "archive"
            / "2026-07-03-v2-refocus" / "strategy.json")
    strategy = load_strategy(path)
    assert strategy is not None
    assert strategy.family == "donchian_break"
    assert strategy.params == {"n": 40, "long_only": True}


def test_hash_payload_remains_backward_compatible(tmp_path):
    strategy = load_strategy(_write(tmp_path, VALID))
    expected = {
        "family": strategy.family,
        "params": strategy.params,
        "exit": strategy.exit,
        "fraction": strategy.fraction,
        "asset": strategy.asset,
    }
    text = json.dumps(expected, sort_keys=True, separators=(",", ":"))
    import hashlib

    assert strategy_hash(strategy) == hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()
