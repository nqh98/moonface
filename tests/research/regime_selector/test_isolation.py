# tests/research/regime_selector/test_isolation.py
import pathlib

PKG = pathlib.Path("src/moonface/research/regime_selector")


def test_no_signal_or_promotion_imports():
    for f in PKG.glob("*.py"):
        text = f.read_text()
        assert "moonface.signal" not in text, f
        assert "promotion" not in text, f
        assert "EXIT_REGISTRY" not in text, f


def test_no_journal_writes():
    for f in PKG.glob("*.py"):
        assert "journal/signals.jsonl" not in f.read_text(), f


def test_no_donchian_base():
    for f in PKG.glob("*.py"):
        text = f.read_text()
        assert "simulate_donchian" not in text, f
        assert "donchian_break" not in text, f
