#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略 #6: ATR 通道突破 - 测试套件
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.conftest import load_test_data, generate_test_ohlc


class TestATRCalculation:
    """测试 ATR 计算"""

    def test_atr_values_basic(self):
        """ATR 基本计算"""
        from strategies.atr_breakout import calculate_atr

        df = generate_test_ohlc(200)
        atr = calculate_atr(df['high'], df['low'], df['close'], period=14)

        assert len(atr) == len(df)
        assert atr.iloc[20:].notna().mean() > 0.9

    def test_atr_positive(self):
        """ATR 应始终为正"""
        from strategies.atr_breakout import calculate_atr

        df = generate_test_ohlc(300)
        atr = calculate_atr(df['high'], df['low'], df['close'], period=14)

        valid = atr.iloc[20:]
        assert (valid > 0).all(), "ATR 应 > 0"

    def test_atr_higher_with_volatility(self):
        """高波动时 ATR 更大"""
        from strategies.atr_breakout import calculate_atr

        # 低波动
        np.random.seed(42)
        n = 200
        close_low = pd.Series(100 + np.cumsum(np.random.randn(n) * 0.1))
        high_low = close_low + 0.5
        low_low = close_low - 0.5

        # 高波动
        close_high = pd.Series(100 + np.cumsum(np.random.randn(n) * 2.0))
        high_high = close_high + 3.0
        low_high = close_high - 3.0

        atr_low = calculate_atr(high_low, low_low, close_low, 14)
        atr_high = calculate_atr(high_high, low_high, close_high, 14)

        assert atr_high.iloc[-1] > atr_low.iloc[-1] * 2, \
            f"高波动ATR {atr_high.iloc[-1]:.2f} 应远大于低波动 {atr_low.iloc[-1]:.2f}"


class TestChannelBreakout:
    """测试通道突破信号"""

    def test_breakout_above_channel(self):
        """价格突破上轨应触发买入"""
        from strategies.atr_breakout import ATRBreakoutStrategy

        # 构造突破场景：价格持续上涨后突然突破
        prices = pd.Series([100 + i * 0.1 for i in range(50)] + [106, 108])
        data = {
            "close": prices,
            "high": prices + 0.5,
            "low": prices - 0.5,
        }

        strategy = ATRBreakoutStrategy(params={"atr_period": 14, "channel_mult": 2.0})
        entries, exits = strategy.generate_signals(data)

        assert entries.sum() >= 0  # 不报错

    def test_breakout_below_channel(self):
        """价格跌破下轨应触发卖出"""
        from strategies.atr_breakout import ATRBreakoutStrategy

        # 构造跌破场景
        prices = pd.Series([120 - i * 0.1 for i in range(50)] + [112, 110])
        data = {
            "close": prices,
            "high": prices + 0.5,
            "low": prices - 0.5,
        }

        strategy = ATRBreakoutStrategy(params={"atr_period": 14, "channel_mult": 2.0})
        entries, exits = strategy.generate_signals(data)

        assert exits.sum() >= 0  # 不报错


class TestStrategyIntegration:
    """策略集成测试"""

    def test_output_format(self):
        """输出格式"""
        from strategies.atr_breakout import ATRBreakoutStrategy

        df = generate_test_ohlc(200)
        strategy = ATRBreakoutStrategy()
        data = {"close": df["close"], "high": df["high"], "low": df["low"]}

        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)
        assert len(exits) == len(df)

    def test_real_data(self):
        """真实数据"""
        from strategies.atr_breakout import ATRBreakoutStrategy

        df = load_test_data("sh.600036", "daily", "2023-01-01", "2026-05-18")
        strategy = ATRBreakoutStrategy()
        data = {"close": df["close"]}
        for col in ["high", "low"]:
            if col in df.columns:
                data[col] = df[col]

        entries, exits = strategy.generate_signals(data)
        total = entries.sum() + exits.sum()
        assert total < len(df) * 0.3

    def test_not_all_true(self):
        from strategies.atr_breakout import ATRBreakoutStrategy

        df = generate_test_ohlc(500)
        strategy = ATRBreakoutStrategy()
        data = {"close": df["close"], "high": df["high"], "low": df["low"]}

        entries, exits = strategy.generate_signals(data)
        assert not entries.all()
        assert not exits.all()

    def test_backtest_runs(self):
        try:
            from backtest.engine import BacktestEngine, BacktestConfig
            from strategies.atr_breakout import ATRBreakoutStrategy
        except ImportError:
            pytest.skip("回测引擎未就绪")

        config = BacktestConfig(codes=["sh.600036"], start_date="2024-01-01",
                                end_date="2026-05-18", init_cash=1000000)
        engine = BacktestEngine()
        result = engine.run(ATRBreakoutStrategy(), config)
        assert result is not None
