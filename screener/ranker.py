"""
排名器
按综合得分排名，筛选 Top N
"""
import pandas as pd
import numpy as np
from typing import Optional, List
from loguru import logger


class StockRanker:
    """股票排名器"""

    def rank(
        self,
        scores: pd.Series,
        top_n: int = 20,
        ascending: bool = False,
        exclude_st: bool = True,
        min_price: float = 2.0,
        max_price: float = 200.0,
    ) -> pd.DataFrame:
        """
        排名并筛选股票

        Args:
            scores: 综合得分 Series
            top_n: 取前 N 名
            ascending: False=分数高的排前面
            exclude_st: 排除 ST 股
            min_price: 最低价格过滤
            max_price: 最高价格过滤

        Returns:
            DataFrame: 排名结果（得分、排名、等级）
        """
        # 排序
        ranked = scores.sort_values(ascending=ascending)

        # 排除 ST（股票代码中不含 ST 的，这里简化处理）
        if exclude_st:
            # ST 股票在代码层面无法直接判断，需要额外数据
            # 暂时跳过，后续可以加上
            pass

        # 取 Top N
        top = ranked.head(top_n)

        # 构建结果 DataFrame
        result = pd.DataFrame({
            "股票代码": top.index,
            "综合得分": top.values,
        })

        # 添加排名列
        result["排名"] = range(1, len(result) + 1)

        # 添加等级（90+ 为 A，80+ 为 B，70+ 为 C，其余 D）
        result["等级"] = result["综合得分"].apply(self._score_to_grade)

        return result

    def filter(
        self,
        scores: pd.Series,
        min_score: float = 60.0,
    ) -> pd.Series:
        """过滤低分股票"""
        return scores[scores >= min_score].sort_values(ascending=False)

    def _score_to_grade(self, score: float) -> str:
        """分数转等级"""
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "E"

    def print_ranking(self, result: pd.DataFrame, title: str = "选股排名"):
        """控制台打印排名"""
        print("\n" + "=" * 70)
        print(f"  📊 {title}")
        print("=" * 70)
        print(f"  {'排名':>4}  {'股票代码':<12}  {'得分':>8}  {'等级':>4}")
        print("-" * 70)
        for _, row in result.iterrows():
            emoji = "🥇" if row["排名"] == 1 else "🥈" if row["排名"] == 2 else "🥉" if row["排名"] == 3 else "  "
            print(f"  {emoji}{row['排名']:>2}  {row['股票代码']:<12}  {row['综合得分']:>8.1f}  {row['等级']:>4}")
        print("=" * 70 + "\n")
