#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#16: ETF折溢价套利策略"""
import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy
def _to_series(obj):
    if isinstance(obj, pd.DataFrame): return obj.iloc[:, 0]
    return obj
def calculate_premium(price: float, nav: float) -> float:
    if nav == 0: return 0.0
    return (price - nav) / nav
def generate_premium_signal(premium: float, threshold: float = 0.005) -> str:
    if premium > threshold: return "sell_etf"
    if premium < -threshold: return "buy_etf"
    return "hold"
class ETFPremiumStrategy(BaseStrategy):
    name = "ETF Premium"
    description = "ETF价格vs净值偏差套利"
    def __init__(self, params=None):
        defaults = {"lookback": 20, "threshold": 0.01}
        if params: defaults.update(params)
        super().__init__(defaults)
    def generate_signals(self, data):
        close = _to_series(data["close"])
        lookback = self.params["lookback"]
        threshold = self.params["threshold"]
        # 用MA代替净值
        nav = close.rolling(lookback, min_periods=1).mean()
        premium = (close - nav) / nav
        # 折价买入
        entries = (premium < -threshold) & (premium.shift(1) >= -threshold)
        # 溢价卖出
        exits = (premium > threshold) & (premium.shift(1) <= threshold)
        return entries, exits
