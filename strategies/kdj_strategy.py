#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略 #5: KDJ 超买超卖策略

买入条件：K 线上穿 D 线 + J < 超卖阈值（默认20）
卖出条件：K 线下穿 D 线 + J > 超买阈值（默认80）

参数：
  n: RSV 周期（默认9）
  m1: K 平滑周期（默认3）
  m2: D 平滑周期（默认3）
  oversold: 超卖阈值（默认20）
  overbought: 超买阈值（默认80）
"""

import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy


def _to_series(obj):
    """兼容 DataFrame 单列"""
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def calculate_kdj(high, low, close, n: int = 9, m1: int = 3, m2: int = 3):
    """
    计算 KDJ 指标
    
    Args:
        high, low, close: 价格序列
        n: RSV 计算周期
        m1: K 线 EMA 周期
        m2: D 线 EMA 周期
    
    Returns:
        (K, D, J) 三个 Series
    """
    high = _to_series(high)
    low = _to_series(low)
    close = _to_series(close)
    
    # RSV = (Close - LowN) / (HighN - LowN) * 100
    low_n = low.rolling(window=n, min_periods=1).min()
    high_n = high.rolling(window=n, min_periods=1).max()
    
    rsv = (close - low_n) / (high_n - low_n) * 100
    rsv = rsv.fillna(50)  # 避免除以0
    
    # K = SMA(RSV, m1)，使用 EMA 递推：K = (2/3)*prev_K + (1/3)*RSV
    k = rsv.ewm(com=m1 - 1, adjust=False).mean()
    
    # D = SMA(K, m2)
    d = k.ewm(com=m2 - 1, adjust=False).mean()
    
    # J = 3K - 2D
    j = 3 * k - 2 * d
    
    return k, d, j


def detect_kd_golden_cross(k, d):
    """K 上穿 D"""
    k = _to_series(k)
    d = _to_series(d)
    prev_diff = k.shift(1) - d.shift(1)
    curr_diff = k - d
    return (prev_diff <= 0) & (curr_diff > 0)


def detect_kd_death_cross(k, d):
    """K 下穿 D"""
    k = _to_series(k)
    d = _to_series(d)
    prev_diff = k.shift(1) - d.shift(1)
    curr_diff = k - d
    return (prev_diff >= 0) & (curr_diff < 0)


class KDJStrategy(BaseStrategy):
    """KDJ 超买超卖策略"""
    
    name = "KDJ"
    description = "K上穿D+J超卖买入，K下穿D+J超买卖出"

    def __init__(self, params=None):
        defaults = {
            "n": 9,
            "m1": 3,
            "m2": 3,
            "oversold": 20,
            "overbought": 80,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        """
        买入：K 上穿 D + J < oversold
        卖出：K 下穿 D + J > overbought
        """
        close = _to_series(data["close"])
        high = _to_series(data.get("high", close))
        low = _to_series(data.get("low", close))
        
        n = self.params["n"]
        m1 = self.params["m1"]
        m2 = self.params["m2"]
        oversold = self.params["oversold"]
        overbought = self.params["overbought"]
        
        k, d, j = calculate_kdj(high, low, close, n, m1, m2)
        
        golden = detect_kd_golden_cross(k, d)
        death = detect_kd_death_cross(k, d)
        
        # 买入：金叉 + J 在超卖区
        entries = golden & (j < oversold)
        
        # 卖出：死叉 + J 在超买区
        exits = death & (j > overbought)
        
        return entries, exits
