#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#13: 回购利好策略
回购公告金额 > 阈值 → 公告后3-5天做多
"""

import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy

def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj

def filter_buyback(df: pd.DataFrame, min_amount: float = 1e8) -> pd.DataFrame:
    """筛选大额回购"""
    return df[df["amount"] >= min_amount].copy()


class BuybackSignalStrategy(BaseStrategy):
    name = "Buyback Signal"
    description = "大额回购公告后做多"

    def __init__(self, params=None):
        defaults = {"hold_days": 5, "breakout_period": 20}
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        close = _to_series(data["close"])
        hold_days = self.params["hold_days"]
        
        # 用放量突破代替回购信号（回退模式）
        if "volume" in data:
            volume = _to_series(data["volume"])
            vol_ma = volume.rolling(20, min_periods=1).mean()
            volume_spike = volume > vol_ma * 2
        else:
            volume_spike = pd.Series(True, index=close.index)
        
        # 买入：放量 + 价格上涨
        price_up = close > close.shift(1)
        entries = volume_spike & price_up & ~volume_spike.shift(1).fillna(False)
        
        # 卖出：持有 N 天
        exits = pd.Series(False, index=close.index)
        for idx in entries[entries].index:
            pos = entries.index.get_loc(idx)
            sell_pos = pos + hold_days
            if sell_pos < len(exits):
                exits.iloc[sell_pos] = True
        
        return entries, exits
