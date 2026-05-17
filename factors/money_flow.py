"""
资金因子
基于北向资金、融资融券等数据，反映市场资金面
"""
import pandas as pd
import numpy as np
from .base_factor import BaseFactor


class MoneyFlowFactor(BaseFactor):
    name = "资金"
    description = "基于北向资金和融资融券的资金面因子"

    def __init__(self, params=None):
        defaults = {
            "northbound_window": 20,  # 北向资金趋势窗口
        }
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def compute(self, data):
        daily = data.get("daily", data.get("close"))

        # 获取股票代码列表
        if isinstance(daily, dict):
            codes = daily.get("close", daily.get("volume")).columns
        elif isinstance(daily, pd.DataFrame):
            codes = daily.columns
        else:
            codes = []

        # 基础分数
        base_score = 50.0

        # 1. 北向资金趋势（如果有数据）
        northbound = data.get("northbound")
        northbound_adjust = 0.0
        if northbound is not None and isinstance(northbound, pd.DataFrame) and len(northbound) > 0:
            try:
                # 取最近N天的净流入趋势
                window = self.params["northbound_window"]
                recent = northbound.tail(window)
                if "北向资金" in recent.columns:
                    net_flow = recent["北向资金"]
                elif len(recent.columns) > 1:
                    net_flow = recent.iloc[:, -1]
                else:
                    net_flow = recent.iloc[:, 0]

                # 正流入=加分，负流入=减分
                avg_flow = net_flow.mean()
                if avg_flow > 0:
                    northbound_adjust = min(20, avg_flow / net_flow.std() * 10) if net_flow.std() > 0 else 10
                else:
                    northbound_adjust = max(-20, avg_flow / net_flow.std() * 10) if net_flow.std() > 0 else -10
            except Exception:
                pass

        # 2. 融资融券趋势（如果有数据）
        margin = data.get("margin")
        margin_adjust = 0.0
        if margin is not None and isinstance(margin, pd.DataFrame) and len(margin) > 0:
            try:
                # 融资余额上升=市场看多
                if "融资余额(元)" in margin.columns:
                    margin_bal = margin["融资余额(元)"]
                else:
                    margin_bal = margin.iloc[:, 0]

                recent_margin = margin_bal.tail(5)
                older_margin = margin_bal.tail(20).head(15)
                if len(recent_margin) > 0 and len(older_margin) > 0:
                    change = (recent_margin.mean() - older_margin.mean()) / older_margin.mean()
                    margin_adjust = change * 1000  # 放大信号
                    margin_adjust = max(-15, min(15, margin_adjust))
            except Exception:
                pass

        # 综合分数（对所有股票给同一市场级分数）
        total_score = base_score + northbound_adjust + margin_adjust
        total_score = max(0, min(100, total_score))

        return pd.Series(total_score, index=codes)
