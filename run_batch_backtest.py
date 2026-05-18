#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量回测脚本 — 24 个策略全量测试
使用沪深300代表性股票 + 指数ETF 进行回测
"""
import sys
import json
import traceback
from datetime import datetime
from pathlib import Path

# 确保项目根目录在路径中
sys.path.insert(0, str(Path(__file__).parent))

from strategies import ALL_STRATEGIES
from backtest.engine import BacktestEngine, BacktestConfig
from backtest.report import ReportGenerator


# ===== 回测配置 =====

# 股票池：全部使用有日线数据的股票（ETF数据在minute_5目录，不在daily）
STOCK_CODES = [
    "sh.600036",  # 招商银行
    "sh.600519",  # 贵州茅台
    "sh.600000",  # 浦发银行
]

def run_all_backtests():
    """执行全部 24 个策略的回测"""
    engine = BacktestEngine(data_dir="./data")
    reporter = ReportGenerator(output_dir="./reports")

    # 配置 — 统一用股票（ETF日线数据不在daily目录）
    stock_config = BacktestConfig(
        codes=STOCK_CODES,
        freq="daily",
        start_date="2021-01-01",
        end_date="2026-05-15",
        init_cash=1_000_000,
        fees=0.001,
        slippage=0.001,
        stamp_fees=0.001,
        size_type="percent",
        size=0.33,  # 每只股票 1/3 仓位
    )

    results = {}
    errors = {}

    print(f"\n{'='*80}")
    print(f"  🚀 Chaos Quant 批量回测 — {len(ALL_STRATEGIES)} 个策略")
    print(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

    for i, (name, strategy_cls) in enumerate(ALL_STRATEGIES.items(), 1):
        print(f"[{i:2d}/24] 回测中：{name} ... ", end="", flush=True)

        try:
            strategy = strategy_cls()

            config = stock_config  # 统一用股票日线数据

            result = engine.run(strategy, config)

            # 保存结果
            reporter.save_json(result)
            reporter.save_trades_csv(result)

            results[name] = result
            print(f"✅ 收益={result.total_return:>7.2%}  夏普={result.sharpe_ratio:>5.2f}  回撤={result.max_drawdown:>7.2%}  交易={result.total_trades:>4d}")

        except Exception as e:
            errors[name] = str(e)
            print(f"❌ 失败: {e}")
            traceback.print_exc()
            continue

    # ===== 汇总报告 =====
    print(f"\n{'='*80}")
    print(f"  📊 批量回测汇总")
    print(f"{'='*80}\n")

    if results:
        reporter.print_comparison(results)

    # 保存汇总 JSON
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_strategies": len(ALL_STRATEGIES),
        "successful": len(results),
        "failed": len(errors),
        "results": {name: r.to_dict() for name, r in results.items()},
        "errors": errors,
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = f"./reports/batch_summary_{ts}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"📄 汇总报告已保存：{summary_path}")

    # 按夏普比率排序
    if results:
        print(f"\n🏆 策略排名（按夏普比率）：")
        sorted_results = sorted(results.items(), key=lambda x: x[1].sharpe_ratio, reverse=True)
        for rank, (name, r) in enumerate(sorted_results, 1):
            print(f"  {rank:2d}. {name:<25} 夏普={r.sharpe_ratio:>6.3f}  收益={r.total_return:>8.2%}  回撤={r.max_drawdown:>8.2%}  胜率={r.win_rate:>6.2%}")

    if errors:
        print(f"\n❌ 失败策略：")
        for name, err in errors.items():
            print(f"  - {name}: {err}")

    return results, errors


if __name__ == "__main__":
    run_all_backtests()
