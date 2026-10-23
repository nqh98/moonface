"""Live collectors writing through data/ (G4).

deribit_chain and liquidation: the pure parse/append/manifest logic for
each, imported by tools/deribit_chain_collect.py and
tools/liquidation_collect.py's async/CLI shells -- the two live cron
paths. bybit_liquidation and bybit_positioning are deferred -- their
source is uncommitted WIP on main, absent from this branch (see the design
spec's G4 execution note, 2026-08-25)."""
