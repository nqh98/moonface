# src/moonface/signal/engine/discipline.py
from __future__ import annotations

from moonface.core.metrics import summarize_r
from moonface.models.engine.config import EngineConfig


def engine_entries(entries: list[dict], version: str) -> list[dict]:
    return [e for e in entries if e.get("strategy_version") == version
            and e.get("status") == "engine"]


def closed_trades(entries: list[dict],
                  version: str) -> list[tuple[float, float, float]]:
    out: list[tuple[float, float, float]] = []
    for e in engine_entries(entries, version):
        if e.get("action") == "EXIT" and e.get("realized_r") is not None:
            out.append((float(e["realized_r"]), float(e.get("atr_frac") or 0.0),
                        float(e.get("fraction") or 0.0)))
    return out


def realized_drawdown_r(entries: list[dict], version: str) -> float:
    """All-time peak-to-trough R drawdown (monotonically non-decreasing)."""
    rs = [r for r, _, _ in closed_trades(entries, version)]
    return summarize_r(rs).max_drawdown_r


def _closed_trade_rs_ts(entries: list[dict],
                        version: str) -> list[tuple[int, float]]:
    """(exit_ts_ms, realized_r) for closed trades, in journal order."""
    out: list[tuple[int, float]] = []
    for e in engine_entries(entries, version):
        if e.get("action") == "EXIT" and e.get("realized_r") is not None:
            out.append((int(e.get("ts_ms") or 0), float(e["realized_r"])))
    return out


def _latest_ts(entries: list[dict], version: str) -> int:
    return max((int(e.get("ts_ms") or 0)
                for e in engine_entries(entries, version)), default=0)


def windowed_drawdown_r(entries: list[dict], cfg: EngineConfig, version: str,
                        now_ms: int) -> float:
    """Peak-to-trough R drawdown over only the closed trades whose exit falls in
    the trailing drawdown_window_days ending at now_ms."""
    horizon = now_ms - int(cfg.drawdown_window_days * 86_400_000)
    rs = [r for ts, r in _closed_trade_rs_ts(entries, version) if ts >= horizon]
    return summarize_r(rs).max_drawdown_r


def hard_breaker_tripped(entries: list[dict], cfg: EngineConfig,
                         version: str) -> bool:
    """All-time catastrophe latch: never un-trips, needs a human reset."""
    return realized_drawdown_r(entries, version) <= -cfg.hard_drawdown_budget_r


def is_paused(entries: list[dict], cfg: EngineConfig, version: str,
              now_ms: int | None = None) -> bool:
    """Layered kill-switch. Pauses on EITHER the hard all-time catastrophe
    breaker (latched) OR the routine trailing-window drawdown (auto-resumes as
    the bad cluster ages out). now_ms defaults to the latest journal entry."""
    if hard_breaker_tripped(entries, cfg, version):
        return True
    if cfg.drawdown_window_days <= 0:                 # window off -> legacy latch
        return realized_drawdown_r(entries, version) <= -cfg.drawdown_budget_r
    if now_ms is None:
        now_ms = _latest_ts(entries, version)
    return windowed_drawdown_r(entries, cfg, version,
                               now_ms) <= -cfg.drawdown_budget_r


def bars_since_last_exit(entries: list[dict], version: str) -> int | None:
    mine = engine_entries(entries, version)
    last_exit = None
    for idx, e in enumerate(mine):
        if e.get("action") == "EXIT":
            last_exit = idx
    if last_exit is None:
        return None
    return len(mine) - 1 - last_exit


def last_trade_was_loss(entries: list[dict], version: str) -> bool:
    ct = closed_trades(entries, version)
    return bool(ct) and ct[-1][0] < 0


def in_cooldown(entries: list[dict], cfg: EngineConfig, version: str) -> bool:
    if not last_trade_was_loss(entries, version):
        return False
    since = bars_since_last_exit(entries, version)
    return since is not None and since < cfg.cooldown_bars


# Frozen tier x profile sizing lookup — NOT in EngineConfig (anti-overfitting).
# v2.1 flattens the ladder to a single surviving WT/B cell; all other cells
# are dead and remain at zero. High-vol still halves the surviving cell.
_TIER_PROFILE_FRACTION: dict[tuple[str, str], float] = {
    ("B", "WT"): 0.005,
}


def tier_size_fraction(tier: str, profile: str, vol_state: str,
                       cfg: EngineConfig) -> float:
    frac = _TIER_PROFILE_FRACTION.get((tier, profile), 0.0)
    if vol_state == "high":
        frac = frac / 2
    return round(min(cfg.max_fraction, frac), 6)
