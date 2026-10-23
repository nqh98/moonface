import pathlib

PKG = pathlib.Path("src/moonface/research/regime_overlay")


def test_no_signal_or_promotion_imports():
    for f in PKG.glob("*.py"):
        text = f.read_text()
        assert "moonface.signal" not in text, f
        assert "promotion" not in text, f
        assert "EXIT_REGISTRY" not in text, f


def test_no_journal_writes():
    for f in PKG.glob("*.py"):
        assert "journal/signals.jsonl" not in f.read_text(), f
