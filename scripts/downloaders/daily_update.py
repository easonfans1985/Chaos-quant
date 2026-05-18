#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chaos Quant - 每日增量数据更新

工作日 15:30 后执行，更新当天所有数据。
用法：
  python scripts/downloaders/daily_update.py           # 全量更新
  python scripts/downloaders/daily_update.py --skip-minute  # 跳过分钟线
  python scripts/downloaders/daily_update.py --dry-run      # 模拟运行
"""

import os
import sys
import time
import argparse
import pandas as pd
import baostock as bs
import akshare as ak
from loguru import logger
from datetime import datetime, timedelta
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# ============ 工具函数 ============

def is_trade_day(date_str: str = None) -> bool:
    """检查是否交易日（简单判断：工作日）"""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    dt = pd.Timestamp(date_str)
    return dt.weekday() < 5  # 周一到周五

def get_today() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def get_all_stock_codes() -> list:
    """获取全市场股票代码列表（从日线文件）"""
    daily_dir = DATA_DIR / "market" / "daily"
    codes = [f.stem for f in daily_dir.glob("*.parquet")]
    return sorted(codes)

def append_to_parquet(filepath: Path, new_df: pd.DataFrame, index_col: str = None):
    """增量追加数据到 parquet 文件"""
    if not new_df.empty:
        if filepath.exists():
            existing = pd.read_parquet(filepath)
            combined = pd.concat([existing, new_df], ignore_index=True)
            if index_col and index_col in combined.columns:
                combined = combined.drop_duplicates(subset=[index_col], keep='last')
                combined = combined.sort_values(index_col).reset_index(drop=True)
            else:
                combined = combined.drop_duplicates(keep='last').reset_index(drop=True)
            combined.to_parquet(filepath, compression='gzip', index=False)
        else:
            filepath.parent.mkdir(parents=True, exist_ok=True)
            new_df.to_parquet(filepath, compression='gzip', index=False)

# ============ Task 1: 日线行情增量（Baostock） ============

def update_daily(today: str, dry_run: bool = False) -> int:
    """更新全市场日线行情，返回更新的股票数"""
    logger.info("=" * 60)
    logger.info("📥 Task 1: 日线行情增量更新（Baostock）")
    
    codes = get_all_stock_codes()
    logger.info(f"  共 {len(codes)} 只股票")
    
    if dry_run:
        logger.info(f"  [DRY RUN] 将下载 {len(codes)} 只股票的日线")
        return len(codes)
    
    lg = bs.login()
    if lg.error_code != '0':
        logger.error(f"  Baostock 登录失败: {lg.error_msg}")
        return 0
    
    daily_dir = DATA_DIR / "market" / "daily"
    updated = 0
    errors = 0
    
    for i, code in enumerate(codes):
        try:
            filepath = daily_dir / f"{code}.parquet"
            
            # 获取已有数据的最后日期
            start = today
            if filepath.exists():
                existing = pd.read_parquet(filepath)
                if not existing.empty and 'date' in existing.columns:
                    last_date = existing['date'].max()
                    start = (pd.Timestamp(last_date) + timedelta(days=1)).strftime("%Y-%m-%d")
            
            if start > today:
                continue
            
            rs = bs.query_history_k_data_plus(
                code,
                "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST",
                start_date=start, end_date=today,
                frequency="d", adjustflag="3"
            )
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            
            if rows:
                df = pd.DataFrame(rows, columns=rs.fields)
                numeric_cols = ["open", "high", "low", "close", "preclose", "volume", "amount", "turn", "pctChg"]
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                append_to_parquet(filepath, df, index_col='date')
                updated += 1
            
            time.sleep(0.05)
            
        except Exception as e:
            errors += 1
            if errors <= 3:
                logger.error(f"  ❌ {code}: {e}")
        
        if (i + 1) % 1000 == 0:
            logger.info(f"  进度: {i+1}/{len(codes)}, 更新: {updated}, 错误: {errors}")
    
    bs.logout()
    logger.info(f"  ✅ 日线更新完成: {updated} 只更新, {errors} 错误")
    return updated

# ============ Task 2: 5分钟线增量（pytdx） ============

def update_minute5(today: str, dry_run: bool = False) -> int:
    """更新全市场5分钟线（pytdx），返回更新的股票数"""
    logger.info("=" * 60)
    logger.info("📥 Task 2: 5分钟线增量更新（pytdx）")
    
    codes = get_all_stock_codes()
    logger.info(f"  共 {len(codes)} 只股票")
    
    if dry_run:
        logger.info(f"  [DRY RUN] 将下载 {len(codes)} 只股票的5分钟线")
        return len(codes)
    
    try:
        from pytdx.hq import TdxHq_API
    except ImportError:
        logger.warning("  pytdx 未安装，跳过5分钟线更新")
        return 0
    
    api = TdxHq_API()
    # 尝试连接服务器
    servers = [
        ('180.153.18.170', 7709),
        ('180.153.18.171', 7709),
        ('202.108.25.239', 7709),
        ('60.12.136.250', 7709),
    ]
    
    connected = False
    for host, port in servers:
        try:
            if api.connect(host, port, time_out=5):
                connected = True
                logger.info(f"  连接 pytdx: {host}:{port}")
                break
        except:
            continue
    
    if not connected:
        logger.error("  pytdx 连接失败")
        return 0
    
    minute_dir = DATA_DIR / "market" / "minute_5"
    updated = 0
    errors = 0
    
    for i, code in enumerate(codes):
        try:
            # 解析市场和代码
            if code.startswith('sh.'):
                market, stock_code = 1, code[3:]
            elif code.startswith('sz.'):
                market, stock_code = 0, code[3:]
            else:
                continue
            
            # 获取最近800条5分钟线（pytdx每次最多800条）
            df = api.to_df(api.get_security_bars(
                category=0,  # 0=5分钟
                market=market,
                code=stock_code,
                start=0,
                count=800
            ))
            
            if df is None or df.empty:
                continue
            
            # 格式化
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.rename(columns={'vol': 'volume'})
            df['code'] = code
            df['adjustflag'] = '3'
            df = df[['code', 'open', 'high', 'low', 'close', 'volume', 'amount', 'adjustflag', 'datetime']]
            for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                df[col] = df[col].astype(float)
            df = df.set_index('datetime')
            
            # 保存（覆盖最后几天的数据）
            filepath = minute_dir / f"{code}.parquet"
            if filepath.exists():
                existing = pd.read_parquet(filepath)
                if not isinstance(existing.index, pd.DatetimeIndex):
                    if 'datetime' in existing.columns:
                        existing['datetime'] = pd.to_datetime(existing['datetime'])
                        existing = existing.set_index('datetime')
                
                combined = pd.concat([existing, df])
                combined = combined[~combined.index.duplicated(keep='last')]
                combined = combined.sort_index()
                combined.to_parquet(filepath, compression='gzip')
            else:
                df.to_parquet(filepath, compression='gzip')
            
            updated += 1
            
        except Exception as e:
            errors += 1
            if errors <= 3:
                logger.error(f"  ❌ {code}: {e}")
        
        if (i + 1) % 1000 == 0:
            logger.info(f"  进度: {i+1}/{len(codes)}, 更新: {updated}, 错误: {errors}")
    
    api.disconnect()
    logger.info(f"  ✅ 5分钟线更新完成: {updated} 只更新, {errors} 错误")
    return updated

# ============ Task 3: 30分钟线增量（Baostock） ============

def update_minute30(today: str, dry_run: bool = False) -> int:
    """更新30分钟线增量"""
    logger.info("=" * 60)
    logger.info("📥 Task 3: 30分钟线增量更新（Baostock）")
    
    if dry_run:
        logger.info("  [DRY RUN] 将下载30分钟线")
        return 0
    
    lg = bs.login()
    if lg.error_code != '0':
        logger.error(f"  Baostock 登录失败: {lg.error_msg}")
        return 0
    
    codes = get_all_stock_codes()
    minute_dir = DATA_DIR / "market" / "minute_30"
    updated = 0
    errors = 0
    
    for code in codes:
        try:
            rs = bs.query_history_k_data_plus(
                code,
                "date,time,code,open,high,low,close,volume,amount,adjustflag",
                start_date=today, end_date=today,
                frequency="30", adjustflag="3"
            )
            rows = []
            while rs.error_code == '0' and rs.next():
                rows.append(rs.get_row_data())
            
            if rows:
                df = pd.DataFrame(rows, columns=rs.fields)
                time_str = df['time'].astype(str)
                df['datetime'] = pd.to_datetime(
                    df['date'] + ' ' + time_str.str[8:10] + ':' + time_str.str[10:12],
                    format='%Y-%m-%d %H:%M'
                )
                for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                
                filepath = minute_dir / f"{code}.parquet"
                append_to_parquet(filepath, df, index_col='datetime')
                updated += 1
            
            time.sleep(0.03)
            
        except Exception as e:
            errors += 1
            if errors <= 3:
                logger.error(f"  ❌ {code}: {e}")
    
    bs.logout()
    logger.info(f"  ✅ 30分钟线更新完成: {updated} 只更新, {errors} 错误")
    return updated

# ============ Task 4-10: AkShare 数据更新 ============

def update_akshare_data(today: str, dry_run: bool = False) -> dict:
    """更新所有 AkShare 数据，返回各任务的文件数"""
    logger.info("=" * 60)
    logger.info("📥 Task 4-10: AkShare 数据更新")
    
    if dry_run:
        logger.info("  [DRY RUN] 将更新所有 AkShare 数据")
        return {"dry_run": True}
    
    results = {}
    today_compact = today.replace("-", "")
    cf_dir = DATA_DIR / "money_flow" / "capital_flow"
    
    # Task 4: 同花顺个股资金流
    try:
        logger.info("  4. 同花顺个股资金流...")
        for symbol in ['即时', '3日排行', '5日排行', '10日排行']:
            df = ak.stock_fund_flow_individual(symbol=symbol)
            path = cf_dir / f"ths_fund_flow_{today_compact}_{symbol}.parquet"
            df.to_parquet(path, compression='gzip')
        results['ths_fund_flow'] = 4
        logger.info("    ✅ 4个周期完成")
    except Exception as e:
        logger.error(f"    ❌ 同花顺资金流失败: {e}")
        results['ths_fund_flow'] = 0
    
    # Task 5: 大单追踪
    try:
        logger.info("  5. 同花顺大单追踪...")
        df = ak.stock_fund_flow_big_deal()
        path = cf_dir / f"ths_big_deal_{today_compact}.parquet"
        df.to_parquet(path, compression='gzip')
        results['ths_big_deal'] = len(df)
        logger.info(f"    ✅ {len(df)} 条")
    except Exception as e:
        logger.error(f"    ❌ 大单追踪失败: {e}")
    
    # Task 6: 行业资金流
    try:
        logger.info("  6. 行业资金流...")
        for symbol in ['即时', '3日排行', '5日排行', '10日排行']:
            df = ak.stock_fund_flow_industry(symbol=symbol)
            path = cf_dir / f"ths_industry_{today_compact}_{symbol}.parquet"
            df.to_parquet(path, compression='gzip')
        results['ths_industry'] = 4
        logger.info("    ✅ 4个周期完成")
    except Exception as e:
        logger.error(f"    ❌ 行业资金流失败: {e}")
    
    # Task 7: 概念资金流
    try:
        logger.info("  7. 概念资金流...")
        for symbol in ['即时', '3日排行', '5日排行', '10日排行']:
            df = ak.stock_fund_flow_concept(symbol=symbol)
            path = cf_dir / f"ths_concept_{today_compact}_{symbol}.parquet"
            df.to_parquet(path, compression='gzip')
        results['ths_concept'] = 4
        logger.info("    ✅ 4个周期完成")
    except Exception as e:
        logger.error(f"    ❌ 概念资金流失败: {e}")
    
    # Task 8: 北向资金
    try:
        logger.info("  8. 北向资金...")
        nb_dir = DATA_DIR / "money_flow" / "northbound"
        for symbol in ['沪股通', '深股通']:
            df = ak.stock_hsgt_hist_em(symbol=symbol)
            path = nb_dir / f"northbound_{symbol}.parquet"
            df.to_parquet(path, compression='gzip')
        results['northbound'] = 2
        logger.info("    ✅ 沪股通+深股通")
    except Exception as e:
        logger.error(f"    ❌ 北向资金失败: {e}")
    
    # Task 9: 龙虎榜
    try:
        logger.info("  9. 龙虎榜...")
        start_date = (pd.Timestamp(today) - timedelta(days=7)).strftime("%Y%m%d")
        end_date = today.replace("-", "")
        df = ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)
        path = DATA_DIR / "money_flow" / "dragon_tiger" / "dragon_tiger.parquet"
        df.to_parquet(path, compression='gzip')
        results['dragon_tiger'] = len(df)
        logger.info(f"    ✅ {len(df)} 条")
    except Exception as e:
        logger.error(f"    ❌ 龙虎榜失败: {e}")
    
    # Task 10: 融资融券
    try:
        logger.info("  10. 融资融券（上交所）...")
        start = (pd.Timestamp(today) - timedelta(days=30)).strftime("%Y%m%d")
        end = today.replace("-", "")
        df = ak.stock_margin_sse(start_date=start, end_date=end)
        path = DATA_DIR / "money_flow" / "margin_trading" / "margin_sse.parquet"
        df.to_parquet(path, compression='gzip')
        results['margin'] = len(df)
        logger.info(f"    ✅ {len(df)} 条")
    except Exception as e:
        logger.error(f"    ❌ 融资融券失败: {e}")
    
    # Task 11: 指数PE/PB
    try:
        logger.info("  11. 指数PE/PB...")
        val_dir = DATA_DIR / "valuation"
        for idx_name in ["上证50", "沪深300", "创业板50", "中证500"]:
            df_pe = ak.stock_index_pe_lg(symbol=idx_name)
            df_pe.to_parquet(val_dir / f"pe_{idx_name}.parquet", compression='gzip')
            df_pb = ak.stock_index_pb_lg(symbol=idx_name)
            df_pb.to_parquet(val_dir / f"pb_{idx_name}.parquet", compression='gzip')
        results['pe_pb'] = 8
        logger.info("    ✅ 4指数 PE+PB")
    except Exception as e:
        logger.error(f"    ❌ 指数估值失败: {e}")
    
    return results

# ============ 主函数 ============

def main():
    parser = argparse.ArgumentParser(description="Chaos Quant - 每日增量数据更新")
    parser.add_argument("--skip-minute", action="store_true", help="跳过分钟线更新（节省时间）")
    parser.add_argument("--skip-baostock", action="store_true", help="跳过 Baostock（只更新 AkShare）")
    parser.add_argument("--dry-run", action="store_true", help="模拟运行，不实际下载")
    parser.add_argument("--date", default=None, help="指定日期 YYYY-MM-DD（默认今天）")
    args = parser.parse_args()
    
    today = args.date or get_today()
    
    logger.info("🚀 Chaos Quant 每日增量更新")
    logger.info(f"  日期: {today}")
    logger.info(f"  项目: {PROJECT_ROOT}")
    logger.info(f"  数据: {DATA_DIR}")
    
    if not is_trade_day(today):
        logger.warning(f"⚠️ {today} 不是工作日，可能没有交易数据")
    
    t_start = time.time()
    
    # Baostock 数据
    if not args.skip_baostock:
        update_daily(today, args.dry_run)
        if not args.skip_minute:
            update_minute5(today, args.dry_run)
            update_minute30(today, args.dry_run)
    
    # AkShare 数据
    ak_results = update_akshare_data(today, args.dry_run)
    
    elapsed = time.time() - t_start
    logger.info("=" * 60)
    logger.info(f"🎉 每日更新完成! 耗时 {elapsed/60:.1f} 分钟")
    logger.info(f"  AkShare 结果: {ak_results}")

if __name__ == "__main__":
    main()
