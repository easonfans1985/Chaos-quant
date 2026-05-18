# strategies/__init__.py
# 全部 24 个策略导出

# 第一层：基础技术（6个）
from .sma_cross import SMACrossStrategy
from .rsi_strategy import RSIStrategy
from .bollinger_strategy import BollingerStrategy
from .macd_divergence import MACDDivergenceStrategy
from .kdj_strategy import KDJStrategy
from .atr_breakout import ATRBreakoutStrategy

# 第二层：资金流驱动（4个）
from .fund_flow_inflow import FundFlowInflowStrategy
from .sector_rotation import SectorRotationStrategy
from .big_deal_track import BigDealTrackStrategy
from .northbound_follow import NorthboundFollowStrategy

# 第三层：基本面+事件（4个）
from .value_pick import ValuePickStrategy
from .earnings_surprise import EarningsSurpriseStrategy
from .buyback_signal import BuybackSignalStrategy
from .lockup_avoid import LockupAvoidStrategy

# 第四层：统计套利+因子（4个）
from .pair_trading import PairTradingStrategy
from .etf_premium import ETFPremiumStrategy
from .momentum_factor import MomentumFactorStrategy
from .multi_factor import MultiFactorStrategy

# 第五层：风控+仓位（3个）
from .risk_atr_position import ATRPositionStrategy
from .risk_max_drawdown import MaxDrawdownStrategy
from .risk_correlation import CorrelationDiversifyStrategy

# 第六层：市场择时（3个）
from .market_valuation import MarketValuationStrategy
from .market_northbound import NorthboundTimingStrategy
from .market_margin import MarginTimingStrategy

# 策略注册表（名称 → 类）
ALL_STRATEGIES = {
    # 基础技术
    "SMA Cross": SMACrossStrategy,
    "RSI": RSIStrategy,
    "Bollinger Bands": BollingerStrategy,
    "MACD Divergence": MACDDivergenceStrategy,
    "KDJ": KDJStrategy,
    "ATR Breakout": ATRBreakoutStrategy,
    # 资金流
    "Fund Flow Inflow": FundFlowInflowStrategy,
    "Sector Rotation": SectorRotationStrategy,
    "Big Deal Track": BigDealTrackStrategy,
    "Northbound Follow": NorthboundFollowStrategy,
    # 基本面+事件
    "Value Pick": ValuePickStrategy,
    "Earnings Surprise": EarningsSurpriseStrategy,
    "Buyback Signal": BuybackSignalStrategy,
    "Lockup Avoid": LockupAvoidStrategy,
    # 统计套利+因子
    "Pair Trading": PairTradingStrategy,
    "ETF Premium": ETFPremiumStrategy,
    "Momentum Factor": MomentumFactorStrategy,
    "Multi Factor": MultiFactorStrategy,
    # 风控+仓位
    "ATR Position": ATRPositionStrategy,
    "Max Drawdown Stop": MaxDrawdownStrategy,
    "Correlation Diversify": CorrelationDiversifyStrategy,
    # 市场择时
    "Market Valuation": MarketValuationStrategy,
    "Market Northbound": NorthboundTimingStrategy,
    "Market Margin": MarginTimingStrategy,
}
