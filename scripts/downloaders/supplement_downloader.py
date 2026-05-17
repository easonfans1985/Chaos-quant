#!/usr/bin/env python3
"""
Chaos Quant - 数据补充下载器
补充之前跳过的空目录数据
"""
import os
import sys
import time
import yaml
import akshare as ak
import baostock as bs
import pandas as pd
from loguru import logger
from tqdm import tqdm
from pathlib import Path
from datetime import datetime


project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

with open(project_root / "config" / "settings.yaml") as f:
    config = yaml.safe_load(f)

data_base = project_root / config["data"]["base_dir"]
start_date = config["download"]["start_date"].replace("-", "")
end_date = config["download"]["end_date"].replace("-", "")


def save_parquet(df: pd.DataFrame, filepath: Path, description: str = ""):
    """保存为 parquet"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(str(filepath), compression="gzip")
    logger.info(f"  ✅ {description}: {len(df)} rows → {filepath.name}")


# ========== Baostock 数据 ==========

def download_dividend():
    """下载分红配股数据（全市场，~9分钟）"""
    logger.info("=" * 50)
    logger.info("📥 开始下载分红配股数据（Baostock）")

    bs.login()

    output_dir = data_base / "fundamental" / "dividend"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 获取全市场股票列表
    stocks = bs.query_stock_list(fields="code,code_name").get_data()
    stocks = stocks[stocks["code"].str.startswith(("sh.6", "sz.0", "sz.3"))]
    codes = stocks["code"].tolist()
    logger.info(f"  共 {len(codes)} 只股票")

    success = 0
    for code in tqdm(codes, desc="分红数据"):
        try:
            rs = bs.query_dividend_data(
                code=code, year="2021", yearType="report"
            )
            data = []
            while rs.error_code == "0" and rs.next():
                data.append(rs.get_row_data())

            if data:
                cols = rs.fields
                df = pd.DataFrame(data, columns=cols)
                filepath = output_dir / f"{code}.parquet"
                df.to_parquet(str(filepath), compression="gzip")
                success += 1

            time.sleep(0.1)
        except Exception as e:
            logger.debug(f"  {code} 分红数据失败: {e}")

    # 也下载 2022-2026 的
    for year in [2022, 2023, 2024, 2025, 2026]:
        for code in tqdm(codes, desc=f"分红{year}"):
            try:
                rs = bs.query_dividend_data(code=code, year=str(year), yearType="report")
                data = []
                while rs.error_code == "0" and rs.next():
                    data.append(rs.get_row_data())
                if data:
                    cols = rs.fields
                    df_new = pd.DataFrame(data, columns=cols)
                    filepath = output_dir / f"{code}.parquet"
                    if filepath.exists():
                        df_old = pd.read_parquet(str(filepath))
                        df = pd.concat([df_old, df_new]).drop_duplicates()
                    else:
                        df = df_new
                    df.to_parquet(str(filepath), compression="gzip")
                    success += 1
                time.sleep(0.1)
            except Exception as e:
                pass

    bs.logout()
    total_files = len(list(output_dir.glob("*.parquet")))
    logger.info(f"  ✅ 分红数据完成：{total_files} 个文件")


def download_financial_indicator():
    """下载财务指标（盈利能力+运营能力，全市场，~18分钟）"""
    logger.info("=" * 50)
    logger.info("📥 开始下载财务指标数据（Baostock）")

    bs.login()

    output_dir = data_base / "fundamental" / "financial_indicator"
    output_dir.mkdir(parents=True, exist_ok=True)

    stocks = bs.query_stock_list(fields="code,code_name").get_data()
    stocks = stocks[stocks["code"].str.startswith(("sh.6", "sz.0", "sz.3"))]
    codes = stocks["code"].tolist()
    logger.info(f"  共 {len(codes)} 只股票")

    # 盈利能力
    logger.info("  📊 下载盈利能力指标...")
    success = 0
    for code in tqdm(codes, desc="盈利能力"):
        try:
            rs = bs.query_profit_data(code=code, year=2021, quarter=4)
            data = []
            while rs.error_code == "0" and rs.next():
                data.append(rs.get_row_data())
            if data:
                cols = rs.fields
                df = pd.DataFrame(data, columns=cols)
                filepath = output_dir / f"{code}.parquet"
                df.to_parquet(str(filepath), compression="gzip")
                success += 1
            time.sleep(0.1)
        except Exception as e:
            pass

    # 补充 2022-2025 年的数据
    for year in [2022, 2023, 2024, 2025]:
        for quarter in [1, 2, 3, 4]:
            for code in tqdm(codes, desc=f"盈利{year}Q{quarter}"):
                try:
                    rs = bs.query_profit_data(code=code, year=year, quarter=quarter)
                    data = []
                    while rs.error_code == "0" and rs.next():
                        data.append(rs.get_row_data())
                    if data:
                        cols = rs.fields
                        df_new = pd.DataFrame(data, columns=cols)
                        filepath = output_dir / f"{code}.parquet"
                        if filepath.exists():
                            df_old = pd.read_parquet(str(filepath))
                            df = pd.concat([df_old, df_new]).drop_duplicates()
                        else:
                            df = df_new
                        df.to_parquet(str(filepath), compression="gzip")
                    time.sleep(0.1)
                except:
                    pass

    bs.logout()
    total_files = len(list(output_dir.glob("*.parquet")))
    logger.info(f"  ✅ 财务指标完成：{total_files} 个文件")


# ========== AkShare 数据 ==========

def download_capital_flow():
    """下载个股资金流（沪深300成分，~3分钟）"""
    logger.info("=" * 50)
    logger.info("📥 开始下载个股资金流（AkShare，沪深300）")

    output_dir = data_base / "money_flow" / "capital_flow"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 获取沪深300成分
    try:
        hs300 = ak.index_stock_cons_weight_csindex(symbol="000300")
        codes = hs300["成分券代码"].tolist()
        logger.info(f"  沪深300共 {len(codes)} 只")
    except Exception as e:
        logger.error(f"获取沪深300成分失败: {e}")
        return

    for code in tqdm(codes, desc="资金流"):
        try:
            df = ak.stock_individual_fund_flow(stock=code, market="sh" if code.startswith("6") else "sz")
            if df is not None and len(df) > 0:
                filepath = output_dir / f"{code}.parquet"
                df.to_parquet(str(filepath), compression="gzip")
            time.sleep(0.5)
        except Exception as e:
            logger.debug(f"  {code} 失败: {e}")

    total_files = len(list(output_dir.glob("*.parquet")))
    logger.info(f"  ✅ 资金流完成：{total_files} 个文件")


def download_macro():
    """下载宏观经济指标"""
    logger.info("=" * 50)
    logger.info("📥 开始下载宏观经济数据（AkShare）")

    output_dir = data_base / "other" / "macro"
    output_dir.mkdir(parents=True, exist_ok=True)

    indicators = {
        "gdp": ("macro_china_gdp", {}),
        "cpi": ("macro_china_cpi", {}),
        "ppi": ("macro_china_ppi", {}),
        "pmi": ("macro_china_pmi", {}),
        "m2": ("macro_china_money_supply", {}),
        "social_finance": ("macro_china_shrzgm", {}),
        "interest_rate": ("macro_china_lpr", {}),
        "fx_reserve": ("macro_china_foreign_exchange", {}),
    }

    for name, (func_name, kwargs) in indicators.items():
        try:
            func = getattr(ak, func_name)
            df = func(**kwargs)
            if df is not None and len(df) > 0:
                save_parquet(df, output_dir / f"{name}.parquet", name)
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"  {name} 失败: {e}")

    total_files = len(list(output_dir.glob("*.parquet")))
    logger.info(f"  ✅ 宏观数据完成：{total_files} 个文件")


def download_shareholder():
    """下载股东数据"""
    logger.info("=" * 50)
    logger.info("📥 开始下载股东数据（AkShare）")

    output_dir = data_base / "other" / "shareholder"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 十大股东
        df = ak.stock_gdfx_free_holding_detail_em(symbol="全部")
        if df is not None and len(df) > 0:
            save_parquet(df, output_dir / "top10_shareholders.parquet", "十大股东")
    except Exception as e:
        logger.warning(f"  十大股东失败: {e}")

    try:
        # 股东户数变化
        df = ak.stock_zh_a_gdhs(symbol="全部")
        if df is not None and len(df) > 0:
            save_parquet(df, output_dir / "shareholder_count.parquet", "股东户数")
    except Exception as e:
        logger.warning(f"  股东户数失败: {e}")

    total_files = len(list(output_dir.glob("*.parquet")))
    logger.info(f"  ✅ 股东数据完成：{total_files} 个文件")


def download_sector():
    """下载板块概念数据"""
    logger.info("=" * 50)
    logger.info("📥 开始下载板块概念数据（AkShare）")

    output_dir = data_base / "reference" / "sector"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 概念板块列表
    for attempt in range(3):
        try:
            df = ak.stock_board_concept_name_em()
            if df is not None and len(df) > 0:
                save_parquet(df, output_dir / "concept_list.parquet", "概念板块列表")
                break
        except Exception as e:
            logger.warning(f"  概念板块第{attempt+1}次失败: {e}")
            time.sleep(2)

    # 行业板块列表
    for attempt in range(3):
        try:
            df = ak.stock_board_industry_name_em()
            if df is not None and len(df) > 0:
                save_parquet(df, output_dir / "industry_board_list.parquet", "行业板块列表")
                break
        except Exception as e:
            logger.warning(f"  行业板块第{attempt+1}次失败: {e}")
            time.sleep(2)

    total_files = len(list(output_dir.glob("*.parquet")))
    logger.info(f"  ✅ 板块数据完成：{total_files} 个文件")


def download_lockup():
    """下载限售解禁数据"""
    logger.info("=" * 50)
    logger.info("📥 开始下载限售解禁数据（AkShare）")

    output_dir = data_base / "other" / "lockup"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        df = ak.stock_restricted_release_queue_sina(symbol="首发原股东限售股份")
        if df is not None and len(df) > 0:
            save_parquet(df, output_dir / "ipo_lockup.parquet", "首发解禁")
    except Exception as e:
        logger.warning(f"  首发解禁失败: {e}")

    try:
        df = ak.stock_restricted_release_queue_sina(symbol="定向增发机构配售股份")
        if df is not None and len(df) > 0:
            save_parquet(df, output_dir / "private_placement_lockup.parquet", "定增解禁")
    except Exception as e:
        logger.warning(f"  定增解禁失败: {e}")

    # 按日期查询最近解禁
    try:
        df = ak.stock_restricted_release_date_em(symbol="全部")
        if df is not None and len(df) > 0:
            save_parquet(df, output_dir / "release_schedule.parquet", "解禁日程")
    except Exception as e:
        logger.warning(f"  解禁日程失败: {e}")

    total_files = len(list(output_dir.glob("*.parquet")))
    logger.info(f"  ✅ 限售解禁完成：{total_files} 个文件")


# ========== 主流程 ==========

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Chaos Quant 数据补充下载")
    parser.add_argument("--all", action="store_true", help="下载全部")
    parser.add_argument("--baostock", action="store_true", help="仅 Baostock 数据（分红+财务指标）")
    parser.add_argument("--akshare", action="store_true", help="仅 AkShare 数据")
    args = parser.parse_args()

    logger.info("🚀 Chaos Quant 数据补充下载器启动")

    if args.all or args.baostock:
        download_dividend()          # ~45分钟（6年 * 5218只）
        download_financial_indicator()  # ~90分钟（5年4季 * 5218只）

    if args.all or args.akshare:
        download_capital_flow()      # ~3分钟（沪深300）
        download_macro()             # ~1分钟
        download_shareholder()       # ~2分钟
        download_sector()            # ~1分钟（重试3次）
        download_lockup()            # ~1分钟

    logger.info("🎉 全部数据补充完成！")
    logger.info("⚠️ 注意：Baostock 的分红和财务指标下载时间较长（分红~45分钟，财务指标~90分钟）")


if __name__ == "__main__":
    main()
