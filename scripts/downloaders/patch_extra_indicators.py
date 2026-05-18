#!/usr/bin/env python3
"""
补全运营效率 + 成长性 财务指标
Baostock: query_operation_data + query_growth_data
"""
import baostock as bs
import pandas as pd
import glob, time
from pathlib import Path
from loguru import logger

BASE_DIR = Path("data/fundamental")

DAILY_DIR = Path("data/market/daily")
codes = sorted([Path(f).stem for f in glob.glob(str(DAILY_DIR / "*.parquet"))])

# 季度列表（2022Q3~2025Q4，和profit一致）
quarters = []
for year in range(2022, 2026):
    for q in range(1, 5):
        quarters.append((year, q))

def download_and_save(api_func, data_subdir, api_name):
    save_dir = BASE_DIR / data_subdir
    save_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[{api_name}] 开始, {len(codes)} 只, {len(quarters)} 季度")
    
    bs.login()
    
    for qi, (year, quarter) in enumerate(quarters):
        logger.info(f"  [{qi+1}/{len(quarters)}] {year}Q{quarter}")
        records = []
        
        for ci, code in enumerate(codes):
            try:
                rs = api_func(code=code, year=year, quarter=quarter)
                rows = []
                while rs.error_code == '0' and rs.next():
                    rows.append(rs.get_row_data())
                if rows:
                    df = pd.DataFrame(rows, columns=rs.fields)
                    records.append(df)
            except:
                pass
            
            if (ci + 1) % 500 == 0:
                logger.info(f"    进度: {ci+1}/{len(codes)}, 已收集 {len(records)}")
            time.sleep(0.1)
        
        if records:
            all_df = pd.concat(records, ignore_index=True)
            for code, group in all_df.groupby("code"):
                filepath = save_dir / f"{code}.parquet"
                if filepath.exists():
                    existing = pd.read_parquet(filepath)
                    combined = pd.concat([existing, group], ignore_index=True)
                    combined = combined.drop_duplicates(subset=["code", "statDate"], keep="last")
                    combined.to_parquet(filepath, index=False)
                else:
                    group.to_parquet(filepath, index=False)
            logger.info(f"    ✅ {year}Q{quarter}: {len(records)} 只")
        else:
            logger.warning(f"    ❌ {year}Q{quarter}: 无数据")
    
    bs.logout()
    files = list(save_dir.glob("*.parquet"))
    logger.info(f"[{api_name}] 完成! 文件数: {len(files)}")


if __name__ == "__main__":
    import sys
    task = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if task in ("operation", "all"):
        download_and_save(bs.query_operation_data, "operation_indicator", "运营效率")
    
    if task in ("growth", "all"):
        download_and_save(bs.query_growth_data, "growth_indicator", "成长性")
