"""
量能因子
基于成交量、换手率、成交额的变化，反映市场活跃度和资金参与度
"""
import pandas as pd
import numpy as np
from .base_factor import BaseFactor


class VolumeFactor(BaseFactor):
    name = "量能"
    description = "基于换手率和成交量变化的量能因子，放量得高分"

    def __init__(self, params=None):
        defaults = {
            "turn_window": 20,       # 换手率均值窗口
            "volume_ratio_window": 5  # 量比窗口
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def compute(self, data):
        daily = data["daily"]

        # 提取数据
        if isinstance(daily, dict):
            turn = daily.get("turn")
            volume = daily.get("volume")
        elif isinstance(daily, pd.DataFrame):
            turn = daily["turn"] if "turn" in daily.columns else None
            volume = daily["volume"] if "volume" in daily.columns else None
        else:
            return pd.Series(50.0)

        scores = pd.Series(50.0)

        # 1. 换手率得分（近期平均换手率越高越好）
        if turn is not None:
            avg_turn = turn.rolling(self.params["turn_window"]).mean().iloc[-1]
            turn_score = self._rank_to_score(avg_turn, ascending=True)

        # 2. 量比得分（最近5日均量 / 20日均量，大于1说明放量）
        if volume is not None:
            vol_short = volume.rolling(self.params["volume_ratio_window"]).mean().iloc[-1]
            vol_long = volume.rolling(self.params["volume_ratio_window"] * 4).mean().iloc[-1]
            volume_ratio = vol_short / vol_long.replace(0, np.nan)
            vol_score = self._rank_to_score(volume_ratio, ascending=True)

        # 3. 成交额变化率（近期增长得高分）
        if isinstance(daily, dict):
            amount = daily.get("amount")
        elif isinstance(daily, pd.DataFrame):
            amount = daily["amount"] if "amount" in daily.columns else None
        else:
            amount = None

        if amount is not None:
            amt_change = amount.pct_change(self.params["volume_ratio_window"]).iloc[-1]
            amt_score = self._rank_to_score(amt_change, ascending=True)

        # 综合得分（加权平均）
        components = []
        if turn is not None:
            components.append(("turn", turn_score, 0.4))
        if volume is not None:
            components.append(("vol", vol_score, 0.4))
        if amount is not None:
            components.append(("amt", amt_score, 0.2))

        if not components:
            return pd.Series(50.0)

        total_weight = sum(w for _, _, w in components)
        scores = sum(s * w for _, s, w in components) / total_weight

        return scores.fillna(50.0)
