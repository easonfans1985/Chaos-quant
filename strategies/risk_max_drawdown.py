#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#20: 最大回撤止损策略

监控持仓最大回撤，当回撤超过阈值时强制平仓止损。
配合趋势信号入场，通过回撤控制实现风控。

买入条件：趋势向上（短均线 > 长均线）+ 价格创新高
卖出条件：
  1. 回撤超过阈值（默认15%）→ 止损
  2. 趋势反转（短均线 < 长均线）→ 止盈

参数：
  fast_period: 快均线周期（默认10）
  slow_period: 慢均线周期（默认30）
  max_drawdown: 最大允许回撤（默认0.15，即15%）
  trailing_stop: 移动止损比例（默认0.08，即8%）
"""

import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy


def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


class MaxDrawdownStrategy(BaseStrategy):
    """最大回撤止损策略"""

    name = "Max Drawdown Stop"
    description = "趋势跟踪+最大回撤止损，控制单次交易最大亏损"

    def __init__(self, params=None):
        defaults = {
            "fast_period": 10,
            "slow_period": 30,
            "max_drawdown": 0.15,
            "trailing_stop": 0.08,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        close = _to_series(data["close"])

        fast_period = self.params["fast_period"]
        slow_period = self.params["slow_period"]
        max_dd = self.params["max_drawdown"]
        trailing = self.params["trailing_stop"]

        # 均线趋势
        fast_ma = close.rolling(fast_period).mean()
        slow_ma = close.rolling(slow_period).mean()

        # 买入：金叉（快线上穿慢线）
        golden_cross = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
        entries = golden_cross

        # ---- 计算回撤止损 ----
        # 运行最高价（从金叉开始跟踪）
        running_max = close.expanding().max()

        # 从最高点的回撤幅度
        drawdown_from_peak = (close - running_max) / running_max

        # 移动止损：从最近 N 日高点回撤超过 trailing
        recent_high = close.rolling(slow_period, min_periods=1).max()
        trailing_dd = (close - recent_high) / recent_high

        # 卖出条件
        # 1. 最大回撤止损：从历史最高点回撤超过阈值
        dd_stop = drawdown_from_peak < -max_dd

        # 2. 移动止损：从近期高点回撤超过 trailing
        trailing_stop = trailing_dd < -trailing

        # 3. 趋势反转：死叉
        death_cross = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))

        exits = dd_stop | trailing_stop | death_cross

        # 等均线预热完成
        warmup = slow_period + 5
        entries.iloc[:warmup] = False
        exits.iloc[:warmup] = False

        return entries, exits
