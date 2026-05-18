#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#17: 动量因子策略

过去 N 日涨幅排名前 10% 的股票做多
定期调仓（默认每周）
"""

import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy


def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def calculate_momentum(prices: pd.Series, period: int = 20) -> pd.Series:
    """计算动量（N日收益率）"""
    return prices.pct_change(period)


def rank_by_momentum(price_df: pd.DataFrame, period: int = 20) -> pd.Series:
    """按动量排名（降序）"""
    momentum = price_df.iloc[-1] / price_df.iloc[-period-1] - 1
    return momentum.sort_values(ascending=False)


def select_top_momentum(price_df: pd.DataFrame, top_n: int = 10,
                         period: int = 20) -> list:
    """选出动量最高的前N只"""
    ranked = rank_by_momentum(price_df, period)
    return ranked.head(top_n).index.tolist()


class MomentumFactorStrategy(BaseStrategy):
    """动量因子策略"""
    
    name = "Momentum Factor"
    description = "N日涨幅前10%做多，每周调仓"

    def __init__(self, params=None):
        defaults = {
            "momentum_period": 20,
            "rotation_period": 5,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        """生成动量信号"""
        close = _to_series(data["close"])
        
        period = self.params["momentum_period"]
        rotation_period = self.params["rotation_period"]
        
        # 计算动量
        momentum = calculate_momentum(close, period)
        
        # 买入：动量从负转正（趋势启动）
        prev_mom = momentum.shift(1)
        entries = (momentum > 0) & (prev_mom <= 0)
        
        # 仅在调仓日执行
        day_idx = pd.Series(range(len(close)), index=close.index)
        is_rotation_day = day_idx % rotation_period == 0
        entries = entries & is_rotation_day
        
        # 卖出：动量转负 + 调仓日
        exits = (momentum < 0) & (prev_mom >= 0) & is_rotation_day
        
        return entries, exits
