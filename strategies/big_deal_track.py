#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#9: 大单追踪策略"""
import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy
def _to_series(obj):
    if isinstance(obj, pd.DataFrame): return obj.iloc[:, 0]
    return obj
def parse_big_deal_data(df: pd.DataFrame) -> pd.DataFrame:
    return df.copy()
def select_big_buy_stocks(df: pd.DataFrame, top_n: int = 10) -> list:
    buys = df[df["direction"] == "买入"].groupby("code")["amount"].sum()
    return buys.nlargest(top_n).index.tolist()
class BigDealTrackStrategy(BaseStrategy):
    name = "Big Deal Track"
    description = "大单净买入最多的股票次日做多"
    def __init__(self, params=None):
        defaults = {"hold_days": 3, "volume_mult": 2.0}
        if params: defaults.update(params)
        super().__init__(defaults)
    def generate_signals(self, data):
        close = _to_series(data["close"])
        hold_days = self.params["hold_days"]
        volume_mult = self.params["volume_mult"]
        if "volume" in data:
            vol = _to_series(data["volume"])
            vol_ma = vol.rolling(20, min_periods=1).mean()
            spike = vol > vol_ma * volume_mult
        else:
            spike = pd.Series(False, index=close.index)
        entries = spike & ~spike.shift(1).fillna(False).infer_objects(copy=False)
        exits = pd.Series(False, index=close.index)
        for idx in entries[entries].index:
            pos = entries.index.get_loc(idx)
            sell_pos = pos + hold_days
            if sell_pos < len(exits):
                exits.iloc[sell_pos] = True
        return entries, exits
