# CHANNEL Forward Paper Registration (frozen)

Pre-registers the forward paper continuation for a frozen classical BTC spec that met the forward-candidate verdict on the unopened holdout.

## Frozen spec
- key: `channel`
- kind/builder: `price` / `atr_channel_break`
- params: `{'k': 1.5, 'atr_period': 14}`
- exit: `atr_trail` `{'k_trail': 2.0, 'max_bars': 120, 'atr_period': 14}`

## Validation result (unopened holdout)
- verdict: `forward_candidate`
- validate exp: `0.2012`
- sealed exp: `0.0028`
- pooled exp: `0.1036` (n=250)
- boot_lo: `-0.2127988183047113`  p_le0: `0.22733`

## Resolution rule (frozen)
CONFIRM iff forward-only pooled n >= 30 AND bootstrap lower bound > 0 AND forward-only expectancy > 0. REFUTE / early-kill on cumulative -30R.

## Honest caveat
Paper-only. Forward registration does not authorize live capital or modify any frozen registry.
