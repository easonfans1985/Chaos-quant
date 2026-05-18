#!/usr/bin/env python3
"""
Chaos Quant - 2026-05-18 数据补缺脚本
任务清单：
1. Baostock 个股5分钟线（全市场5218只）
2. Baostock 30分钟线补缺（2026-01~05）
3. AkShare 个股资金流补全（沪深300）
4. AkShare 融资融券深交所 + 个股明细
5. AkShare 事件数据（回购/解禁/强势股/申万行业）
"""
import os
import sys
import time
import json
import yaml
import akshare as ak
import baostock as bs
import pandas as pd
from loguru import logger
from tqdm import tqdm
from pathlib import Path
from datetime import datetime, timedelta


project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

with open(project_root / "config" / "settings.yaml") as f:
    config = yaml.safe_load(f)

data_base = project_root / config["data"]["base_dir"]
start_date = config["download"]["start_date"]
end_date = config["download"]["end_date"]
baostock_interval = config["download"]["request_interval"]
akshare_interval = config["akshare"]["request_interval"]

# 断点续传状态文件
state_file = data_base / ".patch_state_20260518.json"


def load_state():
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(state_file, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def save_parquet(df, filepath, description=""):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(str(filepath), compression="gzip")
    logger.info(f"  ✅ {description}: {len(df)} rows → {filepath.name}")


# ============================================================
# Task 1: Baostock 个股5分钟线
# ============================================================
def task_minute5_all():
    logger.info("=" * 60)
    logger.info("📥 Task 1: Baostock 个股5分钟线（全市场）")

    state = load_state()
    done = state.get("minute5_all", [])

    bs.login()

    output_dir = data_base / "market" / "minute_5"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 获取全市场股票
    rs = bs.query_stock_basic()
    data = []
    while rs.error_code == "0" and rs.next():
        data.append(rs.get_row_data())
    stocks = pd.DataFrame(data, columns=rs.fields)
    stocks = stocks[(stocks["type"] == "1") & (stocks["status"] == "1")]
    stocks = stocks[stocks["code"].str.startswith(("sh.6", "sz.0", "sz.3"))]
    codes = stocks["code"].tolist()

    pending = [c for c in codes if c not in done]
    logger.info(f"  总计 {len(codes)} 只，已完成 {len(done)}，待下载 {len(pending)}")

    for code in tqdm(pending, desc="个股5分钟线"):
        try:
            filepath = output_dir / f"{code}.parquet"

            # 增量：如果已有数据，从下一天开始
            existing_end = None
            if filepath.exists():
                try:
                    df_old = pd.read_parquet(str(filepath))
                    if not df_old.empty and isinstance(df_old.index, pd.DatetimeIndex):
                        existing_end = df_old.index.max().strftime("%Y-%m-%d")
                except:
                    pass

            if existing_end:
                next_day = (pd.Timestamp(existing_end) + timedelta(days=1)).strftime("%Y-%m-%d")
                if next_day > end_date:
                    done.append(code)
                    continue
                query_start = next_day
            else:
                query_start = start_date

            rs2 = bs.query_history_k_data_plus(
                code,
                "date,time,code,open,high,low,close,volume,amount,adjustflag",
                start_date=query_start,
                end_date=end_date,
                frequency="5",
                adjustflag="3",
            )
            rows = []
            while rs2.error_code == "0" and rs2.next():
                rows.append(rs2.get_row_data())

            if rows:
                df = pd.DataFrame(rows, columns=rs2.fields)
                for col in ["open", "high", "low", "close", "volume", "amount"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                df["datetime"] = pd.to_datetime(
                    df["date"] + " " + df["time"].str.slice(0, 2) + ":" + df["time"].str.slice(2, 4)
                )
                df.set_index("datetime", inplace=True)
                df.drop(columns=["date", "time"], inplace=True)

                if filepath.exists() and existing_end:
                    df_old = pd.read_parquet(str(filepath))
                    df = pd.concat([df_old, df])
                    df = df[~df.index.duplicated(keep="last")]
                    df.sort_index(inplace=True)

                df.to_parquet(str(filepath), compression="gzip")

            done.append(code)
            time.sleep(baostock_interval)

        except Exception as e:
            logger.debug(f"  {code} 失败: {e}")
            time.sleep(0.5)

    bs.logout()
    state["minute5_all"] = done
    save_state(state)
    total = len(list(output_dir.glob("*.parquet")))
    logger.info(f"  ✅ 个股5分钟线完成：共 {total} 个文件")


# ============================================================
# Task 2: Baostock 30分钟线补缺（2026-01~05）
# ============================================================
def task_minute30_patch():
    logger.info("=" * 60)
    logger.info("📥 Task 2: Baostock 30分钟线补缺（2026-01~05）")

    state = load_state()
    done = state.get("minute30_patch", [])

    bs.login()

    output_dir = data_base / "market" / "minute_30"
    patch_start = "2026-01-01"
    patch_end = "2026-05-18"

    # 获取全市场股票
    rs = bs.query_stock_basic()
    data = []
    while rs.error_code == "0" and rs.next():
        data.append(rs.get_row_data())
    stocks = pd.DataFrame(data, columns=rs.fields)
    stocks = stocks[(stocks["type"] == "1") & (stocks["status"] == "1")]
    stocks = stocks[stocks["code"].str.startswith(("sh.6", "sz.0", "sz.3"))]
    codes = stocks["code"].tolist()

    pending = [c for c in codes if c not in done]
    logger.info(f"  总计 {len(codes)} 只，已完成 {len(done)}，待补缺 {len(pending)}")

    for code in tqdm(pending, desc="30分钟线补缺"):
        try:
            filepath = output_dir / f"{code}.parquet"

            rs2 = bs.query_history_k_data_plus(
                code,
                "date,time,code,open,high,low,close,volume,amount,adjustflag",
                start_date=patch_start,
                end_date=patch_end,
                frequency="30",
                adjustflag="3",
            )
            rows = []
            while rs2.error_code == "0" and rs2.next():
                rows.append(rs2.get_row_data())

            if rows:
                df = pd.DataFrame(rows, columns=rs2.fields)
                for col in ["open", "high", "low", "close", "volume", "amount"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")
                df["datetime"] = pd.to_datetime(
                    df["date"] + " " + df["time"].str.slice(0, 2) + ":" + df["time"].str.slice(2, 4)
                )
                df.set_index("datetime", inplace=True)
                df.drop(columns=["date", "time"], inplace=True)

                if filepath.exists():
                    df_old = pd.read_parquet(str(filepath))
                    # 兼容 int 索引（Qlib 迁移数据）
                    if not isinstance(df_old.index, pd.DatetimeIndex):
                        df.to_parquet(str(filepath), compression="gzip")
                    else:
                        df = pd.concat([df_old, df])
                        df = df[~df.index.duplicated(keep="last")]
                        df.sort_index(inplace=True)
                        df.to_parquet(str(filepath), compression="gzip")
                else:
                    df.to_parquet(str(filepath), compression="gzip")

            done.append(code)
            time.sleep(baostock_interval)

        except Exception as e:
            logger.debug(f"  {code} 失败: {e}")
            time.sleep(0.5)

    bs.logout()
    state["minute30_patch"] = done
    save_state(state)
    total = len(list(output_dir.glob("*.parquet")))
    logger.info(f"  ✅ 30分钟线补缺完成：共 {total} 个文件")


# ============================================================
# Task 3: AkShare 个股资金流补全（沪深300）
# ============================================================
def task_capital_flow():
    logger.info("=" * 60)
    logger.info("📥 Task 3: AkShare 个股资金流补全（沪深300）")

    state = load_state()
    done = state.get("capital_flow", [])

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

    # 现有文件
    existing = set(f.stem for f in output_dir.glob("*.parquet"))
    pending = [c for c in codes if c not in existing and c not in done]
    logger.info(f"  已有 {len(existing)} 只，待补 {len(pending)}")

    for code in tqdm(pending, desc="资金流"):
        try:
            market = "sh" if code.startswith("6") else "sz"
            df = ak.stock_individual_fund_flow(stock=code, market=market)
            if df is not None and len(df) > 0:
                filepath = output_dir / f"{code}.parquet"
                df.to_parquet(str(filepath), compression="gzip")
            done.append(code)
            time.sleep(akshare_interval)
        except Exception as e:
            logger.debug(f"  {code} 失败: {e}")
            done.append(code)  # 失败也标记完成，避免重复
            time.sleep(1)

    state["capital_flow"] = done
    save_state(state)
    total = len(list(output_dir.glob("*.parquet")))
    logger.info(f"  ✅ 个股资金流完成：{total} 个文件")


# ============================================================
# Task 4: AkShare 融资融券（深交所 + 个股明细）
# ============================================================
def task_margin_trading():
    logger.info("=" * 60)
    logger.info("📥 Task 4: AkShare 融资融券数据补全")

    state = load_state()
    output_dir = data_base / "money_flow" / "margin_trading"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 4a: 深交所融资融券汇总（逐日）
    logger.info("  4a: 深交所融资融券汇总...")
    try:
        df = ak.stock_margin_szse(date="20260516")
        if df is not None and len(df) > 0:
            save_parquet(df, output_dir / "szse_summary.parquet", "深交所汇总")
    except Exception as e:
        logger.warning(f"  深交所汇总失败: {e}")
        # 尝试不带日期（获取最新）
        try:
            df = ak.stock_margin_szse(date=datetime.now().strftime("%Y%m%d"))
            if df is not None and len(df) > 0:
                save_parquet(df, output_dir / "szse_summary.parquet", "深交所汇总")
        except Exception as e2:
            logger.warning(f"  深交所汇总重试失败: {e2}")

    # 4b: 上交所个股融资融券明细
    logger.info("  4b: 上交所个股融资融券明细...")
    try:
        df = ak.stock_margin_detail_sse(start_date="20210101", end_date="20260518")
        if df is not None and len(df) > 0:
            save_parquet(df, output_dir / "sse_detail.parquet", "上交所个股明细")
    except Exception as e:
        logger.warning(f"  上交所个股明细失败: {e}")

    logger.info("  ✅ 融资融券数据补全完成")


# ============================================================
# Task 5: AkShare 事件数据 + 杂项
# ============================================================
def task_events():
    logger.info("=" * 60)
    logger.info("📥 Task 5: AkShare 事件数据 + 杂项")

    # 5a: 强势股
    logger.info("  5a: 强势股池...")
    try:
        df = ak.stock_zt_pool_strong_em(date=datetime.now().strftime("%Y%m%d"))
        if df is not None and len(df) > 0:
            save_parquet(df, data_base / "money_flow" / "strong_stocks.parquet", "强势股")
    except Exception as e:
        logger.warning(f"  强势股失败: {e}")

    # 5b: 股票回购
    logger.info("  5b: 股票回购...")
    try:
        df = ak.stock_repurchase_em()
        if df is not None and len(df) > 0:
            save_parquet(df, data_base / "other" / "repurchase.parquet", "股票回购")
    except Exception as e:
        logger.warning(f"  股票回购失败: {e}")

    # 5c: 限售解禁日程
    logger.info("  5c: 限售解禁日程...")
    lockup_dir = data_base / "other" / "lockup"
    lockup_dir.mkdir(parents=True, exist_ok=True)
    try:
        df = ak.stock_restricted_release_date_em(symbol="全部")
        if df is not None and len(df) > 0:
            save_parquet(df, lockup_dir / "release_schedule.parquet", "解禁日程")
    except Exception as e:
        logger.warning(f"  解禁日程失败: {e}")

    # 按类型查解禁
    for lockup_type in ["首发原股东限售股份", "定向增发机构配售股份"]:
        try:
            df = ak.stock_restricted_release_queue_sina(symbol=lockup_type)
            if df is not None and len(df) > 0:
                fname = "ipo_lockup.parquet" if "首发" in lockup_type else "private_placement_lockup.parquet"
                save_parquet(df, lockup_dir / fname, lockup_type)
        except Exception as e:
            logger.debug(f"  {lockup_type} 失败: {e}")
        time.sleep(akshare_interval)

    # 5d: 申万行业分类（重试）
    logger.info("  5d: 申万行业分类...")
    industry_dir = data_base / "reference" / "industry"
    industry_dir.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            df = ak.stock_board_industry_name_ths()
            if df is not None and len(df) > 0:
                save_parquet(df, industry_dir / "sw_industry.parquet", "申万行业")
                break
        except Exception as e:
            logger.warning(f"  申万行业第{attempt+1}次失败: {e}")
            time.sleep(2)

    # 5e: 高管增减持
    logger.info("  5e: 高管增减持...")
    try:
        df = ak.stock_gdfx_free_holding_detail_em(symbol="全部")
        if df is not None and len(df) > 0:
            save_parquet(df, data_base / "other" / "executive_trading.parquet", "高管增减持")
    except Exception as e:
        logger.warning(f"  高管增减持失败: {e}")

    # 5f: 业绩报表日程
    logger.info("  5f: 业绩报表日程...")
    try:
        df = ak.stock_yjbb_em(date="20260331")  # 最近一季
        if df is not None and len(df) > 0:
            save_parquet(df, data_base / "other" / "earnings_calendar.parquet", "业绩报表")
    except Exception as e:
        logger.warning(f"  业绩报表失败: {e}")

    logger.info("  ✅ 事件数据补全完成")


# ============================================================
# Main
# ============================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="2026-05-18 数据补缺")
    parser.add_argument("--task", choices=["minute5", "minute30", "capital", "margin", "events", "all"],
                        default="all", help="运行哪个任务")
    args = parser.parse_args()

    logger.info("🚀 Chaos Quant 数据补缺脚本 2026-05-18")
    logger.info(f"  数据目录: {data_base}")
    logger.info(f"  日期范围: {start_date} ~ {end_date}")

    if args.task in ("minute5", "all"):
        task_minute5_all()

    if args.task in ("minute30", "all"):
        task_minute30_patch()

    if args.task in ("capital", "all"):
        task_capital_flow()

    if args.task in ("margin", "all"):
        task_margin_trading()

    if args.task in ("events", "all"):
        task_events()

    logger.info("🎉 全部补缺任务完成！")

    # 统计
    logger.info("\n📊 最终数据统计：")
    for subdir in ["market/daily", "market/minute_5", "market/minute_30",
                    "fundamental/financial_report", "fundamental/financial_indicator",
                    "fundamental/dividend", "valuation/stock_pe", "money_flow/capital_flow",
                    "money_flow/margin_trading", "money_flow/dragon_tiger",
                    "other/macro", "other/shareholder", "other/lockup"]:
        d = data_base / subdir
        if d.exists():
            count = len(list(d.glob("*.parquet")))
            if count > 0:
                size = sum(f.stat().st_size for f in d.rglob("*.parquet"))
                size_mb = size / 1024 / 1024
                logger.info(f"  {subdir}: {count} 文件, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
