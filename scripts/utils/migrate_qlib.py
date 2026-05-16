#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chaos Quant - 数据迁移工具

将现有 Qlib 数据迁移到新的 Chaos Quant 目录结构
"""

import shutil
import pandas as pd
from pathlib import Path
from loguru import logger


def migrate_qlib_data(qlib_dir: str, target_dir: str, dry_run: bool = True):
    """
    迁移 Qlib 数据到新目录

    Args:
        qlib_dir: Qlib 数据目录（如 /Users/mac/qlib/qlib_data_new）
        target_dir: 目标目录（如 /Users/mac/Documents/Chaos-quant/data）
        dry_run: 仅打印，不实际复制
    """
    qlib = Path(qlib_dir)
    target = Path(target_dir)

    if not qlib.exists():
        logger.error(f"Qlib 目录不存在: {qlib}")
        return

    migrations = []

    # 1. cn/1d → market/daily
    src = qlib / "cn" / "1d"
    dst = target / "market" / "daily"
    if src.exists():
        count = len(list(src.glob("*.parquet")))
        migrations.append(("cn/1d → market/daily", src, dst, count))

    # 2. cn/30min → market/minute_30（可选）
    src = qlib / "cn" / "30min"
    dst = target / "market" / "minute_30"
    if src.exists():
        count = len(list(src.glob("*.parquet")))
        migrations.append(("cn/30min → market/minute_30", src, dst, count))

    # 3. cn/financial_report → fundamental/financial_report
    src = qlib / "cn" / "financial_report"
    dst = target / "fundamental" / "financial_report"
    if src.exists():
        count = len(list(src.glob("*.parquet")))
        migrations.append(("cn/financial_report → fundamental/financial_report", src, dst, count))

    # 4. cn/basic → reference/
    src = qlib / "cn" / "basic"
    dst = target / "reference"
    if src.exists():
        count = len(list(src.glob("*")))
        migrations.append(("cn/basic → reference/", src, dst, count))

    # 打印迁移计划
    logger.info(f"找到 {len(migrations)} 个迁移项：")
    total_files = 0
    for name, src, dst, count in migrations:
        logger.info(f"  {name}: {count} 个文件")
        total_files += count

    logger.info(f"总计 {total_files} 个文件")

    if dry_run:
        logger.info("=== dry_run 模式，不实际复制 ===")
        logger.info("使用 --execute 参数执行实际迁移")
        return

    # 执行迁移（不删除原文件，用复制）
    for name, src, dst, count in migrations:
        dst.mkdir(parents=True, exist_ok=True)
        files = list(src.glob("*.parquet")) + list(src.glob("*.csv"))
        for f in files:
            target_file = dst / f.name
            if not target_file.exists():
                shutil.copy2(f, target_file)
        logger.info(f"✅ {name}: 已复制 {len(files)} 个文件")

    logger.info("迁移完成！原文件未删除。")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="迁移 Qlib 数据到 Chaos Quant")
    parser.add_argument("--execute", action="store_true", help="执行实际迁移（默认 dry run）")
    args = parser.parse_args()

    migrate_qlib_data(
        qlib_dir="/Users/mac/qlib/qlib_data_new",
        target_dir="/Users/mac/Documents/Chaos-quant/data",
        dry_run=not args.execute,
    )
