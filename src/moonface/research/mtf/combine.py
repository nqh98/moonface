"""MTF combiner: resample base LTF -> HTF, align point-in-time, bias-filter.

The base series is the finest timeframe (15m). Each HTF is a closed-bar
resample of the base (resample_ohlc). For each base bar i the HTF bias is read
from HTF bars closed by base[i]'s close (align_higher), so no future HTF bar
informs the decision. An LTF trigger (i, side) survives only when side agrees
with the HTF bias at i."""
from __future__ import annotations

from collections.abc import Callable

from moonface.core.models import Candle
from moonface.research.pathsig.data import resample_ohlc
from moonface.research.playbook.mtf import align_higher

# Every timeframe this lane can speak, in milliseconds. 15m is the base; the
# rest are derived by resampling, so they share one source of truth.
TF_MS = {"15m": 900_000, "30m": 1_800_000, "1h": 3_600_000,
         "2h": 7_200_000, "4h": 14_400_000, "1d": 86_400_000}

Entry = tuple[int, str]              # (base-bar index, "LONG" | "SHORT")
BiasFn = Callable[[list[Candle], dict], list[int]]      # -> +1/-1/0 per HTF bar
TriggerFn = Callable[[list[Candle], dict], list[Entry]]  # LTF entries


def derive_htf(base: list[Candle], base_tf: str, htf: str) -> list[Candle]:
    """Closed-bar resample of the base series to the higher timeframe. htf must
    be a whole multiple of base_tf and not finer than it."""
    if TF_MS[htf] < TF_MS[base_tf] or TF_MS[htf] % TF_MS[base_tf] != 0:
        raise ValueError(f"{htf} is not a whole multiple of base {base_tf}")
    return resample_ohlc(base, TF_MS[htf], TF_MS[base_tf])


def htf_bias_series(base: list[Candle], base_tf: str, htf: str,
                    bias_fn: BiasFn, bias_params: dict) -> list[int]:
    """Per-base-bar HTF bias (+1/-1/0). base[i] sees only HTF bars whose close
    is <= base[i]'s close, so the bias is strictly point-in-time."""
    if htf == base_tf:
        return bias_fn(base, bias_params)
    htf_candles = derive_htf(base, base_tf, htf)
    bias = bias_fn(htf_candles, bias_params)
    k = align_higher(base, htf_candles, TF_MS[htf], TF_MS[base_tf])
    return [bias[kk - 1] if kk >= 1 else 0 for kk in k]


def mtf_entries(base: list[Candle], base_tf: str, htf: str,
                bias_fn: BiasFn, bias_params: dict,
                trigger_fn: TriggerFn, trigger_params: dict) -> list[Entry]:
    """LTF triggers kept only where the side matches the HTF bias at that bar."""
    bias = htf_bias_series(base, base_tf, htf, bias_fn, bias_params)
    out: list[Entry] = []
    for i, side in trigger_fn(base, trigger_params):
        want = 1 if side == "LONG" else -1
        if 0 <= i < len(bias) and bias[i] == want:
            out.append((i, side))
    return out
