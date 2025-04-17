"""
Solana节点客户端接口
"""
import logging
from solana.rpc.async_api import AsyncClient

from ..config import GRPC_ENDPOINT

# 配置日志
logger = logging.getLogger(__name__)

class SolanaClient:
    """Solana客户端类"""
    
    def __init__(self, endpoint=None):
        """初始化Solana客户端"""
        self.endpoint = endpoint or GRPC_ENDPOINT
        self.client = None
    
    async def connect(self):
        """连接到Solana节点"""
        try:
            self.client = AsyncClient(self.endpoint)
            # 测试连接
            version = await self.client.get_version()
            logger.info(f"连接到Solana节点成功: {self.endpoint}, 版本: {version}")
            return self.client
        except Exception as e:
            logger.error(f"连接Solana节点错误: {e}")
            raise
    
    async def close(self):
        """关闭客户端连接"""
        if self.client:
            await self.client.close()
            self.client = None
            logger.info("关闭Solana节点连接")
    
    async def get_transaction(self, signature):
        """获取交易详情"""
        try:
            if not self.client:
                await self.connect()
            
            tx = await self.client.get_transaction(signature)
            return tx
        except Exception as e:
            logger.error(f"获取交易错误: {signature}, {e}")
            return None
    
    async def get_account_info(self, account):
        """获取账户信息"""
        try:
            if not self.client:
                await self.connect()
            
            info = await self.client.get_account_info(account)
            return info
        except Exception as e:
            logger.error(f"获取账户信息错误: {account}, {e}")
            return None
    
    async def get_signatures_for_address(self, address, limit=100):
        """获取地址的交易签名列表"""
        try:
            if not self.client:
                await self.connect()
            
            signatures = await self.client.get_signatures_for_address(address, limit=limit)
            return signatures
        except Exception as e:
            logger.error(f"获取地址交易签名错误: {address}, {e}")
            return []
    
    async def get_recent_blockhash(self):
        """获取最新的区块哈希"""
        try:
            if not self.client:
                await self.connect()
            
            resp = await self.client.get_recent_blockhash()
            return resp['result']['value']['blockhash']
        except Exception as e:
            logger.error(f"获取最新区块哈希错误: {e}")
            return None
    
    async def get_program_accounts(self, program_id, filters=None):
        """获取程序账户"""
        try:
            if not self.client:
                await self.connect()
            
            accounts = await self.client.get_program_accounts(program_id, filters=filters)
            return accounts
        except Exception as e:
            logger.error(f"获取程序账户错误: {program_id}, {e}")
            return []
    
    async def subscribe_account(self, address):
        """订阅账户更新"""
        try:
            if not self.client:
                await self.connect()
            
            subscription = await self.client.account_subscribe(address)
            logger.info(f"成功订阅账户: {address}")
            return subscription
        except Exception as e:
            logger.error(f"订阅账户错误: {address}, {e}")
            raise
    
    async def subscribe_program(self, program_id):
        """订阅程序更新"""
        try:
            if not self.client:
                await self.connect()
            
            subscription = await self.client.program_subscribe(program_id)
            logger.info(f"成功订阅程序: {program_id}")
            return subscription
        except Exception as e:
            logger.error(f"订阅程序错误: {program_id}, {e}")
            raise
    
    async def subscribe_signature(self, signature):
        """订阅交易签名确认"""
        try:
            if not self.client:
                await self.connect()
            
            subscription = await self.client.signature_subscribe(signature)
            return subscription
        except Exception as e:
            logger.error(f"订阅交易签名错误: {signature}, {e}")
            raise
    
    async def subscribe_logs(self, filter_str=None):
        """订阅日志"""
        try:
            if not self.client:
                await self.connect()
            
            subscription = await self.client.logs_subscribe(filter_str)
            return subscription
        except Exception as e:
            logger.error(f"订阅日志错误: {e}")
            raise
    
    async def unsubscribe(self, subscription_id):
        """取消订阅"""
        try:
            if not self.client:
                await self.connect()
            
            await self.client.unsubscribe(subscription_id)
        except Exception as e:
            logger.error(f"取消订阅错误: {subscription_id}, {e}")

# 创建一个单例客户端
solana_client = SolanaClient()

async def init_solana_client():
    """初始化Solana客户端"""
    await solana_client.connect()
    return solana_client 