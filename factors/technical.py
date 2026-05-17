"""
技术因子
基于 RSI、布林带位置、MACD 等技术指标
"""
import pandas as pd
import numpy as np
from .base_factor import BaseFactor


class TechnicalFactor(BaseFactor):
    name = "技术"
    description = "基于RSI/布林带位置/MACD的综合技术因子"

    def __init__(self, params=None):
        defaults = {
            "rsi_window": 14,
            "bb_window": 20,
            "bb_std": 2.0,
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def compute(self, data):
        daily = data["daily"]

        # 提取 close
        if isinstance(daily, dict):
            close = daily.get("close")
        elif isinstance(daily, pd.DataFrame):
            close = daily["close"]
        else:
            close = daily

        # 确保 DataFrame
        if not isinstance(close, pd.DataFrame):
            return pd.Series(50.0)

        # 1. RSI 得分（RSI 在 30-70 之间较好，太低超卖太高超买）
        rsi = self._calc_rsi(close, self.params["rsi_window"])
        # RSI=50 得100分，偏离50越远分越低
        rsi_score = 100 - (rsi - 50).abs() * 2
        rsi_score = rsi_score.clip(0, 100)

        # 2. 布林带位置得分（在中轨附近较好）
        bb_score = self._calc_bb_position(close)

        # 综合加权
        scores = rsi_score * 0.5 + bb_score * 0.5
        return scores.fillna(50.0)

    def _calc_rsi(self, close: pd.DataFrame, window: int) -> pd.DataFrame:
        """计算 RSI"""
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(window).mean()
        avg_loss = loss.rolling(window).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]

    def _calc_bb_position(self, close: pd.DataFrame) -> pd.Series:
        """计算布林带位置得分（0=下轨，50=中轨，100=上轨）"""
        window = self.params["bb_window"]
        num_std = self.params["bb_std"]

        sma = close.rolling(window).mean()
        std = close.rolling(window).std()
        upper = sma + num_std * std
        lower = sma - num_std * std

        latest_close = close.iloc[-1]
        latest_upper = upper.iloc[-1]
        latest_lower = lower.iloc[-1]
        latest_sma = sma.iloc[-1]

        # 布林带宽度
        bb_width = latest_upper - latest_lower
        # 位置：(close - lower) / (upper - lower)
        position = (latest_close - latest_lower) / bb_width.replace(0, np.nan)

        # 得分：中轨附近(0.3-0.7)最高分，贴近上下轨低分
        score = 100 - (position - 0.5).abs() * 200
        return score.clip(0, 100).fillna(50.0)
