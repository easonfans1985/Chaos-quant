"""
因子计算引擎
加载原始数据 → 批量计算所有因子 → 返回因子得分矩阵
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from loguru import logger

from backtest.data_loader import DataLoader
from factors.base_factor import BaseFactor


class FactorEngine:
    """因子计算引擎"""

    def __init__(self, data_dir: str = "./data"):
        self.loader = DataLoader(data_dir)
        self._cache = {}

    def load_data(
        self,
        codes: Optional[List[str]] = None,
        start_date: str = "2021-01-01",
        end_date: str = "2026-05-15",
        freq: str = "daily",
    ) -> Dict[str, pd.DataFrame]:
        """
        加载选股所需的全量数据

        Returns:
            {
                "close": DataFrame,    # 收盘价宽表
                "turn": DataFrame,     # 换手率宽表
                "volume": DataFrame,   # 成交量宽表
                "amount": DataFrame,   # 成交额宽表
                "pctChg": DataFrame,   # 涨跌幅宽表
                "valuation": dict,     # PE/PB数据
                "northbound": DataFrame,  # 北向资金
                "margin": DataFrame,   # 融资融券
            }
        """
        logger.info(f"📥 加载数据: {len(codes) if codes else '全市场'} 只, {start_date} ~ {end_date}")

        # 如果没有指定股票，取全市场
        if codes is None:
            codes = self.loader.list_stocks(freq=freq)
            logger.info(f"  全市场共 {len(codes)} 只")

        result = {}

        # 加载 OHLCV 数据（宽表）
        for col in ["close", "open", "high", "low", "volume", "amount", "turn", "pctChg"]:
            try:
                df = self.loader.load_multiple(codes, freq=freq, start_date=start_date, end_date=end_date, column=col)
                result[col] = df
                logger.info(f"  ✅ {col}: {df.shape}")
            except Exception as e:
                logger.warning(f"  ❌ {col}: {e}")

        # 加载估值数据
        valuation = {}
        import glob
        from pathlib import Path
        val_dir = Path(self.loader.data_dir) / "valuation"
        for f in sorted(glob.glob(str(val_dir / "*.parquet"))):
            fname = Path(f).stem
            try:
                df = pd.read_parquet(f)
                valuation[fname] = df
            except:
                pass
        if valuation:
            result["valuation"] = valuation
            logger.info(f"  ✅ 估值: {len(valuation)} 文件")

        # 加载北向资金
        nb_dir = Path(self.loader.data_dir) / "money_flow" / "northbound"
        nb_frames = []
        for f in sorted(glob.glob(str(nb_dir / "*.parquet"))):
            try:
                df = pd.read_parquet(f)
                nb_frames.append(df)
            except:
                pass
        if nb_frames:
            result["northbound"] = pd.concat(nb_frames)
            logger.info(f"  ✅ 北向资金: {sum(len(df) for df in nb_frames)} 行")

        # 加载融资融券
        margin_dir = Path(self.loader.data_dir) / "money_flow" / "margin_trading"
        margin_frames = []
        for f in sorted(glob.glob(str(margin_dir / "*.parquet"))):
            try:
                df = pd.read_parquet(f)
                margin_frames.append(df)
            except:
                pass
        if margin_frames:
            result["margin"] = pd.concat(margin_frames)
            logger.info(f"  ✅ 融资融券: {sum(len(df) for df in margin_frames)} 行")

        # daily 完整数据（给因子用）
        # 因子通过 data["close"] 等直接访问宽表
        # data["valuation"] / data["northbound"] / data["margin"] 是额外数据
        # "daily" key 保留给需要整体 data dict 的因子

        return result

    def compute_factors(
        self,
        data: Dict,
        factors: List[BaseFactor],
    ) -> Dict[str, pd.Series]:
        """
        批量计算所有因子

        Returns:
            {因子名: pd.Series(股票代码 → 0~100分)}
        """
        results = {}
        for factor in factors:
            try:
                scores = factor.compute(data)
                if isinstance(scores, (int, float)):
                    # 标量（如估值因子），需要扩展到所有股票
                    codes = data.get("close", data.get("daily", {}))
                    if isinstance(codes, pd.DataFrame):
                        codes = codes.columns
                    scores = pd.Series(float(scores), index=codes)
                results[factor.name] = scores
                logger.info(f"  ✅ {factor.name}: mean={scores.mean():.1f}, std={scores.std():.1f}")
            except Exception as e:
                logger.error(f"  ❌ {factor.name}: {e}")

        return results
