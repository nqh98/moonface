"""Grid validity + smoke tests for the practical-full re-eval lane.

The program's recurring failure mode in these lanes is a config whose params do
not match its generator's signature (KeyError mid-run). These tests prove every
frozen config resolves end-to-end through net_trade_rs BEFORE the multi-hour run.
"""
import math

from moonface.core.exits import EXECUTABLE_EXITS
from moonface.core.models import Candle
from moonface.research.edge_search import net_trade_rs
from moonface.research.entries import PRICE_FAMILIES
from moonface.research.practical_full import grid


def _synthetic(n=700):
    """Trend + oscillation + intrabar range so every family can fire signals."""
    out = []
    px = 1000.0
    for k in range(n):
        px = 1000.0 + 4.0 * k + 120.0 * math.sin(k / 11.0)
        hi = px + 30.0 + 10.0 * abs(math.sin(k / 5.0))
        lo = px - 30.0 - 10.0 * abs(math.cos(k / 7.0))
        op = px - 5.0 * math.sin(k / 3.0)
        out.append(Candle(timestamp_ms=k * 7_200_000, open=op, high=hi,
                          low=lo, close=px, volume=1.0))
    return out


def test_all_configs_have_known_family_and_exit():
    for c in grid.all_configs(["2h", "4h"]):
        assert c.family in PRICE_FAMILIES, c.label
        assert c.exit_name in EXECUTABLE_EXITS, c.label
        assert "atr_period" in c.exit_params, c.label


def test_every_config_resolves_through_net_trade_rs():
    cs = _synthetic()
    for c in grid.all_configs(["2h", "4h"]):
        rs = net_trade_rs(cs, c.family, c.params, c.exit_name, c.exit_params, c.h)
        assert isinstance(rs, list), c.label


def test_each_group_has_at_least_two_axis_members():
    by_group: dict[str, list] = {}
    for c in grid.all_configs(["2h", "4h"]):
        by_group.setdefault(c.group, []).append(c)
    for g, members in by_group.items():
        assert len(members) >= 2, g  # island check needs neighbours
        assert len({m.axis for m in members}) == len(members), g


def test_covers_requested_new_mechanisms():
    fams = {c.family for c in grid.all_configs(["4h"])}
    # context-filtered / WAIT-heavy trend, vol-breakout cores, mean-revert
    for required in ("vol_regime", "trend_pullback", "vol_compression_breakout",
                     "vol_expansion", "donchian_break", "atr_channel_break",
                     "reversion_in_range"):
        assert required in fams, required


def test_includes_alternative_trend_exits():
    exits = {c.exit_name for c in grid.all_configs(["4h"])}
    assert {"atr_trail", "chandelier"} <= exits
