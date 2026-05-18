#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#22: 指数估值择时策略
沪深300 PE 历史百分位决定总仓位
"""
import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy

def _to_series(obj):
    if isinstance(obj, pd.DataFrame): return obj.iloc[:, 0]
    return obj

def get_valuation_level(percentile: float) -> str:
    if percentile < 0.2: return "very_cheap"
    if percentile < 0.4: return "cheap"
    if percentile < 0.6: return "normal"
    if percentile < 0.8: return "expensive"
    return "very_expensive"

def get_target_position(percentile: float) -> float:
    levels = {"very_cheap": 1.0, "cheap": 0.8, "normal": 0.65, "expensive": 0.4, "very_expensive": 0.1}
    return levels.get(get_valuation_level(percentile), 0.5)

class MarketValuationStrategy(BaseStrategy):
    name = "Market Valuation"
    description = "PE百分位择时，低估加仓高估减仓"

    def __init__(self, params=None):
        defaults = {"lookback": 120, "rotation_period": 10}
        if params: defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        close = _to_series(data["close"])
        lookback = self.params["lookback"]
        rotation_period = self.params["rotation_period"]
        
        # 用价格百分位代替 PE 百分位
        rolling_min = close.rolling(lookback, min_periods=1).min()
        rolling_max = close.rolling(lookback, min_periods=1).max()
        price_pct = (close - rolling_min) / (rolling_max - rolling_min + 1e-10)
        
        # 低估区买入
        entries = (price_pct < 0.3) & (price_pct.shift(1) >= 0.3)
        # 高估区卖出
        exits = (price_pct > 0.8) & (price_pct.shift(1) <= 0.8)
        
        day_idx = pd.Series(range(len(close)), index=close.index)
        entries = entries & (day_idx % rotation_period == 0)
        exits = exits & (day_idx % rotation_period == 0)
        
        return entries, exits
