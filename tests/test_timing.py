#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第六批：市场择时 测试套件
#22 指数估值择时 / #23 北向资金择时 / #24 融资余额择时
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.conftest import generate_test_ohlc

DATA_DIR = Path(__file__).parent.parent / "data"


class TestValuationTiming:
    """#22 指数估值择时"""

    def test_pe_percentile_timing(self):
        from strategies.market_valuation import get_valuation_level

        assert get_valuation_level(0.1) == "very_cheap"
        assert get_valuation_level(0.25) == "cheap"
        assert get_valuation_level(0.5) == "normal"
        assert get_valuation_level(0.75) == "expensive"
        assert get_valuation_level(0.95) == "very_expensive"

    def test_position_by_valuation(self):
        from strategies.market_valuation import get_target_position

        assert get_target_position(0.1) == 1.0   # 100%
        assert get_target_position(0.5) == 0.65   # 65%
        assert get_target_position(0.95) == 0.1   # 10%

    def test_strategy_output(self):
        from strategies.market_valuation import MarketValuationStrategy

        df = generate_test_ohlc(200)
        strategy = MarketValuationStrategy()
        data = {"close": df["close"]}
        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)


class TestNorthboundTiming:
    """#23 北向资金择时"""

    def test_consecutive_flow_detection(self):
        from strategies.market_northbound import detect_flow_regime

        flow = pd.Series([1e8, 2e8, 3e8, 4e8, 5e8])
        assert detect_flow_regime(flow, window=5) == "bullish"

        flow2 = pd.Series([-1e8, -2e8, -3e8, -4e8, -5e8])
        assert detect_flow_regime(flow2, window=5) == "bearish"

        flow3 = pd.Series([1e8, -1e8, 2e8, -2e8, 1e8])
        assert detect_flow_regime(flow3, window=5) == "neutral"

    def test_target_position(self):
        from strategies.market_northbound import get_northbound_position

        assert get_northbound_position("bullish") == 0.8
        assert get_northbound_position("bearish") == 0.3
        assert get_northbound_position("neutral") == 0.5

    def test_strategy_output(self):
        from strategies.market_northbound import NorthboundTimingStrategy

        df = generate_test_ohlc(200)
        strategy = NorthboundTimingStrategy()
        data = {"close": df["close"]}
        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)


class TestMarginTiming:
    """#24 融资余额择时"""

    def test_margin_growth_rate(self):
        from strategies.market_margin import calculate_margin_growth

        balance = pd.Series([1e10, 1.01e10, 1.03e10, 1.06e10])
        growth = calculate_margin_growth(balance, window=3)

        # 3日增速: (1.06e10 - 1.01e10) / 1.01e10 ≈ 4.95%
        assert growth.iloc[-1] > 0.03

    def test_overheat_detection(self):
        from strategies.market_margin import is_market_overheated

        growth = 0.05  # 5% 增速
        assert is_market_overheated(growth, threshold=0.03) == True
        assert is_market_overheated(0.01, threshold=0.03) == False

    def test_panic_detection(self):
        from strategies.market_margin import is_market_panic

        growth = -0.05
        assert is_market_panic(growth, threshold=-0.03) == True

    def test_target_position(self):
        from strategies.market_margin import get_margin_position

        assert get_margin_position(0.05) == 0.3   # 过热
        assert get_margin_position(-0.05) == 0.2   # 恐慌
        assert get_margin_position(0.01) == 0.6     # 正常

    def test_strategy_output(self):
        from strategies.market_margin import MarginTimingStrategy

        df = generate_test_ohlc(200)
        strategy = MarginTimingStrategy()
        data = {"close": df["close"]}
        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)
