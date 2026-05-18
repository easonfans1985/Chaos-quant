#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#14: 限售解禁规避策略"""
import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy
def _to_series(obj):
    if isinstance(obj, pd.DataFrame): return obj.iloc[:, 0]
    return obj
def days_to_lockup(today, lockup_date) -> int:
    return (lockup_date - today).days
def should_avoid(days_to_lockup, avoid_before=5, avoid_after=10) -> bool:
    return -avoid_after <= days_to_lockup <= avoid_before
class LockupAvoidStrategy(BaseStrategy):
    name = "Lockup Avoid"
    description = "解禁日前减仓规避"
    def __init__(self, params=None):
        defaults = {"ma_period": 20}
        if params: defaults.update(params)
        super().__init__(defaults)
    def generate_signals(self, data):
        close = _to_series(data["close"])
        ma_period = self.params["ma_period"]
        ma = close.rolling(ma_period, min_periods=1).mean()
        entries = (close > ma) & (close.shift(1) <= ma.shift(1))
        exits = (close < ma) & (close.shift(1) >= ma.shift(1))
        return entries, exits
