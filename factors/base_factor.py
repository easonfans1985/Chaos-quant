"""
因子基类
所有因子继承此类，实现 compute() 方法
"""
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from typing import Dict, Optional


class BaseFactor(ABC):
    """因子抽象基类"""

    name: str = "base"
    description: str = ""

    def __init__(self, params: Optional[Dict] = None):
        self.params = params or {}

    @abstractmethod
    def compute(self, data: Dict[str, pd.DataFrame]) -> pd.Series:
        """
        计算因子得分

        Args:
            data: 数据字典，包含以下 key：
                - "daily": DataFrame, columns=股票代码, index=DatetimeIndex
                    包含 open/high/low/close/volume/amount/turn/pctChg 等列
                    每列是一个股票的该字段值（宽表格式）
                - "index_daily": 指数日线（可选）
                - "pe": 指数PE（可选）
                - "pb": 指数PB（可选）
                - "northbound": 北向资金（可选）
                - "margin": 融资融券（可选）

        Returns:
            pd.Series, index=股票代码, values=0~100 的得分
            100 分表示最好（如动量最强、估值最低、量能最大）
        """
        pass

    def _rank_to_score(self, series: pd.Series, ascending: bool = True) -> pd.Series:
        """
        将原始值转换为 0-100 分（百分位排名）

        Args:
            series: 原始值
            ascending: True=值越大分数越高，False=值越小分数越高
        """
        if series.std() == 0 or series.isna().all():
            return pd.Series(50.0, index=series.index)

        ranked = series.rank(pct=True, ascending=ascending, na_option="keep")
        scores = ranked * 100
        return scores.fillna(50.0)  # 缺失值给中间分

    def _normalize(self, series: pd.Series) -> pd.Series:
        """Z-score 标准化"""
        if series.std() == 0:
            return pd.Series(0.0, index=series.index)
        return (series - series.mean()) / series.std()

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name}, params={self.params})"
