#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第三批：风控+仓位管理 测试套件
#19 ATR动态仓位 / #20 最大回撤止损 / #21 相关性分散
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.conftest import load_test_data, generate_test_ohlc


# ============ #19 ATR 动态仓位 ============

class TestATRPosition:
    """测试 ATR 动态仓位计算"""

    def test_atr_position_basic(self):
        """基本仓位计算"""
        from risk.risk_atr_position import calculate_atr_position

        # ATR=2.0, 资金100万, 风险1%, 价格50
        position = calculate_atr_position(
            atr=2.0, capital=1e6, risk_pct=0.01, price=50.0
        )
        expected = (1e6 * 0.01) / (2.0 * 50.0)  # = 100 股
        assert position == pytest.approx(expected)

    def test_high_volatility_small_position(self):
        """高波动 → 小仓位"""
        from risk.risk_atr_position import calculate_atr_position

        pos_low_vol = calculate_atr_position(atr=1.0, capital=1e6, risk_pct=0.01, price=50.0)
        pos_high_vol = calculate_atr_position(atr=5.0, capital=1e6, risk_pct=0.01, price=50.0)

        assert pos_high_vol < pos_low_vol

    def test_position_not_negative(self):
        """仓位不应为负"""
        from risk.risk_atr_position import calculate_atr_position

        position = calculate_atr_position(atr=0.001, capital=1e6, risk_pct=0.01, price=50.0)
        assert position > 0

    def test_position_respects_max(self):
        """仓位不应超过上限"""
        from risk.risk_atr_position import calculate_atr_position

        # 极低波动 → 仓位很大，但应被 max_position 限制
        position = calculate_atr_position(
            atr=0.01, capital=1e6, risk_pct=0.01, price=50.0, max_position_pct=0.1
        )
        max_allowed = 1e6 * 0.1 / 50.0  # 总资金的10%对应的股数
        assert position <= max_allowed

    def test_position_series(self):
        """批量计算仓位"""
        from risk.risk_atr_position import calculate_atr_positions

        df = generate_test_ohlc(200)
        df["atr"] = df["close"].rolling(14).std()

        result = calculate_atr_positions(df, capital=1e6, risk_pct=0.01)
        assert len(result) == len(df)
        assert result.iloc[50:].notna().mean() > 0.9
        assert (result.iloc[50:] >= 0).all()


# ============ #20 最大回撤止损 ============

class TestMaxDrawdown:
    """测试最大回撤止损"""

    def test_drawdown_calculation(self):
        """回撤计算"""
        from risk.risk_max_drawdown import calculate_drawdown

        equity = pd.Series([100, 110, 105, 115, 100, 95, 90])
        dd = calculate_drawdown(equity)

        assert dd.iloc[0] == 0.0  # 起点
        assert dd.iloc[1] == 0.0  # 新高
        assert dd.iloc[4] < 0  # 回撤
        assert dd.iloc[6] == pytest.approx(-0.217, abs=0.01)  # 90/115-1

    def test_no_drawdown_when_rising(self):
        """持续上涨无回撤"""
        from risk.risk_max_drawdown import calculate_drawdown

        equity = pd.Series([100, 110, 120, 130, 140])
        dd = calculate_drawdown(equity)
        assert (dd == 0).all()

    def test_stop_trigger(self):
        """止损触发判断"""
        from risk.risk_max_drawdown import should_stop_trading

        # 回撤 12%
        dd = pd.Series([0, 0, -0.05, -0.10, -0.12])
        assert should_stop_trading(dd.iloc[-1], threshold=0.10) == True
        assert should_stop_trading(dd.iloc[-1], threshold=0.15) == False

    def test_drawdown_levels(self):
        """仓位控制等级"""
        from risk.risk_max_drawdown import get_risk_level

        assert get_risk_level(0.0) == "normal"
        assert get_risk_level(-0.03) == "normal"
        assert get_risk_level(-0.06) == "reduce"
        assert get_risk_level(-0.12) == "pause"
        assert get_risk_level(-0.16) == "stop"


# ============ #21 相关性分散 ============

class TestCorrelation:
    """测试相关性分散"""

    def test_correlation_matrix(self):
        """相关性矩阵计算"""
        from risk.risk_correlation import calculate_correlation_matrix

        np.random.seed(42)
        n = 100
        df = pd.DataFrame({
            "A": np.random.randn(n),
            "B": np.random.randn(n) * 0.5 + np.random.randn(n) * 0.5,  # 与A中等相关
            "C": np.random.randn(n),  # 与A不相关
        })

        corr = calculate_correlation_matrix(df)
        assert corr.shape == (3, 3)
        assert (np.diag(corr.values) == 1.0).all()

    def test_find_high_correlation_pairs(self):
        """找高相关性配对"""
        from risk.risk_correlation import find_high_correlation_pairs

        np.random.seed(42)
        n = 200
        base = np.random.randn(n)
        df = pd.DataFrame({
            "A": base,
            "B": base + np.random.randn(n) * 0.1,  # 高相关
            "C": np.random.randn(n),  # 低相关
        })

        pairs = find_high_correlation_pairs(df, threshold=0.5)
        assert len(pairs) > 0
        # A-B 应该是高相关对
        pair_names = [(a, b) for a, b, _ in pairs]
        assert ("A", "B") in pair_names or ("B", "A") in pair_names

    def test_filter_by_correlation(self):
        """按相关性过滤选股"""
        from risk.risk_correlation import filter_by_correlation

        np.random.seed(42)
        n = 200
        base = np.random.randn(n)
        df = pd.DataFrame({
            "A": base,
            "B": base + np.random.randn(n) * 0.1,
            "C": np.random.randn(n),
        })

        selected = filter_by_correlation(df, threshold=0.5)
        assert len(selected) <= 3
        # A 和 B 高相关，应只保留一个
        assert not ("A" in selected and "B" in selected)
