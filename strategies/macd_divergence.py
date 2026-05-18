#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略 #4: MACD 背离策略

买入条件：MACD 柱状图由负转正（金叉）+ 价格底背离
卖出条件：MACD 柱状图由正转负（死叉）+ 价格顶背离
"""

import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy


def _to_series(obj):
    """确保输入是 Series（兼容 DataFrame 单列）"""
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def calculate_macd(close, fast: int = 12, slow: int = 26, signal: int = 9):
    """计算 MACD 指标，返回 (macd_line, signal_line, histogram)"""
    close = _to_series(close)
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def detect_golden_cross(histogram) -> pd.Series:
    """检测金叉：histogram 从负变正"""
    histogram = _to_series(histogram)
    prev = histogram.shift(1)
    return (prev <= 0) & (histogram > 0)


def detect_death_cross(histogram) -> pd.Series:
    """检测死叉：histogram 从正变负"""
    histogram = _to_series(histogram)
    prev = histogram.shift(1)
    return (prev >= 0) & (histogram < 0)


def detect_bullish_divergence(prices, macd_hist, lookback: int = 20) -> pd.Series:
    """检测底背离：价格创新低但 MACD histogram 未创新低"""
    prices = _to_series(prices)
    macd_hist = _to_series(macd_hist)
    
    n = len(prices)
    divergence = pd.Series(False, index=prices.index)
    
    # 向量化：找局部极值点
    for i in range(lookback, n):
        # 跳过 NaN
        if pd.isna(prices.iloc[i]) or pd.isna(macd_hist.iloc[i]):
            continue
        
        window_p = prices.iloc[max(0, i-lookback):i+1]
        window_h = macd_hist.iloc[max(0, i-lookback):i+1]
        
        if window_h.isna().any() or window_p.isna().any():
            continue
        
        current_price = float(prices.iloc[i])
        current_hist = float(macd_hist.iloc[i])
        
        # 在回看窗口找 histogram 的极小值点（排除最近2个）
        if len(window_h) <= 4:
            continue
        prev_h = window_h.iloc[:-3]
        prev_p = window_p.iloc[:-3]
        
        min_idx = prev_h.idxmin()
        min_hist = float(macd_hist.loc[min_idx])
        min_price = float(prices.loc[min_idx])
        
        # 底背离：价格创新低 + histogram 未创新低 + histogram 在回升
        if current_price < min_price and current_hist > min_hist:
            if i >= 2:
                prev2_hist = float(macd_hist.iloc[i-2])
                if current_hist > prev2_hist:
                    divergence.iloc[i] = True
    
    return divergence


def detect_bearish_divergence(prices, macd_hist, lookback: int = 20) -> pd.Series:
    """检测顶背离：价格创新高但 MACD histogram 未创新高"""
    prices = _to_series(prices)
    macd_hist = _to_series(macd_hist)
    
    n = len(prices)
    divergence = pd.Series(False, index=prices.index)
    
    for i in range(lookback, n):
        if pd.isna(prices.iloc[i]) or pd.isna(macd_hist.iloc[i]):
            continue
        
        window_p = prices.iloc[max(0, i-lookback):i+1]
        window_h = macd_hist.iloc[max(0, i-lookback):i+1]
        
        if window_h.isna().any() or window_p.isna().any():
            continue
        
        current_price = float(prices.iloc[i])
        current_hist = float(macd_hist.iloc[i])
        
        if len(window_h) <= 4:
            continue
        prev_h = window_h.iloc[:-3]
        prev_p = window_p.iloc[:-3]
        
        max_idx = prev_h.idxmax()
        max_hist = float(macd_hist.loc[max_idx])
        max_price = float(prices.loc[max_idx])
        
        # 顶背离：价格创新高 + histogram 未创新高 + histogram 在回落
        if current_price > max_price and current_hist < max_hist:
            if i >= 2:
                prev2_hist = float(macd_hist.iloc[i-2])
                if current_hist < prev2_hist:
                    divergence.iloc[i] = True
    
    return divergence


class MACDDivergenceStrategy(BaseStrategy):
    """MACD 背离策略"""
    
    name = "MACD Divergence"
    description = "MACD金叉+底背离做多，死叉+顶背离做空"

    def __init__(self, params=None):
        defaults = {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "lookback": 20,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        """生成买卖信号：买入=金叉|底背离，卖出=死叉|顶背离"""
        close = _to_series(data["close"])
        
        fast = self.params["fast_period"]
        slow = self.params["slow_period"]
        signal = self.params["signal_period"]
        lookback = self.params["lookback"]
        
        _, _, histogram = calculate_macd(close, fast, slow, signal)
        
        golden = detect_golden_cross(histogram)
        death = detect_death_cross(histogram)
        bull_div = detect_bullish_divergence(close, histogram, lookback)
        bear_div = detect_bearish_divergence(close, histogram, lookback)
        
        entries = golden | bull_div
        exits = death | bear_div
        
        return entries, exits
