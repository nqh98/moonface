"""Tests for consolidated runner — single-load, error-tolerant ranking."""
from __future__ import annotations

from moonface.research.consolidated.result import AdapterResult


def test_runner_ranks_and_survives_errors(monkeypatch):
    from moonface.research.consolidated import runner, adapters as A

    A.ADAPTERS.clear()

    @A.register("good")
    def _g(ctx):  # noqa: ANN001
        return [
            AdapterResult(
                "good:1",
                "good",
                "r_trade",
                {},
                "frozen_family",
                "atr_trail",
                "FLAT",
                records=[{"i": 0, "side": "LONG", "net_r": 3.0, "atr_frac": 0.02}],
            )
        ]

    @A.register("boom")
    def _b(ctx):  # noqa: ANN001
        raise RuntimeError("nope")

    monkeypatch.setattr(runner, "_build_context", lambda *a, **k: object())
    out = runner.run(1, 2, ".backtest_cache")
    assert out["rows"][0]["lane"] == "good"
    assert any(
        r.get("status") == "error" and r["lane"] == "boom" for r in out["rows"]
    )
