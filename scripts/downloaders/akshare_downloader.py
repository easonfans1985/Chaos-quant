#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chaos Quant - AkShare 辅助数据下载器

功能：
1. 下载估值数据（PE/PB/市值）
2. 下载行业分类（申万）
3. 下载指数成分股
4. 下载资金流向数据
5. 下载交易日历
"""

import os
import sys
import yaml
import time
import argparse
import pandas as pd
from loguru import logger
from tqdm import tqdm
from pathlib import Path
from datetime import datetime


class AkShareDownloader:
    """AkShare 辅助数据下载器"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "settings.yaml"
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.data_base = Path(__file__).parent.parent.parent / self.config["data"]["base_dir"]
        self.data_base.mkdir(parents=True, exist_ok=True)

        self.request_interval = self.config.get("akshare", {}).get("request_interval", 0.5)

        logger.info("AkShareDownloader 初始化完成")

    def _save(self, df: pd.DataFrame, subdir: str, filename: str):
        """保存数据"""
        dir_path = self.data_base / subdir
        dir_path.mkdir(parents=True, exist_ok=True)
        filepath = dir_path / filename
        df.to_parquet(filepath, compression="gzip")
        logger.info(f"已保存: {filepath} ({len(df)} 行)")

    # ========== 交易日历 ==========

    def download_trade_calendar(self):
        """下载交易日历"""
        import akshare as ak
        logger.info("下载交易日历...")
        # 沪深A股交易日历
        df = ak.tool_trade_date_hist_sina()
        df.columns = ["trade_date"]
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        self._save(df, self.config["data"]["reference"]["trade_calendar"], "trade_calendar.parquet")
        return df

    # ========== 行业分类 ==========

    def download_industry_classification(self):
        """下载申万行业分类"""
        import akshare as ak
        logger.info("下载申万行业分类...")

        try:
            # 申万一级行业分类
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                self._save(df, self.config["data"]["reference"]["industry"], "sw_industry_list.parquet")
        except Exception as e:
            logger.warning(f"申万行业分类下载失败: {e}")

        try:
            # 行业成分股
            df_comp = ak.stock_board_industry_cons_em(symbol="小金属")
            if df_comp is not None and not df_comp.empty:
                self._save(df_comp, self.config["data"]["reference"]["industry"], "sample_industry_stocks.parquet")
        except Exception as e:
            logger.warning(f"行业成分股样例下载失败: {e}")

    def download_all_industry_stocks(self):
        """下载所有行业的成分股"""
        import akshare as ak
        logger.info("下载各行业成分股...")

        try:
            industry_list = ak.stock_board_industry_name_em()
            all_stocks = []
            for _, row in tqdm(industry_list.iterrows(), total=len(industry_list), desc="行业成分股"):
                try:
                    name = row.get("板块名称", row.iloc[0])
                    df = ak.stock_board_industry_cons_em(symbol=name)
                    if df is not None and not df.empty:
                        df["industry"] = name
                        all_stocks.append(df)
                    time.sleep(self.request_interval)
                except Exception as e:
                    logger.warning(f"[{name}] 跳过: {e}")
                    continue

            if all_stocks:
                result = pd.concat(all_stocks, ignore_index=True)
                self._save(result, self.config["data"]["reference"]["industry"], "all_industry_stocks.parquet")
        except Exception as e:
            logger.error(f"下载行业成分股失败: {e}")

    # ========== 指数成分股 ==========

    def download_index_components(self):
        """下载主要指数成分股"""
        import akshare as ak
        logger.info("下载指数成分股...")

        indices = {
            "000300": "沪深300",
            "000905": "中证500",
            "000852": "中证1000",
        }

        for index_code, name in indices.items():
            try:
                df = ak.index_stock_cons_csindex(symbol=index_code)
                if df is not None and not df.empty:
                    df["index_code"] = index_code
                    df["index_name"] = name
                    self._save(df, self.config["data"]["reference"]["index_components"],
                               f"index_{index_code}.parquet")
                time.sleep(self.request_interval)
            except Exception as e:
                logger.warning(f"[{name}] 成分股下载失败: {e}")

    # ========== 估值数据 ==========

    def download_valuation(self, trade_date: str = None):
        """
        下载全市场估值数据（PE/PB/市值）

        Args:
            trade_date: 交易日期 YYYYMMDD，默认最新
        """
        import akshare as ak
        logger.info("下载估值数据...")

        try:
            # 全市场 A 股估值（东方财富源）
            df = ak.stock_a_indicator_lg(symbol="all")
            if df is not None and not df.empty:
                self._save(df, self.config["data"]["valuation"], "a_stock_valuation.parquet")
        except Exception as e:
            logger.error(f"估值数据下载失败: {e}")

    # ========== 北向资金 ==========

    def download_northbound(self, start_date: str = None, end_date: str = None):
        """下载北向资金数据"""
        import akshare as ak
        logger.info("下载北向资金...")

        try:
            # 沪股通+深股通净买入
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="沪股通")
            if df is not None and not df.empty:
                self._save(df, self.config["data"]["money_flow"]["northbound"], "sh_northbound.parquet")

            time.sleep(self.request_interval)

            df2 = ak.stock_hsgt_north_net_flow_in_em(symbol="深股通")
            if df2 is not None and not df2.empty:
                self._save(df2, self.config["data"]["money_flow"]["northbound"], "sz_northbound.parquet")
        except Exception as e:
            logger.error(f"北向资金下载失败: {e}")

    # ========== 资金流向 ==========

    def download_capital_flow(self, trade_date: str = None):
        """下载个股资金流向"""
        import akshare as ak
        logger.info("下载个股资金流向...")

        try:
            if trade_date is None:
                trade_date = datetime.now().strftime("%Y%m%d")

            df = ak.stock_individual_fund_flow_rank(indicator="今日")
            if df is not None and not df.empty:
                self._save(df, self.config["data"]["money_flow"]["capital_flow"],
                           f"capital_flow_{trade_date}.parquet")
        except Exception as e:
            logger.error(f"资金流向下载失败: {e}")

    # ========== 融资融券 ==========

    def download_margin_trading(self):
        """下载融资融券数据"""
        import akshare as ak
        logger.info("下载融资融券数据...")

        try:
            df = ak.stock_margin_underlying_info_sz_sh(date=datetime.now().strftime("%Y%m%d"))
            if df is not None and not df.empty:
                self._save(df, self.config["data"]["money_flow"]["margin_trading"], "margin_data.parquet")
        except Exception as e:
            logger.error(f"融资融券下载失败: {e}")

    # ========== 龙虎榜 ==========

    def download_dragon_tiger(self, start_date: str = None, end_date: str = None):
        """下载龙虎榜数据"""
        import akshare as ak
        logger.info("下载龙虎榜...")

        try:
            if start_date is None:
                start_date = (datetime.now() - pd.Timedelta(days=30)).strftime("%Y%m%d")
            else:
                start_date = start_date.replace("-", "")
            if end_date is None:
                end_date = datetime.now().strftime("%Y%m%d")
            else:
                end_date = end_date.replace("-", "")

            df = ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                self._save(df, self.config["data"]["money_flow"]["dragon_tiger"], "dragon_tiger.parquet")
        except Exception as e:
            logger.error(f"龙虎榜下载失败: {e}")

    # ========== 基本面数据 ==========

    def download_stock_basic_info(self):
        """下载A股基本信息"""
        import akshare as ak
        logger.info("下载A股基本信息...")

        try:
            df = ak.stock_info_a_code_name()
            if df is not None and not df.empty:
                self._save(df, self.config["data"]["reference"]["industry"], "a_stock_basic.parquet")
        except Exception as e:
            logger.error(f"基本信息下载失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="Chaos Quant - AkShare 辅助数据下载器")
    parser.add_argument("--type", choices=[
        "calendar", "industry", "index", "valuation",
        "northbound", "capital_flow", "margin", "dragon_tiger",
        "basic", "all"
    ], default="all", help="下载类型")
    parser.add_argument("--start-date", default=None, help="开始日期")
    parser.add_argument("--end-date", default=None, help="结束日期")
    args = parser.parse_args()

    downloader = AkShareDownloader()

    if args.type in ("calendar", "all"):
        downloader.download_trade_calendar()

    if args.type in ("industry", "all"):
        downloader.download_industry_classification()

    if args.type in ("index", "all"):
        downloader.download_index_components()

    if args.type in ("valuation", "all"):
        downloader.download_valuation()

    if args.type in ("northbound", "all"):
        downloader.download_northbound(args.start_date, args.end_date)

    if args.type in ("capital_flow", "all"):
        downloader.download_capital_flow()

    if args.type in ("margin", "all"):
        downloader.download_margin_trading()

    if args.type in ("dragon_tiger", "all"):
        downloader.download_dragon_tiger(args.start_date, args.end_date)

    if args.type in ("basic", "all"):
        downloader.download_stock_basic_info()

    logger.info("AkShare 数据下载完成！")


if __name__ == "__main__":
    main()
