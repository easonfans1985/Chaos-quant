"""
动量因子
基于历史涨跌幅排名，反映价格趋势强度
"""
import pandas as pd
import numpy as np
from .base_factor import BaseFactor


class MomentumFactor(BaseFactor):
    name = "动量"
    description = "基于历史涨跌幅的动量因子，N日涨幅越大分数越高"

    def __init__(self, params=None):
        defaults = {"window": 20}  # 默认20日动量
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def compute(self, data):
        daily = data["daily"]

        # 取每只股票的 close 列（宽表）
        if isinstance(daily, dict):
            close = daily.get("close")
        elif isinstance(daily, pd.DataFrame):
            close = daily["close"] if "close" in daily.columns else daily
        else:
            close = daily

        window = self.params["window"]

        # 如果是长表（index=date, columns=[code, close]），先转宽表
        if isinstance(close.index, pd.DatetimeIndex) and close.ndim == 1:
            # 单只股票
            pct_change = close.pct_change(window).iloc[-1]
            return self._rank_to_score(pd.Series({close.name or "single": pct_change}))

        # 宽表：每列一只股票
        if isinstance(close, pd.DataFrame):
            pct_change = close.pct_change(window).iloc[-1]
        else:
            pct_change = close.pct_change(window).iloc[-1]

        return self._rank_to_score(pct_change, ascending=True)
