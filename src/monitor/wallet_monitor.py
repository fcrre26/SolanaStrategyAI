"""
钱包监控模块 - 监控钱包活动和池子变化
"""

import logging
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from ..storage.database import Database
from ..analyzer.transaction_parser import parse_transactions

logger = logging.getLogger(__name__)

class WalletMonitor:
    """监控钱包活动和池子变化"""
    
    def __init__(self, wallet_address: str, db: Database):
        self.wallet_address = wallet_address
        self.db = db
        self.is_running = False
        self.retry_count = 0
        self.max_retries = 3
        self.retry_delay = 5  # 秒
        self.monitored_pools = set()
        self.last_sync_time = 0
        self.sync_interval = 300  # 5分钟同步一次
        
    async def start(self):
        """启动监控"""
        logger.info(f"开始监控钱包: {self.wallet_address}")
        self.is_running = True
        
        try:
            # 初始化监控
            await self._initialize_monitoring()
            
            # 启动数据同步任务
            asyncio.create_task(self._sync_data())
            
            # 启动监控循环
            while self.is_running:
                try:
                    # 处理账户更新
                    await self._handle_account_updates()
                    
                    # 处理池子更新
                    await self._handle_pool_updates()
                    
                    # 处理市场数据更新
                    await self._handle_market_updates()
                    
                    # 重置重试计数
                    self.retry_count = 0
                    
                except Exception as e:
                    logger.error(f"监控循环出错: {e}")
                    await self._handle_error(e)
                    
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"监控服务出错: {e}")
            self.is_running = False
            raise
            
    async def _initialize_monitoring(self):
        """初始化监控"""
        try:
            # 获取初始池子列表
            pools = await self.db.get_related_pools(self.wallet_address)
            self.monitored_pools.update(pools)
            
            # 同步历史数据
            await self._sync_historical_data()
            
            logger.info(f"监控初始化完成，已监控 {len(self.monitored_pools)} 个池子")
            
        except Exception as e:
            logger.error(f"初始化监控失败: {e}")
            raise
            
    async def _sync_historical_data(self):
        """同步历史数据"""
        try:
            # 获取最近24小时的数据
            since_timestamp = int((datetime.now().timestamp() - 86400) * 1000)
            
            # 同步交易数据
            transactions = await self.db.get_transactions(
                self.wallet_address,
                since_timestamp=since_timestamp
            )
            
            if transactions:
                parsed_data = await parse_transactions(transactions)
                if parsed_data:
                    await self.db.store_transactions(parsed_data)
                    
            # 同步池子数据
            for pool in self.monitored_pools:
                pool_states = await self.db.get_pool_states(
                    pool,
                    since_timestamp=since_timestamp
                )
                if pool_states:
                    await self.db.store_pool_states(pool_states)
                    
            logger.info("历史数据同步完成")
            
        except Exception as e:
            logger.error(f"同步历史数据失败: {e}")
            
    async def _sync_data(self):
        """定期同步数据"""
        while self.is_running:
            try:
                current_time = datetime.now().timestamp()
                
                if current_time - self.last_sync_time >= self.sync_interval:
                    await self._sync_historical_data()
                    self.last_sync_time = current_time
                    
            except Exception as e:
                logger.error(f"数据同步失败: {e}")
                
            await asyncio.sleep(60)  # 每分钟检查一次
            
    async def _handle_error(self, error: Exception):
        """处理错误"""
        self.retry_count += 1
        
        if self.retry_count >= self.max_retries:
            logger.error(f"达到最大重试次数，停止监控: {error}")
            self.is_running = False
            return
            
        logger.warning(f"发生错误，{self.retry_delay}秒后重试: {error}")
        await asyncio.sleep(self.retry_delay)
        
    async def _handle_account_updates(self):
        """处理账户更新"""
        try:
            # 获取账户更新
            updates = await self._get_account_updates()
            
            for update in updates:
                # 验证数据完整性
                if not self._validate_transaction(update):
                    continue
                    
                # 解析交易数据
                parsed_data = await parse_transactions([update])
                if not parsed_data:
                    continue
                    
                # 存储交易数据
                await self.db.store_transactions(parsed_data)
                
                # 更新监控的池子列表
                self._update_monitored_pools(parsed_data)
                
        except Exception as e:
            logger.error(f"处理账户更新失败: {e}")
            raise
            
    def _validate_transaction(self, transaction: Dict) -> bool:
        """验证交易数据完整性"""
        required_fields = [
            'timestamp',
            'tx_hash',
            'input_token',
            'output_token',
            'input_amount',
            'output_amount'
        ]
        
        return all(field in transaction for field in required_fields)
        
    def _update_monitored_pools(self, transactions: List):
        """更新监控的池子列表"""
        for tx in transactions:
            if 'pool_address' in tx.raw_data:
                self.monitored_pools.add(tx.raw_data['pool_address'])
                
    async def stop(self):
        """停止监控"""
        logger.info("停止监控服务")
        self.is_running = False 