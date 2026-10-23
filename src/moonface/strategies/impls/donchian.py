from __future__ import annotations

from moonface.core.bundle import DataBundle
from moonface.core.indicators import donchian_channel
from moonface.core.risk import risk_unit
from moonface.models.evaluate import Signal, sentinel_extended, wait
from moonface.strategies.registry import register


@register
class DonchianStrategy:
    family = "donchian_break"

    def validate(self, strategy) -> bool:
        params = strategy.params
        exit_params = strategy.exit.get("params")
        return (
            isinstance(params.get("n"), int)
            and params["n"] >= 2
            and isinstance(params.get("long_only", False), bool)
            and isinstance(exit_params, dict)
            and isinstance(exit_params.get("atr_period"), int)
            and exit_params["atr_period"] > 0
            and isinstance(
                exit_params.get("k_stop", exit_params.get("k_trail", 1.0)),
                (int, float),
            )
        )

    def evaluate(self, strategy, bundle: DataBundle) -> Signal:
        if len(bundle.candles) < 2:
            return wait("not enough closed candles")
        n = strategy.params["n"]
        long_only = strategy.params.get("long_only", False)
        last_index = len(bundle.candles) - 1
        extended = sentinel_extended(bundle)
        candles = extended.candles
        if last_index < n:
            return wait("no donchian_break entry on the last closed candle")
        prior_high, prior_low = donchian_channel(candles, last_index, n)
        close = candles[last_index].close
        if close > prior_high:
            side = "LONG"
        elif not long_only and close < prior_low:
            side = "SHORT"
        else:
            return wait("no donchian_break entry on the last closed candle")
        params = strategy.exit["params"]
        k = params.get("k_stop") or params.get("k_trail") or 1.0
        unit = risk_unit(candles, last_index, k, params["atr_period"])
        if unit is None:
            return wait("ATR risk unit undefined on this window")
        price = bundle.candles[last_index].close
        invalidation = price - unit if side == "LONG" else price + unit
        return Signal(
            side, price, round(invalidation, 2), strategy.fraction,
            f"{self.family} {strategy.params} fired {side}",
        )


DONCHIAN = DonchianStrategy()
