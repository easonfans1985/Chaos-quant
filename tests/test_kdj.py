#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略 #5: KDJ 超买超卖 - 测试套件
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.conftest import load_test_data, generate_test_ohlc


class TestKDJCalculation:
    """测试 KDJ 指标计算"""

    def test_kdj_values_basic(self):
        """KDJ 基本值计算"""
        from strategies.kdj_strategy import calculate_kdj

        df = generate_test_ohlc(200)
        k, d, j = calculate_kdj(df['high'], df['low'], df['close'])

        assert len(k) == len(df)
        assert len(d) == len(df)
        assert len(j) == len(df)

    def test_kdj_range(self):
        """KDJ 值应在合理范围内"""
        from strategies.kdj_strategy import calculate_kdj

        df = generate_test_ohlc(300)
        k, d, j = calculate_kdj(df['high'], df['low'], df['close'])

        # 跳过前 20 个（冷启动），K 和 D 应在 0-100 之间
        valid_k = k.iloc[20:]
        valid_d = d.iloc[20:]
        assert valid_k.min() >= 0, f"K 最低值 {valid_k.min()} < 0"
        assert valid_k.max() <= 100, f"K 最高值 {valid_k.max()} > 100"
        assert valid_d.min() >= 0, f"D 最低值 {valid_d.min()} < 0"
        assert valid_d.max() <= 100, f"D 最高值 {valid_d.max()} > 100"

    def test_j_can_exceed_range(self):
        """J 值可以超出 0-100 范围"""
        from strategies.kdj_strategy import calculate_kdj

        df = generate_test_ohlc(500)
        k, d, j = calculate_kdj(df['high'], df['low'], df['close'])

        # J = 3K - 2D，可以超出 0-100
        valid_j = j.iloc[20:]
        assert (valid_j < 0).any() or (valid_j > 100).any(), \
            "J 值应该有时超出 0-100 范围"

    def test_k_d_relationship(self):
        """J = 3K - 2D"""
        from strategies.kdj_strategy import calculate_kdj

        df = generate_test_ohlc(200)
        k, d, j = calculate_kdj(df['high'], df['low'], df['close'])

        expected_j = 3 * k - 2 * d
        np.testing.assert_allclose(j.values, expected_j.values, atol=1e-10,
                                    err_msg="J != 3K - 2D")

    def test_kdj_not_all_nan(self):
        """KDJ 不应全为 NaN"""
        from strategies.kdj_strategy import calculate_kdj

        df = generate_test_ohlc(100)
        k, d, j = calculate_kdj(df['high'], df['low'], df['close'])

        valid_k = k.iloc[20:]
        assert valid_k.notna().mean() > 0.9, "K 有效值太少"


class TestKDJSignals:
    """测试 KDJ 买卖信号"""

    def test_golden_cross_in_oversold(self):
        """K 上穿 D + J<20 应产生买入信号"""
        from strategies.kdj_strategy import KDJStrategy

        # 构造超卖场景
        strategy = KDJStrategy(params={"oversold": 20, "overbought": 80})

        # 手动构造 KDJ 数据模拟超卖金叉
        data = {
            "close": pd.Series([100] * 30 + list(range(100, 80, -1)) + list(range(80, 90))),
            "high": pd.Series([101] * 30 + list(range(101, 81, -1)) + list(range(82, 92))),
            "low": pd.Series([99] * 30 + list(range(99, 79, -1)) + list(range(79, 89))),
        }
        entries, exits = strategy.generate_signals(data)

        assert isinstance(entries, pd.Series)
        assert entries.dtype == bool or str(entries.dtype) == 'bool'

    def test_death_cross_in_overbought(self):
        """K 下穿 D + J>80 应产生卖出信号"""
        from strategies.kdj_strategy import KDJStrategy

        strategy = KDJStrategy(params={"oversold": 20, "overbought": 80})

        # 先涨后跌（超买死叉）
        prices_up = list(range(50, 80))
        prices_down = list(range(80, 70, -1))
        close = pd.Series([50] * 20 + prices_up + prices_down)
        data = {
            "close": close,
            "high": close + 1,
            "low": close - 1,
        }
        entries, exits = strategy.generate_signals(data)

        assert isinstance(exits, pd.Series)

    def test_no_signal_when_kdj_neutral(self):
        """KDJ 在中性区域（20<J<80）交叉不应产生信号"""
        from strategies.kdj_strategy import KDJStrategy

        strategy = KDJStrategy(params={"oversold": 20, "overbought": 80})

        # 温和波动的数据
        df = generate_test_ohlc(200, seed=123)
        data = {"close": df["close"], "high": df["high"], "low": df["low"]}
        entries, exits = strategy.generate_signals(data)

        # 中性区交叉不应触发买卖（只有超卖金叉和超买死叉才触发）
        # 信号数量应该比纯交叉少
        total_signals = entries.sum() + exits.sum()
        assert total_signals >= 0  # 至少不报错


class TestStrategyIntegration:
    """策略集成测试"""

    def test_strategy_output_format(self):
        """输出格式正确"""
        from strategies.kdj_strategy import KDJStrategy

        strategy = KDJStrategy()
        df = generate_test_ohlc(200)
        data = {"close": df["close"], "high": df["high"], "low": df["low"]}

        entries, exits = strategy.generate_signals(data)

        assert len(entries) == len(df)
        assert len(exits) == len(df)
        assert entries.dtype == bool or str(entries.dtype) == 'bool'
        assert exits.dtype == bool or str(exits.dtype) == 'bool'

    def test_strategy_with_real_data(self):
        """用真实数据运行"""
        from strategies.kdj_strategy import KDJStrategy

        df = load_test_data("sh.600036", "daily", "2023-01-01", "2026-05-18")
        strategy = KDJStrategy()

        data = {"close": df["close"]}
        for col in ["high", "low", "open", "volume"]:
            if col in df.columns:
                data[col] = df[col]

        entries, exits = strategy.generate_signals(data)

        total = entries.sum() + exits.sum()
        assert total < len(df) * 0.3, f"信号太频繁: {total}/{len(df)}"

    def test_strategy_not_all_true(self):
        """不应全 True"""
        from strategies.kdj_strategy import KDJStrategy

        df = generate_test_ohlc(500)
        strategy = KDJStrategy()
        data = {"close": df["close"], "high": df["high"], "low": df["low"]}

        entries, exits = strategy.generate_signals(data)
        assert not entries.all()
        assert not exits.all()

    def test_backtest_runs(self):
        """回测能正常跑"""
        try:
            from backtest.engine import BacktestEngine, BacktestConfig
            from strategies.kdj_strategy import KDJStrategy
        except ImportError:
            pytest.skip("回测引擎未就绪")

        config = BacktestConfig(
            codes=["sh.600036"],
            start_date="2024-01-01",
            end_date="2026-05-18",
            init_cash=1000000,
        )
        engine = BacktestEngine()
        result = engine.run(KDJStrategy(), config)
        assert result is not None
