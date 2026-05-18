#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#18: 多因子综合策略

综合打分体系：
  技术面(40%): 动量 + 波动率
  资金面(30%): 成交量变化
  基本面(30%): 价格位置（相对高低）
选出综合得分前 N 名，定期调仓
"""

import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy


def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def calculate_factor_scores(factors: pd.DataFrame, 
                             weights: list = None) -> pd.Series:
    """
    多因子打分
    
    Args:
        factors: DataFrame，每列一个因子
        weights: 权重列表，默认等权
    
    Returns:
        综合得分 Series
    """
    if weights is None:
        weights = [1.0 / len(factors.columns)] * len(factors.columns)
    
    # 标准化每个因子（百分位排名）
    ranked = factors.rank(pct=True)
    
    # 加权求和
    scores = pd.Series(0.0, index=factors.index)
    for col, w in zip(factors.columns, weights):
        scores += ranked[col] * w
    
    return scores


def select_top_by_score(scores: pd.Series, top_n: int = 10) -> list:
    """按得分选出前 N 个"""
    return scores.nlargest(top_n).index.tolist()


class MultiFactorStrategy(BaseStrategy):
    """多因子综合策略"""
    
    name = "Multi Factor"
    description = "技术+资金+基本面综合打分选股"

    def __init__(self, params=None):
        defaults = {
            "momentum_period": 20,
            "volatility_period": 20,
            "volume_period": 10,
            "rotation_period": 10,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        """生成多因子信号"""
        close = _to_series(data["close"])
        
        mom_period = self.params["momentum_period"]
        vol_period = self.params["volatility_period"]
        volu_period = self.params["volume_period"]
        rotation_period = self.params["rotation_period"]
        
        # 计算各因子
        momentum = close.pct_change(mom_period)
        volatility = close.pct_change().rolling(vol_period).std()
        price_position = (close - close.rolling(60, min_periods=1).min()) / \
                         (close.rolling(60, min_periods=1).max() - close.rolling(60, min_periods=1).min() + 1e-10)
        
        # 成交量因子（如有）
        if "volume" in data:
            volume = _to_series(data["volume"])
            volume_change = volume.pct_change(volu_period)
        else:
            volume_change = pd.Series(0.0, index=close.index)
        
        # 构建因子表
        factors = pd.DataFrame({
            "momentum": momentum,
            "low_vol": -volatility,  # 低波动好，取负
            "price_pos": price_position,
            "volume": volume_change,
        })
        
        # 打分
        scores = calculate_factor_scores(
            factors, 
            weights=[0.3, 0.2, 0.3, 0.2]
        )
        
        # 买入：得分从低位突破 80 百分位
        score_threshold = scores.rolling(60, min_periods=1).quantile(0.8)
        entries = (scores > score_threshold) & (scores.shift(1) <= score_threshold.shift(1))
        
        # 卖出：得分跌破 20 百分位
        sell_threshold = scores.rolling(60, min_periods=1).quantile(0.2)
        exits = (scores < sell_threshold) & (scores.shift(1) >= sell_threshold.shift(1))
        
        # 调仓日过滤
        day_idx = pd.Series(range(len(close)), index=close.index)
        is_rotation_day = day_idx % rotation_period == 0
        entries = entries & is_rotation_day
        
        return entries, exits
