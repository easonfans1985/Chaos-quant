#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全市场批量回测 — 24 个策略 × 5400+ 只股票
"""
import sys
import json
import traceback
import warnings
import time
from datetime import datetime
from pathlib import Path

warnings.filterwarnings('ignore')
sys.path.insert(0, str(Path(__file__).parent))

from strategies import ALL_STRATEGIES
from backtest.engine import BacktestEngine, BacktestConfig
from backtest.report import ReportGenerator


def run_full_market_backtest():
    """执行全部 24 个策略 × 全市场回测"""
    engine = BacktestEngine(data_dir="./data")
    reporter = ReportGenerator(output_dir="./reports")

    # 获取全市场股票列表，过滤掉无效股票
    all_codes = engine.loader.list_stocks("daily")
    print(f"📊 原始股票数: {len(all_codes)}")

    # 过滤：只保留有完整 OHLCV 数据且价格正常的股票
    valid_codes = []
    for code in all_codes:
        try:
            df = engine.loader.load_single(code, freq="daily", start_date="2021-01-01")
            if len(df) < 100:
                continue
            # 检查必要列
            required = ["open", "high", "low", "close", "volume"]
            if not all(c in df.columns for c in required):
                continue
            # 检查价格有效
            close = df["close"]
            if close.isna().any() or (close <= 0).any():
                continue
            valid_codes.append(code)
        except Exception:
            continue

    print(f"📊 有效股票数: {len(valid_codes)}")

    # 全市场配置 — 每只 5% 仓位，最多 20 只同时持有
    config = BacktestConfig(
        codes=valid_codes,
        freq="daily",
        start_date="2021-01-01",
        end_date="2026-05-15",
        init_cash=1_000_000,
        fees=0.001,
        slippage=0.001,
        stamp_fees=0.001,
        size_type="percent",  # 按资金比例
        size=0.05,  # 每只 5% 仓位（100万 × 5% = 5万）
    )

    results = {}
    errors = {}
    total_start = time.time()

    print(f"\n{'='*80}")
    print(f"  🚀 全市场批量回测 — {len(ALL_STRATEGIES)} 策略 × {len(all_codes)} 只股票")
    print(f"  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")

    for i, (name, strategy_cls) in enumerate(ALL_STRATEGIES.items(), 1):
        t0 = time.time()
        print(f"[{i:2d}/24] {name} ... ", end="", flush=True)

        try:
            strategy = strategy_cls()
            result = engine.run(strategy, config)

            reporter.save_json(result)
            reporter.save_trades_csv(result)

            elapsed = time.time() - t0
            results[name] = result
            print(
                f"✅ {elapsed:.0f}s | 收益={result.total_return:>7.2%}  "
                f"夏普={result.sharpe_ratio:>6.2f}  回撤={result.max_drawdown:>7.2%}  "
                f"交易={result.total_trades:>5d}"
            )

        except Exception as e:
            elapsed = time.time() - t0
            errors[name] = str(e)
            print(f"❌ {elapsed:.0f}s | {e}")
            traceback.print_exc()
            continue

    total_elapsed = time.time() - total_start

    # ===== 汇总 =====
    print(f"\n{'='*80}")
    print(f"  📊 全市场回测汇总")
    print(f"  ⏱️  总耗时: {total_elapsed/60:.1f} 分钟")
    print(f"{'='*80}\n")

    if results:
        reporter.print_comparison(results)

    # 排名
    if results:
        print(f"\n🏆 全市场策略排名（按夏普比率）：\n")
        sorted_results = sorted(results.items(), key=lambda x: x[1].sharpe_ratio, reverse=True)
        print(f"  {'排名':>4}  {'策略':<25} {'总收益':>10} {'年化':>10} {'最大回撤':>10} {'夏普':>8} {'胜率':>8} {'交易数':>7}")
        print(f"  {'-'*90}")
        for rank, (name, r) in enumerate(sorted_results, 1):
            print(
                f"  {rank:>4}. {name:<25} "
                f"{r.total_return:>9.2%} "
                f"{r.annualized_return:>9.2%} "
                f"{r.max_drawdown:>9.2%} "
                f"{r.sharpe_ratio:>7.3f} "
                f"{r.win_rate:>7.2%} "
                f"{r.total_trades:>6d}"
            )

        # 按收益也排一次
        print(f"\n📈 按总收益排名：\n")
        by_return = sorted(results.items(), key=lambda x: x[1].total_return, reverse=True)
        print(f"  {'排名':>4}  {'策略':<25} {'总收益':>10} {'最大回撤':>10} {'胜率':>8} {'交易数':>7}")
        print(f"  {'-'*75}")
        for rank, (name, r) in enumerate(by_return, 1):
            print(
                f"  {rank:>4}. {name:<25} "
                f"{r.total_return:>9.2%} "
                f"{r.max_drawdown:>9.2%} "
                f"{r.win_rate:>7.2%} "
                f"{r.total_trades:>6d}"
            )

    if errors:
        print(f"\n❌ 失败策略 ({len(errors)})：")
        for name, err in errors.items():
            print(f"  - {name}: {err[:80]}")

    # 保存汇总
    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_elapsed_seconds": round(total_elapsed, 1),
        "market": "全市场",
        "total_stocks": len(all_codes),
        "total_strategies": len(ALL_STRATEGIES),
        "successful": len(results),
        "failed": len(errors),
        "results": {name: r.to_dict() for name, r in results.items()},
        "errors": errors,
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_path = f"./reports/full_market_summary_{ts}.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n📄 汇总报告已保存：{summary_path}")
    print(f"⏱️  总耗时: {total_elapsed/60:.1f} 分钟")

    return results, errors


if __name__ == "__main__":
    run_full_market_backtest()
