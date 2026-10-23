"""Foundation stats of the scoring audit (spec 2026-07-05, §5.1).

block_ci must reproduce calibration.block_bootstrap_rho_ci when given the
same stat, so audit CIs stay comparable with the 2026-07 baseline.
"""
import random

from moonface.models.engine.audit import (baseline_ordering, block_ci,
                                          _rho_stat, _split_trades)
from moonface.models.engine.calibration import (HypoTrade,
                                                block_bootstrap_rho_ci)

H = 3_600_000


def _mk_trade(i, direction, score, net_r):
    return HypoTrade(entry_index=i, exit_index=i + 3, entry_ts_ms=i * H,
                     exit_ts_ms=(i + 3) * H, book="trend",
                     direction=direction, score=score, breadth=3,
                     policy="ALLOW", macro_effective="NEUTRAL",
                     vol_state="normal", net_r=net_r, bars_held=3,
                     exit_reason="stop")


def _panel(n=1200, seed=1, informative=True):
    rng = random.Random(seed)
    out = []
    for k in range(n):
        score = rng.choice((20, 40, 60, 80))
        noise = rng.gauss(0.0, 0.5)
        net_r = (0.02 * score + noise) if informative else noise
        direction = 1 if k % 3 else -1
        out.append(_mk_trade(k * 35, direction, score, round(net_r, 4)))
    return out


def test_block_ci_matches_calibration_bootstrap_for_rho():
    panel = _panel()
    ours = block_ci(panel, lambda t: t.entry_index, _rho_stat)
    theirs = block_bootstrap_rho_ci(panel)
    assert ours is not None and theirs is not None
    assert abs(ours[0] - theirs[0]) < 1e-12
    assert abs(ours[1] - theirs[1]) < 1e-12


def test_block_ci_single_block_returns_none():
    panel = [_mk_trade(i, 1, 60, 0.1) for i in range(5)]  # all in block 0
    assert block_ci(panel, lambda t: t.entry_index, _rho_stat) is None


def test_split_trades_directions():
    panel = _panel(n=30)
    longs = _split_trades(panel, "LONG")
    shorts = _split_trades(panel, "SHORT")
    assert all(t.direction == 1 for t in longs)
    assert all(t.direction == -1 for t in shorts)
    assert len(longs) + len(shorts) == len(_split_trades(panel, "pooled"))


def test_baseline_ordering_shape_and_power_floor():
    report = baseline_ordering(_panel())
    assert set(report) == {"pooled", "LONG", "SHORT"}
    pooled = report["pooled"]
    assert pooled["n"] == 1200
    assert pooled["status"] == "ok"
    assert pooled["spearman_rho"] > 0.3
    assert pooled["rho_ci_95"][0] > 0
    tiny = baseline_ordering(_panel(n=150))
    assert tiny["pooled"]["status"] == "UNDERPOWERED"
