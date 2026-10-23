# tests/playbook/test_cli.py
import importlib

cli = importlib.import_module("tools.playbook.playbook_search")


def test_split_60_20_20_partitions():
    xs = list(range(100))
    a, b, c = cli._split_60_20_20(xs)
    assert (len(a), len(b), len(c)) == (60, 20, 20)
    assert a + b + c == xs


def test_register_text_lists_grid_and_gates():
    txt = cli._prereg_text({"1h": [], "2h": [], "4h": []})
    assert "PREREGISTRATION" in txt
    assert "n_trials" in txt
    assert "Donchian" in txt and "EXIT_REGISTRY unchanged" in txt
