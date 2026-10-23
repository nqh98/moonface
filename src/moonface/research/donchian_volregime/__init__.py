"""Donchian × volatility-regime permission gate (pre-registration 2026-07-02).

The byte-frozen BTC 4h Donchian 40/20 engine is unchanged; the only new degree of
freedom is a strict-subset regime gate that keeps a base trade iff its entry bar is
classified 'High-Vol + Expansion / Trending', else WAIT. See
docs/research-log/specs/2026-07-02-donchian-volregime-design.md.
"""
