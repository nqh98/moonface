"""Lane 1 Track-A event proxy: flag liquidation-cascade bars from OHLCV+OI and
infer the continuation (offload) side.

A cascade bar has (all): a large ATR-normalized body, a volume-participation
spike (level z-score of log-volume), and OI deleveraging (bar-over-bar OI
log-change z-score <= -k). Side = continuation of the bar sign: a big DOWN bar
means longs were liquidated and the exchange must SELL its inventory -> SHORT;
a big UP bar -> LONG. `require_oi_drop=False` yields the vol-matched control
(same body+volume, OI did NOT drop)."""
from __future__ import annotations

from collections.abc import Callable
from math import log

from moonface.core.models import Candle
from moonface.core.risk import risk_unit
from moonface.research.edge.divergence_signals import _log_changes, _zscore
from moonface.research.edge.forced_error_signals import _level_zscore

Entry = tuple[int, str]
Generator = Callable[[list[Candle], dict], list[Entry]]


def make_liq_cascade(oi_feature: list) -> Generator:
    oi = list(oi_feature)

    def gen(candles: list[Candle], params: dict) -> list[Entry]:
        window = params["window"]
        k = params["k"]
        m = params["m"]
        atr_period = params["atr_period"]
        require_oi_drop = params.get("require_oi_drop", True)
        n = len(candles)
        o_log = _log_changes(oi, 1, n)
        vol_log = [
            log(c.volume) if c.volume and c.volume > 0 else None
            for c in candles
        ]
        out: list[Entry] = []
        for i in range(window + 1, n - 1):
            unit = risk_unit(candles, i, 1.0, atr_period)
            if unit is None or unit <= 0.0:
                continue
            body = candles[i].close - candles[i].open
            if abs(body) / unit < m:
                continue
            z_v = _level_zscore(vol_log, i, window)
            if z_v is None or z_v < k:
                continue
            z_o = _zscore(o_log, i, window)
            if z_o is None:
                continue
            oi_dropped = z_o <= -k
            if require_oi_drop != oi_dropped:
                continue
            out.append((i, "LONG" if body > 0 else "SHORT"))
        return out

    return gen
