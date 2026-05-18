#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#23: 北向资金择时策略
北向连续净流入 → 牛市信号，提升仓位
"""
import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy

def _to_series(obj):
    if isinstance(obj, pd.DataFrame): return obj.iloc[:, 0]
    return obj

def detect_flow_regime(flow: pd.Series, window: int = 5) -> str:
    recent = flow.tail(window)
    positive_ratio = (recent > 0).mean()
    if positive_ratio >= 0.8: return "bullish"
    if positive_ratio <= 0.2: return "bearish"
    return "neutral"

def get_northbound_position(regime: str) -> float:
    return {"bullish": 0.8, "bearish": 0.3, "neutral": 0.5}.get(regime, 0.5)

class NorthboundTimingStrategy(BaseStrategy):
    name = "Northbound Timing"
    description = "北向连续净流入→加仓"

    def __init__(self, params=None):
        defaults = {"ma_fast": 10, "ma_slow": 30, "rotation_period": 5}
        if params: defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        close = _to_series(data["close"])
        ma_fast = close.rolling(self.params["ma_fast"], min_periods=1).mean()
        ma_slow = close.rolling(self.params["ma_slow"], min_periods=1).mean()
        rotation_period = self.params["rotation_period"]
        
        entries = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))
        exits = (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))
        
        day_idx = pd.Series(range(len(close)), index=close.index)
        entries = entries & (day_idx % rotation_period == 0)
        exits = exits & (day_idx % rotation_period == 0)
        
        return entries, exits
