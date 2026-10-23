"""Lane 1 — Exchange Liquidation TWAP, Track A (proxy pre-screen).

In-sample, gross, no-lockbox drift screen: does a liquidation cascade (proxied
from OHLCV+OI) precede a continuation drift over 1-4h? A PASS licenses the
Track-B real-feed pre-registration; a FAIL closes Lane 1. Design:
docs/research-log/specs/2026-07-09-lane1-liquidation-twap-design.md.
"""
