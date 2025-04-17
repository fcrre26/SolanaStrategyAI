"""数据库操作模块 - 专注于交易数据存储和查询"""
import json
import sqlite3
import logging
from typing import Dict, Any, Optional
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    """数据库操作类"""
    
    def __init__(self):
        """Initialize database."""
        self.base_dir = 'data'
        self.current_date = datetime.now().strftime('%Y-%m-%d')
        
        # 确保数据目录存在
        os.makedirs(os.path.join(self.base_dir, 'transactions', self.current_date), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, 'pools'), exist_ok=True)
        os.makedirs(os.path.join(self.base_dir, 'market'), exist_ok=True)
        
        # 初始化数据库连接
        self.tx_db = os.path.join(self.base_dir, 'transactions', self.current_date, 'transactions.db')
        self.pools_db = os.path.join(self.base_dir, 'pools', 'pools.db')
        self.market_db = os.path.join(self.base_dir, 'market', 'market.db')
    
    def initialize(self):
        """Initialize database tables."""
        # 交易数据表
        self._execute_query(self.tx_db, '''
            CREATE TABLE IF NOT EXISTS transactions (
                tx_hash TEXT PRIMARY KEY,
                timestamp INTEGER,
                input_token TEXT,
                input_amount REAL,
                output_token TEXT,
                output_amount REAL,
                pool_address TEXT,
                program_id TEXT,
                raw_data TEXT
            )
        ''')
        
        # 池子数据表
        self._execute_query(self.pools_db, '''
            CREATE TABLE IF NOT EXISTS pools (
                pool_address TEXT PRIMARY KEY,
                token_a TEXT,
                token_b TEXT,
                reserve_a REAL,
                reserve_b REAL,
                last_update INTEGER,
                program_id TEXT,
                raw_data TEXT
            )
        ''')
        
        # 市场数据表
        self._execute_query(self.market_db, '''
            CREATE TABLE IF NOT EXISTS market_states (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pool_address TEXT,
                timestamp INTEGER,
                price REAL,
                volume_24h REAL,
                tvl REAL,
                raw_data TEXT
            )
        ''')
        
        logger.info("Database initialized successfully")
    
    def _execute_query(self, db_path: str, query: str, params: tuple = None):
        """Execute SQL query."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
                
            conn.commit()
            
        except Exception as e:
            logger.error(f"Database error: {e}")
            raise
        
        finally:
            if conn:
                conn.close()
    
    async def store_transaction(self, tx_data: Dict[str, Any]):
        """Store transaction data."""
        try:
            query = '''
                INSERT OR REPLACE INTO transactions 
                (tx_hash, timestamp, input_token, input_amount, 
                output_token, output_amount, pool_address, program_id, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
            
            params = (
                tx_data.get('tx_hash'),
                int(datetime.now().timestamp() * 1000),
                tx_data.get('input_token', {}).get('mint'),
                float(tx_data.get('input_token', {}).get('amount', 0)),
                tx_data.get('output_token', {}).get('mint'),
                float(tx_data.get('output_token', {}).get('amount', 0)),
                tx_data.get('pool_address'),
                tx_data.get('program_id'),
                json.dumps(tx_data)
            )
            
            self._execute_query(self.tx_db, query, params)
            logger.debug(f"Stored transaction: {tx_data.get('tx_hash')}")
            
        except Exception as e:
            logger.error(f"Error storing transaction: {e}")
    
    async def store_pool_state(self, pool_data: Dict[str, Any]):
        """Store pool state data."""
        try:
            query = '''
                INSERT OR REPLACE INTO pools 
                (pool_address, token_a, token_b, reserve_a, reserve_b, 
                last_update, program_id, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            '''
            
            params = (
                pool_data.get('pool_address'),
                pool_data.get('token_a'),
                pool_data.get('token_b'),
                float(pool_data.get('reserve_a', 0)),
                float(pool_data.get('reserve_b', 0)),
                int(datetime.now().timestamp() * 1000),
                pool_data.get('program_id'),
                json.dumps(pool_data)
            )
            
            self._execute_query(self.pools_db, query, params)
            logger.debug(f"Stored pool state: {pool_data.get('pool_address')}")
            
        except Exception as e:
            logger.error(f"Error storing pool state: {e}")
    
    async def store_market_state(self, pool_address: str, market_data: Dict[str, Any]):
        """Store market state data."""
        try:
            query = '''
                INSERT INTO market_states 
                (pool_address, timestamp, price, volume_24h, tvl, raw_data)
                VALUES (?, ?, ?, ?, ?, ?)
            '''
            
            params = (
                pool_address,
                market_data.get('timestamp'),
                float(market_data.get('price', 0)),
                float(market_data.get('volume_24h', 0)),
                float(market_data.get('tvl', 0)),
                json.dumps(market_data)
            )
            
            self._execute_query(self.market_db, query, params)
            logger.debug(f"Stored market state for pool: {pool_address}")
            
        except Exception as e:
            logger.error(f"Error storing market state: {e}")
    
    def get_transactions_by_token(self, token_address: str, limit: int = 100):
        """获取代币的所有交易"""
        query = """
        SELECT * FROM transactions 
        WHERE input_token = ? OR output_token = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """
        try:
            conn = sqlite3.connect(self.tx_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, (token_address, token_address, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            if conn:
                conn.close()
    
    def get_transactions_by_pair(self, token_a: str, token_b: str, limit: int = 100):
        """获取交易对的所有交易"""
        query = """
        SELECT * FROM transactions 
        WHERE (input_token = ? AND output_token = ?) 
           OR (input_token = ? AND output_token = ?)
        ORDER BY timestamp DESC
        LIMIT ?
        """
        try:
            conn = sqlite3.connect(self.tx_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, (token_a, token_b, token_b, token_a, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            if conn:
                conn.close()
    
    def get_pool_states_by_address(self, pool_address: str, limit: int = 100):
        """获取池子状态历史"""
        query = """
        SELECT * FROM pools 
        WHERE pool_address = ?
        ORDER BY last_update DESC
        LIMIT ?
        """
        try:
            conn = sqlite3.connect(self.pools_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, (pool_address, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            if conn:
                conn.close()

# 创建一个单例数据库对象
db = Database()

def init_database():
    """初始化数据库"""
    db.initialize()
    return db 