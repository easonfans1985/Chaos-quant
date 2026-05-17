"""
布林带策略
价格跌破下轨买入，突破上轨卖出
"""
import pandas as pd
import vectorbt as vbt
from typing import Dict, Optional
from backtest.base_strategy import BaseStrategy


class BollingerStrategy(BaseStrategy):
    name = "Bollinger Bands"
    description = "布林带策略：价格跌破下轨买入，突破上轨卖出"

    def __init__(self, params: Optional[Dict] = None):
        defaults = {"window": 20, "std_dev": 2.0}
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> tuple:
        close = data["close"]

        bb = vbt.BBANDS.run(
            close,
            window=self.params["window"],
            alpha=self.params["std_dev"],
        )

        # 价格跌破下轨买入（对齐列名）
        lower = bb.lower
        upper = bb.upper
        if isinstance(close, pd.DataFrame) and close.columns.tolist() != lower.columns.tolist():
            lower.columns = close.columns
            upper.columns = close.columns

        entries = close < lower
        exits = close > upper

        # 只取首次穿越信号（避免连续触发）
        entries = entries.vbt.signals.first()
        exits = exits.vbt.signals.first()

        return entries, exits
