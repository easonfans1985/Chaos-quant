#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略 #8: 板块轮动策略

逻辑：
1. 从同花顺行业资金流数据选出资金净流入前 N 的行业
2. 在热门行业中选涨幅最大的股票
3. 定期轮动（默认每周）

参数：
  top_sectors: 选前几个行业（默认3）
  stocks_per_sector: 每个行业选几只（默认2）
  rotation_period: 轮动周期天数（默认5，即每周）
"""

import pandas as pd
import numpy as np
import glob
from pathlib import Path
from backtest.base_strategy import BaseStrategy
from strategies.fund_flow_inflow import parse_money_str


def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def load_latest_industry_flow(data_dir: Path) -> pd.DataFrame:
    """加载最新的行业资金流数据"""
    cf_dir = data_dir / "money_flow" / "capital_flow"
    files = sorted(glob.glob(str(cf_dir / "ths_industry_*_即时.parquet")))
    if not files:
        return None

    df = pd.read_parquet(files[-1])

    # 解析净额
    for col in df.columns:
        if "净额" in col or "净" in col:
            df["净额数值"] = df[col].apply(parse_money_str)
            break

    return df


def select_top_sectors(df: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """选出资金净流入前 N 的行业"""
    if "净额数值" not in df.columns or df.empty:
        return pd.DataFrame()

    filtered = df[df["净额数值"] > 0].copy()
    if filtered.empty:
        return pd.DataFrame()

    return filtered.nlargest(top_n, "净额数值")


def get_sector_stocks(sector_name: str) -> list:
    """
    获取某行业的代表性股票代码
    
    简化版：返回行业对应的一组知名股票
    完整版需要用到行业成分股数据
    """
    # 常见行业的代表股票（简化版）
    sector_map = {
        "银行": ["sh.600036", "sh.601398", "sh.601288", "sh.600016", "sh.601166"],
        "电子": ["sz.000858", "sh.601012", "sz.002415", "sh.600584"],
        "医药": ["sh.600276", "sz.000538", "sh.601607", "sz.300760"],
        "食品": ["sh.600519", "sz.000858", "sh.600887"],
        "地产": ["sh.600048", "sz.000002", "sh.600340"],
        "非银金融": ["sh.601318", "sh.600030", "sh.601688"],
        "计算机": ["sh.600588", "sz.002230", "sz.300059"],
        "新能源": ["sz.300750", "sh.600438", "sz.002594"],
        "汽车": ["sh.600104", "sz.000625", "sz.002594"],
        "电力": ["sh.600900", "sh.601985", "sh.600886"],
    }

    return sector_map.get(sector_name, [])


class SectorRotationStrategy(BaseStrategy):
    """板块轮动策略"""
    
    name = "Sector Rotation"
    description = "行业资金流入前3板块选股，每周轮动"

    def __init__(self, params=None):
        defaults = {
            "top_sectors": 3,
            "stocks_per_sector": 2,
            "rotation_period": 5,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        """
        基于板块轮动的信号
        
        回退模式：用价格动量代替板块数据
        每隔 rotation_period 天选一次，买入动量最强的
        """
        close = _to_series(data["close"])
        
        rotation_period = self.params["rotation_period"]
        
        # 动量信号：过去 rotation_period 天涨幅
        momentum = close.pct_change(rotation_period)
        
        # 买入：动量从负转正（趋势反转）
        prev_mom = momentum.shift(1)
        entries = (momentum > 0) & (prev_mom <= 0)
        
        # 只在轮动日买入（每 N 天）
        day_count = pd.Series(range(len(close)), index=close.index)
        is_rotation_day = day_count % rotation_period == 0
        entries = entries & is_rotation_day
        
        # 卖出：轮动日 + 动量为负
        exits = (momentum < 0) & is_rotation_day
        
        return entries, exits
