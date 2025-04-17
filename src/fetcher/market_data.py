"""Market data collector for Solana."""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from ..parser.dex_parser import DexParser

logger = logging.getLogger(__name__)

class MarketDataCollector:
    """Collector for market data from Solana."""
    
    def __init__(self, client: AsyncClient):
        """Initialize market data collector.
        
        Args:
            client: Solana RPC client
        """
        self.client = client
        self.dex_parser = DexParser(client)
    
    async def get_price_data(self, pool_address: str) -> Dict[str, Any]:
        """Get current price data for a pool.
        
        Args:
            pool_address: Pool account address
            
        Returns:
            Price data dictionary
        """
        try:
            # 使用 DEX 解析器获取池子数据
            pool_data = await self.dex_parser.parse_pool_data(pool_address)
            
            if not pool_data:
                return {}
            
            # 从池子数据中提取价格信息
            tokens = pool_data.get("tokens", {})
            token_a = tokens.get("token_a", {})
            token_b = tokens.get("token_b", {})
            
            # 计算价格
            reserve_a = float(token_a.get("reserve", 0))
            reserve_b = float(token_b.get("reserve", 0))
            decimals_a = int(token_a.get("decimals", 0))
            decimals_b = int(token_b.get("decimals", 0))
            
            if reserve_a > 0 and reserve_b > 0:
                # 考虑代币精度计算价格
                price = (reserve_b / (10 ** decimals_b)) / (reserve_a / (10 ** decimals_a))
            else:
                price = 0.0
            
            # 如果池子数据中直接包含价格信息,使用池子提供的价格
            if "price" in pool_data:
                pool_price = pool_data["price"].get("current_price")
                if pool_price is not None:
                    price = float(pool_price)
            
            return {
                "current_price": price,
                "price_change_24h": 0.0,  # TODO: 需要历史数据计算
                "high_24h": 0.0,          # TODO: 需要历史数据计算
                "low_24h": 0.0,           # TODO: 需要历史数据计算
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
            
        except Exception as e:
            logger.error(f"Error getting price data: {e}")
            return {}
    
    async def get_depth_data(self, pool_address: str) -> Dict[str, Any]:
        """Get current depth data for a pool.
        
        Args:
            pool_address: Pool account address
            
        Returns:
            Depth data dictionary
        """
        try:
            # 使用 DEX 解析器获取池子数据
            pool_data = await self.dex_parser.parse_pool_data(pool_address)
            
            if not pool_data:
                return {}
            
            # 从池子数据中提取深度信息
            tokens = pool_data.get("tokens", {})
            token_a = tokens.get("token_a", {})
            token_b = tokens.get("token_b", {})
            
            # 计算流动性深度
            reserve_a = float(token_a.get("reserve", 0))
            reserve_b = float(token_b.get("reserve", 0))
            decimals_a = int(token_a.get("decimals", 0))
            decimals_b = int(token_b.get("decimals", 0))
            
            # 将储备金额转换为实际金额
            actual_reserve_a = reserve_a / (10 ** decimals_a)
            actual_reserve_b = reserve_b / (10 ** decimals_b)
            
            # 计算总流动性(简单相加,实际应该根据代币价格计算)
            total_liquidity = actual_reserve_a + actual_reserve_b
            
            return {
                "total_liquidity": total_liquidity,
                "bid_depth": actual_reserve_a,  # 买单深度
                "ask_depth": actual_reserve_b,  # 卖单深度
                "depth_change_24h": 0.0,       # TODO: 需要历史数据计算
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
            
        except Exception as e:
            logger.error(f"Error getting depth data: {e}")
            return {}
    
    async def get_volume_data(self, pool_address: str) -> Dict[str, Any]:
        """Get current volume data for a pool.
        
        Args:
            pool_address: Pool account address
            
        Returns:
            Volume data dictionary
        """
        try:
            # 获取最近的交易历史
            signatures = await self.client.get_signatures_for_address(
                Pubkey.from_string(pool_address),
                limit=100  # 获取最近100笔交易
            )
            
            if not signatures:
                return {}
            
            # 分析交易历史
            volume_24h = 0.0
            trade_count = 0
            total_amount = 0.0
            
            current_time = int(datetime.now().timestamp())
            
            for sig_info in signatures:
                # 只统计24小时内的交易
                if current_time - sig_info.block_time > 86400:
                    continue
                    
                # 获取交易详情
                tx = await self.client.get_transaction(sig_info.signature)
                if tx:
                    # 解析交易数据
                    swap_data = await self.dex_parser.parse_swap_instruction(tx)
                    if swap_data:
                        # 累计交易量
                        amount_in = float(swap_data.get("input_token", {}).get("amount", 0))
                        volume_24h += amount_in
                        total_amount += amount_in
                        trade_count += 1
            
            # 计算平均交易大小
            average_trade_size = total_amount / trade_count if trade_count > 0 else 0
            
            return {
                "volume_24h": volume_24h,
                "volume_change_24h": 0.0,  # TODO: 需要前一天的数据计算
                "number_of_trades_24h": trade_count,
                "average_trade_size": average_trade_size,
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
            
        except Exception as e:
            logger.error(f"Error getting volume data: {e}")
            return {}
    
    async def get_market_sentiment(self, pool_address: str) -> Dict[str, Any]:
        """Get current market sentiment data for a pool.
        
        Args:
            pool_address: Pool account address
            
        Returns:
            Market sentiment data dictionary
        """
        try:
            # 获取最近的交易历史
            signatures = await self.client.get_signatures_for_address(
                Pubkey.from_string(pool_address),
                limit=100  # 获取最近100笔交易
            )
            
            if not signatures:
                return {}
            
            # 分析交易模式
            buy_count = 0
            sell_count = 0
            large_tx_count = 0
            total_price_change = 0.0
            
            current_time = int(datetime.now().timestamp())
            last_price = None
            
            for sig_info in signatures:
                # 只分析24小时内的交易
                if current_time - sig_info.block_time > 86400:
                    continue
                    
                # 获取交易详情
                tx = await self.client.get_transaction(sig_info.signature)
                if tx:
                    # 解析交易数据
                    swap_data = await self.dex_parser.parse_swap_instruction(tx)
                    if swap_data:
                        # 分析交易方向
                        amount_in = float(swap_data.get("input_token", {}).get("amount", 0))
                        amount_out = float(swap_data.get("output_token", {}).get("amount", 0))
                        
                        if amount_out > amount_in:
                            buy_count += 1
                        else:
                            sell_count += 1
                        
                        # 检测大额交易
                        if amount_in > 1000:  # 假设1000为大额交易阈值
                            large_tx_count += 1
                        
                        # 计算价格变化
                        current_price = amount_out / amount_in if amount_in > 0 else 0
                        if last_price is not None:
                            total_price_change += (current_price - last_price) / last_price
                        last_price = current_price
            
            total_trades = buy_count + sell_count
            if total_trades > 0:
                # 计算交易频率(每小时交易数)
                trading_frequency = total_trades / 24
                
                # 计算买卖比例
                buy_sell_ratio = buy_count / sell_count if sell_count > 0 else float('inf')
                
                # 计算大单交易频率
                large_tx_frequency = large_tx_count / total_trades
                
                # 计算价格动量(平均价格变化)
                price_momentum = total_price_change / total_trades
            else:
                trading_frequency = 0.0
                buy_sell_ratio = 1.0
                large_tx_frequency = 0.0
                price_momentum = 0.0
            
            return {
                "trading_frequency": trading_frequency,
                "buy_sell_ratio": buy_sell_ratio,
                "large_transaction_frequency": large_tx_frequency,
                "price_momentum": price_momentum,
                "timestamp": int(datetime.now().timestamp() * 1000)
            }
            
        except Exception as e:
            logger.error(f"Error getting market sentiment: {e}")
            return {}
    
    async def collect_market_data(self, pool_address: str) -> Dict[str, Any]:
        """Collect all market data for a pool.
        
        Args:
            pool_address: Pool account address
            
        Returns:
            Complete market data dictionary
        """
        try:
            # 并行获取所有市场数据
            price_data, depth_data, volume_data, sentiment_data = await asyncio.gather(
                self.get_price_data(pool_address),
                self.get_depth_data(pool_address),
                self.get_volume_data(pool_address),
                self.get_market_sentiment(pool_address)
            )
            
            # 获取池子基本信息
            pool_data = await self.dex_parser.parse_pool_data(pool_address)
            
            return {
                "pool_address": pool_address,
                "protocol": pool_data.get("protocol", "unknown"),
                "version": pool_data.get("version"),
                "timestamp": int(datetime.now().timestamp() * 1000),
                "price_data": price_data,
                "depth_data": depth_data,
                "volume_data": volume_data,
                "market_data": sentiment_data,
                "pool_info": {
                    "tokens": pool_data.get("tokens", {}),
                    "fees": pool_data.get("fees", {}),
                    "status": pool_data.get("status", {})
                }
            }
            
        except Exception as e:
            logger.error(f"Error collecting market data: {e}")
            return {} 