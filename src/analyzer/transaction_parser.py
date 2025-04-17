"""
交易数据解析模块
用于解析原始交易数据，提取关键信息用于后续分析
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ParsedTransaction:
    """解析后的交易数据"""
    timestamp: int  # 交易时间戳
    tx_hash: str   # 交易哈希
    type: str      # 交易类型 (buy/sell)
    token_in: str  # 输入代币
    amount_in: float  # 输入数量
    token_out: str   # 输出代币
    amount_out: float # 输出数量
    price: float     # 交易价格
    pool_state: Dict[str, Any]  # 交易时池子状态
    raw_data: Dict[str, Any]    # 原始数据

async def parse_transactions(transactions: List[Dict[str, Any]]) -> Optional[List[ParsedTransaction]]:
    """解析交易数据
    
    Args:
        transactions: 原始交易数据列表
        
    Returns:
        解析后的交易数据列表，如果解析失败返回 None
    """
    try:
        parsed_txs = []
        
        for tx in transactions:
            # 提取基础信息
            timestamp = tx.get('timestamp')
            tx_hash = tx.get('tx_hash')
            
            if not timestamp or not tx_hash:
                logger.warning(f"交易数据缺少必要字段: {tx}")
                continue
                
            # 解析交易类型和代币信息
            token_in = tx.get('input_token')
            token_out = tx.get('output_token')
            amount_in = float(tx.get('input_amount', 0))
            amount_out = float(tx.get('output_amount', 0))
            
            if not all([token_in, token_out, amount_in, amount_out]):
                logger.warning(f"交易数据缺少代币信息: {tx}")
                continue
                
            # 计算交易价格
            try:
                price = amount_out / amount_in if amount_in > 0 else 0
            except:
                price = 0
                
            # 确定交易类型
            type = 'buy' if token_in.lower() in ['usdc', 'usdt'] else 'sell'
            
            # 提取池子状态
            pool_state = tx.get('pool_state', {})
            
            parsed_tx = ParsedTransaction(
                timestamp=timestamp,
                tx_hash=tx_hash,
                type=type,
                token_in=token_in,
                amount_in=amount_in,
                token_out=token_out,
                amount_out=amount_out,
                price=price,
                pool_state=pool_state,
                raw_data=tx
            )
            
            parsed_txs.append(parsed_tx)
            
        if not parsed_txs:
            logger.warning("没有成功解析任何交易")
            return None
            
        # 按时间戳排序
        parsed_txs.sort(key=lambda x: x.timestamp)
        
        return parsed_txs
        
    except Exception as e:
        logger.error(f"解析交易数据时出错: {e}")
        return None 