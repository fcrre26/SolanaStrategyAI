"""Pool monitor manager with multi-threading support."""
import asyncio
import logging
from typing import Dict, List, Set, Any
from datetime import datetime
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey

from ..fetcher.market_data import MarketDataCollector
from ..parser.dex_parser import DexParser
from ..storage.database import Database

logger = logging.getLogger(__name__)

class PoolMonitor:
    """Monitor multiple pools with multi-threading support."""
    
    def __init__(self, rpc_url: str, max_workers: int = 10):
        """Initialize pool monitor.
        
        Args:
            rpc_url: Solana RPC URL
            max_workers: Maximum number of worker threads for pool monitoring
        """
        self.rpc_url = rpc_url
        self.max_workers = max_workers
        
        # 初始化组件
        self.client = AsyncClient(rpc_url)
        self.market_collector = MarketDataCollector(self.client)
        self.dex_parser = DexParser(self.client)
        self.db = Database()
        
        # 监控状态
        self.monitored_address: str = None
        self.monitored_pools: Dict[str, Dict[str, Any]] = {}  # pool_address -> pool_data
        self.pool_tasks: Dict[str, asyncio.Task] = {}  # pool_address -> monitoring_task
        self.active = False
        
        # 线程和队列
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.data_queue = Queue()
        self.processing_thread = None
        
        # 回调函数
        self.callbacks = {
            'pool_update': [],
            'trade_detected': [],
            'price_alert': [],
            'error': []
        }
    
    async def start_monitoring(self, address: str):
        """Start monitoring address and its trading pools.
        
        Args:
            address: Address to monitor
        """
        try:
            self.active = True
            self.monitored_address = address
            
            # 启动数据处理线程
            self.processing_thread = threading.Thread(
                target=self._process_data_queue,
                daemon=True
            )
            self.processing_thread.start()
            
            # 启动主监控任务
            await self._monitor_address_trades()
            
        except Exception as e:
            logger.error(f"Error starting monitoring: {e}")
            self._trigger_callbacks('error', {'error': str(e)})
    
    async def _monitor_address_trades(self):
        """Monitor address trades and manage pool monitoring tasks."""
        try:
            while self.active:
                # 获取最近的交易
                signatures = await self.client.get_signatures_for_address(
                    Pubkey.from_string(self.monitored_address)
                )
                
                if signatures:
                    # 处理每个交易
                    for sig_info in signatures:
                        # 获取交易数据
                        tx = await self.client.get_transaction(sig_info.signature)
                        if not tx:
                            continue
                        
                        # 解析交易数据
                        swap_data = await self.dex_parser.parse_swap_instruction(tx)
                        if not swap_data:
                            continue
                        
                        # 获取池子地址
                        pool_address = swap_data.get("pool_address")
                        if not pool_address:
                            continue
                        
                        # 如果是新池子,启动监控任务
                        if pool_address not in self.pool_tasks:
                            logger.info(f"Found new pool: {pool_address}")
                            task = asyncio.create_task(
                                self._monitor_pool(pool_address)
                            )
                            self.pool_tasks[pool_address] = task
                        
                        # 处理交易数据
                        await self._process_trade(
                            self.monitored_address,
                            sig_info.signature,
                            swap_data
                        )
                
                # 等待一段时间再检查新交易
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error monitoring address trades: {e}")
            self._trigger_callbacks('error', {'error': str(e)})
    
    async def _monitor_pool(self, pool_address: str):
        """Monitor single pool in separate task.
        
        Args:
            pool_address: Pool address to monitor
        """
        try:
            logger.info(f"Starting pool monitor for {pool_address}")
            
            while self.active:
                try:
                    # 收集市场数据
                    market_data = await self.market_collector.collect_market_data(pool_address)
                    
                    # 更新池子状态
                    await self._update_pool_state(pool_address, market_data)
                    
                    # 检查价格警报
                    await self._check_price_alerts(pool_address, market_data)
                    
                    # 等待一段时间再更新
                    await asyncio.sleep(1)  # 可以根据需要调整更新频率
                    
                except Exception as e:
                    logger.error(f"Error in pool monitor loop for {pool_address}: {e}")
                    await asyncio.sleep(5)  # 错误后等待更长时间
                    
        except Exception as e:
            logger.error(f"Pool monitor failed for {pool_address}: {e}")
            self._trigger_callbacks('error', {
                'pool_address': pool_address,
                'error': str(e)
            })
        finally:
            # 清理任务
            if pool_address in self.pool_tasks:
                del self.pool_tasks[pool_address]
    
    async def _process_trade(self, address: str, signature: str, swap_data: Dict[str, Any]):
        """Process trade data.
        
        Args:
            address: Source address
            signature: Transaction signature
            swap_data: Parsed swap data
        """
        try:
            pool_address = swap_data.get("pool_address")
            if not pool_address:
                return
            
            # 获取最新的市场数据
            market_data = self.monitored_pools.get(pool_address, {}).get('market_data', {})
            
            # 将数据放入队列
            self.data_queue.put({
                'type': 'trade',
                'address': address,
                'signature': signature,
                'swap_data': swap_data,
                'market_data': market_data,
                'timestamp': int(datetime.now().timestamp() * 1000)
            })
            
            # 触发交易检测回调
            self._trigger_callbacks('trade_detected', {
                'address': address,
                'signature': signature,
                'swap_data': swap_data,
                'market_data': market_data,
                'pool_address': pool_address
            })
            
        except Exception as e:
            logger.error(f"Error processing trade {signature}: {e}")
            self._trigger_callbacks('error', {
                'address': address,
                'signature': signature,
                'error': str(e)
            })
    
    async def _update_pool_state(self, pool_address: str, market_data: Dict[str, Any]):
        """Update pool state and check alerts.
        
        Args:
            pool_address: Pool address
            market_data: Market data
        """
        try:
            # 更新池子状态
            self.monitored_pools[pool_address] = {
                'last_update': int(datetime.now().timestamp() * 1000),
                'market_data': market_data
            }
            
            # 触发池子更新回调
            self._trigger_callbacks('pool_update', {
                'pool_address': pool_address,
                'market_data': market_data
            })
            
        except Exception as e:
            logger.error(f"Error updating pool state {pool_address}: {e}")
            self._trigger_callbacks('error', {
                'pool_address': pool_address,
                'error': str(e)
            })
    
    async def _check_price_alerts(self, pool_address: str, market_data: Dict[str, Any]):
        """Check price alerts for pool.
        
        Args:
            pool_address: Pool address
            market_data: Market data
        """
        try:
            price_data = market_data.get('price_data', {})
            current_price = price_data.get('current_price', 0)
            
            # 获取历史价格数据
            old_data = self.monitored_pools.get(pool_address, {}).get('market_data', {})
            old_price = old_data.get('price_data', {}).get('current_price', current_price)
            
            # 计算价格变化
            if old_price > 0:
                price_change = (current_price - old_price) / old_price
                
                # 检查价格变化是否超过阈值
                if abs(price_change) >= 0.02:  # 2% 的价格变化阈值
                    self._trigger_callbacks('price_alert', {
                        'pool_address': pool_address,
                        'old_price': old_price,
                        'current_price': current_price,
                        'price_change': price_change,
                        'market_data': market_data
                    })
            
        except Exception as e:
            logger.error(f"Error checking price alerts for {pool_address}: {e}")
            self._trigger_callbacks('error', {
                'pool_address': pool_address,
                'error': str(e)
            })
    
    def _process_data_queue(self):
        """Process data queue in background thread."""
        while self.active:
            try:
                # 从队列获取数据
                data = self.data_queue.get()
                if not data:
                    continue
                
                # 存储数据
                if data['type'] == 'trade':
                    # 存储交易数据
                    asyncio.run(self.db.store_transaction({
                        'tx_hash': data['signature'],
                        'timestamp': data['timestamp'],
                        'from_address': data['address'],
                        'swap_data': data['swap_data'],
                        'success': True
                    }))
                    
                    # 存储市场数据
                    asyncio.run(self.db.store_market_state(
                        data['signature'],
                        data['market_data']
                    ))
                
                self.data_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing data queue: {e}")
                self._trigger_callbacks('error', {'error': str(e)})
    
    def add_callback(self, event_type: str, callback: callable):
        """Add callback for event type.
        
        Args:
            event_type: Event type
            callback: Callback function
        """
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
    
    def _trigger_callbacks(self, event_type: str, data: Dict[str, Any]):
        """Trigger callbacks for event type.
        
        Args:
            event_type: Event type
            data: Event data
        """
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in callback: {e}")
    
    async def stop_monitoring(self):
        """Stop monitoring."""
        self.active = False
        
        # 停止所有池子监控任务
        for task in self.pool_tasks.values():
            task.cancel()
        
        # 等待所有任务完成
        if self.pool_tasks:
            await asyncio.gather(*self.pool_tasks.values(), return_exceptions=True)
        
        # 等待数据队列处理完成
        self.data_queue.join()
        
        # 关闭线程池
        self.executor.shutdown(wait=True)
        
        # 关闭客户端连接
        await self.client.close()
        
        logger.info("Monitoring stopped") 