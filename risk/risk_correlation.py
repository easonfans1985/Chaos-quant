#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
#21 相关性分散

确保持仓间相关系数 < 阈值（默认0.5）
超过阈值则移除相关性最高的配对中得分较低的一只
"""

import pandas as pd
import numpy as np


def calculate_correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """
    计算收益率相关性矩阵
    
    Args:
        returns: DataFrame，每列是一只股票的收益率
    
    Returns:
        相关性矩阵
    """
    return returns.corr()


def find_high_correlation_pairs(returns: pd.DataFrame, 
                                 threshold: float = 0.5) -> list:
    """
    找到高相关性的股票对
    
    Returns:
        [(stock_a, stock_b, correlation), ...] 按相关性降序
    """
    corr = calculate_correlation_matrix(returns)
    
    pairs = []
    cols = corr.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            c = corr.iloc[i, j]
            if abs(c) >= threshold:
                pairs.append((cols[i], cols[j], c))
    
    # 按相关性绝对值降序
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    return pairs


def filter_by_correlation(returns: pd.DataFrame, threshold: float = 0.5,
                           scores: dict = None) -> list:
    """
    按相关性过滤：从高相关对中移除得分较低的
    
    Args:
        returns: DataFrame，每列一只股票
        threshold: 相关系数阈值
        scores: {stock_name: score}，得分高的优先保留
    
    Returns:
        过滤后的股票列表
    """
    if returns.empty:
        return []
    
    selected = list(returns.columns)
    pairs = find_high_correlation_pairs(returns[returns.columns.intersection(selected)], threshold)
    
    for a, b, corr in pairs:
        if a not in selected or b not in selected:
            continue
        
        # 两个都在选中的列表里，移除得分低的
        if scores:
            score_a = scores.get(a, 0)
            score_b = scores.get(b, 0)
            remove = b if score_a >= score_b else a
        else:
            # 无得分，移除后加入的（名字靠后的）
            remove = b
        
        selected.remove(remove)
    
    return selected
