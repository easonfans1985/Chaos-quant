#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
第七批：高级策略 测试套件
#9 大单追踪 / #14 限售解禁规避 / #16 ETF折溢价套利
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.conftest import generate_test_ohlc


class TestBigDealTrack:
    """#9 大单追踪"""

    def test_parse_big_deal(self):
        from strategies.big_deal_track import parse_big_deal_data

        df = pd.DataFrame({
            "股票代码": [600036, 600519],
            "交易价格": [30.5, 1500.0],
            "成交量": [100000, 50000],
        })
        result = parse_big_deal_data(df)
        assert len(result) == 2

    def test_select_big_buy(self):
        from strategies.big_deal_track import select_big_buy_stocks

        df = pd.DataFrame({
            "code": [600036, 600036, 600519, 600519],
            "direction": ["买入", "卖出", "买入", "买入"],
            "amount": [1e8, 5e7, 2e8, 3e8],
        })
        selected = select_big_buy_stocks(df, top_n=2)
        assert len(selected) <= 2
        # 600519 买入额 5亿 > 600036 买入额 1亿
        assert 600519 in selected

    def test_strategy_output(self):
        from strategies.big_deal_track import BigDealTrackStrategy

        df = generate_test_ohlc(200)
        strategy = BigDealTrackStrategy()
        data = {"close": df["close"]}
        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)


class TestLockupAvoid:
    """#14 限售解禁规避"""

    def test_lockup_date_detection(self):
        from strategies.lockup_avoid import days_to_lockup

        today = pd.Timestamp("2026-05-18")
        lockup_date = pd.Timestamp("2026-05-22")
        days = days_to_lockup(today, lockup_date)
        assert days == 4

    def test_should_avoid(self):
        from strategies.lockup_avoid import should_avoid

        assert should_avoid(days_to_lockup=3, avoid_before=5) == True
        assert should_avoid(days_to_lockup=10, avoid_before=5) == False
        assert should_avoid(days_to_lockup=-2, avoid_before=5, avoid_after=10) == True

    def test_strategy_output(self):
        from strategies.lockup_avoid import LockupAvoidStrategy

        df = generate_test_ohlc(200)
        strategy = LockupAvoidStrategy()
        data = {"close": df["close"]}
        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)


class TestETFPremium:
    """#16 ETF折溢价套利"""

    def test_premium_calculation(self):
        from strategies.etf_premium import calculate_premium

        price = 3.05
        nav = 3.00
        premium = calculate_premium(price, nav)
        assert premium == pytest.approx(0.0167, abs=0.001)

    def test_premium_signal(self):
        from strategies.etf_premium import generate_premium_signal

        # 溢价 > 0.5%
        assert generate_premium_signal(0.01, threshold=0.005) == "sell_etf"
        # 折价 > 0.5%
        assert generate_premium_signal(-0.01, threshold=0.005) == "buy_etf"
        # 正常
        assert generate_premium_signal(0.002, threshold=0.005) == "hold"

    def test_strategy_output(self):
        from strategies.etf_premium import ETFPremiumStrategy

        df = generate_test_ohlc(200)
        strategy = ETFPremiumStrategy()
        data = {"close": df["close"]}
        entries, exits = strategy.generate_signals(data)
        assert len(entries) == len(df)
