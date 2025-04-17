"""
Solana交易分析模块
负责分析交易模式和策略特征
"""
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
import statistics
from collections import defaultdict, Counter

from .collector import SolanaCollector
from ..config import Config
from ..utils.helpers import datetime_to_unix_time, unix_time_to_datetime

logger = logging.getLogger(__name__)

class TransactionAnalyzer:
    """Solana交易分析器"""
    
    def __init__(self, collector: SolanaCollector, config: Config):
        """
        初始化交易分析器
        
        Args:
            collector: Solana数据收集器实例
            config: 配置对象
        """
        self.collector = collector
        self.config = config
        
    async def analyze_wallet_trading_pattern(
        self, 
        wallet_address: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        分析钱包的交易模式
        
        Args:
            wallet_address: 钱包地址
            days: 分析最近多少天的数据
            
        Returns:
            交易模式分析结果字典
        """
        # 获取交易历史
        swap_txs = await self.collector.fetch_recent_swap_transactions(
            wallet_address, 
            days=days
        )
        
        if not swap_txs:
            return {
                "success": False,
                "error": "没有找到交换交易数据",
                "wallet": wallet_address,
                "analyzed_days": days
            }
            
        # 分析结果
        result = {
            "success": True,
            "wallet": wallet_address,
            "analyzed_days": days,
            "transaction_count": len(swap_txs),
            "first_transaction_time": None,
            "last_transaction_time": None,
            "tokens_traded": set(),
            "trading_frequency": {},
            "trading_volume": {},
            "trading_amount_distribution": {},
            "preferred_dexs": {},
            "trading_time_patterns": {},
            "token_holding_periods": {},
            "token_pairs_frequency": {},
            "position_sizing": {},
            "win_loss_ratio": {},
            "slippage_data": {},
            "profitability_analysis": {}
        }
        
        # 先从基本统计开始
        token_trades = defaultdict(list)  # 按代币分类的交易
        token_amounts = defaultdict(list)  # 每个代币的交易金额
        dexs_used = Counter()  # 使用的DEX计数
        hourly_distribution = [0] * 24  # 每小时交易分布
        
        # 按时间排序
        sorted_txs = sorted(swap_txs, key=lambda tx: tx.get("blockTime", 0))
        
        if sorted_txs:
            result["first_transaction_time"] = unix_time_to_datetime(sorted_txs[0].get("blockTime", 0)).isoformat()
            result["last_transaction_time"] = unix_time_to_datetime(sorted_txs[-1].get("blockTime", 0)).isoformat()
        
        # 分析每个交易
        for tx in sorted_txs:
            # 提取交易时间
            block_time = tx.get("blockTime", 0)
            tx_time = unix_time_to_datetime(block_time)
            
            # 更新小时分布
            hour = tx_time.hour
            hourly_distribution[hour] += 1
            
            # 识别DEX(根据程序ID)
            if tx.get("transaction") and tx["transaction"].get("message"):
                account_keys = tx["transaction"]["message"].get("accountKeys", [])
                
                # DEX识别逻辑
                if "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4" in account_keys:
                    dexs_used["Jupiter V4"] += 1
                elif "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB" in account_keys:
                    dexs_used["Jupiter V3"] += 1
                elif "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP" in account_keys:
                    dexs_used["Raydium"] += 1
                elif "EMAKHqYYkYvBwAYBQ9WqCHSR8PeqLyYLt2ahcXbgjKiW" in account_keys:
                    dexs_used["Raydium LP"] += 1
                else:
                    dexs_used["Other DEX"] += 1
                    
            # TODO: 这部分需要实际解析交易数据来提取代币和金额
            # 这需要详细的Solana交易解析逻辑，此处仅为框架示例
            # 实际实现时需要根据不同DEX的交易格式解析交易日志
        
        # 编译结果
        # 交易频率分析
        daily_counts = defaultdict(int)
        for tx in sorted_txs:
            tx_date = unix_time_to_datetime(tx.get("blockTime", 0)).date().isoformat()
            daily_counts[tx_date] += 1
            
        result["trading_frequency"] = {
            "daily_average": len(sorted_txs) / days if days > 0 else 0,
            "daily_distribution": dict(daily_counts),
            "hourly_distribution": dict(enumerate(hourly_distribution)),
            "max_transactions_in_day": max(daily_counts.values()) if daily_counts else 0,
            "days_with_activity": len(daily_counts)
        }
        
        # DEX偏好
        result["preferred_dexs"] = dict(dexs_used)
        
        # 将集合转换为列表(JSON可序列化)
        result["tokens_traded"] = list(result["tokens_traded"])
        
        return result
        
    async def analyze_trading_pattern(
        self,
        wallet_address: str,
        days: int = 30,
        model_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        全面分析交易模式并生成策略建议
        
        Args:
            wallet_address: 钱包地址
            days: 分析最近多少天的数据
            model_config: AI模型配置
            
        Returns:
            详细的分析结果和策略建议
        """
        # 获取基础分析数据
        base_analysis = await self.analyze_wallet_trading_pattern(wallet_address, days)
        
        if not base_analysis.get("success"):
            return base_analysis
            
        # 收集更多详细数据
        # 1. 历史交易数据
        swap_txs = await self.collector.fetch_recent_swap_transactions(
            wallet_address, 
            days=days
        )
        
        # 2. 价格历史数据(这里需要实际实现)
        # price_history = await self._fetch_price_history(tokens, days)
        
        # 3. 深度历史数据(这里需要实际实现)
        # depth_history = await self._fetch_depth_history(token_pairs, days)
        
        # 4. 成交量历史(这里需要实际实现)
        # volume_history = await self._fetch_volume_history(tokens, days)
        
        # 5. 池子数据(这里需要实际实现)
        # pool_history = await self._fetch_pool_history(token_pairs, days)
        
        # 准备分析数据
        analysis_data = {
            "wallet_address": wallet_address,
            "base_analysis": base_analysis,
            "trading_history": swap_txs,
            # 下面部分在实际实现时需要填充
            "price_history": {},  # 代币价格历史
            "depth_history": {},  # 市场深度历史
            "volume_history": {},  # 成交量历史
            "pool_history": {},   # 流动性池子历史
            "market_sentiment": await self._get_market_sentiment(),
            "liquidity_data": await self._get_liquidity_data(),
            "routing_efficiency": await self._get_routing_efficiency(),
            "execution_performance": await self._get_execution_performance(),
            "slippage_analysis": await self._get_slippage_analysis(),
            "transaction_anomalies": await self._detect_transaction_anomalies(),
            "market_anomalies": await self._detect_market_anomalies()
        }
        
        # 构建请求LLM进行分析的数据
        return await self._request_llm_analysis(analysis_data, model_config)
        
    async def _get_market_sentiment(self) -> Dict[str, Any]:
        """获取市场情绪数据"""
        # 实际实现时应该获取真实数据
        return {
            "overall_sentiment": "neutral",
            "market_fear_greed_index": 50,
            "trending_tokens": ["SOL", "JTO", "BONK"],
            "sentiment_by_token": {
                "SOL": "bullish",
                "JTO": "neutral",
                "BONK": "bullish"
            }
        }
        
    async def _get_liquidity_data(self) -> Dict[str, Any]:
        """获取流动性数据"""
        # 实际实现时应该获取真实数据
        return {
            "overall_liquidity": "high",
            "liquidity_by_token": {
                "SOL": "very high",
                "JTO": "medium",
                "BONK": "high"
            },
            "liquidity_trends": "increasing"
        }
        
    async def _get_routing_efficiency(self) -> Dict[str, Any]:
        """获取路由效率数据"""
        # 实际实现时应该获取真实数据
        return {
            "average_routing_efficiency": 0.92,
            "optimal_route_frequency": 0.85,
            "suboptimal_routes": [
                {"pair": "SOL/JTO", "efficiency": 0.76},
                {"pair": "BONK/USDC", "efficiency": 0.82}
            ]
        }
        
    async def _get_execution_performance(self) -> Dict[str, Any]:
        """获取执行性能数据"""
        # 实际实现时应该获取真实数据
        return {
            "average_execution_time": 1.2,  # 秒
            "execution_success_rate": 0.98,
            "failure_reasons": {
                "slippage_too_high": 0.01,
                "insufficient_funds": 0.005,
                "price_impact_too_high": 0.005
            }
        }
        
    async def _get_slippage_analysis(self) -> Dict[str, Any]:
        """获取滑点分析数据"""
        # 实际实现时应该获取真实数据
        return {
            "average_slippage": 0.3,  # 百分比
            "slippage_by_token": {
                "SOL": 0.2,
                "JTO": 0.5,
                "BONK": 0.4
            },
            "slippage_by_trade_size": {
                "small": 0.2,  # <$100
                "medium": 0.3,  # $100-$1000
                "large": 0.6   # >$1000
            }
        }
        
    async def _detect_transaction_anomalies(self) -> Dict[str, Any]:
        """检测交易异常"""
        # 实际实现时应该分析真实数据
        return {
            "unusual_trade_sizes": [
                {"timestamp": "2023-04-01T12:34:56Z", "token": "SOL", "amount": 100, "deviation": 5.2}
            ],
            "timing_anomalies": [
                {"pattern": "unusually high frequency", "period": "2023-04-01T12:00:00Z to 2023-04-01T13:00:00Z"}
            ],
            "price_impact_anomalies": [
                {"timestamp": "2023-04-02T08:12:34Z", "token": "JTO", "impact": 4.5, "expected_max": 2.0}
            ]
        }
        
    async def _detect_market_anomalies(self) -> Dict[str, Any]:
        """检测市场异常"""
        # 实际实现时应该分析真实数据
        return {
            "liquidity_anomalies": [
                {"token": "JTO", "timestamp": "2023-04-03T15:45:00Z", "event": "sudden liquidity decrease"}
            ],
            "volatility_spikes": [
                {"token": "BONK", "timestamp": "2023-04-02T19:30:00Z", "volatility_increase": 120}
            ],
            "correlated_movements": [
                {"tokens": ["SOL", "JTO"], "correlation": 0.92, "period": "2023-04-01 to 2023-04-05"}
            ]
        }
        
    async def _request_llm_analysis(
        self, 
        analysis_data: Dict[str, Any],
        model_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        请求大型语言模型进行分析
        
        Args:
            analysis_data: 分析数据
            model_config: 模型配置
            
        Returns:
            分析结果
        """
        # 设置默认配置
        if model_config is None:
            model_config = {
                "model": "gpt-4",
                "temperature": 0.2,
                "max_tokens": 2500
            }
            
        # 构建系统提示
        system_prompt = """
        你是一位专业的加密货币交易策略分析师，专注于Solana生态系统的交易模式分析。
        你的任务是分析提供的交易数据，识别交易模式，并提取完整的自动化交易策略。
        
        请仔细分析提供的数据，包括:
        1. 交易历史
        2. 价格历史
        3. 市场深度
        4. 成交量数据
        5. 流动性池数据
        6. 市场情绪
        7. 滑点分析
        8. 异常检测结果
        
        你的输出必须是严格的JSON格式，包含以下关键部分:
        
        1. 交易模式识别
        2. 策略提取
        3. 改进建议
        4. 风险分析
        
        确保你的分析全面、详细，并基于数据提供具体的策略参数。
        """
        
        # 构建用户提示
        user_prompt = f"""
        请分析以下交易数据并提取完整的交易策略:
        
        钱包地址: {analysis_data['wallet_address']}
        分析时段: {analysis_data['base_analysis']['analyzed_days']} 天
        交易次数: {analysis_data['base_analysis']['transaction_count']}
        
        请根据以下数据进行分析:
        
        1. 基础分析:
        - 交易频率: {json.dumps(analysis_data['base_analysis']['trading_frequency'])}
        - 偏好的DEX: {json.dumps(analysis_data['base_analysis']['preferred_dexs'])}
        - 交易代币: {json.dumps(analysis_data['base_analysis']['tokens_traded'])}
        
        2. 市场情绪数据:
        {json.dumps(analysis_data['market_sentiment'])}
        
        3. 流动性数据:
        {json.dumps(analysis_data['liquidity_data'])}
        
        4. 路由效率:
        {json.dumps(analysis_data['routing_efficiency'])}
        
        5. 执行性能:
        {json.dumps(analysis_data['execution_performance'])}
        
        6. 滑点分析:
        {json.dumps(analysis_data['slippage_analysis'])}
        
        7. 交易异常:
        {json.dumps(analysis_data['transaction_anomalies'])}
        
        8. 市场异常:
        {json.dumps(analysis_data['market_anomalies'])}
        
        请提供以下输出格式的分析结果:
        
        {
            "pattern_recognition": {
                "primary_pattern": "主要交易模式",
                "secondary_patterns": ["次要模式1", "次要模式2"],
                "timing_patterns": "时间模式分析",
                "token_selection_logic": "代币选择逻辑"
            },
            "strategy": {
                "name": "策略名称",
                "description": "策略简要描述",
                "target_selection": {
                    "criteria": ["选择标准1", "选择标准2"],
                    "filters": ["过滤条件1", "过滤条件2"]
                },
                "entry_strategy": {
                    "triggers": ["入场触发条件1", "入场触发条件2"],
                    "confirmation_signals": ["确认信号1", "确认信号2"],
                    "optimal_timing": "最佳入场时机描述"
                },
                "exit_strategy": {
                    "take_profit": "止盈策略",
                    "stop_loss": "止损策略",
                    "trailing_mechanisms": "追踪止损机制"
                },
                "position_management": {
                    "sizing": "仓位大小计算方法",
                    "scaling": "加减仓策略",
                    "hedging": "对冲策略(如适用)"
                },
                "risk_control": {
                    "max_position_size": "最大仓位建议",
                    "max_daily_loss": "每日最大亏损限制",
                    "correlation_management": "相关性管理策略"
                },
                "automation_flow": {
                    "monitoring_frequency": "监控频率",
                    "trigger_actions": ["触发动作1", "触发动作2"],
                    "fallback_procedures": ["应急程序1", "应急程序2"]
                }
            },
            "improvement_suggestions": {
                "efficiency_gains": ["效率提升建议1", "效率提升建议2"],
                "risk_reduction": ["风险降低建议1", "风险降低建议2"],
                "profitability_enhancements": ["盈利能力提升建议1", "盈利能力提升建议2"]
            },
            "risk_analysis": {
                "identified_risks": ["已识别风险1", "已识别风险2"],
                "mitigation_strategies": ["风险缓解策略1", "风险缓解策略2"],
                "market_dependency_factors": ["市场依赖因素1", "市场依赖因素2"]
            }
        }
        """
        
        # 实际实现时，这里应调用配置的大型语言模型API
        # 例如 OpenAI API, Azure OpenAI, Anthropic Claude等
        
        # 模拟返回结果(实际应用中需要实现真实API调用)
        return {
            "success": True,
            "analysis_request": {
                "wallet_address": analysis_data['wallet_address'],
                "days_analyzed": analysis_data['base_analysis']['analyzed_days'],
                "transaction_count": analysis_data['base_analysis']['transaction_count']
            },
            "analysis_result": {
                "pattern_recognition": {
                    "primary_pattern": "短期动量跟踪与反转点捕捉",
                    "secondary_patterns": ["流动性突破", "波动率收缩后的爆发"],
                    "timing_patterns": "倾向于亚洲交易时段(UTC+8)开始,美国交易时段(UTC-5)结束前执行交易",
                    "token_selection_logic": "偏好高波动性但有足够流动性的中小市值代币"
                },
                "strategy": {
                    "name": "Solana生态动量波段捕捉策略",
                    "description": "利用短期价格动量识别潜在趋势,在确认信号出现后入场,设置紧密止损和分散止盈目标",
                    "target_selection": {
                        "criteria": ["24小时成交量>$200,000", "市值<$100M", "日波动率>5%"],
                        "filters": ["排除近期已下跌超过30%的代币", "必须在至少3个主要DEX有足够流动性"]
                    },
                    "entry_strategy": {
                        "triggers": ["价格突破4小时EMA", "成交量比前3日平均增加50%"],
                        "confirmation_signals": ["RSI(4)从超卖区回升", "MACD柱状图转正"],
                        "optimal_timing": "亚洲交易时段早期或美国交易时段开始后1小时内"
                    },
                    "exit_strategy": {
                        "take_profit": "分散设置:30%仓位在5%利润退出,50%在10%退出,20%在20%或更高退出",
                        "stop_loss": "入场价下方3-5%,具体根据token历史波动率调整",
                        "trailing_mechanisms": "在利润达到8%后启动3%追踪止损"
                    },
                    "position_management": {
                        "sizing": "单次交易使用可用资金的5-15%,根据信号强度调整",
                        "scaling": "在利润达到8%且确认趋势继续时增加25%仓位",
                        "hedging": "在大额仓位建立后,使用小仓位做空SOL作为市场风险对冲"
                    },
                    "risk_control": {
                        "max_position_size": "单个代币最大持仓不超过总资产的20%",
                        "max_daily_loss": "设置2%账户价值的每日止损限制",
                        "correlation_management": "同时持有的代币相关性应低于0.7"
                    },
                    "automation_flow": {
                        "monitoring_frequency": "价格和成交量每10分钟检查一次",
                        "trigger_actions": ["入场信号时立即市价单买入", "止损触发时无缓冲立即卖出"],
                        "fallback_procedures": ["大市场波动时暂停自动交易", "单日损失超过阈值后24小时内不开新仓"]
                    }
                },
                "improvement_suggestions": {
                    "efficiency_gains": [
                        "使用Jupiter聚合器获得更好的执行价格", 
                        "在非高波动时段将监控频率降至30分钟"
                    ],
                    "risk_reduction": [
                        "增加链上数据分析以预判鲸鱼动向", 
                        "为每个交易增加隐性成本(gas+滑点)计算"
                    ],
                    "profitability_enhancements": [
                        "增加对热门Tokens社交媒体情绪分析", 
                        "考虑将部分空闲资金用于稳定币流动性挖矿增加被动收入"
                    ]
                },
                "risk_analysis": {
                    "identified_risks": [
                        "中小市值代币流动性风险", 
                        "过于依赖技术指标可能导致信号延迟", 
                        "Solana网络拥堵风险"
                    ],
                    "mitigation_strategies": [
                        "使用分散限价单代替单一市价单减少滑点", 
                        "结合链上数据与价格动作双重确认", 
                        "保持至少30%资金不投入交易以应对机会或紧急情况"
                    ],
                    "market_dependency_factors": [
                        "策略在中低波动市场表现不佳", 
                        "对SOL主网性能和稳定性有较强依赖", 
                        "大型鲸鱼活动可能干扰中小市值代币价格走势"
                    ]
                }
            }
        } 