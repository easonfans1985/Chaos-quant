#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略 #6: ATR 通道突破策略

买入条件：收盘价突破 ATR 上轨（close > MA + mult * ATR）
卖出条件：收盘价跌破 ATR 下轨（close < MA - mult * ATR）

参数：
  atr_period: ATR 周期（默认14）
  ma_period: 均线周期（默认20）
  channel_mult: 通道倍数（默认2.0）
"""

import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy


def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def calculate_atr(high, low, close, period: int = 14):
    """
    计算 ATR（Average True Range）
    
    TR = max(H-L, |H-prevC|, |L-prevC|)
    ATR = EMA(TR, period)
    """
    high = _to_series(high)
    low = _to_series(low)
    close = _to_series(close)
    
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=period, adjust=False).mean()
    
    return atr


class ATRBreakoutStrategy(BaseStrategy):
    """ATR 通道突破策略"""
    
    name = "ATR Breakout"
    description = "价格突破ATR上轨做多，跌破下轨做空"

    def __init__(self, params=None):
        defaults = {
            "atr_period": 14,
            "ma_period": 20,
            "channel_mult": 2.0,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        """
        买入：close > MA + mult * ATR
        卖出：close < MA - mult * ATR
        """
        close = _to_series(data["close"])
        high = _to_series(data.get("high", close))
        low = _to_series(data.get("low", close))
        
        atr_period = self.params["atr_period"]
        ma_period = self.params["ma_period"]
        mult = self.params["channel_mult"]
        
        # 计算指标
        atr = calculate_atr(high, low, close, atr_period)
        ma = close.rolling(window=ma_period).mean()
        
        upper_band = ma + mult * atr
        lower_band = ma - mult * atr
        
        # 突破信号
        prev_close = close.shift(1)
        prev_upper = upper_band.shift(1)
        prev_lower = lower_band.shift(1)
        
        # 买入：收盘价从下方突破上轨
        entries = (close > upper_band) & (prev_close <= prev_upper)
        
        # 卖出：收盘价从上方跌破下轨
        exits = (close < lower_band) & (prev_close >= prev_lower)
        
        return entries, exits
