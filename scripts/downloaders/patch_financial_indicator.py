#!/usr/bin/env python3
"""
补全财务指标数据 v2（修复版）
Baostock query_profit_data 用 year + quarter(1-4) 参数
"""
import baostock as bs
import pandas as pd
import glob
import time
from pathlib import Path
from loguru import logger

DATA_DIR = Path(__file__).parent.parent / "data" / "fundamental" / "financial_indicator"

def get_all_codes():
    daily_dir = Path(__file__).parent.parent / "data" / "market" / "daily"
    files = glob.glob(str(daily_dir / "*.parquet"))
    return sorted([Path(f).stem for f in files])

def main():
    logger.info("财务指标补全 v2 启动")
    
    # 需要补的季度：year + quarter(1-4)
    # 已有: 2021Q4, 2022Q1, 2022Q2
    existing_quarters = {(2021, 4), (2022, 1), (2022, 2)}
    
    quarters = []
    for year in range(2022, 2026):
        for q in range(1, 5):
            if (year, q) not in existing_quarters:
                quarters.append((year, q))
    
    logger.info(f"需要补 {len(quarters)} 个季度: {quarters}")
    
    codes = get_all_codes()
    logger.info(f"股票数: {len(codes)}")
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    bs.login()
    
    for qi, (year, quarter) in enumerate(quarters):
        logger.info(f"[{qi+1}/{len(quarters)}] {year}Q{quarter}")
        quarter_records = []
        
        for ci, code in enumerate(codes):
            try:
                rs = bs.query_profit_data(code=code, year=year, quarter=quarter)
                rows = []
                while rs.error_code == '0' and rs.next():
                    rows.append(rs.get_row_data())
                if rows:
                    df = pd.DataFrame(rows, columns=rs.fields)
                    quarter_records.append(df)
            except Exception as e:
                pass
            
            if (ci + 1) % 500 == 0:
                logger.info(f"  进度: {ci+1}/{len(codes)}, 已收集 {len(quarter_records)} 只")
            time.sleep(0.1)
        
        # 合并到文件
        if quarter_records:
            all_df = pd.concat(quarter_records, ignore_index=True)
            for code, group in all_df.groupby("code"):
                filepath = DATA_DIR / f"{code}.parquet"
                if filepath.exists():
                    existing = pd.read_parquet(filepath)
                    combined = pd.concat([existing, group], ignore_index=True)
                    combined = combined.drop_duplicates(subset=["code", "statDate"], keep="last")
                    combined.to_parquet(filepath, index=False)
                else:
                    group.to_parquet(filepath, index=False)
            logger.info(f"  ✅ {year}Q{quarter}: {len(quarter_records)} 只, 已合并")
        else:
            logger.warning(f"  ❌ {year}Q{quarter}: 无数据")
    
    bs.logout()
    
    # 最终统计
    files = list(DATA_DIR.glob("*.parquet"))
    logger.info(f"完成! 文件总数: {len(files)}")

if __name__ == "__main__":
    main()
