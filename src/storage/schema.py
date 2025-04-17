"""
数据库模型定义
"""
import sqlite3

# 数据库初始化SQL语句
INIT_DB_SQL = """
-- 基础交易表
CREATE TABLE IF NOT EXISTS base_transactions (
    tx_hash TEXT PRIMARY KEY,
    block_number INTEGER,
    timestamp INTEGER,
    from_address TEXT,
    to_address TEXT,
    success INTEGER,
    gas_cost REAL,
    input_token TEXT,
    input_amount REAL,
    output_token TEXT,
    output_amount REAL,
    created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
);

-- 市场状态表
CREATE TABLE IF NOT EXISTS market_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_hash TEXT,
    price_data TEXT,  -- JSON
    depth_data TEXT,  -- JSON
    volume_data TEXT, -- JSON
    market_data TEXT, -- JSON
    timestamp INTEGER,
    FOREIGN KEY (tx_hash) REFERENCES base_transactions(tx_hash)
);

-- 执行状态表
CREATE TABLE IF NOT EXISTS execution_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_hash TEXT,
    route_data TEXT,    -- JSON
    slippage_data TEXT, -- JSON
    performance_data TEXT, -- JSON
    timestamp INTEGER,
    FOREIGN KEY (tx_hash) REFERENCES base_transactions(tx_hash)
);

-- 池子状态表
CREATE TABLE IF NOT EXISTS pool_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tx_hash TEXT,
    pool_address TEXT,
    reserve_data TEXT, -- JSON
    fee_data TEXT,     -- JSON
    timestamp INTEGER,
    FOREIGN KEY (tx_hash) REFERENCES base_transactions(tx_hash)
);

-- 分析结果表
CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_pair TEXT,
    timestamp INTEGER,
    analysis_result TEXT, -- JSON
    created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
);

-- 监控地址表
CREATE TABLE IF NOT EXISTS monitored_addresses (
    address TEXT PRIMARY KEY,
    name TEXT,
    description TEXT,
    is_active INTEGER DEFAULT 1,
    last_activity INTEGER,
    created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
    updated_at INTEGER DEFAULT (strftime('%s', 'now') * 1000)
);

-- 监控交易对表
CREATE TABLE IF NOT EXISTS monitored_pairs (
    pair_id TEXT PRIMARY KEY,
    token_a TEXT,
    token_b TEXT,
    address_id TEXT,
    start_time INTEGER,
    last_activity INTEGER,
    last_analysis INTEGER,
    is_active INTEGER DEFAULT 1,
    created_at INTEGER DEFAULT (strftime('%s', 'now') * 1000),
    FOREIGN KEY (address_id) REFERENCES monitored_addresses(address)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_base_transactions_tokens ON base_transactions(input_token, output_token);
CREATE INDEX IF NOT EXISTS idx_base_transactions_timestamp ON base_transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_market_states_timestamp ON market_states(timestamp);
CREATE INDEX IF NOT EXISTS idx_pool_states_pool_address ON pool_states(pool_address);
CREATE INDEX IF NOT EXISTS idx_analysis_results_token_pair ON analysis_results(token_pair);
"""

def get_schema_sql():
    """返回数据库模型SQL"""
    return INIT_DB_SQL 