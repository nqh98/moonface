from __future__ import annotations

from statistics import fmean, pstdev

from moonface.core.models import Candle

Entry = tuple[int, str]


def make_eth_lead_momentum(feature: list[float | None]):
    """Cross-asset lead-lag: z-score of the feature series' lookback-bar return
    over a rolling window; enter the traded asset in the direction of the move
    when |z| >= z_thr. None gaps skip the bar (the loader enforces coverage
    loudly; this generator only has to be deterministic)."""

    def gen(candles: list[Candle], params: dict) -> list[Entry]:
        window, lookback = params["window"], params["lookback"]
        z_thr = params["z_thr"]
        n = len(candles)
        rets: list[float | None] = [None] * n
        for i in range(lookback, min(n, len(feature))):
            now, then = feature[i], feature[i - lookback]
            if now is not None and then is not None and then != 0:
                rets[i] = now / then - 1.0
        out: list[Entry] = []
        for i in range(window + lookback, n - 1):
            r_i = rets[i]
            if r_i is None:
                continue
            sample = [r for r in rets[i - window + 1: i + 1] if r is not None]
            if len(sample) < window // 2:
                continue
            sd = pstdev(sample)
            if sd == 0:
                continue
            z = (r_i - fmean(sample)) / sd
            if z >= z_thr:
                out.append((i, "LONG"))
            elif z <= -z_thr:
                out.append((i, "SHORT"))
        return out

    return gen
