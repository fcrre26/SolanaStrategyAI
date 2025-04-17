import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).parent.parent.absolute()

# Solana节点配置
GRPC_ENDPOINT = "solana-yellowstone-grpc.publicnode.com:443"
AMM_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"  # Raydium AMM程序ID

# 火山引擎API配置
AI_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
AI_API_KEY = os.environ.get("ARK_API_KEY", "")

# 数据库配置
DB_PATH = str(Path(BASE_DIR) / "data" / "trading_data.db")

# 监控配置
MONITORING_INTERVAL = 1.0  # 监控间隔(秒)
ANALYSIS_INTERVAL = 300.0  # 分析间隔(秒)
INACTIVE_THRESHOLD = 72 * 3600  # 不活跃阈值(秒)

# 数据收集配置
DATA_LIMIT = 100  # 每次查询的数据限制
LOG_LEVEL = "INFO"  # 日志级别

# 路径配置
REPORTS_DIR = str(Path(BASE_DIR) / "reports")

# 系统平台检测
IS_WINDOWS = os.name == 'nt' 