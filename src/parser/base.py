"""
基础解析器模块，提供通用的交易解析接口和功能。
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from solana.rpc.types import TxInfo
from solana.transaction import Transaction
from solana.rpc.commitment import Commitment
from solana.rpc.api import Client

@dataclass
class ParsedInstruction:
    """解析后的指令数据结构"""
    program_id: str
    name: str
    accounts: List[Dict[str, Any]]
    args: Dict[str, Any]
    inner_instructions: List['ParsedInstruction'] = None

@dataclass
class ParsedTransaction:
    """解析后的交易数据结构"""
    signature: str
    instructions: List[ParsedInstruction]
    timestamp: int
    slot: int
    fee: int
    status: str

class BaseParser:
    """基础解析器类"""
    
    def __init__(self, rpc_client: Client):
        """
        初始化解析器
        
        Args:
            rpc_client: Solana RPC客户端
        """
        self.rpc_client = rpc_client
        self.program_parsers = {}
    
    def register_program_parser(self, program_id: str, parser_func):
        """
        注册程序解析器
        
        Args:
            program_id: 程序ID
            parser_func: 解析函数
        """
        self.program_parsers[program_id] = parser_func
    
    async def parse_transaction(self, signature: str) -> Optional[ParsedTransaction]:
        """
        解析交易
        
        Args:
            signature: 交易签名
            
        Returns:
            解析后的交易数据
        """
        try:
            # 获取交易信息
            tx_info = await self.rpc_client.get_transaction(
                signature,
                commitment=Commitment("confirmed")
            )
            
            if not tx_info or not tx_info.value:
                return None
                
            # 解析交易
            return await self._parse_transaction_info(tx_info.value)
            
        except Exception as e:
            print(f"Error parsing transaction {signature}: {str(e)}")
            return None
    
    async def _parse_transaction_info(self, tx_info: TxInfo) -> ParsedTransaction:
        """
        解析交易信息
        
        Args:
            tx_info: 交易信息
            
        Returns:
            解析后的交易数据
        """
        # 解析指令
        instructions = []
        for idx, ix in enumerate(tx_info.transaction.message.instructions):
            program_id = str(ix.program_id)
            
            # 查找对应的解析器
            parser = self.program_parsers.get(program_id)
            if parser:
                parsed_ix = await parser(ix, tx_info)
                if parsed_ix:
                    instructions.append(parsed_ix)
            
        # 处理内部指令
        if tx_info.meta and tx_info.meta.inner_instructions:
            for inner in tx_info.meta.inner_instructions:
                parent_idx = inner.index
                if parent_idx < len(instructions):
                    parent_ix = instructions[parent_idx]
                    inner_instructions = []
                    
                    for inner_ix in inner.instructions:
                        program_id = str(inner_ix.program_id)
                        parser = self.program_parsers.get(program_id)
                        if parser:
                            parsed_inner = await parser(inner_ix, tx_info)
                            if parsed_inner:
                                inner_instructions.append(parsed_inner)
                    
                    if inner_instructions:
                        parent_ix.inner_instructions = inner_instructions
        
        return ParsedTransaction(
            signature=tx_info.transaction.signatures[0],
            instructions=instructions,
            timestamp=tx_info.block_time,
            slot=tx_info.slot,
            fee=tx_info.meta.fee,
            status="success" if tx_info.meta.err is None else "failed"
        )
    
    def parse_logs(self, logs: List[str]) -> List[Dict[str, Any]]:
        """
        解析交易日志
        
        Args:
            logs: 交易日志列表
            
        Returns:
            解析后的日志数据
        """
        parsed_logs = []
        call_stack = []
        current_depth = 0
        
        for log in logs:
            if log.startswith("Program "):
                # 程序调用
                program_id = log.split(" ")[1]
                call_stack.append({
                    "program_id": program_id,
                    "depth": current_depth,
                    "logs": []
                })
                current_depth += 1
            elif log.startswith("Program return: "):
                # 程序返回
                if call_stack:
                    current_depth -= 1
                    parsed_logs.append(call_stack.pop())
            else:
                # 程序日志
                if call_stack:
                    call_stack[-1]["logs"].append(log)
        
        return parsed_logs 