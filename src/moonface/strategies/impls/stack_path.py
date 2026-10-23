from __future__ import annotations

from moonface.core.bundle import DataBundle
from moonface.core.risk import atr, risk_unit
from moonface.models.evaluate import Signal, sentinel_extended, wait
from moonface.strategies.registry import register


def segment_sse(closes: list[float], j: int, i: int) -> float:
    """Sum of Squared Errors (SSE) for a linear segment from index j to i."""
    if i == j:
        return 0.0
    val_j = closes[j]
    val_i = closes[i]
    diff = val_i - val_j
    span = i - j
    sse = 0.0
    for t in range(j, i + 1):
        line_val = val_j + diff * (t - j) / span
        sse += (closes[t] - line_val) ** 2
    return sse


@register
class StackPathStrategy:
    family = "stack_path"

    def validate(self, strategy) -> bool:
        params = strategy.params or {}
        exit_params = (strategy.exit or {}).get("params", {})
        return (
            isinstance(params.get("lookback_bars"), int)
            and params["lookback_bars"] >= 10
            and isinstance(params.get("penalty_factor"), (int, float))
            and params["penalty_factor"] > 0
            and isinstance(params.get("stack_threshold"), int)
            and params["stack_threshold"] >= 0
            and isinstance(params.get("slope_threshold"), (int, float))
            and params["slope_threshold"] >= 0
            and isinstance(params.get("long_only", False), bool)
            and isinstance(strategy.exit, dict)
            and isinstance(exit_params, dict)
            and isinstance(exit_params.get("atr_period"), int)
            and exit_params["atr_period"] > 0
            and isinstance(
                exit_params.get("k_stop", exit_params.get("k_trail", 1.0)),
                (int, float),
            )
        )

    def evaluate(self, strategy, bundle: DataBundle) -> Signal:
        candles = bundle.candles
        n_lookback = strategy.params["lookback_bars"]
        long_only = strategy.params.get("long_only", False)
        
        # Check sufficient history
        if len(candles) < n_lookback:
            return wait(f"not enough closed candles: need {n_lookback}, have {len(candles)}")
        
        last_index = len(candles) - 1
        extended = sentinel_extended(bundle)
        ext_candles = extended.candles
        
        # 1. Monotonic Stack Depth (MSD) Analysis
        # We compute the PGE (Previous Greater Element) and PLE (Previous Lesser Element)
        # stack depth for highs and lows respectively, over the lookback window.
        window_candles = ext_candles[last_index - n_lookback + 1 : last_index + 1]
        
        # High PGE depth
        pge_stack: list[float] = []
        pge_depth = 0
        for c in window_candles:
            while pge_stack and pge_stack[-1] <= c.high:
                pge_stack.pop()
            pge_stack.append(c.high)
        pge_depth = len(pge_stack)
        
        # Low PLE depth
        ple_stack: list[float] = []
        ple_depth = 0
        for c in window_candles:
            while ple_stack and ple_stack[-1] >= c.low:
                ple_stack.pop()
            ple_stack.append(c.low)
        ple_depth = len(ple_stack)
        
        stack_score = ple_depth - pge_depth
        
        # 2. Shortest Path Piecewise Linear Segmentation
        # We run a DAG shortest path algorithm on the close prices of the lookback window.
        closes = [c.close for c in window_candles]
        n_len = len(closes)
        
        exit_params = strategy.exit["params"]
        atr_period = exit_params["atr_period"]
        a_val = atr(ext_candles[: last_index + 1], atr_period)
        if a_val <= 0:
            return wait("ATR risk unit undefined on this window")
            
        penalty = strategy.params["penalty_factor"] * (a_val ** 2)
        
        # DP table: dp[i] is the shortest path cost to reach index i
        dp = [0.0] * n_len
        parent = [0] * n_len
        
        for i in range(1, n_len):
            # Base case: single segment from 0 to i
            dp[i] = segment_sse(closes, 0, i)
            parent[i] = 0
            for j in range(1, i):
                cost = dp[j] + segment_sse(closes, j, i) + penalty
                if cost < dp[i]:
                    dp[i] = cost
                    parent[i] = j
                    
        # Reconstruct last segment
        last_pivot = parent[n_len - 1]
        last_seg_len = n_len - 1 - last_pivot
        if last_seg_len <= 0:
            last_seg_len = 1
            
        slope = (closes[-1] - closes[last_pivot]) / last_seg_len
        slope_atr = slope / a_val
        
        # 3. Composite Signal Decision
        stack_threshold = strategy.params["stack_threshold"]
        slope_threshold = strategy.params["slope_threshold"]
        
        decision = "WAIT"
        if stack_score >= stack_threshold and slope_atr >= slope_threshold:
            decision = "LONG"
        elif not long_only and stack_score <= -stack_threshold and slope_atr <= -slope_threshold:
            decision = "SHORT"
            
        notes = (
            f"MSD={stack_score} (PLE={ple_depth}, PGE={pge_depth}) | "
            f"ShortestPath slope_atr={slope_atr:.4f} (last segment len={last_seg_len})"
        )
        
        if decision == "WAIT":
            return wait(f"no consensus: {notes}")
            
        k = exit_params.get("k_stop") or exit_params.get("k_trail") or 1.0
        unit = risk_unit(ext_candles, last_index, k, atr_period)
        if unit is None:
            return wait("ATR risk unit undefined on this window")
            
        price = candles[last_index].close
        invalidation = price - unit if decision == "LONG" else price + unit
        
        return Signal(
            decision=decision,
            price=price,
            invalidation=round(invalidation, 2),
            fraction=strategy.fraction,
            reason=f"{self.family} fired {decision} | {notes}",
            timeframe=strategy.asset.get("timeframe", "4h"),
            risk_notes=notes,
            tier=strategy.status,
        )


STACK_PATH = StackPathStrategy()
