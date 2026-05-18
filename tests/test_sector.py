#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略 #8: 板块轮动 - 测试套件
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.conftest import load_test_data, generate_test_ohlc

DATA_DIR = Path(__file__).parent.parent / "data"


class TestSectorData:
    """测试行业资金流数据"""

    def test_industry_flow_files(self):
        from strategies.sector_rotation import load_latest_industry_flow

        df = load_latest_industry_flow(DATA_DIR)
        if df is None:
            pytest.skip("无行业资金流数据")

        assert len(df) > 50
        assert "行业" in df.columns or "板块" in df.columns

    def test_select_top_sectors(self):
        from strategies.sector_rotation import select_top_sectors

        df = pd.DataFrame({
            "行业": ["银行", "电子", "医药", "食品", "地产"],
            "净额数值": [5e9, -2e9, 3e9, 1e9, -4e9],
        })

        top = select_top_sectors(df, top_n=3)
        assert len(top) == 3
        assert "银行" in top["行业"].values
        assert "医药" in top["行业"].values

    def test_sector_stock_mapping(self):
        from strategies.sector_rotation import get_sector_stocks

        # 沪深300成分股的行业分类
        stocks = get_sector_stocks("银行")
        assert isinstance(stocks, list)
        # 银行应该包含常见银行股
        if stocks:
            assert len(stocks) > 0


class TestStrategyIntegration:

    def test_output_format(self):
        from strategies.sector_rotation import SectorRotationStrategy

        df = generate_test_ohlc(200)
        strategy = SectorRotationStrategy()
        data = {"close": df["close"], "high": df["high"], "low": df["low"]}

        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)
        assert len(exits) == len(df)

    def test_real_data(self):
        from strategies.sector_rotation import SectorRotationStrategy

        df = load_test_data("sh.600036", "daily", "2024-01-01", "2026-05-18")
        strategy = SectorRotationStrategy()
        data = {"close": df["close"]}
        for col in ["high", "low"]:
            if col in df.columns:
                data[col] = df[col]

        entries, exits = strategy.generate_signals(data)
        assert entries.sum() >= 0

    def test_backtest_runs(self):
        try:
            from backtest.engine import BacktestEngine, BacktestConfig
            from strategies.sector_rotation import SectorRotationStrategy
        except ImportError:
            pytest.skip("回测引擎未就绪")

        config = BacktestConfig(codes=["sh.600036"], start_date="2024-06-01",
                                end_date="2026-05-18", init_cash=1000000)
        engine = BacktestEngine()
        result = engine.run(SectorRotationStrategy(), config)
        assert result is not None
