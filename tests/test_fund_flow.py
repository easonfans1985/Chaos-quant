#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
策略 #7: 主力资金流入 - 测试套件
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.conftest import load_test_data, generate_test_ohlc

DATA_DIR = Path(__file__).parent.parent / "data"


class TestFundFlowParser:
    """测试资金流数据解析"""

    def test_parse_money_str(self):
        """解析带亿/万的金额字符串"""
        from strategies.fund_flow_inflow import parse_money_str

        assert parse_money_str("1.33亿") == 1.33e8
        assert parse_money_str("-1.92亿") == -1.92e8
        assert parse_money_str("5000万") == 5e7
        assert parse_money_str("-300万") == -3e6
        assert parse_money_str("0") == 0.0
        assert parse_money_str("123.45") == 123.45

    def test_parse_percent_str(self):
        """解析百分比字符串"""
        from strategies.fund_flow_inflow import parse_percent_str

        assert parse_percent_str("5.23%") == pytest.approx(5.23)
        assert parse_percent_str("-2.10%") == pytest.approx(-2.10)
        assert parse_percent_str("0%") == pytest.approx(0.0)

    def test_load_fund_flow_data(self):
        """加载资金流数据"""
        from strategies.fund_flow_inflow import load_latest_fund_flow

        df = load_latest_fund_flow(DATA_DIR)
        if df is None:
            pytest.skip("无资金流数据")

        assert len(df) > 1000, f"资金流数据只有 {len(df)} 条"
        assert "股票代码" in df.columns
        assert "净额" in df.columns


class TestFundFlowSignals:
    """测试资金流信号"""

    def test_high_inflow_stocks(self):
        """筛选高流入股票"""
        from strategies.fund_flow_inflow import select_inflow_stocks

        # 模拟资金流数据
        df = pd.DataFrame({
            "股票代码": [600000, 600036, 600519, 1, 858],
            "净额数值": [5e8, -2e8, 1e9, 3e8, -5e8],
            "最新价": [10.0, 30.0, 1500.0, 15.0, 50.0],
        })

        selected = select_inflow_stocks(df, min_inflow=1e8, top_n=3)
        assert len(selected) <= 3
        # 600519(10亿), 600000(5亿), 000001(3亿) 应被选中
        assert 600519 in selected["股票代码"].values
        assert 600000 in selected["股票代码"].values

    def test_no_stocks_below_threshold(self):
        """低于阈值的股票不应被选中"""
        from strategies.fund_flow_inflow import select_inflow_stocks

        df = pd.DataFrame({
            "股票代码": [600000, 600036],
            "净额数值": [1e6, -5e8],  # 100万和 -5亿
            "最新价": [10.0, 30.0],
        })

        selected = select_inflow_stocks(df, min_inflow=1e8, top_n=10)
        assert len(selected) == 0  # 都不满足


class TestStrategyIntegration:
    """策略集成测试"""

    def test_output_format(self):
        """输出格式"""
        from strategies.fund_flow_inflow import FundFlowInflowStrategy

        df = generate_test_ohlc(200)
        strategy = FundFlowInflowStrategy()
        data = {"close": df["close"], "high": df["high"], "low": df["low"]}

        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)
        assert len(exits) == len(df)

    def test_real_data_backtest(self):
        """真实数据回测"""
        try:
            from backtest.engine import BacktestEngine, BacktestConfig
            from strategies.fund_flow_inflow import FundFlowInflowStrategy
        except ImportError:
            pytest.skip("回测引擎未就绪")

        config = BacktestConfig(
            codes=["sh.600036"],
            start_date="2024-06-01",
            end_date="2026-05-18",
            init_cash=1000000,
        )
        engine = BacktestEngine()
        result = engine.run(FundFlowInflowStrategy(), config)
        assert result is not None

    def test_with_fund_flow_file(self):
        """有资金流文件时能正常处理"""
        from strategies.fund_flow_inflow import load_latest_fund_flow, code_to_baostock

        df = load_latest_fund_flow(DATA_DIR)
        if df is None:
            pytest.skip("无资金流数据")

        # 验证代码转换
        code = code_to_baostock(600036)
        assert code == "sh.600036"
        code2 = code_to_baostock(858)
        assert code2 == "sz.000858"
