#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略 #7: 主力资金流入策略

逻辑：
1. 从同花顺资金流数据筛选主力净流入 > 阈值的股票
2. 结合价格突破（收盘价 > 20日高点）确认买入
3. 资金净流出或持有 N 天后卖出

参数：
  min_inflow: 最低净流入金额（默认1亿）
  top_n: 最多选多少只（默认10）
  hold_days: 最大持有天数（默认5）
  breakout_period: 突破回看天数（默认20）
"""

import pandas as pd
import numpy as np
import glob
import os
from pathlib import Path
from backtest.base_strategy import BaseStrategy


def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def parse_money_str(s) -> float:
    """解析带'亿'/'万'的金额字符串"""
    if pd.isna(s):
        return 0.0
    s = str(s).strip()
    if s.endswith('亿'):
        return float(s[:-1]) * 1e8
    elif s.endswith('万'):
        return float(s[:-1]) * 1e4
    else:
        try:
            return float(s)
        except ValueError:
            return 0.0


def parse_percent_str(s) -> float:
    """解析百分比字符串"""
    if pd.isna(s):
        return 0.0
    s = str(s).strip().replace('%', '')
    try:
        return float(s)
    except ValueError:
        return 0.0


def code_to_baostock(code) -> str:
    """将纯数字代码转为 baostock 格式 (sh.600036 / sz.000858)"""
    code = str(code).zfill(6)
    if code.startswith(('6', '5')):
        return f"sh.{code}"
    else:
        return f"sz.{code}"


def load_latest_fund_flow(data_dir: Path) -> pd.DataFrame:
    """加载最新的同花顺即时资金流数据"""
    cf_dir = data_dir / "money_flow" / "capital_flow"
    files = sorted(glob.glob(str(cf_dir / "ths_fund_flow_*_即时.parquet")))
    if not files:
        return None
    
    df = pd.read_parquet(files[-1])
    
    # 解析金额
    df['净额数值'] = df['净额'].apply(parse_money_str)
    df['流入数值'] = df['流入资金'].apply(parse_money_str)
    df['流出数值'] = df['流出资金'].apply(parse_money_str)
    df['成交额数值'] = df['成交额'].apply(parse_money_str)
    df['涨跌幅数值'] = df['涨跌幅'].apply(parse_percent_str)
    df['换手率数值'] = df['换手率'].apply(parse_percent_str)
    
    return df


def select_inflow_stocks(df: pd.DataFrame, min_inflow: float = 1e8, 
                          top_n: int = 10) -> pd.DataFrame:
    """筛选高净流入股票"""
    # 过滤：净流入 > 阈值
    filtered = df[df['净额数值'] >= min_inflow].copy()
    
    if filtered.empty:
        return filtered
    
    # 按净流入排序，取前 N
    filtered = filtered.nlargest(top_n, '净额数值')
    
    return filtered


class FundFlowInflowStrategy(BaseStrategy):
    """主力资金流入策略"""
    
    name = "Fund Flow Inflow"
    description = "主力净流入>1亿+价格突破做多"

    def __init__(self, params=None):
        defaults = {
            "min_inflow": 1e8,
            "top_n": 10,
            "hold_days": 5,
            "breakout_period": 20,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        """
        基于资金流入+价格突破生成信号
        
        纯技术面回退：无资金流数据时，用价格动量代替
        """
        close = _to_series(data["close"])
        
        breakout_period = self.params["breakout_period"]
        
        # 价格突破信号：收盘价创 breakout_period 新高
        rolling_high = close.rolling(window=breakout_period, min_periods=1).max()
        
        # 买入：收盘价接近或突破近期高点（> 95% 的滚动高点）
        entries = close >= rolling_high * 0.98
        
        # 只在突破当日买入（之前不是）
        prev_breakout = close.shift(1) >= rolling_high.shift(1) * 0.98
        entries = entries & ~prev_breakout
        
        # 卖出：持有 N 天后
        hold_days = self.params["hold_days"]
        exits = pd.Series(False, index=close.index)
        
        # 找到每个买入点后 hold_days 天卖出
        entry_indices = entries[entries].index
        for idx in entry_indices:
            pos = entries.index.get_loc(idx)
            sell_pos = pos + hold_days
            if sell_pos < len(exits):
                exits.iloc[sell_pos] = True
        
        # 止损：跌破 20 日低点
        rolling_low = close.rolling(window=20, min_periods=1).min()
        exits = exits | (close < rolling_low * 0.97)
        
        # 避免连续卖出
        prev_exit = exits.shift(1).fillna(False)
        exits = exits & ~prev_exit
        
        return entries, exits
