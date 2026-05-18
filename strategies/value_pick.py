#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#11: 低估值价值策略
PE < 阈值 + ROE > 阈值，长期持有定期轮动
"""

import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy

def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj

def calculate_pe_percentile(pe_series: pd.Series, current: float) -> float:
    """计算当前 PE 在历史中的百分位"""
    return (pe_series < current).mean() * 100

def filter_value_stocks(df: pd.DataFrame, pe_max: float = 15, 
                         roe_min: float = 12) -> pd.DataFrame:
    """筛选低估值+高ROE股票"""
    return df[(df["pe"] <= pe_max) & (df["roe"] >= roe_min)].copy()


class ValuePickStrategy(BaseStrategy):
    name = "Value Pick"
    description = "低PE+高ROE价值选股"

    def __init__(self, params=None):
        defaults = {"lookback": 60, "rotation_period": 20}
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        close = _to_series(data["close"])
        lookback = self.params["lookback"]
        rotation_period = self.params["rotation_period"]
        
        # 价格低于均线 → 低估信号
        ma = close.rolling(lookback, min_periods=1).mean()
        price_ratio = close / ma
        
        # 买入：价格从低位回到均线附近
        entries = (price_ratio > 0.95) & (price_ratio.shift(1) <= 0.95)
        
        # 调仓日过滤
        day_idx = pd.Series(range(len(close)), index=close.index)
        entries = entries & (day_idx % rotation_period == 0)
        
        # 卖出：价格远超均线
        exits = (price_ratio > 1.15) & (day_idx % rotation_period == 0)
        
        return entries, exits
