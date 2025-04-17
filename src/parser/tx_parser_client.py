"""
Solana交易解析客户端，用于调用Node.js解析服务。
"""
import aiohttp
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class TransactionParserClient:
    """
    交易解析客户端，调用Node.js的solana-tx-parser-public服务。
    """
    
    def __init__(self, api_url: str = "http://localhost:3000"):
        """
        初始化解析客户端
        
        Args:
            api_url: 解析服务的API地址
        """
        self.api_url = api_url
        
    async def parse_transaction(self, signature: str) -> Optional[Dict[str, Any]]:
        """
        解析交易
        
        Args:
            signature: 交易签名
            
        Returns:
            解析后的交易数据
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/parse/{signature}") as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(f"Error parsing transaction {signature}: {error_text}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error calling parser service: {str(e)}")
            return None
            
    async def is_service_available(self) -> bool:
        """
        检查解析服务是否可用
        
        Returns:
            服务是否可用
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/health") as response:
                    return response.status == 200
        except:
            return False 