"""
双均线交叉策略
短期均线上穿长期均线买入，下穿卖出
"""
import pandas as pd
import vectorbt as vbt
from typing import Dict, Optional
from backtest.base_strategy import BaseStrategy


class SMACrossStrategy(BaseStrategy):
    name = "SMA Cross"
    description = "双均线交叉策略：短期均线上穿长期均线买入，下穿卖出"

    def __init__(self, params: Optional[Dict] = None):
        defaults = {"fast_window": 10, "slow_window": 30}
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> tuple:
        close = data["close"]

        fast_sma = vbt.MA.run(close, window=self.params["fast_window"])
        slow_sma = vbt.MA.run(close, window=self.params["slow_window"])

        entries = fast_sma.ma_crossed_above(slow_sma)
        exits = fast_sma.ma_crossed_below(slow_sma)

        return entries, exits
