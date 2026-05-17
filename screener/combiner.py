"""
多因子合成器
将多个因子得分按权重合成综合得分
"""
import pandas as pd
import numpy as np
from typing import Dict, Optional
from loguru import logger


class FactorCombiner:
    """多因子合成器"""

    # 默认权重
    DEFAULT_WEIGHTS = {
        "动量": 0.25,
        "估值": 0.20,
        "量能": 0.20,
        "技术": 0.20,
        "资金": 0.15,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

    def combine(
        self,
        factor_scores: Dict[str, pd.Series],
        weights: Optional[Dict[str, float]] = None,
    ) -> pd.Series:
        """
        合成多因子得分

        Args:
            factor_scores: {因子名: pd.Series(股票代码→0~100分)}
            weights: 可选覆盖权重

        Returns:
            pd.Series: 综合得分（0~100）
        """
        w = weights or self.weights

        # 收集有数据的因子
        available_factors = {k: v for k, v in factor_scores.items() if v is not None and len(v) > 0}

        if not available_factors:
            raise ValueError("没有可用的因子得分")

        # 取所有因子的共同股票代码
        all_codes = set()
        for scores in available_factors.values():
            all_codes.update(scores.index)
        all_codes = sorted(all_codes)

        # 计算加权得分
        combined = pd.Series(0.0, index=all_codes)
        total_weight = 0.0

        for factor_name, scores in available_factors.items():
            weight = w.get(factor_name, 0.1)  # 未配置的因子给默认权重
            # 对齐索引
            aligned = scores.reindex(all_codes).fillna(50.0)
            combined += aligned * weight
            total_weight += weight
            logger.debug(f"  {factor_name}: weight={weight:.2f}, mean={aligned.mean():.1f}")

        if total_weight > 0:
            combined /= total_weight

        logger.info(f"  合成得分: mean={combined.mean():.1f}, std={combined.std():.1f}, "
                     f"min={combined.min():.1f}, max={combined.max():.1f}")

        return combined

    def set_weights(self, weights: Dict[str, float]):
        """更新权重"""
        self.weights = weights

    def get_weights(self) -> Dict[str, float]:
        """获取当前权重"""
        return self.weights.copy()
