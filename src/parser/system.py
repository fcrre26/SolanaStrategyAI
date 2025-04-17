"""
系统程序解析器模块，用于解析Solana系统程序的指令。
"""
from typing import Dict, Any, Optional
from solana.rpc.types import TxInfo
from solana.transaction import TransactionInstruction
from .base import ParsedInstruction

class SystemParser:
    """系统程序解析器"""
    
    SYSTEM_PROGRAM_ID = "11111111111111111111111111111111"
    
    @staticmethod
    async def parse_instruction(ix: TransactionInstruction, tx_info: TxInfo) -> Optional[ParsedInstruction]:
        """
        解析系统程序指令
        
        Args:
            ix: 交易指令
            tx_info: 交易信息
            
        Returns:
            解析后的指令数据
        """
        try:
            # 系统程序指令类型
            instruction_types = {
                0: "create_account",
                1: "assign",
                2: "transfer",
                3: "create_account_with_seed",
                4: "advance_nonce_account",
                5: "withdraw_nonce_account",
                6: "initialize_nonce_account",
                7: "authorize_nonce_account",
                8: "allocate",
                9: "allocate_with_seed",
                10: "assign_with_seed",
                11: "transfer_with_seed",
                12: "upgrade_non_centralized_system_program"
            }
            
            # 获取指令类型
            instruction_type = ix.data[0]
            name = instruction_types.get(instruction_type, "unknown")
            
            # 解析账户
            accounts = []
            for acc in ix.accounts:
                accounts.append({
                    "pubkey": str(acc.pubkey),
                    "is_signer": acc.is_signer,
                    "is_writable": acc.is_writable
                })
            
            # 解析参数
            args = {}
            if instruction_type == 0:  # create_account
                args = {
                    "lamports": int.from_bytes(ix.data[1:9], "little"),
                    "space": int.from_bytes(ix.data[9:13], "little"),
                    "owner": str(ix.data[13:45])
                }
            elif instruction_type == 2:  # transfer
                args = {
                    "lamports": int.from_bytes(ix.data[1:9], "little")
                }
            
            return ParsedInstruction(
                program_id=SystemParser.SYSTEM_PROGRAM_ID,
                name=name,
                accounts=accounts,
                args=args
            )
            
        except Exception as e:
            print(f"Error parsing System instruction: {str(e)}")
            return None 