#!/usr/bin/env python3
"""
Chaos Quant - 全市场5分钟线下载
Baostock 单连接串行，按年分批查询，断点续传
预计 38 小时完成 5204 只
"""
import sys
import json
import time
import yaml
import baostock as bs
import pandas as pd
from loguru import logger
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent.parent
with open(project_root / "config" / "settings.yaml") as f:
    config = yaml.safe_load(f)

data_base = project_root / config["data"]["base_dir"]
output_dir = data_base / "market" / "minute_5"
output_dir.mkdir(parents=True, exist_ok=True)
state_file = data_base / ".minute5_state.json"

FIELDS = "date,time,code,open,high,low,close,volume,amount,adjustflag"
YEARS = [2021, 2022, 2023, 2024, 2025, 2026]


def load_state():
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {"done": [], "last_code": None}


def save_state(state):
    tmp = state_file.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f)
    tmp.replace(state_file)


def get_stock_codes():
    bs.login()
    rs = bs.query_stock_basic()
    data = []
    while rs.error_code == "0" and rs.next():
        data.append(rs.get_row_data())
    bs.logout()
    df = pd.DataFrame(data, columns=rs.fields)
    df = df[(df["type"] == "1") & (df["status"] == "1")]
    df = df[df["code"].str.startswith(("sh.6", "sz.0", "sz.3"))]
    return df["code"].tolist()


def download_code(code, end_date="2026-05-18"):
    """下载单只股票全部5分钟线，按年分批"""
    filepath = output_dir / f"{code}.parquet"

    # 检查增量起点
    existing_max = None
    if filepath.exists():
        try:
            df_old = pd.read_parquet(str(filepath))
            if not df_old.empty and isinstance(df_old.index, pd.DatetimeIndex):
                existing_max = df_old.index.max()
        except:
            pass

    all_new = []
    for year in YEARS:
        start = f"{year}-01-01"
        end = f"{year}-12-31" if year < 2026 else end_date

        # 跳过已有年份
        if existing_max and existing_max.year > year:
            continue
        if existing_max and existing_max.year == year:
            start = (existing_max + timedelta(days=1)).strftime("%Y-%m-%d")
            if start > end:
                continue

        rs = bs.query_history_k_data_plus(
            code, FIELDS,
            start_date=start, end_date=end,
            frequency="5", adjustflag="3",
        )
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())

        if rows:
            df = pd.DataFrame(rows, columns=rs.fields)
            for col in ["open", "high", "low", "close", "volume", "amount"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["datetime"] = pd.to_datetime(
                df["date"] + " " + df["time"].str.slice(0, 2) + ":" + df["time"].str.slice(2, 4),
                format="%Y-%m-%d %H:%M"
            )
            df.set_index("datetime", inplace=True)
            df.drop(columns=["date", "time"], inplace=True)
            all_new.append(df)

        time.sleep(0.1)

    # 合并保存
    if all_new:
        if filepath.exists() and existing_max is not None:
            df_old = pd.read_parquet(str(filepath))
            all_new.insert(0, df_old)
        combined = pd.concat(all_new)
        combined = combined[~combined.index.duplicated(keep="last")]
        combined.sort_index(inplace=True)
        combined.to_parquet(str(filepath), compression="gzip")
    elif not filepath.exists():
        # 无数据，创建空文件标记
        pass

    return True


def main():
    logger.info("🚀 全市场5分钟线下载启动")
    codes = get_stock_codes()
    logger.info(f"  全市场: {len(codes)} 只")

    state = load_state()
    done_set = set(state["done"])
    pending = [c for c in codes if c not in done_set]
    logger.info(f"  已完成: {len(done_set)}，待下载: {len(pending)}")

    if not pending:
        logger.info("✅ 全部完成")
        return

    bs.login()
    t_start = time.time()
    success = 0
    fail = 0

    for i, code in enumerate(pending):
        try:
            download_code(code)
            success += 1
            done_set.add(code)

            if (i + 1) % 50 == 0:
                state["done"] = list(done_set)
                save_state(state)
                elapsed = time.time() - t_start
                rate_s = elapsed / (i + 1)
                eta_h = (len(pending) - i - 1) * rate_s / 3600
                total_files = len(list(output_dir.glob("*.parquet")))
                logger.info(
                    f"  [{i+1}/{len(pending)}] "
                    f"速度: {rate_s:.1f}s/只 | "
                    f"剩余: {eta_h:.1f}h | "
                    f"文件: {total_files}"
                )

        except Exception as e:
            fail += 1
            logger.warning(f"  {code} 失败: {e}")
            # 失败时重新登录
            try:
                bs.logout()
            except:
                pass
            time.sleep(2)
            bs.login()

    bs.logout()

    state["done"] = list(done_set)
    save_state(state)

    total_files = len(list(output_dir.glob("*.parquet")))
    total_gb = sum(f.stat().st_size for f in output_dir.glob("*.parquet")) / 1024**3
    elapsed_h = (time.time() - t_start) / 3600

    logger.info(f"\n✅ 全市场5分钟线完成！")
    logger.info(f"  成功: {success}, 失败: {fail}")
    logger.info(f"  文件: {total_files}, 大小: {total_gb:.1f} GB")
    logger.info(f"  耗时: {elapsed_h:.1f} 小时")


if __name__ == "__main__":
    main()
