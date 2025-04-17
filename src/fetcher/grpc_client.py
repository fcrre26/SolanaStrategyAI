"""GRPC client for Solana data subscription."""
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

import grpc
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from yellowstone_grpc.service import GeyserService
from yellowstone_grpc.generated.geyser_pb2 import (
    SubscribeAccountRequest,
    SubscribeProgramRequest,
    SubscribeBlockRequest,
    SubscribeLogsRequest,
    CommitmentLevel
)

# 导入 GRPC 生成的代码
# TODO: 需要生成 GRPC 代码

logger = logging.getLogger(__name__)

class GrpcSubscriber:
    """GRPC subscriber for Solana data."""
    
    GRPC_ENDPOINT = "solana-yellowstone-grpc.publicnode.com:443"
    
    def __init__(self):
        """Initialize GRPC subscriber."""
        # 创建 GRPC channel
        self.channel = grpc.aio.secure_channel(
            self.GRPC_ENDPOINT,
            grpc.ssl_channel_credentials()
        )
        
        # 创建 GRPC stub
        self.stub = GeyserService(self.channel)
        
        # 存储活跃的订阅
        self.active_subscriptions: Dict[str, Any] = {}
        
    async def subscribe_account(self, address: str):
        """Subscribe to account updates.
        
        Args:
            address: Account address to monitor
        """
        try:
            # 创建账户订阅请求
            request = SubscribeAccountRequest(
                account=address,
                commitment=CommitmentLevel.CONFIRMED
            )
            
            # 启动订阅
            subscription = await self.stub.SubscribeAccount(request)
            
            # 存储订阅
            self.active_subscriptions[f"account_{address}"] = subscription
            
            logger.info(f"Successfully subscribed to account {address}")
            return subscription
            
        except Exception as e:
            logger.error(f"Error subscribing to account {address}: {e}")
            raise
    
    async def subscribe_program(self, program_id: str):
        """Subscribe to program updates.
        
        Args:
            program_id: Program ID to monitor
        """
        try:
            # 创建程序订阅请求
            request = SubscribeProgramRequest(
                program_id=program_id,
                commitment=CommitmentLevel.CONFIRMED
            )
            
            # 启动订阅
            subscription = await self.stub.SubscribeProgram(request)
            
            # 存储订阅
            self.active_subscriptions[f"program_{program_id}"] = subscription
            
            logger.info(f"Successfully subscribed to program {program_id}")
            return subscription
            
        except Exception as e:
            logger.error(f"Error subscribing to program {program_id}: {e}")
            raise
    
    async def subscribe_blocks(self):
        """Subscribe to new blocks."""
        try:
            # 创建区块订阅请求
            request = SubscribeBlockRequest(
                commitment=CommitmentLevel.CONFIRMED
            )
            
            # 启动订阅
            subscription = await self.stub.SubscribeBlocks(request)
            
            # 存储订阅
            self.active_subscriptions["blocks"] = subscription
            
            logger.info("Successfully subscribed to blocks")
            return subscription
            
        except Exception as e:
            logger.error(f"Error subscribing to blocks: {e}")
            raise
    
    async def subscribe_logs(self, mention_addresses: Optional[List[str]] = None):
        """Subscribe to transaction logs.
        
        Args:
            mention_addresses: Optional list of addresses to filter logs
        """
        try:
            # 创建日志订阅请求
            request = SubscribeLogsRequest(
                commitment=CommitmentLevel.CONFIRMED,
                mention_addresses=mention_addresses or []
            )
            
            # 启动订阅
            subscription = await self.stub.SubscribeLogs(request)
            
            # 存储订阅
            subscription_key = "logs"
            if mention_addresses:
                subscription_key = f"logs_{'_'.join(mention_addresses)}"
            self.active_subscriptions[subscription_key] = subscription
            
            logger.info(f"Successfully subscribed to logs {mention_addresses or 'all'}")
            return subscription
            
        except Exception as e:
            logger.error(f"Error subscribing to logs: {e}")
            raise
    
    async def process_account_update(self, update):
        """Process account update.
        
        Args:
            update: Account update data
        """
        try:
            # 解析账户更新数据
            account_data = {
                "pubkey": update.account,
                "lamports": update.lamports,
                "owner": update.owner,
                "data": update.data,
                "slot": update.slot,
                "write_version": update.write_version
            }
            
            logger.debug(f"Received account update: {account_data}")
            return account_data
            
        except Exception as e:
            logger.error(f"Error processing account update: {e}")
            raise
    
    async def process_program_update(self, update):
        """Process program update.
        
        Args:
            update: Program update data
        """
        try:
            # 解析程序更新数据
            program_data = {
                "program_id": update.program_id,
                "account": update.account,
                "data": update.data,
                "slot": update.slot
            }
            
            logger.debug(f"Received program update: {program_data}")
            return program_data
            
        except Exception as e:
            logger.error(f"Error processing program update: {e}")
            raise
    
    async def process_block_update(self, update):
        """Process block update.
        
        Args:
            update: Block update data
        """
        try:
            # 解析区块更新数据
            block_data = {
                "slot": update.slot,
                "block_hash": update.block_hash,
                "parent_slot": update.parent_slot,
                "block_time": update.block_time,
                "block_height": update.block_height
            }
            
            logger.debug(f"Received block update: {block_data}")
            return block_data
            
        except Exception as e:
            logger.error(f"Error processing block update: {e}")
            raise
    
    async def process_log_update(self, update):
        """Process log update.
        
        Args:
            update: Log update data
        """
        try:
            # 解析日志更新数据
            log_data = {
                "signature": update.signature,
                "slot": update.slot,
                "logs": update.logs,
                "timestamp": update.timestamp
            }
            
            logger.debug(f"Received log update: {log_data}")
            return log_data
            
        except Exception as e:
            logger.error(f"Error processing log update: {e}")
            raise
    
    async def close(self):
        """Close all subscriptions and channel."""
        try:
            # 关闭所有订阅
            for subscription in self.active_subscriptions.values():
                await subscription.cancel()
            
            # 关闭 channel
            await self.channel.close()
            
            logger.info("Successfully closed all subscriptions and channel")
            
        except Exception as e:
            logger.error(f"Error closing subscriptions: {e}")
            raise 