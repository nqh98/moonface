# Ensemble Forward Paper Registration (frozen, Lane 3)

Net-vote ensemble of the forward-candidate survivors from Lanes 1-2.

## Frozen members
- `breadth_thrust` builder=`breadth_thrust` params=`{'base_period': 50, 'high_band': 0.6, 'low_band': 0.4, 'window': 6}`
- `net_new_highs` builder=`net_new_highs` params=`{'long_thr': 0.3, 'n': 20, 'short_thr': -0.3}`
- `breadth_momentum` builder=`breadth_momentum` params=`{'base_period': 50, 'n': 10, 'thr': 0.1}`

## Combination rule
Daily net vote: each member emits +1/-1/0; ensemble state = sign(sum), ties -> FLAT. Mapped to BTC via non-overlapping transition entries (h=48), frozen atr_trail exit.

## t0 (forward start) = 1782300000000  (max member sealed-window end)

## Resolution rule
CONFIRM iff forward-only pooled n>=30 AND bootstrap CI lower bound > 0 AND forward-only exp > 0; REFUTE / early-kill at cumulative -30R.

Paper-only. Diagnostic in-sample numbers are selection-biased and cannot promote anything; only this forward record carries weight.
