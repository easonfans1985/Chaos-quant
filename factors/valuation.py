"""
估值因子
基于指数 PE/PB 分位数，反映市场整体估值水平
注意：目前只有指数级估值，个股估值待补
"""
import pandas as pd
import numpy as np
from .base_factor import BaseFactor


class ValuationFactor(BaseFactor):
    name = "估值"
    description = "基于指数PE/PB历史分位数的估值因子，分位数越低分数越高（越便宜）"

    def __init__(self, params=None):
        defaults = {"metric": "pe"}  # pe 或 pb
        if params:
            defaults.update(params)
        super().__init__(defaults)

    def compute(self, data):
        metric = self.params["metric"]

        # 取估值数据
        valuation_data = data.get("valuation")
        if valuation_data is None:
            # 如果没有估值数据，返回中性分数
            daily = data.get("daily", data.get("close"))
            if isinstance(daily, pd.DataFrame):
                codes = daily.columns if "close" not in daily.columns else daily["close"].columns
            else:
                codes = []
            return pd.Series(50.0, index=codes)

        # valuation_data 应该是指数PE/PB数据
        # 包含历史分位数信息
        if isinstance(valuation_data, dict):
            df = valuation_data.get(metric, valuation_data.get("pe"))
        else:
            df = valuation_data

        if df is None or (isinstance(df, pd.DataFrame) and len(df) == 0):
            daily = data.get("daily", data.get("close"))
            if isinstance(daily, pd.DataFrame):
                codes = daily.columns
            else:
                codes = []
            return pd.Series(50.0, index=codes)

        # 取最新一行的分位数
        if isinstance(df, pd.DataFrame):
            latest = df.iloc[-1]
            # 找分位列
            quantile_col = None
            for col in df.columns:
                if "quantile" in col.lower() or "分位" in col:
                    quantile_col = col
                    break

            if quantile_col:
                quantile_value = latest[quantile_col]
            else:
                # 没有分位列，自己算
                current_val = latest.iloc[-1] if len(latest) > 0 else 50
                quantile_value = (df.iloc[-1] < df).mean().iloc[0] if len(df.columns) > 0 else 0.5

            # 估值越低分越高（100 - 分位数*100）
            score = 100 * (1 - float(quantile_value))
        else:
            score = 50.0

        # 对所有股票给同一个分数（因为是指数级估值）
        daily = data.get("daily", data.get("close"))
        if isinstance(daily, pd.DataFrame):
            codes = daily.columns
        elif isinstance(daily, dict) and "close" in daily:
            codes = daily["close"].columns
        else:
            codes = []

        return pd.Series(score, index=codes)
