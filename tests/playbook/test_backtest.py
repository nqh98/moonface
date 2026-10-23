from moonface.core.models import Candle
from moonface.research.playbook.families import all_playbook_configs
from moonface.research.playbook.mtf import MTFView
from moonface.research.playbook.backtest import replay, playbook_trade_rs

H = 3_600_000


def _h1(prices):
    return [Candle(i * H, p, p + 2.0, p - 2.0, p, 1.0) for i, p in enumerate(prices)]


def _resample(h1, factor):
    out = []
    for k in range(0, len(h1), factor):
        chunk = h1[k:k + factor]
        out.append(Candle(chunk[0].timestamp_ms, chunk[0].open,
                          max(c.high for c in chunk), min(c.low for c in chunk),
                          chunk[-1].close, sum(c.volume for c in chunk)))
    return out


def _view():
    prices = [100.0 + i * 0.05 for i in range(1300)]
    prices[900] = prices[899] + 3.0      # breakout spike past bar 880 (regime has >=220 closed h4 bars)
    prices[1100] = prices[1099] + 3.0    # 2nd breakout, >96 bars after the first
    h1 = _h1(prices)
    return MTFView.build(h1, _resample(h1, 2), _resample(h1, 4))


def test_replay_produces_trades_and_journal():
    cfg = all_playbook_configs()[0]
    trades, journal = replay(_view(), cfg)
    assert isinstance(trades, list)
    assert all(t.outcome_class in {"clean", "late", "choppy", "failed_by_regime"}
               for t in trades)
    assert len(journal) >= len(trades)        # at least one event per trade
    rs = playbook_trade_rs(_view(), cfg)
    assert len(rs) == len(trades)


def test_single_position_no_overlap():
    cfg = all_playbook_configs()[0]
    trades, _ = replay(_view(), cfg)
    idx = sorted(t.entry_index for t in trades)
    assert idx == sorted(set(idx))            # no duplicate entries
