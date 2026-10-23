"""Multi-timeframe confluence L/S BTC signal lane (15m -> 1d).

A higher timeframe (HTF) sets the directional regime/bias; a lower timeframe
(LTF) fires the entry trigger. A signal is emitted only when the LTF trigger
agrees with the HTF bias, so trades always run with the slow-timeframe trend.
The explicit lever is drawdown reduction: the program's structural wall has
been path drawdown, and trading only with the HTF trend is the standard way to
cut the adverse excursions that killed single-timeframe breakouts.

The base series is fetched once at the finest timeframe (15m); every HTF is a
closed-bar resample of that base, so there is a single source of truth and no
cross-series alignment ambiguity. Point-in-time alignment (align_higher) makes
the HTF bias use only HTF bars closed by the time the LTF bar closes -- no
look-ahead. Scoring reuses the frozen 3-stage gate (gross Z -> DSR -> econ
walk-forward). Pure modules; network IO lives in tools/."""
