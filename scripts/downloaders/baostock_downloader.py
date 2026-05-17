#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chaos Quant - Baostock 行情数据下载器

功能：
1. 下载日线和5分钟线行情数据
2. 下载复权因子
3. 下载指数行情
4. 支持增量更新
5. 断点续传
"""

import os
import sys
import yaml
import time
import signal
import argparse
import pandas as pd
import baostock as bs
from loguru import logger
from tqdm import tqdm
from datetime import datetime, timedelta
from pathlib import Path


class BaoStockDownloader:
    """Baostock 行情数据下载器"""

    def __init__(self, config_path: str = None):
        # 加载配置
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.data_base = Path(__file__).parent.parent.parent / self.config["data"]["base_dir"]
        self.data_base.mkdir(parents=True, exist_ok=True)

        # 下载状态文件（用于断点续传）
        self.state_file = self.data_base / ".download_state.json"

        # 优雅退出
        self._running = True
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # 请求间隔
        self.request_interval = self.config["download"]["request_interval"]

        logger.info("BaoStockDownloader 初始化完成")

    def _signal_handler(self, signum, frame):
        logger.warning("收到退出信号，正在保存状态...")
        self._running = False

    def _load_state(self) -> dict:
        """加载下载状态"""
        if self.state_file.exists():
            import json
            with open(self.state_file, "r") as f:
                return json.load(f)
        return {}

    def _save_state(self, state: dict):
        """保存下载状态"""
        import json
        with open(self.state_file, "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def login(self):
        """登录 Baostock"""
        lg = bs.login()
        if lg.error_code != "0":
            logger.error(f"Baostock 登录失败: {lg.error_msg}")
            sys.exit(1)
        logger.info("Baostock 登录成功")

    def logout(self):
        """登出 Baostock"""
        bs.logout()
        logger.info("Baostock 已登出")

    def get_stock_list(self) -> pd.DataFrame:
        """获取全部A股股票列表"""
        logger.info("获取股票列表...")
        rs = bs.query_stock_basic()
        stock_list = []
        while rs.error_code == "0" and rs.next():
            stock_list.append(rs.get_row_data())

        df = pd.DataFrame(stock_list, columns=rs.fields)

        # 只要正常上市的股票（type=1股票，status=1上市）
        df = df[(df["type"] == "1") & (df["status"] == "1")]
        logger.info(f"获取到 {len(df)} 只上市股票")
        return df

    def get_index_list(self) -> list:
        """获取主要指数代码列表"""
        indices = [
            "sh.000001",   # 上证指数
            "sh.000002",   # 上证A指
            "sh.000003",   # 上证B指
            "sh.000016",   # 上证50
            "sh.000300",   # 沪深300
            "sh.000905",   # 中证500
            "sh.000906",   # 中证800
            "sh.000852",   # 中证1000
            "sz.399001",   # 深证成指
            "sz.399003",   # 成份B指
            "sz.399005",   # 中小板指
            "sz.399006",   # 创业板指
            "sz.399673",   # 创业板50
            "sh.000688",   # 科创50
        ]
        return indices

    def get_etf_list(self) -> list:
        """获取ETF基金列表"""
        logger.info("获取ETF列表...")
        rs = bs.query_stock_basic()
        etf_list = []
        while rs.error_code == "0" and rs.next():
            row = rs.get_row_data()
            # type=2 基金，code以 sh.51/sz.15/sz.16 开头多为ETF
            if row[2] == "2":  # type字段
                code = row[0]  # code字段
                if any(code.startswith(prefix) for prefix in
                       ["sh.51", "sz.15", "sz.16", "sh.56", "sh.58"]):
                    etf_list.append(code)
        logger.info(f"获取到 {len(etf_list)} 只ETF")
        return etf_list

    def download_daily(self, code: str, start_date: str, end_date: str,
                       adjust_flag: str = "3") -> pd.DataFrame:
        """
        下载日线行情

        Args:
            code: 股票代码，如 sh.600000
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            adjust_flag: 复权类型 1-后复权 2-前复权 3-不复权
        """
        rs = bs.query_history_k_data_plus(
            code,
            "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag=adjust_flag,
        )

        data = []
        while rs.error_code == "0" and rs.next():
            data.append(rs.get_row_data())

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data, columns=rs.fields)

        # 类型转换
        numeric_cols = ["open", "high", "low", "close", "preclose",
                        "volume", "amount", "turn", "pctChg"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        return df

    def download_minute(self, code: str, start_date: str, end_date: str,
                        frequency: str = "5", adjust_flag: str = "3") -> pd.DataFrame:
        """
        下载分钟线行情

        Args:
            code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            frequency: 5/15/30/60
            adjust_flag: 复权类型
        """
        rs = bs.query_history_k_data_plus(
            code,
            "date,time,code,open,high,low,close,volume,amount,adjustflag",
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            adjustflag=adjust_flag,
        )

        data = []
        while rs.error_code == "0" and rs.next():
            data.append(rs.get_row_data())

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data, columns=rs.fields)

        numeric_cols = ["open", "high", "low", "close", "volume", "amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 分钟线用 datetime 作为索引
        df["datetime"] = pd.to_datetime(df["date"] + " " + df["time"].str.slice(0, 2) + ":" + df["time"].str.slice(2, 4))
        df.set_index("datetime", inplace=True)
        df.drop(columns=["date", "time"], inplace=True)
        return df

    def download_adjust_factor(self, code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """下载复权因子"""
        rs = bs.query_adjust_factor(code=code, start_date=start_date, end_date=end_date)

        data = []
        while rs.error_code == "0" and rs.next():
            data.append(rs.get_row_data())

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data, columns=rs.fields)
        numeric_cols = ["foreAdjustFactor", "backAdjustFactor", "adjustFactor"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)
        return df

    def _get_existing_data_end_date(self, filepath: Path) -> str:
        """获取已有数据的最后日期，用于增量更新"""
        if not filepath.exists():
            return None
        try:
            df = pd.read_parquet(filepath)
            if df.empty:
                return None
            last_date = df.index.max()
            # 处理索引类型不一致（Qlib迁移数据可能是int索引）
            if not isinstance(last_date, pd.Timestamp):
                return None
            return last_date.strftime("%Y-%m-%d")
        except Exception:
            return None

    def _save_data(self, df: pd.DataFrame, filepath: Path):
        """保存数据到 parquet（增量追加）"""
        filepath.parent.mkdir(parents=True, exist_ok=True)

        if filepath.exists():
            existing = pd.read_parquet(filepath)
            # 如果已有数据索引不是 datetime（如 Qlib 迁移的 int 索引），全量覆盖
            if not isinstance(existing.index, pd.DatetimeIndex):
                df.to_parquet(filepath, compression="gzip")
                return
            # 合并，去重（按索引）
            combined = pd.concat([existing, df])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined.sort_index(inplace=True)
            combined.to_parquet(filepath, compression="gzip")
        else:
            df.to_parquet(filepath, compression="gzip")

    def download_stock_daily_batch(self, stock_codes: list, start_date: str, end_date: str,
                                   desc: str = "下载日线"):
        """批量下载股票日线"""
        state = self._load_state()
        state_key = f"daily_{desc}"
        done_codes = state.get(state_key, [])

        daily_dir = self.data_base / self.config["data"]["market"]["daily"]
        daily_dir.mkdir(parents=True, exist_ok=True)

        pending = [c for c in stock_codes if c not in done_codes]
        logger.info(f"[{desc}] 总计 {len(stock_codes)} 只，已完成 {len(done_codes)}，待下载 {len(pending)}")

        for code in tqdm(pending, desc=desc):
            if not self._running:
                logger.warning("用户中断，保存状态...")
                break

            try:
                filepath = daily_dir / f"{code}.parquet"

                # 增量更新：获取已有数据的最后日期
                existing_end = self._get_existing_data_end_date(filepath)
                if existing_end:
                    # 从已有数据的下一天开始
                    next_day = (pd.Timestamp(existing_end) + timedelta(days=1)).strftime("%Y-%m-%d")
                    if next_day > end_date:
                        # 数据已是最新
                        done_codes.append(code)
                        continue
                    df = self.download_daily(code, next_day, end_date)
                else:
                    df = self.download_daily(code, start_date, end_date)

                if not df.empty:
                    self._save_data(df, filepath)

                done_codes.append(code)
                time.sleep(self.request_interval)

            except Exception as e:
                logger.error(f"[{code}] 下载失败: {e}")
                time.sleep(1)

        state[state_key] = done_codes
        self._save_state(state)
        logger.info(f"[{desc}] 完成，共下载 {len(done_codes)} 只")

    def download_stock_minute_batch(self, stock_codes: list, start_date: str, end_date: str,
                                     frequency: str = "5", desc: str = "下载5分钟线"):
        """批量下载分钟线"""
        state = self._load_state()
        state_key = f"minute_{frequency}_{desc}"
        done_codes = state.get(state_key, [])

        freq_map = {"5": "minute_5", "15": "minute_15", "30": "minute_30", "60": "minute_60"}
        minute_dir = self.data_base / self.config["data"]["market"][freq_map[frequency]]
        minute_dir.mkdir(parents=True, exist_ok=True)

        pending = [c for c in stock_codes if c not in done_codes]
        logger.info(f"[{desc}] 总计 {len(stock_codes)}，已完成 {len(done_codes)}，待下载 {len(pending)}")

        for code in tqdm(pending, desc=desc):
            if not self._running:
                logger.warning("用户中断，保存状态...")
                break

            try:
                filepath = minute_dir / f"{code}.parquet"

                existing_end = self._get_existing_data_end_date(filepath)
                if existing_end:
                    next_day = (pd.Timestamp(existing_end) + timedelta(days=1)).strftime("%Y-%m-%d")
                    if next_day > end_date:
                        done_codes.append(code)
                        continue
                    df = self.download_minute(code, next_day, end_date, frequency)
                else:
                    df = self.download_minute(code, start_date, end_date, frequency)

                if not df.empty:
                    self._save_data(df, filepath)

                done_codes.append(code)
                time.sleep(self.request_interval)

            except Exception as e:
                logger.error(f"[{code}] 下载失败: {e}")
                time.sleep(1)

        state[state_key] = done_codes
        self._save_state(state)
        logger.info(f"[{desc}] 完成，共下载 {len(done_codes)} 只")


def main():
    parser = argparse.ArgumentParser(description="Chaos Quant - Baostock 行情数据下载器")
    parser.add_argument("--mode", choices=["daily", "minute5", "all"], default="all",
                        help="下载模式：daily-仅日线，minute5-仅5分钟线，all-全部")
    parser.add_argument("--scope", choices=["all", "hs300", "etf", "index", "etf_index_hs300"],
                        default=None, help="股票范围")
    parser.add_argument("--start-date", default=None, help="开始日期 YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="结束日期 YYYY-MM-DD")
    args = parser.parse_args()

    downloader = BaoStockDownloader()

    # 读取配置
    cfg = downloader.config["download"]
    scope = args.scope or cfg["scope"]
    start_date = args.start_date or cfg["start_date"]
    end_date = args.end_date or cfg["end_date"]

    logger.info(f"开始下载 | 范围: {scope} | 日期: {start_date} ~ {end_date} | 模式: {args.mode}")

    try:
        downloader.login()

        stock_codes = []
        index_codes = []
        etf_codes = []

        if scope in ("all", "etf_index_hs300"):
            stocks = downloader.get_stock_list()
            stock_codes = stocks["code"].tolist()
            index_codes = downloader.get_index_list()
            etf_codes = downloader.get_etf_list()
        elif scope == "etf":
            etf_codes = downloader.get_etf_list()
        elif scope == "index":
            index_codes = downloader.get_index_list()
        elif scope == "hs300":
            # TODO: 从 AkShare 获取沪深300成分
            logger.warning("hs300 范围暂未实现，请使用 etf_index_hs300")
            return

        # 下载日线
        if args.mode in ("daily", "all"):
            all_codes = stock_codes + etf_codes + index_codes
            if all_codes:
                downloader.download_stock_daily_batch(all_codes, start_date, end_date, desc="全部日线")

        # 下载5分钟线
        if args.mode in ("minute5", "all"):
            # 分钟线只下载 ETF + 指数 + 可选成分股
            minute_codes = etf_codes + index_codes
            if minute_codes:
                downloader.download_stock_minute_batch(
                    minute_codes, start_date, end_date,
                    frequency="5", desc="ETF+指数5分钟线"
                )

    finally:
        downloader.logout()

    logger.info("全部下载完成！")


if __name__ == "__main__":
    main()
