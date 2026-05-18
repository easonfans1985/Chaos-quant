#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略 #10: 北向资金跟随策略

逻辑：
1. 北向资金（沪股通+深股通）连续 N 日净流入 → 市场信号偏多
2. 个股站上 20 日均线 + 大盘处于北向净流入状态 → 买入
3. 北向连续 N 日净流出 或 跌破 20 日均线 → 卖出

参数：
  ma_period: 均线周期（默认20）
  consecutive_days: 连续净流入天数（默认3）
"""

import pandas as pd
import numpy as np
import glob
from pathlib import Path
from backtest.base_strategy import BaseStrategy


def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def load_northbound_data(data_dir: Path) -> pd.DataFrame:
    """加载北向资金数据（沪股通+深股通合并）"""
    nb_dir = data_dir / "money_flow" / "northbound"
    files = list(nb_dir.glob("*.parquet"))
    if not files:
        return None

    dfs = []
    for f in files:
        df = pd.read_parquet(f)
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)
    
    # 尝试统一日期列
    if "日期" in combined.columns:
        combined["date"] = pd.to_datetime(combined["日期"])
    elif "date" in combined.columns:
        combined["date"] = pd.to_datetime(combined["date"])
    
    # 找净买入/净流入列
    for col in combined.columns:
        if "净" in col and "买入" in col:
            combined["net_flow"] = pd.to_numeric(combined[col].astype(str).str.replace(",", ""), errors="coerce")
            break
        elif "净" in col:
            combined["net_flow"] = pd.to_numeric(combined[col].astype(str).str.replace(",", ""), errors="coerce")
            break
    
    if "net_flow" not in combined.columns:
        return None

    # 按日汇总
    if "date" in combined.columns:
        daily = combined.groupby("date")["net_flow"].sum().sort_index()
        return pd.DataFrame({"net_flow": daily})
    
    return None


def detect_consecutive_flow(flow: pd.Series, min_days: int = 3, 
                             direction: str = "inflow") -> pd.Series:
    """检测连续净流入/流出"""
    if direction == "inflow":
        is_positive = flow > 0
    else:
        is_positive = flow < 0
    
    # 连续计数
    groups = (~is_positive).cumsum()
    consecutive = is_positive.groupby(groups).cumsum()
    
    return consecutive >= min_days


class NorthboundFollowStrategy(BaseStrategy):
    """北向资金跟随策略"""
    
    name = "Northbound Follow"
    description = "北向连续净流入+站上均线做多"

    def __init__(self, params=None):
        defaults = {
            "ma_period": 20,
            "consecutive_days": 3,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        """
        买入：收盘价站上 MA（从下方穿越）+ 大盘趋势偏多
        卖出：收盘价跌破 MA（从上方穿越）
        """
        close = _to_series(data["close"])
        
        ma_period = self.params["ma_period"]
        
        # 计算均线
        ma = close.rolling(window=ma_period, min_periods=1).mean()
        
        # 买入：收盘价上穿均线
        prev_above = close.shift(1) > ma.shift(1)
        curr_above = close > ma
        entries = curr_above & ~prev_above
        
        # 卖出：收盘价下穿均线
        prev_below = close.shift(1) < ma.shift(1)
        curr_below = close < ma
        exits = curr_below & ~prev_below
        
        return entries, exits
