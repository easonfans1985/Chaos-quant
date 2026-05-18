#!/usr/bin/env python3
"""
Chaos Quant - pytdx 全市场5分钟线下载（并行版）
统一输出格式：
  - DatetimeIndex (正确交易时间 09:30-15:00)
  - 列: open, high, low, close, volume, amount, code, adjustflag
  - parquet gzip 压缩
  - 3连接并行，5204只 ≈ 3-4小时
"""
import sys
import json
import time
import random
import yaml
import pandas as pd
from loguru import logger
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from pytdx.hq import TdxHq_API

project_root = Path(__file__).parent.parent.parent
with open(project_root / "config" / "settings.yaml") as f:
    config = yaml.safe_load(f)

data_base = project_root / config["data"]["base_dir"]
output_dir = data_base / "market" / "minute_5"
output_dir.mkdir(parents=True, exist_ok=True)
state_file = data_base / ".minute5_pytdx_state.json"

WORKERS = 4  # 并行连接数
START_DATE = "2021-01-01"  # 数据起始

TDX_SERVERS = [
    ("180.153.18.170", 7709),
    ("180.153.18.171", 7709),
    ("202.108.25.239", 7709),
    ("202.108.25.238", 7709),
    ("60.12.136.250", 7709),
    ("115.238.56.198", 7709),
    ("218.75.126.9", 7709),
    ("115.238.90.165", 7709),
    ("124.160.88.183", 7709),
]


def load_state():
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {"done": []}


def save_state(state):
    tmp = state_file.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f)
    tmp.replace(state_file)


def get_stock_list():
    """获取全市场股票列表（用 baostock）"""
    import baostock as bs
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


def code_to_tdx(baostock_code):
    """sh.600000 → (1, '600000'), sz.000001 → (0, '000001')"""
    if baostock_code.startswith("sh."):
        return 1, baostock_code[3:]
    elif baostock_code.startswith("sz."):
        return 0, baostock_code[3:]
    return None, None


def connect_tdx():
    """连接一个可用的 pytdx 服务器"""
    servers = TDX_SERVERS.copy()
    random.shuffle(servers)
    api = TdxHq_API()
    for host, port in servers:
        try:
            if api.connect(host, port, time_out=5):
                return api
        except:
            continue
    return None


def download_one_stock(baostock_code):
    """
    下载单只股票5分钟线，输出统一格式：
    - DatetimeIndex
    - 列: open, high, low, close, volume, amount, code, adjustflag
    """
    market, tdx_code = code_to_tdx(baostock_code)
    if market is None:
        return None

    api = connect_tdx()
    if api is None:
        raise ConnectionError("无法连接 pytdx 服务器")

    try:
        all_dfs = []
        for start in range(0, 80000, 800):  # 最多100次翻页 = 80000条
            try:
                df = api.to_df(api.get_security_bars(0, market, tdx_code, start, 800))
                if df is None or df.empty:
                    break
                all_dfs.append(df)
            except:
                break

        if not all_dfs:
            return None

        combined = pd.concat(all_dfs, ignore_index=True)
        combined.drop_duplicates(subset=["datetime"], keep="last", inplace=True)

        # 构建统一格式
        result = pd.DataFrame({
            "code": baostock_code,
            "open": combined["open"].values,
            "high": combined["high"].values,
            "low": combined["low"].values,
            "close": combined["close"].values,
            "volume": combined["vol"].astype("int64").values,
            "amount": combined["amount"].values,
            "adjustflag": "3",  # pytdx 不复权
        })

        # 正确的 datetime 索引
        result["datetime"] = pd.to_datetime(combined["datetime"])
        result.set_index("datetime", inplace=True)
        result.sort_index(inplace=True)

        # 只保留配置的日期范围
        result = result[result.index >= START_DATE]

        return result

    finally:
        try:
            api.disconnect()
        except:
            pass


def download_and_save(baostock_code):
    """下载并保存"""
    filepath = output_dir / f"{baostock_code}.parquet"

    try:
        df = download_one_stock(baostock_code)

        if df is not None and not df.empty:
            df.to_parquet(str(filepath), compression="gzip")
            return baostock_code, "ok"
        else:
            return baostock_code, "empty"

    except Exception as e:
        return baostock_code, f"error: {e}"


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--start-from", type=int, default=0, help="从第N只开始")
    args = parser.parse_args()

    logger.info("🚀 pytdx 全市场5分钟线下载")
    logger.info(f"  并行连接: {args.workers}")
    logger.info(f"  统一格式: DatetimeIndex + open/high/low/close/volume/amount/code/adjustflag")

    codes = get_stock_list()
    logger.info(f"  全市场: {len(codes)} 只")

    state = load_state()
    done_set = set(state["done"])

    pending = [c for c in codes if c not in done_set]
    logger.info(f"  已完成: {len(done_set)}，待下载: {len(pending)}")

    if not pending:
        logger.info("✅ 全部完成")
        return

    t_start = time.time()
    success = 0
    fail = 0
    empty = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download_and_save, code): code for code in pending}

        for i, future in enumerate(as_completed(futures), 1):
            code, result = future.result()

            if result == "ok":
                success += 1
                done_set.add(code)
            elif result == "empty":
                empty += 1
                done_set.add(code)  # 无数据也标记完成
            else:
                fail += 1

            if i % 100 == 0:
                state["done"] = list(done_set)
                save_state(state)
                elapsed = time.time() - t_start
                rate = elapsed / i
                eta_h = (len(pending) - i) * rate / 3600
                total_files = len(list(output_dir.glob("*.parquet")))
                logger.info(
                    f"  [{i}/{len(pending)}] "
                    f"✅{success} ⬜{empty} ❌{fail} | "
                    f"{rate:.1f}s/只 | "
                    f"剩余: {eta_h:.1f}h | "
                    f"文件: {total_files}"
                )

    # 最终保存
    state["done"] = list(done_set)
    save_state(state)

    total_files = len(list(output_dir.glob("*.parquet")))
    total_gb = sum(f.stat().st_size for f in output_dir.glob("*.parquet")) / 1024**3
    elapsed_h = (time.time() - t_start) / 3600

    logger.info(f"\n✅ 全市场5分钟线完成！")
    logger.info(f"  成功: {success}, 无数据: {empty}, 失败: {fail}")
    logger.info(f"  文件: {total_files}, 大小: {total_gb:.1f} GB")
    logger.info(f"  耗时: {elapsed_h:.1f} 小时")

    # 抽检一个文件验证格式
    sample = list(output_dir.glob("*.parquet"))[:1]
    if sample:
        df = pd.read_parquet(str(sample[0]))
        logger.info(f"\n  抽检 {sample[0].name}:")
        logger.info(f"    列: {df.columns.tolist()}")
        logger.info(f"    索引: {df.index.name} ({type(df.index).__name__})")
        logger.info(f"    时间示例: {df.index[0]} ~ {df.index[-1]}")


if __name__ == "__main__":
    main()
