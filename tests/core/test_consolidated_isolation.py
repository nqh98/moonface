import pathlib

from moonface.core.exits import EXIT_REGISTRY, EXECUTABLE_EXITS


def test_exit_registry_unchanged():
    # consolidated must not have mutated exit membership
    assert "atr_trail" in EXIT_REGISTRY and "donchian_trail" in EXECUTABLE_EXITS


def test_consolidated_imports_no_dsr():
    root = pathlib.Path("src/moonface/research/consolidated")
    for p in root.glob("*.py"):
        src = p.read_text()
        assert "deflated_sharpe" not in src
        assert "import dsr" not in src and "portfolio_dsr" not in src


def test_runner_writes_only_under_experiments_consolidated_ls():
    src = pathlib.Path("tools/consolidated/consolidated_ls.py").read_text()
    assert "experiments/consolidated_ls" in src
    for forbidden in ("PREREGISTRATION.json", "promotion/"):
        assert forbidden not in pathlib.Path(
            "src/moonface/research/consolidated/report.py").read_text()
