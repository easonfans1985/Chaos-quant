#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#21: 相关性分散策略

通过多资产低相关性分散风险：
- 选择相关性低的股票/ETF 组合
- 当组合内相关性飙升（危机模式）→ 减仓
- 当相关性恢复正常 → 恢复仓位

在单一资产（如单只股票）回测中，用价格与均线偏离度
作为"拥挤度"代理指标：
- 偏离度异常高 → 拥挤交易 → 减仓
- 偏离度回归正常 → 重新入场

参数：
  lookback: 相关性/偏离度计算窗口（默认60）
  corr_threshold: 相关性预警阈值（默认0.8）
  entry_zscore: 入场Z-score阈值（默认-1.5）
  exit_zscore: 离场Z-score阈值（默认2.0）
"""

import pandas as pd
import numpy as np
from backtest.base_strategy import BaseStrategy


def _to_series(obj):
    if isinstance(obj, pd.DataFrame):
        return obj.iloc[:, 0]
    return obj


class CorrelationDiversifyStrategy(BaseStrategy):
    """相关性分散策略"""

    name = "Correlation Diversify"
    description = "监测拥挤度/相关性异常，高相关性时减仓避险"

    def __init__(self, params=None):
        defaults = {
            "lookback": 60,
            "corr_threshold": 0.8,
            "entry_zscore": -1.5,
            "exit_zscore": 2.0,
            "trend_period": 20,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data):
        close = _to_series(data["close"])

        lookback = self.params["lookback"]
        entry_z = self.params["entry_zscore"]
        exit_z = self.params["exit_zscore"]
        trend_period = self.params["trend_period"]

        # 计算收益率
        returns = close.pct_change()

        # 计算滚动均值和标准差
        rolling_mean = returns.rolling(lookback).mean()
        rolling_std = returns.rolling(lookback).std()

        # Z-score：当前收益率偏离均值的程度
        zscore = (returns - rolling_mean) / (rolling_std + 1e-10)

        # 波动率百分位（拥挤度代理）
        rolling_vol = returns.rolling(lookback).std() * np.sqrt(252)
        vol_percentile = rolling_vol.rolling(lookback * 2, min_periods=lookback).apply(
            lambda x: (x.iloc[-1] > x).mean(), raw=False
        )

        # 趋势判断
        trend_ma = close.rolling(trend_period).mean()
        uptrend = close > trend_ma

        # 买入：趋势向上 + Z-score从极低恢复（恐慌后反弹）
        oversold_recovery = (zscore > entry_z) & (zscore.shift(1) <= entry_z)
        low_vol = vol_percentile < 0.6  # 波动率不太高
        entries = oversold_recovery & uptrend & low_vol

        # 卖出：Z-score过高（过度拥挤）或 波动率飙升
        overbought = zscore > exit_z
        high_vol = (vol_percentile > 0.85) & (vol_percentile.shift(1) <= 0.85)
        downtrend = (close < trend_ma) & (close.shift(1) >= trend_ma.shift(1))
        exits = overbought | high_vol | downtrend

        # 预热期
        warmup = lookback * 2
        entries.iloc[:warmup] = False
        exits.iloc[:warmup] = False

        return entries, exits
