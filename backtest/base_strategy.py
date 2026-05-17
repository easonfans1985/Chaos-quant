"""
Chaos Quant 策略基类
所有策略继承此类，实现 generate_signals 方法
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional
import pandas as pd
import vectorbt as vbt


class BaseStrategy(ABC):
    """策略抽象基类"""

    name: str = "base"
    description: str = ""

    def __init__(self, params: Optional[Dict] = None):
        self.params = params or {}

    @abstractmethod
    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> tuple:
        """
        生成买卖信号

        Args:
            data: {"open": DF, "high": DF, "low": DF, "close": DF, "volume": DF}
                  每个 DF 都是 index=DatetimeIndex, columns=股票代码

        Returns:
            (entries, exits): 两个布尔 DataFrame，True 表示触发信号
        """
        pass

    def get_param_defaults(self) -> Dict:
        """返回默认参数"""
        return {}

    def __repr__(self):
        return f"{self.__class__.__name__}(params={self.params})"
