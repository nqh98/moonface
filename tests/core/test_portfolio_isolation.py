import inspect
import importlib
from pathlib import Path

import pytest

from moonface.core.exits import EXIT_REGISTRY

PORTFOLIO_MODULES = [
    "moonface.research.portfolio.components",
    "moonface.research.portfolio.streams",
    "moonface.research.portfolio.correlation",
    "moonface.research.portfolio.operators",
    "moonface.research.portfolio.evaluate",
    "moonface.research.portfolio.gates",
    "moonface.research.portfolio.validate",
    "moonface.research.portfolio.pipeline",
    "moonface.research.portfolio.grid",
]
FORBIDDEN = ("promotion/strategy.json", "journal/signals.jsonl", "df7cc856",
             "donchian_trail", "research.practical", "research.playbook",
             "research.btcspec", "research.system_search")
EXPECTED_EXITS = {"horizon_hold", "atr_trail", "horizon_wide_stop",
                  "breakeven_horizon", "fixed_bracket"}


@pytest.mark.parametrize("mod_name", PORTFOLIO_MODULES)
def test_portfolio_modules_clean(mod_name):
    mod = importlib.import_module(mod_name)
    src = inspect.getsource(mod)
    for needle in FORBIDDEN:
        assert needle not in src, f"{mod_name} references forbidden {needle!r}"


def test_exit_registry_unchanged():
    assert set(EXIT_REGISTRY) == EXPECTED_EXITS


def test_portfolio_search_cli_clean():
    """tools/portfolio_search.py must not reference forbidden substrings."""
    cli_path = Path(__file__).resolve().parents[2] / "tools" / "portfolio" / "portfolio_search.py"
    src = cli_path.read_text()
    for needle in FORBIDDEN:
        assert needle not in src, f"portfolio_search.py references forbidden {needle!r}"
