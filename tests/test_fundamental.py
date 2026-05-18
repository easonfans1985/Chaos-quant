#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第五批：基本面+事件驱动 测试套件
#11 低估值价值 / #12 业绩超预期 / #13 回购利好
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.conftest import load_test_data, generate_test_ohlc

DATA_DIR = Path(__file__).parent.parent / "data"


# ============ #11 低估值价值 ============

class TestValuePick:
    """测试低估值价值策略"""

    def test_pe_percentile(self):
        """PE 百分位计算"""
        from strategies.value_pick import calculate_pe_percentile

        pe = pd.Series([10, 15, 20, 25, 30, 35, 40, 8, 12, 50])
        percentile = calculate_pe_percentile(pe, current=15)

        assert 0 <= percentile <= 100
        # 15 在 10 个值中排第4小 → 30-40 百分位
        assert percentile < 50

    def test_value_filter(self):
        """价值筛选"""
        from strategies.value_pick import filter_value_stocks

        df = pd.DataFrame({
            "code": ["sh.600036", "sh.600519", "sz.000858", "sz.000001"],
            "pe": [6.0, 30.0, 25.0, 8.0],
            "roe": [15.0, 25.0, 12.0, 10.0],
        })

        selected = filter_value_stocks(df, pe_max=15, roe_min=12)
        assert "sh.600036" in selected["code"].values  # PE=6, ROE=15
        assert "sh.600519" not in selected["code"].values  # PE=30 > 15

    def test_strategy_output(self):
        from strategies.value_pick import ValuePickStrategy

        df = generate_test_ohlc(200)
        strategy = ValuePickStrategy()
        data = {"close": df["close"]}
        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)


# ============ #12 业绩超预期 ============

class TestEarningsSurprise:
    """测试业绩超预期策略"""

    def test_earnings_growth(self):
        """盈利增长检测"""
        from strategies.earnings_surprise import calculate_earnings_growth

        current = pd.Series([1e8, 5e7, 2e8])
        previous = pd.Series([8e7, 6e7, 1e8])

        growth = calculate_earnings_growth(current, previous)
        assert growth.iloc[0] == pytest.approx(0.25, abs=0.01)  # +25%
        assert growth.iloc[1] < 0  # 负增长
        assert growth.iloc[2] == pytest.approx(1.0, abs=0.01)  # +100%

    def test_surprise_filter(self):
        """超预期筛选"""
        from strategies.earnings_surprise import filter_earnings_surprise

        df = pd.DataFrame({
            "code": ["sh.600036", "sh.600519", "sz.000001"],
            "growth": [0.3, -0.1, 0.5],
        })

        selected = filter_earnings_surprise(df, min_growth=0.2)
        assert len(selected) == 2
        assert "sh.600036" in selected["code"].values
        assert "sz.000001" in selected["code"].values

    def test_strategy_output(self):
        from strategies.earnings_surprise import EarningsSurpriseStrategy

        df = generate_test_ohlc(200)
        strategy = EarningsSurpriseStrategy()
        data = {"close": df["close"]}
        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)


# ============ #13 回购利好 ============

class TestBuybackSignal:
    """测试回购利好策略"""

    def test_buyback_filter(self):
        """回购筛选"""
        from strategies.buyback_signal import filter_buyback

        df = pd.DataFrame({
            "code": ["sh.600036", "sh.600519", "sz.000001"],
            "amount": [5e8, 5e6, 2e8],
        })

        selected = filter_buyback(df, min_amount=1e8)
        assert len(selected) == 2
        assert "sh.600036" in selected["code"].values

    def test_strategy_output(self):
        from strategies.buyback_signal import BuybackSignalStrategy

        df = generate_test_ohlc(200)
        strategy = BuybackSignalStrategy()
        data = {"close": df["close"]}
        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)


# ============ 集成回测 ============

class TestBacktest:
    def test_value_backtest(self):
        try:
            from backtest.engine import BacktestEngine, BacktestConfig
            from strategies.value_pick import ValuePickStrategy
        except ImportError:
            pytest.skip("回测引擎未就绪")
        config = BacktestConfig(codes=["sh.600036"], start_date="2024-01-01",
                                end_date="2026-05-18", init_cash=1000000)
        result = BacktestEngine().run(ValuePickStrategy(), config)
        assert result is not None

    def test_earnings_backtest(self):
        try:
            from backtest.engine import BacktestEngine, BacktestConfig
            from strategies.earnings_surprise import EarningsSurpriseStrategy
        except ImportError:
            pytest.skip("回测引擎未就绪")
        config = BacktestConfig(codes=["sh.600036"], start_date="2024-01-01",
                                end_date="2026-05-18", init_cash=1000000)
        result = BacktestEngine().run(EarningsSurpriseStrategy(), config)
        assert result is not None

    def test_buyback_backtest(self):
        try:
            from backtest.engine import BacktestEngine, BacktestConfig
            from strategies.buyback_signal import BuybackSignalStrategy
        except ImportError:
            pytest.skip("回测引擎未就绪")
        config = BacktestConfig(codes=["sh.600036"], start_date="2024-01-01",
                                end_date="2026-05-18", init_cash=1000000)
        result = BacktestEngine().run(BuybackSignalStrategy(), config)
        assert result is not None
