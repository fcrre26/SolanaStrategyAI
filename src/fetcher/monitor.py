"""
交易监控模块
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional

from ..config import AMM_PROGRAM_ID, MONITORING_INTERVAL, ANALYSIS_INTERVAL, INACTIVE_THRESHOLD
from ..storage.database import db
from ..utils.helpers import extract_token_pair, is_buy_transaction, is_sell_transaction, current_timestamp
from .client import solana_client
from .collector import collect_trading_data, collect_pool_data, collect_market_data, collect_route_data

# 配置日志
logger = logging.getLogger(__name__)

class TransactionMonitor:
    """交易监控类"""
    
    def __init__(self, wallet_address: str):
        """初始化监控器"""
        self.wallet_address = wallet_address
        self.monitored_pairs: Dict[str, Dict] = {}
        self.active = False
        self.last_processed_signature = None
        self.account_subscription = None
        self.amm_subscription = None
        self.log_subscription = None
    
    async def start(self):
        """启动监控"""
        if self.active:
            logger.warning(f"监控已经在运行中: {self.wallet_address}")
            return False
        
        try:
            # 初始化客户端
            await solana_client.connect()
            
            # 添加监控地址到数据库
            db.insert_monitored_address(self.wallet_address, "监控地址", "通过程序添加的监控地址")
            
            # 订阅账户更新
            self.account_subscription = await solana_client.subscribe_account(self.wallet_address)
            
            # 订阅AMM程序更新
            self.amm_subscription = await solana_client.subscribe_program(AMM_PROGRAM_ID)
            
            # 订阅日志更新
            self.log_subscription = await solana_client.subscribe_logs()
            
            # 加载已经监控的交易对
            self._load_monitored_pairs()
            
            # 标记为活跃状态
            self.active = True
            
            # 启动监控任务
            asyncio.create_task(self._monitor_loop())
            
            logger.info(f"开始监控钱包: {self.wallet_address}")
            return True
            
        except Exception as e:
            logger.error(f"启动监控失败: {e}")
            await self.stop()
            return False
    
    async def stop(self):
        """停止监控"""
        self.active = False
        
        # 取消订阅
        try:
            if self.account_subscription:
                await solana_client.unsubscribe(self.account_subscription)
            if self.amm_subscription:
                await solana_client.unsubscribe(self.amm_subscription)
            if self.log_subscription:
                await solana_client.unsubscribe(self.log_subscription)
        except Exception as e:
            logger.error(f"取消订阅失败: {e}")
        
        logger.info(f"停止监控钱包: {self.wallet_address}")
    
    def _load_monitored_pairs(self):
        """从数据库加载已监控的交易对"""
        try:
            pairs = db.get_monitored_pairs(self.wallet_address)
            
            for pair in pairs:
                pair_id = pair['pair_id']
                self.monitored_pairs[pair_id] = {
                    "token_a": pair['token_a'],
                    "token_b": pair['token_b'],
                    "start_time": pair['start_time'],
                    "last_activity": pair['last_activity'],
                    "last_analysis": pair.get('last_analysis', 0)
                }
            
            logger.info(f"已加载 {len(pairs)} 个监控交易对")
            
        except Exception as e:
            logger.error(f"加载监控交易对失败: {e}")
    
    async def _monitor_loop(self):
        """监控主循环"""
        while self.active:
            try:
                # 处理账户更新
                await self._process_account_updates()
                
                # 处理AMM程序更新
                await self._process_amm_updates()
                
                # 处理监控中的交易对
                await self._process_monitored_pairs()
                
                # 清理不活跃的交易对
                self._cleanup_inactive_pairs()
                
                # 等待下一次监控
                await asyncio.sleep(MONITORING_INTERVAL)
                
            except asyncio.CancelledError:
                logger.info("监控任务被取消")
                break
            except Exception as e:
                logger.error(f"监控循环错误: {e}")
                await asyncio.sleep(5)  # 出错后等待一段时间再重试
    
    async def _process_account_updates(self):
        """处理账户更新"""
        if not self.account_subscription:
            return
        
        try:
            # 非阻塞检查是否有更新
            while True:
                try:
                    update = await asyncio.wait_for(self.account_subscription.recv(), timeout=0.1)
                    
                    # 获取交易详情
                    signature = update.signature
                    if signature == self.last_processed_signature:
                        continue
                    
                    self.last_processed_signature = signature
                    tx = await solana_client.get_transaction(signature)
                    if not tx:
                        continue
                    
                    # 提取交易对信息
                    token_pair = extract_token_pair(tx)
                    if not token_pair:
                        continue
                    
                    # 处理交易
                    await self._process_transaction(tx, token_pair)
                    
                except asyncio.TimeoutError:
                    # 没有更新，跳出循环
                    break
                
        except Exception as e:
            logger.error(f"处理账户更新错误: {e}")
    
    async def _process_amm_updates(self):
        """处理AMM程序更新"""
        if not self.amm_subscription:
            return
        
        try:
            # 非阻塞检查是否有更新
            while True:
                try:
                    update = await asyncio.wait_for(self.amm_subscription.recv(), timeout=0.1)
                    
                    # 处理AMM更新
                    # 这里实现具体的AMM更新处理逻辑
                    # ...
                    
                except asyncio.TimeoutError:
                    # 没有更新，跳出循环
                    break
                
        except Exception as e:
            logger.error(f"处理AMM更新错误: {e}")
    
    async def _process_transaction(self, tx, token_pair):
        """处理交易"""
        try:
            # 检查交易类型
            is_buy = is_buy_transaction(tx, self.wallet_address)
            is_sell = is_sell_transaction(tx, self.wallet_address)
            
            # 如果不是买入或卖出交易，跳过
            if not is_buy and not is_sell:
                return
            
            # 更新或创建监控交易对
            current_time = current_timestamp()
            
            if token_pair not in self.monitored_pairs:
                # 如果是买入交易，添加到监控列表
                if is_buy:
                    token_a, token_b = token_pair.split('/')
                    self.monitored_pairs[token_pair] = {
                        "token_a": token_a,
                        "token_b": token_b,
                        "start_time": current_time,
                        "last_activity": current_time,
                        "last_analysis": 0
                    }
                    
                    # 添加到数据库
                    db.insert_monitored_pair(token_pair, token_a, token_b, self.wallet_address)
                    logger.info(f"添加新监控交易对: {token_pair}")
            else:
                # 更新最后活动时间
                self.monitored_pairs[token_pair]["last_activity"] = current_time
                logger.info(f"更新交易对活动: {token_pair}")
            
            # 存储交易数据
            tx_data = {
                "tx_hash": tx.get("transaction_id") or tx.get("signature"),
                "block_number": tx.get("slot"),
                "timestamp": tx.get("block_time", int(time.time())),
                "from_address": tx.get("from_address"),
                "to_address": tx.get("to_address"),
                "success": True,  # 默认成功，可根据实际情况修改
                "gas_cost": tx.get("fee", 0),
                "input_token": tx.get("input_token"),
                "input_amount": tx.get("input_amount", 0),
                "output_token": tx.get("output_token"),
                "output_amount": tx.get("output_amount", 0)
            }
            
            # 插入交易数据
            db.insert_transaction(tx_data)
            
        except Exception as e:
            logger.error(f"处理交易错误: {e}")
    
    async def _process_monitored_pairs(self):
        """处理监控中的交易对"""
        if not self.monitored_pairs:
            return
        
        current_time = current_timestamp()
        for pair, data in list(self.monitored_pairs.items()):
            try:
                # 收集交易数据
                trading_data = await collect_trading_data(solana_client, pair)
                if trading_data:
                    # 保存到数据库
                    tx_hash = f"auto_collect_{current_time}_{pair.replace('/', '_')}"
                    db.insert_market_state(tx_hash, trading_data)
                
                # 收集池子数据
                pool_data = await collect_pool_data(solana_client, pair)
                if pool_data:
                    db.insert_pool_state(tx_hash, pool_data)
                
                # 收集市场数据
                market_data = await collect_market_data(solana_client, pair)
                if market_data:
                    # 市场数据可以合并到市场状态表
                    pass
                
                # 收集路由数据
                route_data = await collect_route_data(solana_client, pair)
                if route_data:
                    # 路由数据可以保存到执行状态表
                    db.insert_execution_state(tx_hash, {"route_data": route_data})
                
                # 检查是否需要进行分析
                if current_time - data.get("last_analysis", 0) > ANALYSIS_INTERVAL:
                    # 执行分析 (将在analyzer模块实现)
                    # await analyze_trading_pattern(pair, data)
                    data["last_analysis"] = current_time
                
            except Exception as e:
                logger.error(f"处理交易对错误: {pair}, {e}")
    
    def _cleanup_inactive_pairs(self):
        """清理不活跃的交易对"""
        current_time = current_timestamp()
        for pair, data in list(self.monitored_pairs.items()):
            if current_time - data["last_activity"] > INACTIVE_THRESHOLD:
                logger.info(f"清理不活跃交易对: {pair}")
                del self.monitored_pairs[pair]

# 监控管理器
monitors = {}

def get_monitor(wallet_address: str) -> TransactionMonitor:
    """获取或创建监控实例"""
    if wallet_address not in monitors:
        monitors[wallet_address] = TransactionMonitor(wallet_address)
    return monitors[wallet_address]

async def start_monitoring(wallet_address: str) -> bool:
    """启动监控钱包"""
    monitor = get_monitor(wallet_address)
    return await monitor.start()

async def stop_monitoring(wallet_address: str) -> bool:
    """停止监控钱包"""
    if wallet_address in monitors:
        await monitors[wallet_address].stop()
        del monitors[wallet_address]
        return True
    return False 