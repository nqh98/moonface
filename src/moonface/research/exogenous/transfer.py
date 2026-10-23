from __future__ import annotations

from moonface.research.exogenous.evaluate import econ_verdict


def transfer_report(closes_by_asset, decision_ts_by_asset, series_by_id,
                    assets=("ETHUSDT", "SOLUSDT")) -> dict:
    out: dict[str, dict] = {}
    for a in assets:
        v = econ_verdict(closes_by_asset[a], decision_ts_by_asset[a], series_by_id)
        out[a] = {"passed": v.passed, "metrics": v.metrics, "reasons": v.reasons}
    return out


def transfer_passes(report: dict) -> bool:
    return bool(report) and all(r["passed"] for r in report.values())
