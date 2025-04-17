"""
模拟数据生成器，用于测试和开发
"""
import random
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple

def generate_address() -> str:
    """生成随机Solana地址"""
    return ''.join(random.choices('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz', k=44))

def generate_signature() -> str:
    """生成随机交易签名"""
    return ''.join(random.choices('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz', k=88))

def generate_transaction_data(wallet_address: str = None) -> Dict[str, Any]:
    """生成模拟交易数据"""
    if not wallet_address:
        wallet_address = generate_address()
    
    # 常用代币列表
    tokens = {
        "SOL": "So11111111111111111111111111111111111111112",
        "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
        "SRM": "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt"
    }
    
    # 随机选择两个不同的代币
    token_keys = list(tokens.keys())
    token_a_key, token_b_key = random.sample(token_keys, 2)
    token_a, token_b = tokens[token_a_key], tokens[token_b_key]
    
    # 随机确定交易方向 (买入 or 卖出)
    is_buy = random.choice([True, False])
    
    # 如果是买入，用户发送token_b获取token_a；如果是卖出，用户发送token_a获取token_b
    if is_buy:
        input_token = token_b
        output_token = token_a
        input_amount = round(random.uniform(1, 1000), 2)
        output_amount = round(input_amount / random.uniform(0.8, 1.2), 6)
    else:
        input_token = token_a
        output_token = token_b
        input_amount = round(random.uniform(0.1, 10), 6)
        output_amount = round(input_amount * random.uniform(0.8, 1.2), 2)
    
    timestamp = int(time.time() * 1000)
    
    return {
        "transaction_hash": generate_signature(),
        "block_number": random.randint(100000000, 200000000),
        "timestamp": timestamp,
        "wallet_address": wallet_address,
        "amm_address": generate_address(),
        "success": random.random() > 0.05,  # 5% 失败率
        "gas_cost": round(random.uniform(0.000001, 0.00005), 8),
        "input_token": input_token,
        "input_amount": input_amount,
        "output_token": output_token,
        "output_amount": output_amount,
        "token_pair": f"{token_a_key}/{token_b_key}"
    }

def generate_market_state_data(transaction_hash: str) -> Dict[str, Any]:
    """生成市场状态数据"""
    return {
        "transaction_hash": transaction_hash,
        "price": round(random.uniform(0.1, 100), 6),
        "depth": {
            "bids": [
                [round(random.uniform(0.1, 100), 6), round(random.uniform(1, 1000), 2)]
                for _ in range(5)
            ],
            "asks": [
                [round(random.uniform(0.1, 100), 6), round(random.uniform(1, 1000), 2)]
                for _ in range(5)
            ]
        },
        "volume": round(random.uniform(10000, 1000000), 2),
        "market_data": json.dumps({
            "24h_change": round(random.uniform(-10, 10), 2),
            "24h_high": round(random.uniform(90, 110), 2),
            "24h_low": round(random.uniform(90, 110), 2),
            "market_cap": round(random.uniform(1000000, 100000000), 2)
        })
    }

def generate_execution_state_data(transaction_hash: str) -> Dict[str, Any]:
    """生成执行状态数据"""
    return {
        "transaction_hash": transaction_hash,
        "route": json.dumps({
            "path": [generate_address() for _ in range(random.randint(1, 3))],
            "type": random.choice(["direct", "split", "multi-hop"])
        }),
        "slippage": round(random.uniform(0, 2), 4),
        "performance": json.dumps({
            "execution_time": random.randint(100, 2000),
            "block_time": random.randint(400, 600),
            "confirmation_time": random.randint(1000, 5000)
        })
    }

def generate_pool_state_data(transaction_hash: str) -> Dict[str, Any]:
    """生成池状态数据"""
    return {
        "transaction_hash": transaction_hash,
        "pool_address": generate_address(),
        "reserve": json.dumps({
            "token_a": round(random.uniform(10000, 1000000), 2),
            "token_b": round(random.uniform(10000, 1000000), 2)
        }),
        "fee": json.dumps({
            "fee_rate": round(random.uniform(0.1, 1), 2),
            "fee_amount": round(random.uniform(0.1, 10), 6)
        })
    }

def generate_historical_trading_data(wallet_address: str, days: int = 30, daily_tx_count: Tuple[int, int] = (1, 10)) -> List[Dict[str, Any]]:
    """生成历史交易数据
    
    Args:
        wallet_address: 钱包地址
        days: 生成多少天的数据
        daily_tx_count: 每天交易数量范围(最小值, 最大值)
        
    Returns:
        包含交易数据、市场数据、执行数据和池数据的字典列表
    """
    now = datetime.now()
    result = []
    
    for day in range(days):
        target_date = now - timedelta(days=day)
        # 当天随机交易数量
        tx_count = random.randint(daily_tx_count[0], daily_tx_count[1])
        
        for _ in range(tx_count):
            # 在当天随机时间点
            tx_time = target_date.replace(
                hour=random.randint(0, 23),
                minute=random.randint(0, 59),
                second=random.randint(0, 59)
            )
            timestamp = int(tx_time.timestamp() * 1000)
            
            # 生成基础交易数据
            tx_data = generate_transaction_data(wallet_address)
            tx_data['timestamp'] = timestamp
            
            # 生成关联数据
            market_data = generate_market_state_data(tx_data['transaction_hash'])
            execution_data = generate_execution_state_data(tx_data['transaction_hash'])
            pool_data = generate_pool_state_data(tx_data['transaction_hash'])
            
            result.append({
                'transaction': tx_data,
                'market': market_data,
                'execution': execution_data,
                'pool': pool_data
            })
    
    # 按时间戳排序
    result.sort(key=lambda x: x['transaction']['timestamp'])
    return result 