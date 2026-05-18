#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chaos Quant - 策略测试套件

测试驱动开发：
1. 先写测试验证策略逻辑正确性
2. 验证数据质量（缺失、异常值、格式）
3. 然后实现策略，确保通过所有测试

运行方式：
  pytest tests/ -v                    # 全部测试
  pytest tests/test_macd.py -v        # 单策略测试
  pytest tests/test_data_quality.py -v # 数据质量测试
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# ============ 测试辅助工具 ============

def load_test_data(code: str = "sh.600036", freq: str = "daily", 
                   start: str = "2024-01-01", end: str = "2026-05-18"):
    """加载测试数据"""
    freq_dir = "daily" if freq == "daily" else f"minute_{freq}"
    filepath = DATA_DIR / "market" / freq_dir / f"{code}.parquet"
    if not filepath.exists():
        pytest.skip(f"数据文件不存在: {filepath}")
    
    df = pd.read_parquet(filepath)
    
    # 确保有 datetime 索引
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
        elif 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')
    
    # 过滤日期
    if start:
        df = df[df.index >= pd.Timestamp(start)]
    if end:
        df = df[df.index <= pd.Timestamp(end)]
    
    return df


def generate_test_ohlc(n: int = 200, seed: int = 42):
    """生成测试用 OHLC 数据（随机游走）"""
    np.random.seed(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n) * 0.3)
    low = close - np.abs(np.random.randn(n) * 0.3)
    open_ = close + np.random.randn(n) * 0.2
    volume = (np.random.rand(n) * 1e6).astype(int)
    
    return pd.DataFrame({
        'open': open_, 'high': high, 'low': low, 'close': close,
        'volume': volume
    }, index=dates)
