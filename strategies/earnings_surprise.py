#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#12: 业绩超预期策略
财报净利润同比增 > 20% + 价格确认
"""

import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy

def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj

def calculate_earnings_growth(current: pd.Series, previous: pd.Series) -> pd.Series:
    """计算盈利同比增长率"""
    return (current - previous) / previous.abs().replace(0, np.nan)

def filter_earnings_surprise(df: pd.DataFrame, min_growth: float = 0.2) -> pd.DataFrame:
    """筛选业绩超预期股票"""
    return df[df["growth"] >= min_growth].copy()


class EarningsSurpriseStrategy(BaseStrategy):
    name = "Earnings Surprise"
    description = "盈利增长>20%+价格确认做多"

    def __init__(self, params=None):
        defaults = {"lookback": 20, "hold_days": 20}
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        close = _to_series(data["close"])
        lookback = self.params["lookback"]
        hold_days = self.params["hold_days"]
        
        # 用价格动量代替盈利增长（回退模式）
        growth_proxy = close.pct_change(lookback)
        
        # 买入：动量突破20%
        entries = (growth_proxy > 0.05) & (growth_proxy.shift(1) <= 0.05)
        
        # 卖出：持有 N 天后
        exits = pd.Series(False, index=close.index)
        entry_indices = entries[entries].index
        for idx in entry_indices:
            pos = entries.index.get_loc(idx)
            sell_pos = pos + hold_days
            if sell_pos < len(exits):
                exits.iloc[sell_pos] = True
        
        return entries, exits
