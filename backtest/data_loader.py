"""
Chaos Quant 数据加载器
将 Parquet 数据加载为 VectorBT 兼容格式
"""
import os
import glob
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Union
from loguru import logger


class DataLoader:
    """从本地 Parquet 文件加载行情数据，输出 VectorBT 兼容的 DataFrame"""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.market_dir = self.data_dir / "market"
        self.daily_dir = self.market_dir / "daily"
        self.minute_dirs = {
            5: self.market_dir / "minute_5",
            15: self.market_dir / "minute_15",
            30: self.market_dir / "minute_30",
            60: self.market_dir / "minute_60",
        }

    def load_single(
        self,
        code: str,
        freq: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        加载单只股票数据

        Args:
            code: 股票代码，如 "sh.600000" 或 "600000"（自动补全）
            freq: 频率 "daily" / "minute_5" / "minute_15" / "minute_30" / "minute_60"
            start_date: 起始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"
            columns: 需要的列，None 则返回全部

        Returns:
            DataFrame，index 为 DatetimeIndex
        """
        # 标准化代码
        code = self._normalize_code(code)

        # 定位文件
        filepath = self._find_file(code, freq)
        if filepath is None:
            raise FileNotFoundError(f"找不到 {code} 的 {freq} 数据文件")

        df = pd.read_parquet(filepath)

        # 确保 date 列是 DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date")
            elif "datetime" in df.columns:
                df["datetime"] = pd.to_datetime(df["datetime"])
                df = df.set_index("datetime")

        # 过滤日期
        if start_date:
            df = df[df.index >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df.index <= pd.Timestamp(end_date)]

        # 选择列
        if columns:
            available = [c for c in columns if c in df.columns]
            df = df[available]

        return df

    def load_multiple(
        self,
        codes: List[str],
        freq: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        column: str = "close",
    ) -> pd.DataFrame:
        """
        加载多只股票的指定列，合并为宽表（VectorBT 推荐格式）

        Returns:
            DataFrame, index=DatetimeIndex, columns=股票代码
        """
        frames = {}
        for code in codes:
            try:
                df = self.load_single(code, freq=freq, start_date=start_date, end_date=end_date)
                if column in df.columns:
                    frames[code] = df[column]
                else:
                    logger.warning(f"{code} 缺少列 {column}")
            except FileNotFoundError as e:
                logger.warning(str(e))

        if not frames:
            raise ValueError("没有成功加载任何数据")

        result = pd.DataFrame(frames)
        result.index.name = "date"
        return result

    def load_all(
        self,
        freq: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        column: str = "close",
        max_stocks: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        加载全市场所有股票数据为宽表

        Args:
            max_stocks: 限制加载数量（调试用）
        """
        files = sorted(glob.glob(str(self._get_freq_dir(freq) / "*.parquet")))
        if max_stocks:
            files = files[:max_stocks]

        codes = [Path(f).stem for f in files]
        return self.load_multiple(codes, freq=freq, start_date=start_date, end_date=end_date, column=column)

    def load_index(
        self,
        index_code: str = "sh.000300",
        freq: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """加载指数数据"""
        return self.load_single(index_code, freq=freq, start_date=start_date, end_date=end_date)

    def list_stocks(self, freq: str = "daily") -> List[str]:
        """列出所有可用的股票代码"""
        freq_dir = self._get_freq_dir(freq)
        if not freq_dir.exists():
            return []
        return sorted([f.stem for f in freq_dir.glob("*.parquet")])

    def load_for_vbt(
        self,
        codes: Union[str, List[str]],
        freq: str = "daily",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """
        加载数据为 VectorBT 直接可用的 dict 格式

        Returns:
            {"open": DataFrame, "high": DataFrame, "low": DataFrame,
             "close": DataFrame, "volume": DataFrame}
        """
        if isinstance(codes, str):
            codes = [codes]

        result = {}
        for col in ["open", "high", "low", "close", "volume"]:
            df = self.load_multiple(codes, freq=freq, start_date=start_date, end_date=end_date, column=col)
            result[col] = df

        return result

    # ---- 内部方法 ----

    def _normalize_code(self, code: str) -> str:
        """标准化股票代码：600000 → sh.600000"""
        if "." in code:
            return code.lower()
        num = code.zfill(6)
        if num.startswith(("6", "5")):
            return f"sh.{num}"
        elif num.startswith(("0", "3", "1")):
            return f"sz.{num}"
        elif num.startswith("4") or num.startswith("8"):
            return f"bj.{num}"
        return num

    def _get_freq_dir(self, freq: str) -> Path:
        if freq == "daily":
            return self.daily_dir
        return self.minute_dirs.get(int(freq.replace("minute_", "")), self.daily_dir)

    def _find_file(self, code: str, freq: str) -> Optional[str]:
        freq_dir = self._get_freq_dir(freq)
        filepath = freq_dir / f"{code}.parquet"
        if filepath.exists():
            return str(filepath)
        return None
