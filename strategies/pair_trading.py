#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#15: 配对交易策略

两只高相关股票价差偏离均值时做回归交易
价差 > 2σ → 做空A+做多B
价差 < -2σ → 做多A+做空B
价差回归均值时平仓
"""

import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy


def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def calculate_spread(price_a, price_b, period: int = 60):
    """计算价差和对冲比率（使用线性回归）"""
    price_a = _to_series(price_a)
    price_b = _to_series(price_b)
    
    # 用最近 period 的数据做回归
    a = price_a.iloc[-period:]
    b = price_b.iloc[-period:]
    
    # 简单 OLS: price_a = ratio * price_b + intercept
    ratio = np.dot(a - a.mean(), b - b.mean()) / np.dot(b - b.mean(), b - b.mean())
    if ratio <= 0:
        ratio = 1.0
    
    spread = price_a - ratio * price_b
    return spread, ratio


def calculate_zscore(spread: pd.Series, window: int = 20) -> pd.Series:
    """计算 Z-Score"""
    mean = spread.rolling(window=window, min_periods=1).mean()
    std = spread.rolling(window=window, min_periods=1).std()
    std = std.replace(0, np.nan)
    return (spread - mean) / std


def generate_pair_signals(zscore: pd.Series, entry_threshold: float = 2.0,
                           exit_threshold: float = 0.5):
    """生成配对交易信号"""
    # 做多价差：Z < -entry_threshold
    entries_long = zscore < -entry_threshold
    
    # 做空价差：Z > entry_threshold
    entries_short = zscore > entry_threshold
    
    # 平仓：Z 回归到 exit_threshold 以内
    exits = zscore.abs() < exit_threshold
    
    return entries_long, entries_short, exits


def test_cointegration(price_a, price_b):
    """
    简化版协整检验（相关系数 + 价差平稳性）
    返回 (score, pvalue)
    """
    price_a = _to_series(price_a)
    price_b = _to_series(price_b)
    
    corr = price_a.corr(price_b)
    
    # 简单价差
    spread = price_a - price_b * (price_a.mean() / price_b.mean())
    
    # ADF 近似：价差的自相关系数
    if len(spread) > 10:
        autocorr = spread.autocorr()
        # 自相关越低 → 越平稳 → pvalue 越小
        pvalue = max(0, 1 - abs(corr) * (1 - abs(autocorr)))
    else:
        pvalue = 1.0
    
    return corr, pvalue


class PairTradingStrategy(BaseStrategy):
    """配对交易策略（单只股票回退模式）"""
    
    name = "Pair Trading"
    description = "价差偏离2σ做均值回归"

    def __init__(self, params=None):
        defaults = {
            "lookback": 60,
            "zscore_window": 20,
            "entry_threshold": 2.0,
            "exit_threshold": 0.5,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        """
        单只股票回退：用价格与均线的偏离代替价差
        """
        close = _to_series(data["close"])
        
        lookback = self.params["lookback"]
        zscore_window = self.params["zscore_window"]
        entry_threshold = self.params["entry_threshold"]
        exit_threshold = self.params["exit_threshold"]
        
        # 价差 = 价格 - 均线
        ma = close.rolling(window=lookback, min_periods=1).mean()
        spread = close - ma
        
        # Z-Score
        zscore = calculate_zscore(spread, zscore_window)
        
        # 信号
        entries_long, entries_short, exits = generate_pair_signals(
            zscore, entry_threshold, exit_threshold
        )
        
        # 单向回测：entries_long 当买入，exits 当卖出
        return entries_long, exits
