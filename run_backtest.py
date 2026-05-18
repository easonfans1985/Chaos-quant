#!/usr/bin/env python3
"""
Chaos Quant 回测入口
用法：
  python run_backtest.py                           # 默认：沪深300成分股 + 双均线
  python run_backtest.py --strategy rsi             # RSI策略
  python run_backtest.py --strategy bollinger       # 布林带策略
  python run_backtest.py --codes sh.600000 sz.000001  # 指定股票
  python run_backtest.py --all                      # 全市场（慢）
  python run_backtest.py --compare                  # 三策略对比
"""
import argparse
import sys
from pathlib import Path

# 确保项目根目录在 sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backtest.engine import BacktestEngine, BacktestConfig
from backtest.report import ReportGenerator
from strategies import SMACrossStrategy, RSIStrategy, BollingerStrategy, MACDDivergenceStrategy, KDJStrategy, ATRBreakoutStrategy, FundFlowInflowStrategy, NorthboundFollowStrategy, SectorRotationStrategy, PairTradingStrategy, MomentumFactorStrategy, MultiFactorStrategy, ValuePickStrategy, EarningsSurpriseStrategy, BuybackSignalStrategy, MarketValuationStrategy, NorthboundTimingStrategy, MarginTimingStrategy


# 沪深300代表性成分股（用于快速回测）
HS300_SAMPLE = [
    "sh.600000",  # 浦发银行
    "sh.600036",  # 招商银行
    "sh.600519",  # 贵州茅台
    "sz.000858",  # 五粮液
    "sh.601318",  # 中国平安
    "sz.000333",  # 美的集团
    "sh.600276",  # 恒瑞医药
    "sz.002714",  # 牧原股份
    "sh.601888",  # 中国中免
    "sh.600900",  # 长江电力
]

STRATEGIES = {
    "sma": SMACrossStrategy,
    "rsi": RSIStrategy,
    "bollinger": BollingerStrategy,
    "macd": MACDDivergenceStrategy,
    "kdj": KDJStrategy,
    "atr": ATRBreakoutStrategy,
    "fund_flow": FundFlowInflowStrategy,
    "northbound": NorthboundFollowStrategy,
    "sector": SectorRotationStrategy,
    "pair": PairTradingStrategy,
    "momentum": MomentumFactorStrategy,
    "multifactor": MultiFactorStrategy,
    "value": ValuePickStrategy,
    "earnings": EarningsSurpriseStrategy,
    "buyback": BuybackSignalStrategy,
    "val_timing": MarketValuationStrategy,
    "nb_timing": NorthboundTimingStrategy,
    "margin_timing": MarginTimingStrategy,
    "big_deal": BigDealTrackStrategy,
    "lockup": LockupAvoidStrategy,
    "etf": ETFPremiumStrategy,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Chaos Quant 回测系统")
    parser.add_argument("--strategy", "-s", default="sma", choices=STRATEGIES.keys(),
                        help="策略选择：sma / rsi / bollinger")
    parser.add_argument("--codes", "-c", nargs="+", default=None,
                        help="股票代码，如 sh.600000 sz.000001")
    parser.add_argument("--all", action="store_true", help="全市场回测（慢）")
    parser.add_argument("--compare", action="store_true", help="三策略对比")
    parser.add_argument("--start", default="2021-01-01", help="起始日期")
    parser.add_argument("--end", default="2026-05-15", help="结束日期")
    parser.add_argument("--cash", type=float, default=1_000_000, help="初始资金")
    parser.add_argument("--no-plot", action="store_true", help="不显示图表")
    return parser.parse_args()


def main():
    args = parse_args()

    # 确定股票池
    if args.codes:
        codes = args.codes
    elif getattr(args, "all"):
        from backtest.data_loader import DataLoader
        loader = DataLoader()
        codes = loader.list_stocks()
        print(f"📋 全市场模式：共 {len(codes)} 只股票")
    else:
        codes = HS300_SAMPLE

    # 配置
    config = BacktestConfig(
        codes=codes,
        start_date=args.start,
        end_date=args.end,
        init_cash=args.cash,
    )

    engine = BacktestEngine()
    reporter = ReportGenerator()

    if args.compare:
        # 多策略对比
        strategies = [
            SMACrossStrategy(),
            RSIStrategy(),
            BollingerStrategy(),
        ]
        results = engine.run_multi_strategy(strategies, config)
        reporter.print_comparison(results)

        for name, result in results.items():
            reporter.save_json(result)
            if not args.no_plot:
                reporter.plot_equity_curve(result, show=False)
    else:
        # 单策略回测
        strategy_cls = STRATEGIES[args.strategy]
        strategy = strategy_cls()

        result = engine.run(strategy, config)
        reporter.print_summary(result)
        reporter.save_json(result)
        reporter.save_trades_csv(result)

        if not args.no_plot:
            reporter.plot_equity_curve(result, show=False)
            reporter.plot_drawdown(result, show=False)


if __name__ == "__main__":
    main()
