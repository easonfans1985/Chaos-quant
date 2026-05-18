#!/usr/bin/env python3
"""
Chaos Quant - 30分钟线格式整合脚本
把 Qlib 迁移数据 + baostock 补缺数据 合并为统一格式：
  - DatetimeIndex（正确交易时间）
  - 列: code, open, high, low, close, volume, amount, adjustflag
  - parquet gzip 压缩
"""
import pandas as pd
from pathlib import Path
from loguru import logger
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
data_base = project_root / "data" / "market" / "minute_30"
backup_dir = data_base / "_qlib_backup"

TOTAL_EXPECTED = 5400  # 大约数


def merge_one(code_stem: str) -> str:
    """
    合并单个股票的 Qlib 数据和 baostock 补缺数据
    返回: 'ok' / 'skip' / 'error'
    """
    main_file = data_base / f"{code_stem}.parquet"
    patch_file = data_base / f"{code_stem}_patch.parquet"

    if not main_file.exists():
        return "skip"

    # 读取 Qlib 数据
    df_old = pd.read_parquet(str(main_file))

    # 提取统一格式的列
    def extract_uniform(df):
        """从任意格式的 df 提取统一列"""
        result = pd.DataFrame()

        # code
        if "code" in df.columns:
            result["code"] = df["code"].values
        elif "instrument" in df.columns:
            result["code"] = df["instrument"].values
        else:
            result["code"] = code_stem

        # OHLCV
        result["open"] = pd.to_numeric(df["open"], errors="coerce").values
        result["high"] = pd.to_numeric(df["high"], errors="coerce").values
        result["low"] = pd.to_numeric(df["low"], errors="coerce").values
        result["close"] = pd.to_numeric(df["close"], errors="coerce").values

        if "volume" in df.columns:
            result["volume"] = pd.to_numeric(df["volume"], errors="coerce").values
        elif "turnover_volume" in df.columns:
            result["volume"] = pd.to_numeric(df["turnover_volume"], errors="coerce").values
        else:
            result["volume"] = 0

        if "amount" in df.columns:
            result["amount"] = pd.to_numeric(df["amount"], errors="coerce").values
        elif "turnover" in df.columns:
            result["amount"] = pd.to_numeric(df["turnover"], errors="coerce").values
        else:
            result["amount"] = 0.0

        result["adjustflag"] = "3"

        # datetime 索引
        if isinstance(df.index, pd.DatetimeIndex):
            result.index = df.index
        elif "datetime" in df.columns:
            result.index = pd.to_datetime(df["datetime"])
        elif "date" in df.columns and "time" in df.columns:
            hour = df["time"].astype(str).str[8:10]
            minute = df["time"].astype(str).str[10:12]
            result.index = pd.to_datetime(
                df["date"].astype(str) + " " + hour + ":" + minute,
                format="%Y-%m-%d %H:%M"
            )
        elif "date" in df.columns:
            result.index = pd.to_datetime(df["date"])
        else:
            return None

        return result

    # 处理 Qlib 主数据
    df_uniform = extract_uniform(df_old)
    if df_uniform is None:
        return "error"

    # 处理 baostock 补缺数据
    if patch_file.exists():
        df_patch = pd.read_parquet(str(patch_file))
        df_patch_uniform = extract_uniform(df_patch)
        if df_patch_uniform is not None and not df_patch_uniform.empty:
            df_uniform = pd.concat([df_uniform, df_patch_uniform])

    # 去重、排序
    df_uniform = df_uniform[~df_uniform.index.duplicated(keep="last")]
    df_uniform.sort_index(inplace=True)

    # 只保留 2021-01-01 之后
    df_uniform = df_uniform[df_uniform.index >= "2021-01-01"]

    if df_uniform.empty:
        return "empty"

    # 保存
    df_uniform.to_parquet(str(main_file), compression="gzip")

    # 删除补丁文件
    if patch_file.exists():
        patch_file.unlink()

    return "ok"


def main():
    logger.info("🔧 30分钟线格式整合开始")

    # 备份 Qlib 原始数据（第一次运行时）
    if not backup_dir.exists():
        logger.info("  创建 Qlib 原始数据备份...")
        backup_dir.mkdir(parents=True, exist_ok=True)

    # 获取所有主文件
    main_files = sorted(data_base.glob("*.parquet"))
    # 排除备份目录里的
    main_files = [f for f in main_files if f.parent == data_base]
    logger.info(f"  找到 {len(main_files)} 个主文件")

    # 第一次运行：备份
    if not backup_dir.exists() or not list(backup_dir.glob("*.parquet")):
        logger.info("  备份 Qlib 原始文件到 _qlib_backup/ ...")
        import shutil
        for f in main_files:
            if not f.name.endswith("_patch.parquet"):
                backup_to = backup_dir / f.name
                if not backup_to.exists():
                    shutil.copy2(str(f), str(backup_to))
        logger.info(f"  已备份 {len(list(backup_dir.glob('*.parquet')))} 个文件")

    ok = 0
    skip = 0
    error = 0
    empty = 0

    for f in main_files:
        if f.name.endswith("_patch.parquet"):
            continue  # 跳过补丁文件，由主文件处理时合并

        code_stem = f.stem
        result = merge_one(code_stem)

        if result == "ok":
            ok += 1
        elif result == "skip":
            skip += 1
        elif result == "empty":
            empty += 1
        else:
            error += 1

        if (ok + skip + empty + error) % 500 == 0:
            logger.info(f"  进度: ok={ok} skip={skip} empty={empty} error={error}")

    # 清理残留的补丁文件（没有主文件对应的）
    remaining_patches = list(data_base.glob("*_patch.parquet"))
    for p in remaining_patches:
        p.unlink()

    logger.info(f"\n✅ 整合完成！")
    logger.info(f"  成功: {ok}, 跳过: {skip}, 无数据: {empty}, 失败: {error}")

    # 验证
    samples = list(data_base.glob("*.parquet"))[:3]
    for f in samples:
        df = pd.read_parquet(str(f))
        logger.info(f"  {f.name}: {len(df)}行, 索引={type(df.index).__name__}, "
                    f"列={df.columns.tolist()}, 时间={df.index.min()}~{df.index.max()}")


if __name__ == "__main__":
    main()
