"""
RSI 超买超卖策略
RSI 低于阈值买入，高于阈值卖出
"""
import pandas as pd
import vectorbt as vbt
from typing import Dict, Optional
from backtest.base_strategy import BaseStrategy


class RSIStrategy(BaseStrategy):
    name = "RSI"
    description = "RSI 超买超卖策略：RSI 低于阈值买入，高于阈值卖出"

    def __init__(self, params: Optional[Dict] = None):
        defaults = {"window": 14, "buy_threshold": 30, "sell_threshold": 70}
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def generate_signals(self, data: Dict[str, pd.DataFrame]) -> tuple:
        close = data["close"]

        rsi = vbt.RSI.run(close, window=self.params["window"])

        entries = rsi.rsi_crossed_below(self.params["buy_threshold"])
        exits = rsi.rsi_crossed_above(self.params["sell_threshold"])

        return entries, exits
