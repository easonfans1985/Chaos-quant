#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据质量测试套件
验证所有数据文件的完整性、格式、缺失值等
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"

# 测试用的代表性股票
TEST_CODES = ["sh.600036", "sh.600519", "sz.000858", "sz.000001"]
TEST_INDEX = "sh.000300"


class TestDailyData:
    """日线数据质量测试"""
    
    @pytest.fixture
    def daily_dir(self):
        return DATA_DIR / "market" / "daily"
    
    def test_daily_files_exist(self, daily_dir):
        """日线文件是否存在"""
        files = list(daily_dir.glob("*.parquet"))
        assert len(files) > 5000, f"日线文件数 {len(files)} < 5000"
    
    def test_daily_data_format(self, daily_dir):
        """日线数据格式是否正确"""
        for code in TEST_CODES:
            filepath = daily_dir / f"{code}.parquet"
            if not filepath.exists():
                continue
            
            df = pd.read_parquet(filepath)
            
            # 必须有这些列
            required = ["open", "high", "low", "close", "volume"]
            for col in required:
                assert col in df.columns, f"{code} 缺少列 {col}, 有: {df.columns.tolist()}"
            
            # 数值列应该是数字
            for col in required:
                if col in df.columns:
                    assert pd.api.types.is_numeric_dtype(df[col]), \
                        f"{code} 列 {col} 类型={df[col].dtype}, 应为数值"
            
            # 不能有大量 NaN
            for col in required:
                if col in df.columns:
                    nan_pct = df[col].isna().mean()
                    assert nan_pct < 0.1, f"{code} 列 {col} NaN率={nan_pct:.2%}"
    
    def test_daily_no_zero_prices(self, daily_dir):
        """日线价格不能为0（除退市外）"""
        for code in TEST_CODES:
            filepath = daily_dir / f"{code}.parquet"
            if not filepath.exists():
                continue
            df = pd.read_parquet(filepath)
            if 'close' in df.columns:
                zeros = (df['close'] == 0).sum()
                assert zeros == 0, f"{code} 有 {zeros} 个0价格"
    
    def test_daily_date_range(self, daily_dir):
        """日线日期范围应为 2021-01 ~ 今天"""
        filepath = daily_dir / "sh.600036.parquet"
        if not filepath.exists():
            pytest.skip("sh.600036 日线不存在")
        
        df = pd.read_parquet(filepath)
        dates = pd.to_datetime(df['date'] if 'date' in df.columns else df.index)
        
        assert dates.min() <= pd.Timestamp("2021-02-01"), \
            f"日线起始日期 {dates.min()} 晚于 2021-02-01"
        assert dates.max() >= pd.Timestamp("2026-05-01"), \
            f"日线结束日期 {dates.max()} 早于 2026-05-01"
    
    def test_daily_ohlc_relation(self, daily_dir):
        """OHLC 关系：high >= max(open,close), low <= min(open,close)"""
        for code in TEST_CODES:
            filepath = daily_dir / f"{code}.parquet"
            if not filepath.exists():
                continue
            df = pd.read_parquet(filepath)
            
            for col in ['open', 'high', 'low', 'close']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            if all(c in df.columns for c in ['open', 'high', 'low', 'close']):
                violations_high = (df['high'] < df[['open', 'close']].max(axis=1)).sum()
                violations_low = (df['low'] > df[['open', 'close']].min(axis=1)).sum()
                assert violations_high == 0, f"{code} 有 {violations_high} 条 high < max(open,close)"
                assert violations_low == 0, f"{code} 有 {violations_low} 条 low > min(open,close)"


class TestMinuteData:
    """分钟线数据质量测试"""
    
    def test_minute5_files_exist(self):
        """5分钟线文件是否存在"""
        m5_dir = DATA_DIR / "market" / "minute_5"
        files = list(m5_dir.glob("*.parquet"))
        assert len(files) > 5000, f"5分钟线文件数 {len(files)} < 5000"
    
    def test_minute5_data_format(self):
        """5分钟线数据格式"""
        filepath = DATA_DIR / "market" / "minute_5" / "sh.600036.parquet"
        if not filepath.exists():
            pytest.skip("sh.600036 5分钟线不存在")
        
        df = pd.read_parquet(filepath)
        required = ["open", "high", "low", "close", "volume"]
        for col in required:
            assert col in df.columns or col in ['turnover_volume'], \
                f"5分钟线缺少列 {col}"
        
        # 行数至少应该有几万行（2年×240天×48条）
        assert len(df) > 10000, f"5分钟线只有 {len(df)} 行，太少"
    
    def test_minute30_files_exist(self):
        """30分钟线文件是否存在"""
        m30_dir = DATA_DIR / "market" / "minute_30"
        files = list(m30_dir.glob("*.parquet"))
        assert len(files) > 5000, f"30分钟线文件数 {len(files)} < 5000"
    
    def test_minute30_date_range(self):
        """30分钟线日期范围"""
        filepath = DATA_DIR / "market" / "minute_30" / "sh.600036.parquet"
        if not filepath.exists():
            pytest.skip("sh.600036 30分钟线不存在")
        
        df = pd.read_parquet(filepath)
        
        # 找日期列
        if 'datetime' in df.columns:
            dates = pd.to_datetime(df['datetime'])
        elif isinstance(df.index, pd.DatetimeIndex):
            dates = df.index
        elif 'date' in df.columns:
            dates = pd.to_datetime(df['date'])
        else:
            pytest.skip("30分钟线无日期列")
        
        assert dates.max() >= pd.Timestamp("2026-04-01"), \
            f"30分钟线结束 {dates.max()} 早于 2026-04-01"


class TestFundFlowData:
    """资金流数据质量测试"""
    
    def test_ths_fund_flow_files(self):
        """同花顺资金流文件"""
        cf_dir = DATA_DIR / "money_flow" / "capital_flow"
        ths_files = list(cf_dir.glob("ths_fund_flow_*.parquet"))
        assert len(ths_files) >= 4, f"同花顺资金流文件 {len(ths_files)} < 4"
        
        # 检查第一个文件
        df = pd.read_parquet(ths_files[0])
        assert len(df) > 4000, f"同花顺资金流只有 {len(df)} 条，应>4000"
    
    def test_ths_big_deal(self):
        """大单追踪"""
        bd_files = list((DATA_DIR / "money_flow" / "capital_flow").glob("ths_big_deal_*.parquet"))
        assert len(bd_files) >= 1, "大单追踪文件不存在"
        df = pd.read_parquet(bd_files[0])
        assert len(df) > 1000, f"大单追踪只有 {len(df)} 条"
    
    def test_northbound_data(self):
        """北向资金"""
        nb_dir = DATA_DIR / "money_flow" / "northbound"
        files = list(nb_dir.glob("*.parquet"))
        assert len(files) >= 2, "北向资金文件不足（应有沪股通+深股通）"
    
    def test_industry_flow(self):
        """行业资金流"""
        ind_files = list((DATA_DIR / "money_flow" / "capital_flow").glob("ths_industry_*.parquet"))
        assert len(ind_files) >= 4, f"行业资金流文件 {len(ind_files)} < 4"


class TestFundamentalData:
    """基本面数据质量测试"""
    
    def test_financial_indicator(self):
        """财务指标"""
        fi_dir = DATA_DIR / "fundamental" / "financial_indicator"
        files = list(fi_dir.glob("*.parquet"))
        assert len(files) > 5000, f"财务指标文件 {len(files)} < 5000"
    
    def test_financial_report(self):
        """财务报表"""
        fr_dir = DATA_DIR / "fundamental" / "financial_report"
        files = list(fr_dir.glob("*.parquet"))
        assert len(files) > 700, f"财务报表文件 {len(files)} < 700"
    
    def test_dividend(self):
        """分红数据"""
        div_dir = DATA_DIR / "fundamental" / "dividend"
        files = list(div_dir.glob("*.parquet"))
        assert len(files) > 2000, f"分红文件 {len(files)} < 2000"


class TestValuationData:
    """估值数据质量测试"""
    
    def test_stock_pe(self):
        """个股PE"""
        pe_dir = DATA_DIR / "valuation" / "stock_pe"
        files = list(pe_dir.glob("*.parquet"))
        assert len(files) > 5000, f"个股PE文件 {len(files)} < 5000"
    
    def test_index_pe(self):
        """指数PE"""
        pe_files = list((DATA_DIR / "valuation").glob("pe_*.parquet"))
        assert len(pe_files) >= 4, f"指数PE文件 {len(pe_files)} < 4"
