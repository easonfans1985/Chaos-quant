#!/usr/bin/env python3
"""
Chaos Quant 选股器
用法：
  python run_screener.py                       # 默认：全市场，Top 20
  python run_screener.py --top 50              # Top 50
  python run_screener.py --codes sh.600036 sh.600519  # 指定股票
  python run_screener.py --no-valuation        # 不用估值因子
  python run_screener.py --weights 动量=0.4 量能=0.3 技术=0.3  # 自定义权重
"""
import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from screener.factor_engine import FactorEngine
from screener.combiner import FactorCombiner
from screener.ranker import StockRanker
from factors import MomentumFactor, ValuationFactor, VolumeFactor, TechnicalFactor, MoneyFlowFactor
from loguru import logger


def parse_args():
    parser = argparse.ArgumentParser(description="Chaos Quant 选股器")
    parser.add_argument("--top", type=int, default=20, help="排名前 N 只（默认20）")
    parser.add_argument("--codes", nargs="+", default=None, help="指定股票代码")
    parser.add_argument("--start", default="2021-01-01", help="数据起始日期")
    parser.add_argument("--end", default="2026-05-15", help="数据结束日期")
    parser.add_argument("--no-valuation", action="store_true", help="不使用估值因子")
    parser.add_argument("--no-money-flow", action="store_true", help="不使用资金因子")
    parser.add_argument("--output", default=None, help="输出JSON文件路径")
    parser.add_argument("--weights", nargs="+", default=None,
                        help="自定义权重，格式: 因子名=权重（如 动量=0.4 量能=0.3）")
    return parser.parse_args()


def main():
    args = parse_args()

    logger.info("🚀 Chaos Quant 选股器启动")

    # 1. 确定因子列表
    factors = [
        MomentumFactor({"window": 20}),
        ValuationFactor(),
        VolumeFactor(),
        TechnicalFactor(),
        MoneyFlowFactor(),
    ]

    if args.no_valuation:
        factors = [f for f in factors if not isinstance(f, ValuationFactor)]
    if args.no_money_flow:
        factors = [f for f in factors if not isinstance(f, MoneyFlowFactor)]

    logger.info(f"📊 启用因子: {[f.name for f in factors]}")

    # 2. 加载数据
    engine = FactorEngine()
    data = engine.load_data(
        codes=args.codes,
        start_date=args.start,
        end_date=args.end,
    )

    # 3. 计算因子
    logger.info("📈 计算因子得分...")
    factor_scores = engine.compute_factors(data, factors)

    # 4. 合成
    weights = None
    if args.weights:
        weights = {}
        for w_str in args.weights:
            name, val = w_str.split("=")
            weights[name] = float(val)
        logger.info(f"  自定义权重: {weights}")

    combiner = FactorCombiner(weights=weights)
    combined_scores = combiner.combine(factor_scores)

    # 5. 排名
    ranker = StockRanker()
    result = ranker.rank(combined_scores, top_n=args.top)
    ranker.print_ranking(result, title=f"Chaos Quant 选股排名 Top {args.top}")

    # 6. 输出
    if args.output:
        output_path = Path(args.output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = project_root / "reports" / f"screener_{ts}.json"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 构建输出
    output = {
        "timestamp": datetime.now().isoformat(),
        "params": {
            "top_n": args.top,
            "date_range": f"{args.start} ~ {args.end}",
            "factors": [f.name for f in factors],
            "weights": combiner.get_weights(),
        },
        "factor_scores": {name: {k: round(v, 2) for k, v in scores.items()}
                          for name, scores in factor_scores.items()},
        "ranking": result.to_dict("records"),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"📄 结果已保存: {output_path}")


if __name__ == "__main__":
    main()
