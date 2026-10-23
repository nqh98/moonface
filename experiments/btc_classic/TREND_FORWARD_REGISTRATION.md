# TREND Forward Paper Registration (frozen)

Pre-registers the forward paper continuation for a frozen classical BTC spec that met the forward-candidate verdict on the unopened holdout.

## Frozen spec
- key: `trend`
- kind/builder: `price` / `ma_cross`
- params: `{'fast': 20, 'slow': 100}`
- exit: `atr_trail` `{'k_trail': 2.0, 'max_bars': 120, 'atr_period': 14}`

## Validation result (unopened holdout)
- verdict: `forward_candidate`
- validate exp: `0.1737`
- sealed exp: `0.1401`
- pooled exp: `0.1574` (n=68)
- boot_lo: `-0.4041067039440139`  p_le0: `0.27028`

## Resolution rule (frozen)
CONFIRM iff forward-only pooled n >= 30 AND bootstrap lower bound > 0 AND forward-only expectancy > 0. REFUTE / early-kill on cumulative -30R.

## Honest caveat
Paper-only. Forward registration does not authorize live capital or modify any frozen registry.
