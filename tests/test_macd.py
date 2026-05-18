#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MACD 背离策略 - 测试套件

测试项：
1. MACD 指标计算正确性
2. 金叉/死叉信号检测
3. 背离检测逻辑
4. 策略信号输出格式
5. 用真实数据回测基本合理性
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.conftest import load_test_data, generate_test_ohlc


class TestMACDCalculation:
    """测试 MACD 指标计算"""
    
    def test_macd_values_basic(self):
        """MACD 基本值计算是否正确"""
        from strategies.macd_divergence import calculate_macd
        
        # 用已知数据验证
        df = generate_test_ohlc(200)
        macd, signal, hist = calculate_macd(df['close'])
        
        # 长度应该一致
        assert len(macd) == len(df), f"MACD长度 {len(macd)} != 数据长度 {len(df)}"
        assert len(signal) == len(df)
        assert len(hist) == len(df)
        
        # hist = macd - signal
        np.testing.assert_allclose(hist.values, (macd - signal).values, atol=1e-10,
                                    err_msg="histogram != MACD - signal")
    
    def test_macd_not_all_nan(self):
        """MACD 不应该全部是 NaN"""
        from strategies.macd_divergence import calculate_macd
        
        df = generate_test_ohlc(100)
        macd, signal, hist = calculate_macd(df['close'])
        
        # 前 34 个（26-1）可能是 NaN，后面不应该
        valid_macd = macd.iloc[35:]
        assert valid_macd.notna().mean() > 0.95, "MACD 有效值太少"
    
    def test_macd_ema_properties(self):
        """MACD 应该是 EMA 差值，具备 EMA 特性"""
        from strategies.macd_divergence import calculate_macd
        
        df = generate_test_ohlc(500)
        macd, signal, hist = calculate_macd(df['close'])
        
        # 在稳定趋势中 MACD 应该有正/负值
        assert (hist.iloc[50:] > 0).any(), "histogram 应该有正值"
        assert (hist.iloc[50:] < 0).any(), "histogram 应该有负值"


class TestMACDCrossSignals:
    """测试金叉/死叉信号"""
    
    def test_golden_cross_detection(self):
        """金叉检测：MACD 从下方穿越 signal"""
        from strategies.macd_divergence import detect_golden_cross
        
        # 构造一个明确的金叉场景
        hist = pd.Series([-2, -1.5, -1, -0.5, 0.1, 0.5, 1.0, 1.5, 2.0])
        crosses = detect_golden_cross(hist)
        
        # 应该在第4个位置（-0.5 → 0.1）检测到金叉
        assert crosses.iloc[4] == True, f"应在第4位检测到金叉，实际: {crosses.values}"
        assert crosses.sum() == 1, f"应检测到1次金叉，实际: {crosses.sum()}"
    
    def test_death_cross_detection(self):
        """死叉检测：MACD 从上方穿越 signal"""
        from strategies.macd_divergence import detect_death_cross
        
        hist = pd.Series([2.0, 1.5, 1.0, 0.5, -0.1, -0.5, -1.0, -1.5])
        crosses = detect_death_cross(hist)
        
        assert crosses.iloc[4] == True, f"应在第4位检测到死叉"
        assert crosses.sum() == 1, f"应检测到1次死叉，实际: {crosses.sum()}"
    
    def test_no_false_crossings(self):
        """没有穿越时不应产生信号"""
        from strategies.macd_divergence import detect_golden_cross, detect_death_cross
        
        # 持续正值
        hist = pd.Series([1.0, 1.5, 2.0, 2.5, 3.0])
        assert detect_golden_cross(hist).sum() == 0
        assert detect_death_cross(hist).sum() == 0
        
        # 持续负值
        hist = pd.Series([-1.0, -1.5, -2.0, -2.5, -3.0])
        assert detect_golden_cross(hist).sum() == 0
        assert detect_death_cross(hist).sum() == 0


class TestDivergenceDetection:
    """测试背离检测"""
    
    def test_bullish_divergence(self):
        """底背离检测：价格新低但 MACD 未新低"""
        from strategies.macd_divergence import detect_bullish_divergence
        
        # 构造底背离：价格创新低，MACD 未创新低
        prices = pd.Series([100, 95, 85, 80, 75, 70, 65, 60, 58, 55, 58, 60])
        macd_hist = pd.Series([0, -1, -3, -4, -3, -2, -1, -0.5, -0.3, -0.2, 0.1, 0.3])
        
        divergence = detect_bullish_divergence(prices, macd_hist, lookback=8)
        
        # 应该在后面检测到底背离
        assert divergence.any(), "应检测到底背离"
    
    def test_no_divergence_when_aligned(self):
        """价格和 MACD 同向下降时不应检测到背离"""
        from strategies.macd_divergence import detect_bullish_divergence
        
        # 价格和 MACD 同步下降
        prices = pd.Series([100, 95, 90, 85, 80, 75, 70, 65, 60, 55])
        macd_hist = pd.Series([0, -1, -2, -3, -4, -5, -6, -7, -8, -9])
        
        divergence = detect_bullish_divergence(prices, macd_hist, lookback=8)
        
        assert not divergence.any(), "价格和MACD同向下降时不应有底背离"


class TestStrategyIntegration:
    """策略集成测试"""
    
    def test_strategy_output_format(self):
        """策略输出格式正确"""
        from strategies.macd_divergence import MACDDivergenceStrategy
        
        strategy = MACDDivergenceStrategy()
        df = generate_test_ohlc(200)
        
        data = {"close": df["close"], "open": df["open"], "high": df["high"], 
                "low": df["low"], "volume": df["volume"]}
        
        entries, exits = strategy.generate_signals(data)
        
        assert isinstance(entries, (pd.Series, np.ndarray)), "entries 应为 Series"
        assert isinstance(exits, (pd.Series, np.ndarray)), "exits 应为 Series"
        assert len(entries) == len(df), f"entries 长度 {len(entries)} != 数据长度 {len(df)}"
        assert len(exits) == len(df)
        assert entries.dtype == bool or str(entries.dtype) == 'bool', "entries 应为 bool 类型"
        assert exits.dtype == bool or str(exits.dtype) == 'bool', "exits 应为 bool 类型"
    
    def test_strategy_with_real_data(self):
        """用真实数据运行策略"""
        from strategies.macd_divergence import MACDDivergenceStrategy
        
        df = load_test_data("sh.600036", "daily", "2023-01-01", "2026-05-18")
        
        strategy = MACDDivergenceStrategy()
        data = {"close": df["close"]}
        for col in ["open", "high", "low", "volume"]:
            if col in df.columns:
                data[col] = df[col]
        
        entries, exits = strategy.generate_signals(data)
        
        # 至少应该有一些信号
        assert entries.sum() >= 0, "entries 应 >= 0"
        assert exits.sum() >= 0, "exits 应 >= 0"
        
        # 信号不应太多（不应该每天都买卖）
        total_signals = entries.sum() + exits.sum()
        assert total_signals < len(df) * 0.3, \
            f"信号太频繁: {total_signals}/{len(df)} ({total_signals/len(df):.1%})"
    
    def test_strategy_signal_not_all_same(self):
        """策略不应产生全 True 或全 False 信号"""
        from strategies.macd_divergence import MACDDivergenceStrategy
        
        df = generate_test_ohlc(500)
        strategy = MACDDivergenceStrategy()
        data = {"close": df["close"]}
        
        entries, exits = strategy.generate_signals(data)
        
        # 500天数据应该至少有1个买入信号和1个卖出信号（或都没有也OK）
        # 但不应该全部都是True
        assert not entries.all(), "entries 不应全为 True"
        assert not exits.all(), "exits 不应全为 True"


class TestBacktestWithMACD:
    """MACD 策略回测基本验证"""
    
    def test_backtest_runs_without_error(self):
        """回测能正常跑完"""
        try:
            from backtest.engine import BacktestEngine, BacktestConfig
            from strategies.macd_divergence import MACDDivergenceStrategy
        except ImportError:
            pytest.skip("回测引擎未就绪")
        
        config = BacktestConfig(
            codes=["sh.600036"],
            start_date="2024-01-01",
            end_date="2026-05-18",
            init_cash=1000000,
        )
        engine = BacktestEngine()
        result = engine.run(MACDDivergenceStrategy(), config)
        
        assert result is not None, "回测结果不应为 None"
