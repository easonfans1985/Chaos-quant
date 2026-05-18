#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#19: ATR 动态仓位策略

根据 ATR（平均真实波幅）动态调整仓位大小：
- ATR 大（波动高）→ 减小仓位（控制风险）
- ATR 小（波动低）→ 增大仓位（利用稳定行情）

配合趋势信号，在方向明确+波动低时重仓，方向明确+波动高时轻仓。

参数：
  atr_period: ATR 周期（默认14）
  target_volatility: 目标年化波动率（默认0.15，即15%）
  trend_period: 趋势判断均线周期（默认50）
  rebalance_period: 仓位再平衡周期（默认20个交易日）
"""

import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy


def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


def calc_atr(high, low, close, period=14):
    """计算 ATR"""
    high = _to_series(high)
    low = _to_series(low)
    close = _to_series(close)
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


class ATRPositionStrategy(BaseStrategy):
    """ATR 动态仓位策略"""

    name = "ATR Position"
    description = "基于ATR波动率动态调整仓位，低波动加仓，高波动减仓"

    def __init__(self, params=None):
        defaults = {
            "atr_period": 14,
            "target_volatility": 0.15,
            "trend_period": 50,
            "rebalance_period": 20,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        close = _to_series(data["close"])
        high = _to_series(data.get("high", close))
        low = _to_series(data.get("low", close))

        atr_period = self.params["atr_period"]
        target_vol = self.params["target_volatility"]
        trend_period = self.params["trend_period"]
        rebalance_period = self.params["rebalance_period"]

        # 计算指标
        atr = calc_atr(high, low, close, atr_period)
        trend_ma = close.rolling(trend_period).mean()

        # 年化波动率估算：ATR / close * sqrt(252)
        daily_vol = atr / close
        annual_vol = daily_vol * np.sqrt(252)

        # 目标仓位 = 目标波动率 / 实际波动率（上限1.0）
        position_ratio = target_vol / (annual_vol + 1e-10)
        position_ratio = position_ratio.clip(upper=1.0, lower=0.1)

        # 趋势方向判断
        uptrend = close > trend_ma

        # 买入信号：上升趋势 + 波动率从高回落（仓位增加）
        vol_declining = annual_vol < annual_vol.shift(5) * 0.9
        entries = uptrend & vol_declining

        # 卖出信号：波动率飙升（仓位极低）或趋势反转
        vol_spike = annual_vol > annual_vol.shift(5) * 1.5
        downtrend = close < trend_ma
        exits = downtrend | vol_spike

        # 至少等 atr_period + trend_period 根K线才开始
        warmup = atr_period + trend_period
        entries.iloc[:warmup] = False
        exits.iloc[:warmup] = False

        return entries, exits
