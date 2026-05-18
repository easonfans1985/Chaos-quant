#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#24: 融资余额择时策略
融资余额快速上升 → 过热减仓
"""
import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy

def _to_series(obj):
    if isinstance(obj, pd.DataFrame): return obj.iloc[:, 0]
    return obj

def calculate_margin_growth(balance: pd.Series, window: int = 5) -> pd.Series:
    return balance.pct_change(window)

def is_market_overheated(growth: float, threshold: float = 0.03) -> bool:
    return growth > threshold

def is_market_panic(growth: float, threshold: float = -0.03) -> bool:
    return growth < threshold

def get_margin_position(growth: float) -> float:
    if is_market_overheated(growth): return 0.3
    if is_market_panic(growth): return 0.2
    return 0.6

class MarginTimingStrategy(BaseStrategy):
    name = "Margin Timing"
    description = "融资余额增速择时"

    def __init__(self, params=None):
        defaults = {"fast_period": 10, "slow_period": 40, "rotation_period": 5}
        if params: defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        close = _to_series(data["close"])
        fast = self.params["fast_period"]
        slow = self.params["slow_period"]
        rotation_period = self.params["rotation_period"]
        
        # 用成交量增速代替融资余额增速
        if "volume" in data:
            vol = _to_series(data["volume"])
            vol_growth = vol.pct_change(5)
            overheated = vol_growth > vol_growth.rolling(60, min_periods=1).quantile(0.9)
        else:
            overheated = pd.Series(False, index=close.index)
        
        # 快慢均线
        ma_fast = close.rolling(fast, min_periods=1).mean()
        ma_slow = close.rolling(slow, min_periods=1).mean()
        
        entries = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1)) & ~overheated
        exits = ((ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))) | overheated
        
        day_idx = pd.Series(range(len(close)), index=close.index)
        entries = entries & (day_idx % rotation_period == 0)
        
        return entries, exits
