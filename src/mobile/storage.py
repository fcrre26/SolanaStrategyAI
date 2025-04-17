"""
移动端存储模块
负责在移动设备上存储和管理Solana交易数据，并提交给API进行分析
"""
import os
import json
import time
import logging
import aiohttp
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta

from ..solana.parser import parse_transaction, prepare_for_mobile_storage, prepare_for_api_analysis

# 基础日志配置
logger = logging.getLogger(__name__)

class MobileStorage:
    """
    移动端存储适配器
    负责在移动设备上存储和管理Solana交易数据，并将数据提交给API进行分析
    """
    
    def __init__(self, base_dir: str = None, api_endpoint: str = None, api_key: str = None):
        """
        初始化移动端存储
        
        Args:
            base_dir: 基础存储目录
            api_endpoint: API分析端点
            api_key: API访问密钥
        """
        # 存储目录设置
        self.base_dir = base_dir or os.path.join(os.path.expanduser("~"), "solana_analyzer")
        self.transactions_dir = os.path.join(self.base_dir, "transactions")
        self.analysis_dir = os.path.join(self.base_dir, "analysis")
        
        # API设置
        self.api_endpoint = api_endpoint or "https://ark.cn-beijing.volces.com/api/v3"
        self.api_key = api_key
        
        # 创建必要的目录
        self._ensure_directories()
    
    def _ensure_directories(self):
        """确保所需的目录存在"""
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.transactions_dir, exist_ok=True)
        os.makedirs(self.analysis_dir, exist_ok=True)
    
    def _get_wallet_dir(self, wallet_address: str) -> str:
        """获取钱包的存储目录"""
        wallet_dir = os.path.join(self.transactions_dir, wallet_address)
        os.makedirs(wallet_dir, exist_ok=True)
        return wallet_dir
    
    def store_transaction(self, tx_data: Dict[str, Any], wallet_address: str = None) -> str:
        """
        存储单个交易
        
        Args:
            tx_data: 原始交易数据
            wallet_address: 钱包地址
            
        Returns:
            存储文件路径
        """
        try:
            # 解析交易
            parsed_tx = parse_transaction(tx_data)
            
            # 提取钱包地址(如果未提供)
            if not wallet_address:
                signers = parsed_tx.get("signers", [])
                if signers:
                    wallet_address = signers[0]
                else:
                    wallet_address = "unknown"
            
            # 准备用于移动存储的数据
            mobile_tx = prepare_for_mobile_storage(parsed_tx)
            
            # 获取交易ID
            tx_id = mobile_tx.get("transaction_id", f"unknown_{int(time.time())}")
            
            # 获取钱包目录
            wallet_dir = self._get_wallet_dir(wallet_address)
            
            # 创建文件路径
            file_path = os.path.join(wallet_dir, f"{tx_id}.json")
            
            # 添加存储时间和钱包地址信息
            mobile_tx["stored_at"] = datetime.now().isoformat()
            mobile_tx["wallet_address"] = wallet_address
            
            # 写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(mobile_tx, f, indent=2, ensure_ascii=False)
            
            logger.info(f"交易已存储: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"存储交易出错: {e}")
            return ""
    
    def store_transactions(self, tx_data_list: List[Dict[str, Any]], wallet_address: str = None) -> List[str]:
        """
        批量存储交易
        
        Args:
            tx_data_list: 原始交易数据列表
            wallet_address: 钱包地址
            
        Returns:
            存储文件路径列表
        """
        file_paths = []
        for tx_data in tx_data_list:
            file_path = self.store_transaction(tx_data, wallet_address)
            if file_path:
                file_paths.append(file_path)
        return file_paths
    
    def list_transactions(self, wallet_address: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        列出指定钱包的交易
        
        Args:
            wallet_address: 钱包地址
            days: 列出最近多少天的交易
            
        Returns:
            交易数据列表
        """
        results = []
        
        wallet_dir = self._get_wallet_dir(wallet_address)
        if not os.path.exists(wallet_dir):
            return results
        
        # 计算截止日期
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # 遍历目录下的所有交易文件
        for filename in os.listdir(wallet_dir):
            if not filename.endswith(".json"):
                continue
                
            file_path = os.path.join(wallet_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    tx_data = json.load(f)
                
                # 检查存储时间
                stored_at = tx_data.get("stored_at")
                if stored_at:
                    stored_time = datetime.fromisoformat(stored_at)
                    if stored_time < cutoff_date:
                        continue
                
                results.append(tx_data)
            except Exception as e:
                logger.error(f"读取交易文件出错: {file_path}, {e}")
        
        # 按时间排序(新的在前)
        results.sort(key=lambda x: x.get("stored_at", ""), reverse=True)
        return results
    
    def get_transaction(self, tx_id: str, wallet_address: str) -> Optional[Dict[str, Any]]:
        """
        获取指定交易的数据
        
        Args:
            tx_id: 交易ID
            wallet_address: 钱包地址
            
        Returns:
            交易数据或None
        """
        wallet_dir = self._get_wallet_dir(wallet_address)
        file_path = os.path.join(wallet_dir, f"{tx_id}.json")
        
        if not os.path.exists(file_path):
            return None
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取交易文件出错: {file_path}, {e}")
            return None
    
    def delete_transaction(self, tx_id: str, wallet_address: str) -> bool:
        """
        删除指定交易
        
        Args:
            tx_id: 交易ID
            wallet_address: 钱包地址
            
        Returns:
            是否成功删除
        """
        wallet_dir = self._get_wallet_dir(wallet_address)
        file_path = os.path.join(wallet_dir, f"{tx_id}.json")
        
        if not os.path.exists(file_path):
            return False
            
        try:
            os.remove(file_path)
            logger.info(f"交易已删除: {file_path}")
            return True
        except Exception as e:
            logger.error(f"删除交易文件出错: {file_path}, {e}")
            return False
    
    def clear_transactions(self, wallet_address: str, days: int = None) -> int:
        """
        清除指定钱包的交易
        
        Args:
            wallet_address: 钱包地址
            days: 清除多少天前的交易(None表示全部清除)
            
        Returns:
            清除的交易数量
        """
        wallet_dir = self._get_wallet_dir(wallet_address)
        if not os.path.exists(wallet_dir):
            return 0
            
        removed_count = 0
        
        # 计算截止日期(如果指定)
        cutoff_date = None
        if days is not None:
            cutoff_date = datetime.now() - timedelta(days=days)
        
        # 遍历目录下的所有交易文件
        for filename in os.listdir(wallet_dir):
            if not filename.endswith(".json"):
                continue
                
            file_path = os.path.join(wallet_dir, filename)
            
            # 如果设置了天数，需要检查存储时间
            if cutoff_date:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        tx_data = json.load(f)
                    
                    # 检查存储时间
                    stored_at = tx_data.get("stored_at")
                    if stored_at:
                        stored_time = datetime.fromisoformat(stored_at)
                        if stored_time > cutoff_date:
                            continue  # 跳过较新的交易
                except Exception:
                    pass  # 如果读取失败，默认删除
            
            # 删除文件
            try:
                os.remove(file_path)
                removed_count += 1
            except Exception as e:
                logger.error(f"删除交易文件出错: {file_path}, {e}")
        
        logger.info(f"已清除 {removed_count} 个交易")
        return removed_count
    
    def store_analysis_result(self, result: Dict[str, Any], wallet_address: str, analysis_id: str = None) -> str:
        """
        存储分析结果
        
        Args:
            result: 分析结果
            wallet_address: 钱包地址
            analysis_id: 分析ID(默认自动生成)
            
        Returns:
            存储文件路径
        """
        # 确保分析目录存在
        wallet_analysis_dir = os.path.join(self.analysis_dir, wallet_address)
        os.makedirs(wallet_analysis_dir, exist_ok=True)
        
        # 生成分析ID
        if not analysis_id:
            timestamp = int(time.time())
            analysis_id = f"analysis_{timestamp}"
        
        # 创建文件路径
        file_path = os.path.join(wallet_analysis_dir, f"{analysis_id}.json")
        
        # 添加元数据
        result_with_meta = {
            "analysis_id": analysis_id,
            "wallet_address": wallet_address,
            "timestamp": datetime.now().isoformat(),
            "result": result
        }
        
        # 写入文件
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result_with_meta, f, indent=2, ensure_ascii=False)
        
        logger.info(f"分析结果已存储: {file_path}")
        return file_path
    
    def list_analysis_results(self, wallet_address: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        列出指定钱包的分析结果
        
        Args:
            wallet_address: 钱包地址
            limit: 最多返回多少条结果
            
        Returns:
            分析结果列表
        """
        results = []
        
        wallet_analysis_dir = os.path.join(self.analysis_dir, wallet_address)
        if not os.path.exists(wallet_analysis_dir):
            return results
        
        # 遍历目录下的所有分析文件
        for filename in os.listdir(wallet_analysis_dir):
            if not filename.endswith(".json"):
                continue
                
            file_path = os.path.join(wallet_analysis_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    analysis_data = json.load(f)
                results.append(analysis_data)
            except Exception as e:
                logger.error(f"读取分析文件出错: {file_path}, {e}")
        
        # 按时间排序(新的在前)
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # 限制返回数量
        return results[:limit]
    
    def get_analysis_result(self, analysis_id: str, wallet_address: str) -> Optional[Dict[str, Any]]:
        """
        获取指定分析结果
        
        Args:
            analysis_id: 分析ID
            wallet_address: 钱包地址
            
        Returns:
            分析结果或None
        """
        wallet_analysis_dir = os.path.join(self.analysis_dir, wallet_address)
        file_path = os.path.join(wallet_analysis_dir, f"{analysis_id}.json")
        
        if not os.path.exists(file_path):
            return None
            
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"读取分析文件出错: {file_path}, {e}")
            return None
    
    async def request_api_analysis(self, wallet_address: str, days: int = 30, model: str = "deepseek-v3-250324") -> Optional[Dict[str, Any]]:
        """
        请求API分析交易数据
        
        Args:
            wallet_address: 钱包地址
            days: 分析最近多少天的交易
            model: 使用的模型
            
        Returns:
            分析结果或None
        """
        if not self.api_key:
            logger.error("API密钥未设置")
            return None
        
        try:
            # 获取最近的交易数据
            transactions = self.list_transactions(wallet_address, days)
            if not transactions:
                logger.warning(f"没有找到钱包 {wallet_address} 的交易数据")
                return None
            
            # 准备API分析数据
            api_data = prepare_for_api_analysis(transactions, wallet_address)
            
            # 构建系统提示
            system_prompt = """
            你是一位专业的加密货币交易策略分析师，专注于Solana生态系统的交易模式分析。
            你的任务是分析提供的交易数据，识别交易模式，并提取完整的自动化交易策略。
            
            请仔细分析提供的数据，包括:
            1. 交易历史
            2. DEX使用情况
            3. 代币交易模式
            4. 交易频率
            
            你的输出必须是严格的JSON格式，包含以下关键部分:
            
            1. 交易模式识别
            2. 策略提取
            3. 改进建议
            4. 风险分析
            
            确保你的分析全面、详细，并基于数据提供具体的策略参数。
            """
            
            # 构建用户提示
            user_prompt = f"""
            请分析以下交易数据并提取完整的交易策略:
            
            钱包地址: {wallet_address}
            分析时段: {days} 天
            交易次数: {api_data['transaction_count']}
            
            请根据以下数据进行分析:
            
            1. 交易类型统计:
            {json.dumps(api_data['transaction_types'], indent=2)}
            
            2. DEX使用情况:
            {json.dumps(api_data['dex_usage'], indent=2)}
            
            3. 代币交易模式:
            {json.dumps(api_data['token_trading_patterns'], indent=2)}
            
            请提供以下输出格式的分析结果:
            
            {
                "pattern_recognition": {
                    "primary_pattern": "主要交易模式",
                    "secondary_patterns": ["次要模式1", "次要模式2"],
                    "timing_patterns": "时间模式分析",
                    "token_selection_logic": "代币选择逻辑"
                },
                "strategy": {
                    "name": "策略名称",
                    "description": "策略简要描述",
                    "target_selection": {
                        "criteria": ["选择标准1", "选择标准2"],
                        "filters": ["过滤条件1", "过滤条件2"]
                    },
                    "entry_strategy": {
                        "triggers": ["入场触发条件1", "入场触发条件2"],
                        "confirmation_signals": ["确认信号1", "确认信号2"],
                        "optimal_timing": "最佳入场时机描述"
                    },
                    "exit_strategy": {
                        "take_profit": "止盈策略",
                        "stop_loss": "止损策略",
                        "trailing_mechanisms": "追踪止损机制"
                    },
                    "position_management": {
                        "sizing": "仓位大小计算方法",
                        "scaling": "加减仓策略",
                        "hedging": "对冲策略(如适用)"
                    },
                    "risk_control": {
                        "max_position_size": "最大仓位建议",
                        "max_daily_loss": "每日最大亏损限制",
                        "correlation_management": "相关性管理策略"
                    },
                    "automation_flow": {
                        "monitoring_frequency": "监控频率",
                        "trigger_actions": ["触发动作1", "触发动作2"],
                        "fallback_procedures": ["应急程序1", "应急程序2"]
                    }
                },
                "improvement_suggestions": {
                    "efficiency_gains": ["效率提升建议1", "效率提升建议2"],
                    "risk_reduction": ["风险降低建议1", "风险降低建议2"],
                    "profitability_enhancements": ["盈利能力提升建议1", "盈利能力提升建议2"]
                },
                "risk_analysis": {
                    "identified_risks": ["已识别风险1", "已识别风险2"],
                    "mitigation_strategies": ["风险缓解策略1", "风险缓解策略2"],
                    "market_dependency_factors": ["市场依赖因素1", "市场依赖因素2"]
                }
            }
            """
            
            # 调用API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_endpoint}/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.3
                    }
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"API请求失败 ({response.status}): {error_text}")
                        return None
                        
                    response_data = await response.json()
                    
            # 解析结果
            if not response_data or "choices" not in response_data:
                logger.error("无效的API响应")
                return None
                
            result_text = response_data["choices"][0]["message"]["content"]
            
            # 尝试解析JSON结果
            try:
                # 提取JSON部分(如果包含在Markdown代码块中)
                if "```json" in result_text and "```" in result_text:
                    json_text = result_text.split("```json")[1].split("```")[0].strip()
                    result = json.loads(json_text)
                else:
                    # 尝试直接解析
                    result = json.loads(result_text)
                    
                # 存储分析结果
                self.store_analysis_result(result, wallet_address)
                
                return result
                
            except json.JSONDecodeError:
                logger.error(f"无法解析API结果为JSON: {result_text[:100]}...")
                # 存储原始文本结果
                self.store_analysis_result({"raw_text": result_text}, wallet_address)
                return {"raw_text": result_text}
                
        except Exception as e:
            logger.error(f"API分析请求出错: {e}")
            return None
    
    def get_storage_info(self) -> Dict[str, Any]:
        """
        获取存储信息和统计数据
        
        Returns:
            存储信息字典
        """
        info = {
            "base_dir": self.base_dir,
            "wallets": [],
            "total_transactions": 0,
            "total_analyses": 0,
            "storage_size": 0
        }
        
        # 统计钱包数据
        if os.path.exists(self.transactions_dir):
            for wallet in os.listdir(self.transactions_dir):
                wallet_dir = os.path.join(self.transactions_dir, wallet)
                if not os.path.isdir(wallet_dir):
                    continue
                    
                # 计算交易数量
                tx_count = len([f for f in os.listdir(wallet_dir) if f.endswith(".json")])
                info["total_transactions"] += tx_count
                
                # 计算分析数量
                analysis_dir = os.path.join(self.analysis_dir, wallet)
                analysis_count = 0
                if os.path.exists(analysis_dir):
                    analysis_count = len([f for f in os.listdir(analysis_dir) if f.endswith(".json")])
                    info["total_analyses"] += analysis_count
                
                info["wallets"].append({
                    "address": wallet,
                    "transactions": tx_count,
                    "analyses": analysis_count
                })
        
        # 计算总存储大小
        info["storage_size"] = self._get_dir_size(self.base_dir)
        
        return info
    
    def _get_dir_size(self, path: str) -> int:
        """获取目录大小(字节)"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
        return total_size

# 创建默认存储实例
default_storage = MobileStorage()

# 外部接口函数
def get_storage() -> MobileStorage:
    """获取默认存储实例"""
    return default_storage

def init_storage(base_dir: str = None, api_endpoint: str = None, api_key: str = None) -> MobileStorage:
    """
    初始化存储
    
    Args:
        base_dir: 基础存储目录
        api_endpoint: API分析端点
        api_key: API访问密钥
        
    Returns:
        存储实例
    """
    global default_storage
    default_storage = MobileStorage(base_dir, api_endpoint, api_key)
    return default_storage

async def analyze_wallet(wallet_address: str, days: int = 30) -> Optional[Dict[str, Any]]:
    """
    分析钱包交易
    
    Args:
        wallet_address: 钱包地址
        days: 分析最近多少天的交易
        
    Returns:
        分析结果或None
    """
    storage = get_storage()
    return await storage.request_api_analysis(wallet_address, days) 