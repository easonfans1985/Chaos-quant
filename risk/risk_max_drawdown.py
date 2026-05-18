#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#20 最大回撤止损

回撤等级：
  < 5%  → normal  （正常交易）
  5-10% → reduce  （仓位减半）
  10-15% → pause  （仅平仓不开新仓）
  > 15% → stop    （全部清仓，暂停5天）
"""

import pandas as pd
import numpy as np


def calculate_drawdown(equity: pd.Series) -> pd.Series:
    """
    计算回撤序列
    
    Args:
        equity: 权益曲线（资金/净值）
    
    Returns:
        回撤序列（负数，0表示无回撤）
    """
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return drawdown


def should_stop_trading(current_drawdown: float, threshold: float = 0.10) -> bool:
    """回撤是否超过止损阈值"""
    return current_drawdown <= -threshold


def get_risk_level(current_drawdown: float) -> str:
    """
    根据回撤返回风险等级
    
    Returns:
        "normal" / "reduce" / "pause" / "stop"
    """
    dd = abs(current_drawdown)
    
    if dd < 0.05:
        return "normal"
    elif dd < 0.10:
        return "reduce"
    elif dd < 0.15:
        return "pause"
    else:
        return "stop"


def get_position_multiplier(risk_level: str) -> float:
    """根据风险等级返回仓位乘数"""
    multipliers = {
        "normal": 1.0,
        "reduce": 0.5,
        "pause": 0.0,
        "stop": 0.0,
    }
    return multipliers.get(risk_level, 1.0)
