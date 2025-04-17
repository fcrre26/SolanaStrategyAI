"""
Anchor程序解析器模块，用于解析Anchor程序的指令。
"""
from typing import Dict, Any, Optional
from solana.rpc.types import TxInfo
from solana.transaction import TransactionInstruction
from anchorpy import Idl, Program
from .base import ParsedInstruction

class AnchorParser:
    """Anchor程序解析器"""
    
    def __init__(self, idl: Idl, program_id: str):
        """
        初始化Anchor解析器
        
        Args:
            idl: Anchor IDL
            program_id: 程序ID
        """
        self.idl = idl
        self.program_id = program_id
        self.program = Program(idl, program_id)
    
    async def parse_instruction(self, ix: TransactionInstruction, tx_info: TxInfo) -> Optional[ParsedInstruction]:
        """
        解析Anchor指令
        
        Args:
            ix: 交易指令
            tx_info: 交易信息
            
        Returns:
            解析后的指令数据
        """
        try:
            # 解码指令数据
            decoded = self.program.coder.instruction.decode(ix.data)
            if not decoded:
                return None
                
            name, args = decoded
            
            # 解析账户
            accounts = []
            for idx, acc in enumerate(ix.accounts):
                account_info = {
                    "pubkey": str(acc.pubkey),
                    "is_signer": acc.is_signer,
                    "is_writable": acc.is_writable
                }
                
                # 尝试从IDL中获取账户名称
                if idx < len(self.idl.instructions[0].accounts):
                    account_info["name"] = self.idl.instructions[0].accounts[idx].name
                
                accounts.append(account_info)
            
            return ParsedInstruction(
                program_id=self.program_id,
                name=name,
                accounts=accounts,
                args=args
            )
            
        except Exception as e:
            print(f"Error parsing Anchor instruction: {str(e)}")
            return None 