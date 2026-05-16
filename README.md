# Chaos Quant - A股个人量化交易系统

> 作者：easonfans1985 | 创建于：2026-05-16

## 项目简介

Chaos Quant 是一个面向个人投资者的 A 股量化交易系统，支持数据自动采集、策略回测、AI 辅助分析。

## 技术选型

| 组件 | 选择 |
|------|------|
| 数据源 | Baostock（行情+财务）+ AkShare（资金+板块+宏观） |
| 存储格式 | Parquet 文件 |
| 回测框架 | VectorBT（主力）+ Backtrader（备选） |
| 开发语言 | Python 3.12 |
| AI 层 | OpenClaw agent |
| 版本管理 | Git + GitHub |

## 目录结构

```
Chaos-quant/
├── config/              # 配置文件
│   └── settings.yaml    # 主配置
├── data/                # 数据存储（不提交到 Git）
│   ├── market/          # 行情数据
│   │   ├── daily/       # 日线
│   │   ├── minute_5/    # 5分钟线
│   │   ├── minute_15/   # 15分钟线
│   │   ├── minute_30/   # 30分钟线
│   │   └── minute_60/   # 60分钟线
│   ├── fundamental/     # 基本面数据
│   │   ├── financial_report/   # 三大报表
│   │   ├── financial_indicator/ # 财务指标
│   │   └── dividend/    # 分红配股
│   ├── valuation/       # 估值数据（PE/PB/市值）
│   ├── reference/       # 参考数据
│   │   ├── industry/    # 行业分类
│   │   ├── sector/      # 板块概念
│   │   ├── index_components/ # 指数成分
│   │   └── trade_calendar/ # 交易日历
│   ├── money_flow/      # 资金流向
│   │   ├── northbound/  # 北向资金
│   │   ├── capital_flow/ # 个股资金流
│   │   ├── margin_trading/ # 融资融券
│   │   └── dragon_tiger/ # 龙虎榜
│   └── other/           # 其他数据
│       ├── shareholder/ # 股东数据
│       ├── lockup/      # 限售解禁
│       └── macro/       # 宏观指标
├── scripts/             # 脚本
│   ├── downloaders/     # 数据下载器
│   ├── utils/           # 工具函数
│   └── analysis/        # 分析脚本
├── strategies/          # 策略代码
├── tests/               # 测试
└── docs/                # 文档
```

## 数据源分配

| 数据类型 | 来源 | 说明 |
|----------|------|------|
| 日线/分钟线行情 | Baostock | 质量高，有复权因子 |
| 指数行情 | Baostock | 覆盖主要指数 |
| 财务报表/指标 | Baostock | 字段全，质量稳定 |
| 分红配股 | Baostock | 字段更全 |
| 估值（PE/PB/市值） | AkShare | 东方财富源 |
| 行业分类（申万） | AkShare | Baostock 没有 |
| 板块/概念 | AkShare | 只有它有 |
| 指数成分股 | AkShare | 更全更及时 |
| 北向资金 | AkShare | 东方财富源 |
| 资金流向 | AkShare | 东方财富源 |
| 融资融券 | AkShare | 东方财富源 |
| 龙虎榜 | AkShare | 东方财富源 |
| 限售解禁 | AkShare | 东方财富源 |
| 交易日历 | exchange-calendars | 最准确 |
| 股东数据 | AkShare | 更及时 |

## 开发流程

1. OpenClaw agent 负责规划和设计
2. Claude Code 负责具体编码
3. 代码提交到 GitHub：github.com/easonfans1985/Chaos-quant

## 现有数据

位置：`/Users/mac/qlib/qlib_data_new/`（可直接复用）
- 日线行情：5000+ 只（停更于 2026-01-10）
- 30分钟线：5399 只
- 财务报告：783 只
- 基本信息：有
