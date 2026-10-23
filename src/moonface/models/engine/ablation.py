from __future__ import annotations

from statistics import median

from moonface.core.models import Candle
from moonface.models.engine.config import EngineConfig, engine_hash
from moonface.models.engine.confluence import (VETO_LONG_ONLY,
                                               VETO_M4_EXCLUDED, VETO_NO_CT)
from moonface.models.engine.discipline import engine_entries, tier_size_fraction
from moonface.models.engine.position import (PositionState, manage_position,
                                             open_position)


def _shadow_score_summary(rows: list[dict]) -> dict:
    valid_rows: list[tuple[dict, float]] = []
    for row in rows:
        score = row.get("shadow_score")
        if score is None:
            continue
        try:
            valid_rows.append((row, float(score)))
        except (TypeError, ValueError):
            continue
    if not valid_rows:
        return {
            "count": 0,
            "min": None,
            "median": None,
            "max": None,
            "tier_a": 0,
            "tier_b": 0,
        }

    tier_a = 0
    tier_b = 0
    scores = [score for _, score in valid_rows]
    for row, score in valid_rows:
        tier = row.get("tier")
        if tier is None:
            tier = "B"
        if str(tier).upper() == "A":
            tier_a += 1
        else:
            tier_b += 1

    return {
        "count": len(scores),
        "min": min(scores),
        "median": median(scores),
        "max": max(scores),
        "tier_a": tier_a,
        "tier_b": tier_b,
    }


def veto_family(veto: str | None) -> str:
    if veto is None:
        return "none"
    text = str(veto).strip()
    if not text:
        return "none"
    if text == VETO_NO_CT:
        return "no_ct"
    if text == VETO_LONG_ONLY:
        return "long_only"
    if text == VETO_M4_EXCLUDED:
        return "m4_pullback"
    if text.startswith("macro"):
        return "macro"
    return "other"


def _skipped_row(entry: dict, reason: str) -> dict:
    score = entry.get("shadow_score")
    direction = entry.get("shadow_direction")
    tier = entry.get("tier")
    return {
        "candle_ts_ms": entry.get("candle_ts_ms"),
        "family": entry.get("family") or veto_family(entry.get("veto")),
        "shadow_score": score,
        "shadow_direction": direction,
        "tier": tier,
        "fraction": None,
        "bars_held": None,
        "resolved": False,
        "net_r": None,
        "exit_ts_ms": None,
        "reason": reason,
        "skipped": reason,
    }


def _replay_counterfactual(
    candles: list[Candle],
    cfg: EngineConfig,
    entry: dict,
    candle_index: int,
    family: str,
) -> dict:
    direction = entry.get("shadow_direction")
    shadow_score = entry.get("shadow_score")
    if direction in (None, 0) or shadow_score is None:
        return _skipped_row(entry, "missing shadow fields")
    if candle_index < cfg.atr_period + 1:
        warmup_entry = dict(entry, candle_ts_ms=candles[candle_index].timestamp_ms)
        return _skipped_row(warmup_entry, "insufficient ATR warmup before veto bar")

    try:
        direction = int(direction)
        score = float(shadow_score)
    except (TypeError, ValueError):
        return _skipped_row(entry, "invalid shadow fields")
    if direction not in (-1, 1):
        return _skipped_row(entry, "invalid shadow fields")
    tier = entry.get("tier") or "B"
    regime_vol = str(entry.get("regime_vol") or "normal")
    profile = "CT" if family == "no_ct" else "WT"
    fraction = tier_size_fraction(tier, "WT", regime_vol, cfg)
    pos = open_position(
        candles[: candle_index + 1],
        cfg,
        direction,
        0.0,
        fraction,
        profile,
    )

    bars_held = pos.bars_held
    for future in range(candle_index + 1, len(candles)):
        step = manage_position([candles[future]], cfg, pos, 0, 0.0)
        if step.action == "EXIT":
            return {
                "candle_ts_ms": candles[candle_index].timestamp_ms,
                "family": family,
                "shadow_score": score,
                "shadow_direction": direction,
                "tier": tier,
                "fraction": fraction,
                "bars_held": int(step.bars_held or 0),
                "resolved": True,
                "net_r": round(float(step.realized_r or 0.0), 4),
                "exit_ts_ms": candles[future].timestamp_ms,
                "reason": step.reason,
                "skipped": None,
            }

        pos = PositionState(
            direction=step.direction,
            entry_price=float(step.entry_price or pos.entry_price),
            stop=float(step.stop or pos.stop),
            extreme=float(step.extreme or pos.extreme),
            atr_at_entry=float(step.atr_at_entry or pos.atr_at_entry),
            fraction=float(step.fraction or pos.fraction),
            bars_held=int(step.bars_held or bars_held),
            profile=step.profile,
            target=step.target,
        )
        bars_held = pos.bars_held

    return {
        "candle_ts_ms": candles[candle_index].timestamp_ms,
        "family": family,
        "shadow_score": score,
        "shadow_direction": direction,
        "tier": tier,
        "fraction": fraction,
        "bars_held": bars_held,
        "resolved": False,
        "net_r": None,
        "exit_ts_ms": None,
        "reason": "unresolved at end of series",
        "skipped": None,
    }


def gate_ablation(entries: list[dict], candles: list[Candle],
                  cfg: EngineConfig) -> dict:
    version = engine_hash(cfg)
    mine = [e for e in engine_entries(entries, version) if e.get("veto")]

    score_rows = [e for e in mine if e.get("shadow_score") is not None]
    rows: list[dict] = []
    families: dict[str, dict[str, float | int]] = {}
    family_entries: dict[str, list[dict]] = {}
    replayed = 0
    resolved = 0
    realized_total = 0.0

    candle_index = {c.timestamp_ms: idx for idx, c in enumerate(candles)}
    for entry in mine:
        family = veto_family(entry.get("veto"))
        entry = dict(entry, family=family)
        family_entries.setdefault(family, []).append(entry)
        agg = families.setdefault(
            family,
            {
                "n_vetoed": 0,
                "resolved": 0,
                "net_r_if_taken": 0.0,
            },
        )
        agg["n_vetoed"] = int(agg["n_vetoed"]) + 1

        score = entry.get("shadow_score")
        ts_ms = entry.get("candle_ts_ms")
        if score is None:
            row = _skipped_row(entry, "missing shadow fields")
            rows.append(row)
            continue
        if ts_ms is None:
            row = _skipped_row(entry, "missing candle timestamp")
            rows.append(row)
            continue
        try:
            idx = candle_index.get(int(ts_ms))
        except (TypeError, ValueError):
            row = _skipped_row(entry, "invalid candle timestamp")
            rows.append(row)
            continue
        if idx is None:
            row = _skipped_row(entry, "veto bar not in candle series")
            rows.append(row)
            continue
        row = _replay_counterfactual(candles, cfg, entry, idx, family)
        rows.append(row)
        if row.get("skipped") is None:
            replayed += 1
        if row["resolved"]:
            resolved += 1
            realized_total += float(row["net_r"] or 0.0)
            agg["resolved"] = int(agg["resolved"]) + 1
            agg["net_r_if_taken"] = float(agg["net_r_if_taken"]) + float(row["net_r"] or 0.0)

    return {
        "engine_hash": version,
        "n_vetoed": len(mine),
        "shadow_scores": _shadow_score_summary(score_rows),
        "counterfactual": {
            "replayed": replayed,
            "resolved": resolved,
            "net_r_if_taken": round(realized_total, 4),
            "gate_saved_r": round(-realized_total, 4),
            "rows": rows,
        },
        "families": {
            fam: {
                "n_vetoed": agg["n_vetoed"],
                "resolved": agg["resolved"],
                "net_r_if_taken": round(float(agg["net_r_if_taken"]), 4),
                "veto_saved_r": round(-float(agg["net_r_if_taken"]), 4),
                "shadow_scores": _shadow_score_summary([
                    e for e in family_entries[fam]
                    if e.get("shadow_score") is not None
                ]),
            }
            for fam, agg in sorted(families.items())
        },
        "assumptions": [
            "no_ct counterfactuals replay the CT exit discipline without a "
            "sweep wick (entry-anchored stop); other families replay WT",
            "veto rows without candle_ts_ms or shadow_score are skipped",
            "unresolved replays contribute 0R",
        ],
        "note": (
            "Pure reporter only: it replays vetoed setups counterfactually and "
            "does not mutate state or apply any gating."
        ),
    }
