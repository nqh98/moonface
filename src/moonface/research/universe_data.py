"""Moved to moonface.data.universe at G4 (repo restructure design spec,
phase G4). Re-exported here for the ~95 existing importers across
research/, signal/, and tools/ that this phase deliberately does not touch
-- each is a lane G6 converts individually. New code should import
moonface.data.universe directly."""
from moonface.data.universe import (  # noqa: F401
    DailyRow, fetch_daily_klines, fetch_funding_rates, fetch_perp_candles,
    list_um_perp_symbols, load_daily_cache, parse_klines_payload,
    parse_symbol_listing, save_daily_cache,
)
from moonface.data.universe import _INTERVAL_MS  # noqa: F401 -- one test imports this private name
