"""
辅助工具函数模块
"""
import time
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path

from ..config import REPORTS_DIR

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def current_timestamp():
    """获取当前时间戳（毫秒）"""
    return int(time.time() * 1000)

def format_timestamp(timestamp, format_str="%Y-%m-%d %H:%M:%S"):
    """将时间戳格式化为可读时间字符串"""
    # 处理毫秒时间戳
    if timestamp > 1000000000000:
        timestamp = timestamp / 1000
    
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime(format_str)

def ensure_directory(directory_path):
    """确保目录存在"""
    path = Path(directory_path)
    path.mkdir(parents=True, exist_ok=True)
    return path

def generate_token_pair_id(token_a, token_b):
    """生成交易对ID，确保顺序一致"""
    # 确保token_a和token_b按字母顺序排序，生成一致的ID
    sorted_tokens = sorted([token_a, token_b])
    return f"{sorted_tokens[0]}/{sorted_tokens[1]}"

def generate_unique_id(prefix="", length=16):
    """生成唯一ID"""
    timestamp = str(int(time.time() * 1000))
    hash_obj = hashlib.md5(f"{timestamp}{prefix}".encode())
    return f"{prefix}{hash_obj.hexdigest()[:length]}"

def safe_json_loads(json_str, default=None):
    """安全加载JSON字符串"""
    try:
        if not json_str:
            return default or {}
        return json.loads(json_str)
    except json.JSONDecodeError:
        logger.error(f"JSON解析错误: {json_str[:100]}")
        return default or {}

def save_to_json_file(data, filename, directory=None):
    """保存数据到JSON文件"""
    directory = directory or REPORTS_DIR
    ensure_directory(directory)
    
    file_path = Path(directory) / filename
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(file_path)
    except Exception as e:
        logger.error(f"保存JSON文件错误: {e}")
        return None

def load_from_json_file(file_path):
    """从JSON文件加载数据"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载JSON文件错误: {e}")
        return None

def format_number(number, decimal_places=4):
    """格式化数值，保留指定小数位"""
    if number is None:
        return "0"
    try:
        return f"{float(number):.{decimal_places}f}"
    except (ValueError, TypeError):
        return str(number)

def calculate_percentage_change(old_value, new_value):
    """计算百分比变化"""
    if old_value == 0:
        return 0
    try:
        return ((new_value - old_value) / abs(old_value)) * 100
    except (TypeError, ZeroDivisionError):
        return 0

def parse_token_pair(pair_str):
    """解析交易对字符串，返回(token_a, token_b)"""
    if not pair_str or '/' not in pair_str:
        return None, None
    
    parts = pair_str.split('/')
    if len(parts) != 2:
        return None, None
    
    return parts[0].strip(), parts[1].strip()

def extract_token_pair(tx):
    """从交易数据中提取交易对"""
    if not tx:
        return None
    
    try:
        input_token = tx.get('input_token') or tx.get('token_info', {}).get('input_token', {}).get('address')
        output_token = tx.get('output_token') or tx.get('token_info', {}).get('output_token', {}).get('address')
        
        if not input_token or not output_token:
            return None
        
        return generate_token_pair_id(input_token, output_token)
    except Exception as e:
        logger.error(f"提取交易对错误: {e}")
        return None

def detect_transaction_type(tx, wallet_address):
    """检测交易类型（买入/卖出）"""
    if not tx or not wallet_address:
        return "unknown"
    
    try:
        from_address = tx.get('from_address')
        to_address = tx.get('to_address')
        
        if from_address and from_address.lower() == wallet_address.lower():
            return "sell"
        
        if to_address and to_address.lower() == wallet_address.lower():
            return "buy"
        
        return "other"
    except Exception as e:
        logger.error(f"检测交易类型错误: {e}")
        return "unknown"

def is_buy_transaction(tx, wallet_address):
    """检测是否是买入交易"""
    return detect_transaction_type(tx, wallet_address) == "buy"

def is_sell_transaction(tx, wallet_address):
    """检测是否是卖出交易"""
    return detect_transaction_type(tx, wallet_address) == "sell" 