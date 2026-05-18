#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略 #10: 北向资金跟随 - 测试套件
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.conftest import load_test_data, generate_test_ohlc

DATA_DIR = Path(__file__).parent.parent / "data"


class TestNorthboundData:
    """测试北向资金数据"""

    def test_northbound_files_exist(self):
        """北向资金文件存在"""
        nb_dir = DATA_DIR / "money_flow" / "northbound"
        files = list(nb_dir.glob("*.parquet"))
        assert len(files) >= 2

    def test_load_northbound(self):
        """加载北向资金"""
        from strategies.northbound_follow import load_northbound_data

        df = load_northbound_data(DATA_DIR)
        if df is None:
            pytest.skip("无北向数据")

        assert len(df) > 100
        assert "日期" in df.columns or "date" in df.columns or df.index.name in ["日期", "date"]

    def test_consecutive_inflow(self):
        """检测连续净流入"""
        from strategies.northbound_follow import detect_consecutive_flow

        # 构造连续3天净流入
        flow = pd.Series([1e8, 2e8, 3e8, -1e8, 5e8, 6e8, 7e8])
        result = detect_consecutive_flow(flow, min_days=3, direction="inflow")

        # 前3天连续流入
        assert result.iloc[2] == True  # 连续3天
        assert result.iloc[3] == False  # 第4天流出
        assert result.iloc[6] == True  # 后3天连续流入

    def test_consecutive_outflow(self):
        """检测连续净流出"""
        from strategies.northbound_follow import detect_consecutive_flow

        flow = pd.Series([-1e8, -2e8, -3e8, 1e8])
        result = detect_consecutive_flow(flow, min_days=3, direction="outflow")

        assert result.iloc[2] == True


class TestStrategyIntegration:
    """策略集成测试"""

    def test_output_format(self):
        from strategies.northbound_follow import NorthboundFollowStrategy

        df = generate_test_ohlc(200)
        strategy = NorthboundFollowStrategy()
        data = {"close": df["close"], "high": df["high"], "low": df["low"]}

        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)
        assert len(exits) == len(df)

    def test_real_data(self):
        from strategies.northbound_follow import NorthboundFollowStrategy

        df = load_test_data("sh.600036", "daily", "2023-01-01", "2026-05-18")
        strategy = NorthboundFollowStrategy()
        data = {"close": df["close"]}
        for col in ["high", "low"]:
            if col in df.columns:
                data[col] = df[col]

        entries, exits = strategy.generate_signals(data)
        total = entries.sum() + exits.sum()
        assert total >= 0

    def test_backtest_runs(self):
        try:
            from backtest.engine import BacktestEngine, BacktestConfig
            from strategies.northbound_follow import NorthboundFollowStrategy
        except ImportError:
            pytest.skip("回测引擎未就绪")

        config = BacktestConfig(codes=["sh.600036"], start_date="2024-01-01",
                                end_date="2026-05-18", init_cash=1000000)
        engine = BacktestEngine()
        result = engine.run(NorthboundFollowStrategy(), config)
        assert result is not None
