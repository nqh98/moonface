"""Paper-emission adapter for an accepted playbook config. Resamples the 1h
bundle to 2h/4h internally and projects the engine's 5-state output onto the
Signal contract: LONG_SIGNAL -> LONG/paper, everything else -> WAIT."""
from __future__ import annotations

from moonface.core.bundle import DataBundle
from moonface.core.models import Candle
from moonface.research.playbook.config import LONG_SIGNAL
from moonface.research.playbook.engine import evaluate_bar
from moonface.research.playbook.families import all_playbook_configs
from moonface.research.playbook.mtf import MTFView
from moonface.models.evaluate import Signal, wait
from moonface.strategies.registry import register


def _resample(h1: list[Candle], factor: int) -> list[Candle]:
    out: list[Candle] = []
    for k in range(0, len(h1), factor):
        ch = h1[k:k + factor]
        out.append(Candle(ch[0].timestamp_ms, ch[0].open,
                          max(c.high for c in ch), min(c.low for c in ch),
                          ch[-1].close, sum(c.volume for c in ch)))
    return out


def _config_for(label: str):
    for c in all_playbook_configs():
        if c.label == label:
            return c
    return None


@register
class PlaybookStrategy:
    family = "playbook"

    def validate(self, strategy) -> bool:
        label = (strategy.params or {}).get("label", "")
        return _config_for(label) is not None

    def evaluate(self, strategy, bundle: DataBundle) -> Signal:
        label = (strategy.params or {}).get("label", "")
        cfg = _config_for(label)
        if cfg is None:
            return wait(f"unknown playbook config {label!r}")
        h1 = bundle.candles
        if len(h1) < cfg.params.ma_slow + cfg.params.slope_n:
            return wait("insufficient history for playbook regime")
        view = MTFView.build(h1, _resample(h1, 2), _resample(h1, 4))
        st = evaluate_bar(view, len(h1) - 1, cfg.params, cfg.exit_name, cfg.exit_params)
        notes = f"regime={st.regime} setup={st.setup} {st.reason}"
        if st.status == LONG_SIGNAL:
            return Signal(decision="LONG", price=st.entry, invalidation=st.stop,
                          fraction=None, reason=st.reason, confidence=st.confidence,
                          timeframe="1h", risk_notes=notes, tier="paper")
        return Signal(decision="WAIT", price=None, invalidation=None, fraction=None,
                      reason=st.reason, confidence=st.confidence, timeframe="1h",
                      risk_notes=notes, tier="paper")
