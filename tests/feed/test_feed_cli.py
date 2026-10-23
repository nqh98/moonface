from __future__ import annotations

import json

from moonface.core.models import Candle
from moonface.feed.cli import run


def _c(i, o, h, lo, c):
    return Candle(1780275600000 + i * 4 * 3_600_000, o, h, lo, c, 1.0)


def _bundle(symbol, *_a, **_kw):
    """A bundle whose final candle is a sweep->CHOCH LONG confirmation."""
    from moonface.core.bundle import DataBundle
    bars = []
    idx = 0
    for leg in range(11):
        b = 100 + 10 * leg
        for o, h, lo, c in [
            (b, b + 2, b - 3, b), (b + 3, b + 6, b, b + 3),
            (b + 6, b + 9, b + 4, b + 6), (b + 9, b + 12, b + 7, b + 9),
            (b + 12, b + 15, b + 10, b + 12), (b + 10, b + 13, b + 5, b + 10),
            (b + 5, b + 8, b, b + 5), (b, b + 3, b - 6, b), (b - 3, b, b - 6, b - 3),
            (b - 5, b - 2, b - 20, b - 2), (b - 2, b + 20, b - 4, b + 18),
        ]:
            bars.append(_c(idx, o, h, lo, c))
            idx += 1
    # D-T9: truncate to 66 bars so the final candle (i=65) is a confirmed
    # sweep_choch LONG; the full 121-bar fixture's last candle fires nothing.
    return DataBundle(candles=bars[:66])


def test_once_dry_run_prints_card_without_posting(capsys, tmp_path):
    posted: list[str] = []

    def fake_post(msg):
        posted.append(msg)

    rc = run(["--once", "--state", str(tmp_path / "f.jsonl")],
             fetch_bundle=_bundle,
             select_universe=lambda *a, **k: ["BTC/USDT:USDT"],
             post=fake_post)
    assert rc == 0
    out = capsys.readouterr().out
    assert "🟢 BTCUSDT • LONG" in out
    assert "[SMC SETUP — heuristic; no validated out-of-sample edge]" in out
    assert posted == []                      # dry-run: nothing posted


def test_once_post_calls_telegram_and_records_state(tmp_path):
    posted: list[str] = []
    state = tmp_path / "f.jsonl"
    run(["--once", "--post", "--state", str(state)],
        fetch_bundle=_bundle,
        select_universe=lambda *a, **k: ["BTC/USDT:USDT"],
        post=lambda m: posted.append(m))
    assert len(posted) == 1
    assert "BTCUSDT • LONG" in posted[0]
    lines = [ln for ln in state.read_text().splitlines() if ln.strip()]
    assert json.loads(lines[0])["status"] == "open"
    assert json.loads(lines[0])["symbol"] == "BTC/USDT:USDT"


def test_disclaimer_prints_banner(capsys):
    rc = run(["--disclaimer"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "not financial advice" in out.lower()
    assert "no validated out-of-sample edge" in out.lower()
