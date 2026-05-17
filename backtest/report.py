"""
Chaos Quant 报告生成器
输出回测结果为控制台摘要、CSV、HTML 图表
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from loguru import logger

from backtest.engine import BacktestResult


class ReportGenerator:
    """回测报告生成器"""

    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def print_summary(self, result: BacktestResult):
        """控制台打印回测摘要"""
        print("\n" + "=" * 60)
        print(f"  📊 回测报告：{result.strategy_name}")
        print("=" * 60)
        print(f"  📅 区间：{result.config.start_date} ~ {result.config.end_date}")
        print(f"  💰 初始资金：{result.config.init_cash:,.0f}")
        print(f"  📈 股票：{', '.join(result.config.codes)}")
        print("-" * 60)
        print(f"  总收益率：      {result.total_return:>10.2%}")
        print(f"  年化收益率：    {result.annualized_return:>10.2%}")
        print(f"  最大回撤：      {result.max_drawdown:>10.2%}")
        print(f"  夏普比率：      {result.sharpe_ratio:>10.3f}")
        print(f"  Sortino 比率：  {result.sortino_ratio:>10.3f}")
        print(f"  Calmar 比率：   {result.calmar_ratio:>10.3f}")
        print("-" * 60)
        print(f"  总交易次数：    {result.total_trades:>10d}")
        print(f"  胜率：          {result.win_rate:>10.2%}")
        print(f"  盈亏比：        {result.profit_factor:>10.3f}")
        print(f"  平均交易收益：  {result.avg_trade_return:>10.2%}")
        print("=" * 60 + "\n")

    def print_comparison(self, results: Dict[str, BacktestResult]):
        """多策略对比表"""
        print("\n" + "=" * 80)
        print(f"  📊 策略对比报告")
        print("=" * 80)
        print(f"  {'策略':<20} {'总收益':>10} {'年化':>10} {'最大回撤':>10} {'夏普':>8} {'胜率':>8} {'交易数':>8}")
        print("-" * 80)

        for name, r in results.items():
            print(
                f"  {name:<20} "
                f"{r.total_return:>9.2%} "
                f"{r.annualized_return:>9.2%} "
                f"{r.max_drawdown:>9.2%} "
                f"{r.sharpe_ratio:>7.3f} "
                f"{r.win_rate:>7.2%} "
                f"{r.total_trades:>7d}"
            )
        print("=" * 80 + "\n")

    def save_json(self, result: BacktestResult, filename: Optional[str] = None) -> str:
        """保存为 JSON"""
        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{result.strategy_name}_{ts}.json"

        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"📄 JSON 报告已保存：{filepath}")
        return str(filepath)

    def save_trades_csv(self, result: BacktestResult, filename: Optional[str] = None) -> str:
        """保存交易明细为 CSV"""
        if result.trades is None or result.trades.empty:
            logger.warning("无交易记录，跳过 CSV 导出")
            return ""

        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{result.strategy_name}_trades_{ts}.csv"

        filepath = self.output_dir / filename
        result.trades.to_csv(filepath, index=False, encoding="utf-8-sig")

        logger.info(f"📄 交易明细已保存：{filepath}")
        return str(filepath)

    def plot_equity_curve(self, result: BacktestResult, show: bool = True, save: bool = True):
        """绘制资金曲线"""
        if result.portfolio is None:
            logger.warning("无 Portfolio 对象，无法绘图")
            return

        fig = result.portfolio.plot_value()
        fig.update_layout(
            title=f"{result.strategy_name} - 资金曲线",
            xaxis_title="日期",
            yaxis_title="资金",
        )

        if save:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.output_dir / f"{result.strategy_name}_equity_{ts}.html"
            fig.write_html(str(filepath))
            logger.info(f"📈 资金曲线已保存：{filepath}")

        if show:
            fig.show()

        return fig

    def plot_drawdown(self, result: BacktestResult, show: bool = True, save: bool = True):
        """绘制回撤曲线"""
        if result.portfolio is None:
            return

        fig = result.portfolio.plot_drawdowns()
        fig.update_layout(
            title=f"{result.strategy_name} - 回撤曲线",
            xaxis_title="日期",
            yaxis_title="回撤",
        )

        if save:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.output_dir / f"{result.strategy_name}_drawdown_{ts}.html"
            fig.write_html(str(filepath))
            logger.info(f"📈 回撤曲线已保存：{filepath}")

        if show:
            fig.show()

        return fig
