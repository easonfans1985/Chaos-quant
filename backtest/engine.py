"""
Chaos Quant 回测引擎
基于 VectorBT 的高性能回测
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field, asdict

import pandas as pd
import numpy as np
import vectorbt as vbt
from loguru import logger

from backtest.data_loader import DataLoader
from backtest.base_strategy import BaseStrategy


@dataclass
class BacktestConfig:
    """回测配置"""
    # 股票池
    codes: List[str] = field(default_factory=lambda: ["sh.600000"])
    # 数据频率
    freq: str = "daily"
    # 回测区间
    start_date: str = "2021-01-01"
    end_date: str = "2026-05-15"
    # 初始资金
    init_cash: float = 1_000_000.0
    # 手续费率
    fees: float = 0.001  # 万一
    # 滑点
    slippage: float = 0.001
    # 仓位管理
    size_type: str = "amount"  # "amount" / "value" / "percent"
    size: float = 100  # 每次交易数量（股）
    # 印花税（卖出时）
    stamp_fees: float = 0.001  # 千一（A股标准）


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_name: str
    config: BacktestConfig
    total_return: float = 0.0
    annualized_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    avg_trade_return: float = 0.0
    profit_factor: float = 0.0
    portfolio: Optional[object] = None  # vbt.Portfolio
    trades: Optional[pd.DataFrame] = None

    def to_dict(self) -> dict:
        """转为字典（排除不可序列化的 portfolio）"""
        d = {
            "strategy_name": self.strategy_name,
            "config": asdict(self.config),
            "metrics": {
                "total_return": f"{self.total_return:.2%}",
                "annualized_return": f"{self.annualized_return:.2%}",
                "max_drawdown": f"{self.max_drawdown:.2%}",
                "sharpe_ratio": round(self.sharpe_ratio, 3),
                "sortino_ratio": round(self.sortino_ratio, 3),
                "calmar_ratio": round(self.calmar_ratio, 3),
                "win_rate": f"{self.win_rate:.2%}",
                "total_trades": self.total_trades,
                "avg_trade_return": f"{self.avg_trade_return:.2%}",
                "profit_factor": round(self.profit_factor, 3),
            }
        }
        return d


class BacktestEngine:
    """回测引擎"""

    def __init__(self, data_dir: str = "./data"):
        self.loader = DataLoader(data_dir)

    def run(
        self,
        strategy: BaseStrategy,
        config: Optional[BacktestConfig] = None,
    ) -> BacktestResult:
        """
        执行回测

        Args:
            strategy: 策略实例
            config: 回测配置

        Returns:
            BacktestResult
        """
        if config is None:
            config = BacktestConfig()

        logger.info(f"🚀 回测开始：{strategy.name} | {len(config.codes)} 只股票")
        logger.info(f"   区间：{config.start_date} ~ {config.end_date} | 初始资金：{config.init_cash:,.0f}")

        # 1. 加载数据
        logger.info("📥 加载数据...")
        data = self.loader.load_for_vbt(
            codes=config.codes,
            freq=config.freq,
            start_date=config.start_date,
            end_date=config.end_date,
        )

        # 2. 清理数据：填充 NaN，确保价格 > 0
        for col in data:
            data[col] = data[col].ffill().bfill().fillna(0)
        # 将 0 价格替换为 NaN 再 forward fill（避免 0 价格交易）
        close = data["close"].replace(0, float('nan')).ffill()
        data["close"] = close

        # 3. 生成信号
        logger.info("📊 生成交易信号...")
        entries, exits = strategy.generate_signals(data)

        # 确保信号是布尔值且无 NaN
        entries = entries.fillna(False).astype(bool)
        exits = exits.fillna(False).astype(bool)

        # 4. 构建 Portfolio（每只 5% 仓位，最多 20 只同时持仓）
        logger.info("⚙️ 构建投资组合...")

        # 限制每天最多 20 只持仓：如果买入信号 > 20，只保留当天 close 涨幅最大的 20 个
        MAX_HOLDINGS = 20
        entries_limited = entries.copy()
        for date_idx in range(entries.shape[0]):
            row = entries.iloc[date_idx]
            if row.sum() > MAX_HOLDINGS:
                # 按当天涨幅排序，只保留前 MAX_HOLDINGS 个
                close_row = data["close"].iloc[date_idx]
                if date_idx > 0:
                    pct_change = (close_row - data["close"].iloc[date_idx - 1]) / data["close"].iloc[date_idx - 1]
                    pct_change = pct_change.fillna(0)
                else:
                    pct_change = close_row
                buy_cols = row[row].index
                sorted_cols = pct_change[buy_cols].sort_values(ascending=False).index[:MAX_HOLDINGS]
                mask = pd.Series(False, index=entries.columns)
                mask[sorted_cols] = True
                entries_limited.iloc[date_idx] = row & mask

        portfolio = vbt.Portfolio.from_signals(
            close=data["close"],
            entries=entries_limited,
            exits=exits,
            init_cash=config.init_cash,
            fees=config.fees,
            slippage=config.slippage,
            size=config.size,
            size_type=config.size_type,
            freq="1D" if config.freq == "daily" else f"{config.freq.replace('minute_', '')}min",
            accumulate=False,
            cash_sharing=True,
            group_by=True,
            call_seq="auto",
        )

        # 4. 计算指标
        result = self._calc_metrics(strategy.name, config, portfolio)

        logger.info(f"✅ 回测完成：总收益 {result.total_return:.2%}，夏普 {result.sharpe_ratio:.2f}")
        return result

    def run_multi_strategy(
        self,
        strategies: List[BaseStrategy],
        config: Optional[BacktestConfig] = None,
    ) -> Dict[str, BacktestResult]:
        """多策略对比回测"""
        results = {}
        for strategy in strategies:
            try:
                result = self.run(strategy, config)
                results[strategy.name] = result
            except Exception as e:
                logger.error(f"策略 {strategy.name} 回测失败：{e}")
        return results

    @staticmethod
    def _to_float(val):
        """将 scalar 或单元素 Series 转为 float"""
        if isinstance(val, pd.Series):
            return float(val.iloc[0])
        return float(val)

    def _calc_metrics(
        self,
        strategy_name: str,
        config: BacktestConfig,
        portfolio: vbt.Portfolio,
    ) -> BacktestResult:
        """从 Portfolio 对象提取关键指标"""
        f = self._to_float

        total_return = f(portfolio.total_return())
        max_drawdown = f(portfolio.max_drawdown())

        # 年化收益
        annualized_return = f(portfolio.annualized_return())

        # 夏普比率（无风险利率取 2%）
        sharpe = f(portfolio.sharpe_ratio(risk_free=0.02))

        # Sortino
        try:
            sortino = f(portfolio.sortino_ratio(risk_free=0.02))
        except Exception:
            sortino = 0.0

        # Calmar
        try:
            calmar = f(portfolio.calmar_ratio())
        except Exception:
            calmar = 0.0

        # 交易统计
        trades = portfolio.trades.records_readable
        total_trades = len(trades)
        win_rate = 0.0
        avg_trade_return = 0.0
        profit_factor = 0.0

        if total_trades > 0:
            winners = trades[trades["PnL"] > 0]
            losers = trades[trades["PnL"] <= 0]
            win_rate = len(winners) / total_trades
            avg_trade_return = trades["Return"].mean() if "Return" in trades.columns else 0.0

            gross_profit = winners["PnL"].sum() if len(winners) > 0 else 0.0
            gross_loss = abs(losers["PnL"].sum()) if len(losers) > 0 else 1e-10
            profit_factor = gross_profit / gross_loss

        return BacktestResult(
            strategy_name=strategy_name,
            config=config,
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            win_rate=win_rate,
            total_trades=total_trades,
            avg_trade_return=avg_trade_return,
            profit_factor=profit_factor,
            portfolio=portfolio,
            trades=trades,
        )
