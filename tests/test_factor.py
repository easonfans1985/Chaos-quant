#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第四批：统计套利+组合 测试套件
#15 配对交易 / #17 动量因子 / #18 多因子综合
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.conftest import load_test_data, generate_test_ohlc


# ============ #15 配对交易 ============

class TestPairTrading:
    """测试配对交易"""

    def test_spread_calculation(self):
        """价差计算"""
        from strategies.pair_trading import calculate_spread

        price_a = pd.Series([100, 101, 102, 103, 104])
        price_b = pd.Series([50, 50.5, 51, 51.5, 52])

        spread, ratio = calculate_spread(price_a, price_b)
        assert len(spread) == 5
        assert ratio > 0  # 对冲比率应为正
        # spread = price_a - ratio * price_b
        expected = price_a - ratio * price_b
        np.testing.assert_allclose(spread.values, expected.values, atol=0.01)

    def test_zscore_calculation(self):
        """Z-Score 计算"""
        from strategies.pair_trading import calculate_zscore

        spread = pd.Series(np.random.randn(200))
        zscore = calculate_zscore(spread, window=20)

        assert len(zscore) == 200
        # Z-Score 均值应接近0
        valid = zscore.iloc[40:]
        assert abs(valid.mean()) < 0.5

    def test_entry_signal(self):
        """入场信号：Z-Score 超过阈值"""
        from strategies.pair_trading import generate_pair_signals

        zscore = pd.Series([0, 0.5, 1.0, 2.5, 3.0, 2.0, 0.5, -2.5, -3.0, 0])
        entries_long, entries_short, exits = generate_pair_signals(
            zscore, entry_threshold=2.0, exit_threshold=0.5
        )

        # Z > 2 时做空（entries_short），Z < -2 时做多（entries_long）
        assert entries_long.iloc[7] == True  # Z=-2.5
        assert entries_short.iloc[3] == True  # Z=2.5

    def test_exit_signal(self):
        """平仓信号：Z-Score 回归"""
        from strategies.pair_trading import generate_pair_signals

        zscore = pd.Series([3.0, 2.0, 1.0, 0.3, 0.1, 0.0])
        _, _, exits = generate_pair_signals(zscore, entry_threshold=2.0, exit_threshold=0.5)

        assert exits.iloc[3] == True  # Z=0.3 < 0.5

    def test_cointegration_test(self):
        """协整检验"""
        from strategies.pair_trading import test_cointegration

        np.random.seed(42)
        n = 200
        base = np.cumsum(np.random.randn(n))
        price_a = pd.Series(base + np.random.randn(n) * 0.5)
        price_b = pd.Series(base * 1.5 + np.random.randn(n) * 0.5)

        score, pvalue = test_cointegration(price_a, price_b)
        assert 0 <= pvalue <= 1
        # 高度相关序列的 pvalue 应该较小
        assert pvalue < 0.1


# ============ #17 动量因子 ============

class TestMomentumFactor:
    """测试动量因子"""

    def test_momentum_calculation(self):
        """动量计算"""
        from strategies.momentum_factor import calculate_momentum

        prices = pd.Series([100, 105, 110, 108, 115, 120, 118])
        mom = calculate_momentum(prices, period=3)

        assert len(mom) == 7
        # 最后一期 period=3: 118/108 - 1
        assert mom.iloc[-1] == pytest.approx(118/108 - 1, abs=0.01)

    def test_momentum_rank(self):
        """动量排名"""
        from strategies.momentum_factor import rank_by_momentum

        df = pd.DataFrame({
            "A": [100, 110, 120],  # +20%
            "B": [100, 95, 90],    # -10%
            "C": [100, 105, 115],  # +15%
        })
        ranked = rank_by_momentum(df, period=2)

        assert ranked.index[0] == "A"  # 最高动量
        assert ranked.index[-1] == "B"

    def test_select_top_momentum(self):
        """选出动量最高的"""
        from strategies.momentum_factor import select_top_momentum

        df = pd.DataFrame({
            "A": [100, 110, 120],
            "B": [100, 95, 90],
            "C": [100, 105, 115],
        })
        top = select_top_momentum(df, top_n=2, period=2)

        assert len(top) == 2
        assert "A" in top
        assert "B" not in top

    def test_momentum_strategy_output(self):
        """策略输出格式"""
        from strategies.momentum_factor import MomentumFactorStrategy

        df = generate_test_ohlc(200)
        strategy = MomentumFactorStrategy()
        data = {"close": df["close"]}
        entries, exits = strategy.generate_signals(data)

        assert len(entries) == len(df)
        assert len(exits) == len(df)


# ============ #18 多因子综合 ============

class TestMultiFactor:
    """测试多因子综合"""

    def test_factor_scoring(self):
        """因子打分"""
        from strategies.multi_factor import calculate_factor_scores

        factors = pd.DataFrame({
            "momentum": [0.1, -0.05, 0.2, 0.0, 0.15],
            "volatility": [0.3, 0.1, 0.5, 0.2, 0.4],
            "volume": [1e6, 5e5, 2e6, 8e5, 1.5e6],
        })

        scores = calculate_factor_scores(factors, weights=[0.4, 0.3, 0.3])
        assert len(scores) == 5
        # 因子3（高动量+中波动+高成交量）应得分最高
        assert scores.iloc[2] > scores.iloc[1]

    def test_select_top_by_score(self):
        """按综合分选股"""
        from strategies.multi_factor import select_top_by_score

        scores = pd.Series({"A": 0.9, "B": 0.3, "C": 0.7, "D": 0.5, "E": 0.8})
        selected = select_top_by_score(scores, top_n=3)

        assert len(selected) == 3
        assert "A" in selected
        assert "B" not in selected

    def test_multi_factor_strategy_output(self):
        """策略输出"""
        from strategies.multi_factor import MultiFactorStrategy

        df = generate_test_ohlc(200)
        strategy = MultiFactorStrategy()
        data = {"close": df["close"], "high": df["high"], "low": df["low"], "volume": df["volume"]}
        entries, exits = strategy.generate_signals(data)

        assert len(entries) == len(df)
        assert len(exits) == len(df)
