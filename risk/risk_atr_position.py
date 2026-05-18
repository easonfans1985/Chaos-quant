#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#19 ATR 动态仓位管理

仓位 = 风险预算 / (ATR × 价格)
波动大 → 仓位小，波动小 → 仓位大
"""

import pandas as pd
import numpy as np


def calculate_atr_position(atr: float, capital: float, risk_pct: float = 0.01,
                           price: float = 1.0, max_position_pct: float = 0.2) -> float:
    """
    计算单只股票的持仓股数
    
    Args:
        atr: ATR 值
        capital: 总资金
        risk_pct: 单笔最大亏损占总资金比例（默认1%）
        price: 当前价格
        max_position_pct: 单只股票最大占总资金比例（默认20%）
    
    Returns:
        持仓股数（float，需向下取整）
    """
    if atr <= 0 or price <= 0:
        return 0.0
    
    # 风险预算 = 总资金 × 风险比例
    risk_budget = capital * risk_pct
    
    # 仓位 = 风险预算 / (ATR × 价格因子)
    position = risk_budget / (atr * price)
    
    # 上限：不超过总资金的 max_position_pct
    max_shares = capital * max_position_pct / price
    position = min(position, max_shares)
    
    return max(position, 0.0)


def calculate_atr_positions(df: pd.DataFrame, capital: float = 1e6,
                             risk_pct: float = 0.01, atr_period: int = 14,
                             max_position_pct: float = 0.2) -> pd.Series:
    """
    批量计算 ATR 仓位
    
    Args:
        df: DataFrame，需要 close 列，可选 high/low
        capital: 总资金
        risk_pct: 单笔风险比例
        atr_period: ATR 周期
        max_position_pct: 单只最大仓位比例
    """
    close = df["close"]
    high = df["high"] if "high" in df.columns else close
    low = df["low"] if "low" in df.columns else close
    
    # 计算 TR 和 ATR
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=atr_period, adjust=False).mean()
    
    # 逐行计算仓位
    positions = pd.Series(np.nan, index=df.index)
    for i in range(len(df)):
        if pd.isna(atr.iloc[i]) or pd.isna(close.iloc[i]) or atr.iloc[i] <= 0:
            continue
        positions.iloc[i] = calculate_atr_position(
            atr=atr.iloc[i], capital=capital, risk_pct=risk_pct,
            price=close.iloc[i], max_position_pct=max_position_pct
        )
    
    return positions
