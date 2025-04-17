"""
Solana transaction parser using solana-tx-parser.
"""
import json
import logging
from typing import Dict, List, Any, Optional

from solana.rpc.types import TxOpts
from solana.rpc.commitment import Commitment
from solders.pubkey import Pubkey
from solders.transaction import Transaction

logger = logging.getLogger(__name__)

class TransactionParser:
    """
    Parser for Solana transactions using solana-tx-parser.
    """
    
    def __init__(self):
        """Initialize the parser."""
        # Load known program IDs and their IDLs
        self.known_programs = {
            "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB": "Jupiter",
            "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca",
            "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium"
        }
    
    def parse_transaction(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a transaction using solana-tx-parser.
        
        Args:
            tx_data: Raw transaction data from RPC
            
        Returns:
            Parsed transaction data
        """
        try:
            # Extract basic transaction info
            result = {
                "signature": tx_data.get("transaction", {}).get("signatures", [])[0],
                "slot": tx_data.get("slot"),
                "block_time": tx_data.get("blockTime"),
                "success": not tx_data.get("meta", {}).get("err"),
                "fee": tx_data.get("meta", {}).get("fee", 0),
                "instructions": [],
                "token_transfers": [],
                "program_ids": set(),
                "accounts": set()
            }
            
            # Parse instructions
            if "message" in tx_data.get("transaction", {}):
                message = tx_data["transaction"]["message"]
                
                # Get account keys
                account_keys = []
                for key in message.get("accountKeys", []):
                    if isinstance(key, str):
                        account_keys.append(key)
                    elif isinstance(key, dict) and "pubkey" in key:
                        account_keys.append(key["pubkey"])
                        
                result["accounts"].update(account_keys)
                
                # Parse each instruction
                for idx, ix in enumerate(message.get("instructions", [])):
                    parsed_ix = self._parse_instruction(ix, account_keys)
                    if parsed_ix:
                        result["instructions"].append(parsed_ix)
                        if "programId" in parsed_ix:
                            result["program_ids"].add(parsed_ix["programId"])
                            
            # Parse token transfers
            if "meta" in tx_data and "postTokenBalances" in tx_data["meta"]:
                pre_balances = tx_data["meta"].get("preTokenBalances", [])
                post_balances = tx_data["meta"].get("postTokenBalances", [])
                
                # Create balance maps
                pre_map = {
                    (b.get("accountIndex"), b.get("mint")): b 
                    for b in pre_balances if "mint" in b
                }
                post_map = {
                    (b.get("accountIndex"), b.get("mint")): b 
                    for b in post_balances if "mint" in b
                }
                
                # Find balance changes
                for key in post_map:
                    idx, mint = key
                    post_bal = post_map[key]
                    
                    if key in pre_map:
                        pre_bal = pre_map[key]
                        
                        pre_amount = float(pre_bal.get("uiTokenAmount", {}).get("uiAmount", 0))
                        post_amount = float(post_bal.get("uiTokenAmount", {}).get("uiAmount", 0))
                        
                        if post_amount != pre_amount:
                            transfer = {
                                "token": mint,
                                "from_index": idx if post_amount < pre_amount else None,
                                "to_index": idx if post_amount > pre_amount else None,
                                "amount": abs(post_amount - pre_amount),
                                "decimals": post_bal.get("uiTokenAmount", {}).get("decimals", 0)
                            }
                            result["token_transfers"].append(transfer)
                            
            # Convert sets to lists for JSON serialization
            result["program_ids"] = list(result["program_ids"])
            result["accounts"] = list(result["accounts"])
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing transaction: {e}")
            return None
            
    def _parse_instruction(self, ix: Dict[str, Any], account_keys: List[str]) -> Optional[Dict[str, Any]]:
        """
        Parse a single instruction.
        
        Args:
            ix: Instruction data
            account_keys: List of account public keys
            
        Returns:
            Parsed instruction data
        """
        try:
            program_id_index = ix.get("programIdIndex")
            if program_id_index is None or program_id_index >= len(account_keys):
                return None
                
            program_id = account_keys[program_id_index]
            
            # Get account metas
            accounts = []
            for idx in ix.get("accounts", []):
                if idx < len(account_keys):
                    accounts.append({
                        "pubkey": account_keys[idx],
                        "is_signer": idx < ix.get("header", {}).get("numRequiredSignatures", 0),
                        "is_writable": idx < ix.get("header", {}).get("numRequiredWritableSignings", 0)
                    })
                    
            # Parse data based on program
            parsed_data = None
            if program_id in self.known_programs:
                program_name = self.known_programs[program_id]
                if program_name == "Jupiter":
                    parsed_data = self._parse_jupiter_data(ix.get("data"))
                elif program_name == "Orca":
                    parsed_data = self._parse_orca_data(ix.get("data"))
                elif program_name == "Raydium":
                    parsed_data = self._parse_raydium_data(ix.get("data"))
                    
            return {
                "programId": program_id,
                "accounts": accounts,
                "data": parsed_data or ix.get("data")
            }
            
        except Exception as e:
            logger.error(f"Error parsing instruction: {e}")
        return None
    
    def _parse_jupiter_data(self, data: str) -> Optional[Dict[str, Any]]:
        """Parse Jupiter instruction data."""
        try:
            # Implement Jupiter-specific parsing
            return None
        except Exception as e:
            logger.error(f"Error parsing Jupiter data: {e}")
        return None
            
    def _parse_orca_data(self, data: str) -> Optional[Dict[str, Any]]:
        """Parse Orca instruction data."""
        try:
            # Implement Orca-specific parsing
            return None
        except Exception as e:
            logger.error(f"Error parsing Orca data: {e}")
        return None
            
    def _parse_raydium_data(self, data: str) -> Optional[Dict[str, Any]]:
        """Parse Raydium instruction data."""
        try:
            # Implement Raydium-specific parsing
            return None
        except Exception as e:
            logger.error(f"Error parsing Raydium data: {e}")
        return None

# 创建解析器实例
parser = TransactionParser()

# 外部接口函数
def parse_transaction(tx_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析单个交易
    
    Args:
        tx_data: 原始交易数据
        
    Returns:
        解析后的交易数据
    """
    return parser.parse_transaction(tx_data)

def prepare_for_mobile_storage(parsed_txs: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    准备用于移动端存储的数据
    
    Args:
        parsed_txs: 单个或多个已解析的交易数据
        
    Returns:
        适合移动端存储的数据
    """
    if isinstance(parsed_txs, dict):
        return parser.prepare_for_storage(parsed_txs)
    elif isinstance(parsed_txs, list):
        return [parser.prepare_for_storage(tx) for tx in parsed_txs]
    else:
        raise ValueError("输入数据类型错误，应为字典或字典列表")

def prepare_for_api_analysis(parsed_txs: List[Dict[str, Any]], wallet_address: str) -> Dict[str, Any]:
        """
        准备用于API分析的数据
        
        Args:
            parsed_txs: 已解析的交易数据列表
            wallet_address: 钱包地址
            
        Returns:
            适合提交给API分析的数据
        """
    return parser.prepare_for_api_analysis(parsed_txs, wallet_address)

def extract_trading_pairs(parsed_txs: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        从解析后的交易中提取交易对
        
        Args:
            parsed_txs: 已解析的交易数据列表
            
        Returns:
            交易对及其交易次数
        """
    return parser.extract_trading_pairs(parsed_txs) 
            if log_messages and isinstance(log_messages, list):
                for log in log_messages:
                    if any(keyword in log for keyword in ["liquidity", "Liquidity", "deposit", "Deposit", "withdraw", "Withdraw", "pool", "Pool"]):
                        return True
                        
        return False
    
    def _is_stake_transaction(self, tx_data: Dict[str, Any]) -> bool:
        """检查是否为质押交易"""
        # 检查日志中是否包含质押相关关键词
        if "meta" in tx_data and "logMessages" in tx_data["meta"]:
            log_messages = tx_data["meta"]["logMessages"]
            if log_messages and isinstance(log_messages, list):
                for log in log_messages:
                    if any(keyword in log for keyword in ["stake", "Stake", "delegate", "Delegate", "unstake", "Unstake", "withdraw", "Withdraw"]):
                        return True
                        
        return False
    
    # 详细信息提取方法
    def _extract_dex_info(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取DEX信息"""
        dex_info = {
            "name": None,
            "program_id": None
        }
        
        # 根据账户检查DEX程序ID
        if "transaction" in tx_data and "message" in tx_data["transaction"]:
            account_keys = tx_data["transaction"]["message"].get("accountKeys", [])
            for program_id, dex_name in self.KNOWN_DEX_PROGRAMS.items():
                if program_id in account_keys:
                    dex_info["name"] = dex_name
                    dex_info["program_id"] = program_id
                    break
                    
        return dex_info
    
    def _extract_token_transfers(self, tx_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取代币转账信息"""
        token_transfers = []
        
        # 需要解析交易日志或解码交易指令
        # 这是一个简化的实现，实际需要解析SPL Token指令和日志
        if "meta" in tx_data and "postTokenBalances" in tx_data["meta"] and "preTokenBalances" in tx_data["meta"]:
            pre_balances = tx_data["meta"]["preTokenBalances"]
            post_balances = tx_data["meta"]["postTokenBalances"]
            
            # 创建余额索引
            pre_bal_map = {(b.get("accountIndex"), b.get("mint")): b for b in pre_balances if "mint" in b}
            post_bal_map = {(b.get("accountIndex"), b.get("mint")): b for b in post_balances if "mint" in b}
            
            # 提取账户映射
            account_keys = []
            if "transaction" in tx_data and "message" in tx_data["transaction"]:
                account_keys = tx_data["transaction"]["message"].get("accountKeys", [])
            
            # 查找余额变化
            for key in post_bal_map:
                idx, mint = key
                post_bal = post_bal_map[key]
                
                # 检查此代币在交易前是否有余额记录
                if key in pre_bal_map:
                    pre_bal = pre_bal_map[key]
                    
                    pre_amount = int(pre_bal.get("uiTokenAmount", {}).get("amount", "0"))
                    post_amount = int(post_bal.get("uiTokenAmount", {}).get("amount", "0"))
                    
                    # 如果余额增加，说明是接收方
                    if post_amount > pre_amount:
                        token_transfer = {
                            "token": mint,
                            "token_symbol": self.KNOWN_TOKENS.get(mint, "Unknown"),
                            "from_address": None,  # 无法直接确定发送方
                            "to_address": post_bal.get("owner"),
                            "amount": (post_amount - pre_amount) / (10 ** post_bal.get("uiTokenAmount", {}).get("decimals", 0))
                        }
                        token_transfers.append(token_transfer)
                    # 如果余额减少，说明是发送方
                    elif post_amount < pre_amount:
                        token_transfer = {
                            "token": mint,
                            "token_symbol": self.KNOWN_TOKENS.get(mint, "Unknown"),
                            "from_address": pre_bal.get("owner"),
                            "to_address": None,  # 无法直接确定接收方
                            "amount": (pre_amount - post_amount) / (10 ** pre_bal.get("uiTokenAmount", {}).get("decimals", 0))
                        }
                        token_transfers.append(token_transfer)
                # 如果交易前没有记录，但交易后有，说明是新创建的代币账户
                else:
                    post_amount = int(post_bal.get("uiTokenAmount", {}).get("amount", "0"))
                    if post_amount > 0:
                        token_transfer = {
                            "token": mint,
                            "token_symbol": self.KNOWN_TOKENS.get(mint, "Unknown"),
                            "from_address": None,
                            "to_address": post_bal.get("owner"),
                            "amount": post_amount / (10 ** post_bal.get("uiTokenAmount", {}).get("decimals", 0))
                        }
                        token_transfers.append(token_transfer)
                        
        return token_transfers
    
    def _extract_swap_info(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取交换信息"""
        swap_info = {
            "input_token": None,
            "input_token_symbol": None,
            "input_amount": None,
            "output_token": None,
            "output_token_symbol": None,
            "output_amount": None,
            "price_impact": None,
            "route_type": None
        }
        
        # 从代币转账中推断交换信息
        token_transfers = self._extract_token_transfers(tx_data)
        
        # 按照地址分组
        transfers_by_address = {}
        for transfer in token_transfers:
            from_addr = transfer.get("from_address")
            to_addr = transfer.get("to_address")
            
            if from_addr:
                if from_addr not in transfers_by_address:
                    transfers_by_address[from_addr] = {"in": [], "out": []}
                transfers_by_address[from_addr]["out"].append(transfer)
                
            if to_addr:
                if to_addr not in transfers_by_address:
                    transfers_by_address[to_addr] = {"in": [], "out": []}
                transfers_by_address[to_addr]["in"].append(transfer)
        
        # 尝试找到同时有代币流入和流出的地址(可能是交换发起者)
        candidate_addresses = []
        for addr, transfers in transfers_by_address.items():
            if transfers["in"] and transfers["out"]:
                candidate_addresses.append(addr)
                
        # 如果找到了候选地址，使用第一个作为交换发起者
        if candidate_addresses:
            trader_addr = candidate_addresses[0]
            in_transfers = transfers_by_address[trader_addr]["in"]
            out_transfers = transfers_by_address[trader_addr]["out"]
            
            # 假设最大的流出是输入代币，最大的流入是输出代币
            if out_transfers:
                max_out = max(out_transfers, key=lambda t: t.get("amount", 0))
                swap_info["input_token"] = max_out.get("token")
                swap_info["input_token_symbol"] = max_out.get("token_symbol")
                swap_info["input_amount"] = max_out.get("amount")
                
            if in_transfers:
                max_in = max(in_transfers, key=lambda t: t.get("amount", 0))
                swap_info["output_token"] = max_in.get("token")
                swap_info["output_token_symbol"] = max_in.get("token_symbol")
                swap_info["output_amount"] = max_in.get("amount")
                
        # 检查日志中的路由信息
        if "meta" in tx_data and "logMessages" in tx_data["meta"]:
            log_messages = tx_data["meta"]["logMessages"]
            if log_messages and isinstance(log_messages, list):
                for log in log_messages:
                    if "route" in log.lower():
                        if "direct" in log.lower():
                            swap_info["route_type"] = "direct"
                        elif "split" in log.lower():
                            swap_info["route_type"] = "split"
                        elif "multi" in log.lower() or "hop" in log.lower():
                            swap_info["route_type"] = "multi-hop"
                            
        return swap_info
    
    def _extract_liquidity_info(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取流动性信息"""
        # 简化实现，实际需要解析具体的流动性操作
        return {
            "operation": "unknown",  # 可能是add, remove等
            "pool_address": None,
            "tokens": [],
            "amounts": []
        }
    
    def _extract_stake_info(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取质押信息"""
        # 简化实现，实际需要解析具体的质押操作
        return {
            "operation": "unknown",  # 可能是stake, unstake等
            "validator": None,
            "amount": None
        }

# 创建解析器实例
parser = TransactionParser()

# 外部接口函数
def parse_transaction(tx_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析单个交易
    
    Args:
        tx_data: 原始交易数据
        
    Returns:
        解析后的交易数据
    """
    return parser.parse_transaction(tx_data)

def prepare_for_mobile_storage(parsed_txs: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    准备用于移动端存储的数据
    
    Args:
        parsed_txs: 单个或多个已解析的交易数据
        
    Returns:
        适合移动端存储的数据
    """
    if isinstance(parsed_txs, dict):
        return parser.prepare_for_storage(parsed_txs)
    elif isinstance(parsed_txs, list):
        return [parser.prepare_for_storage(tx) for tx in parsed_txs]
    else:
        raise ValueError("输入数据类型错误，应为字典或字典列表")

def prepare_for_api_analysis(parsed_txs: List[Dict[str, Any]], wallet_address: str) -> Dict[str, Any]:
    """
    准备用于API分析的数据
    
    Args:
        parsed_txs: 已解析的交易数据列表
        wallet_address: 钱包地址
        
    Returns:
        适合提交给API分析的数据
    """
    return parser.prepare_for_api_analysis(parsed_txs, wallet_address)

def extract_trading_pairs(parsed_txs: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    从解析后的交易中提取交易对
    
    Args:
        parsed_txs: 已解析的交易数据列表
        
    Returns:
        交易对及其交易次数
    """
    return parser.extract_trading_pairs(parsed_txs) 