"""
代币程序解析器模块，用于解析Solana代币程序的指令。
"""
from typing import Dict, Any, Optional
from solana.rpc.types import TxInfo
from solana.transaction import TransactionInstruction
from .base import ParsedInstruction

class TokenParser:
    """代币程序解析器"""
    
    TOKEN_PROGRAM_ID = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    
    @staticmethod
    async def parse_instruction(ix: TransactionInstruction, tx_info: TxInfo) -> Optional[ParsedInstruction]:
        """
        解析代币程序指令
        
        Args:
            ix: 交易指令
            tx_info: 交易信息
            
        Returns:
            解析后的指令数据
        """
        try:
            # 代币程序指令类型
            instruction_types = {
                0: "initialize_mint",
                1: "initialize_account",
                2: "initialize_multisig",
                3: "transfer",
                4: "approve",
                5: "revoke",
                6: "set_authority",
                7: "mint_to",
                8: "burn",
                9: "close_account",
                10: "freeze_account",
                11: "thaw_account",
                12: "transfer_checked",
                13: "approve_checked",
                14: "mint_to_checked",
                15: "burn_checked",
                16: "initialize_account2",
                17: "sync_native",
                18: "initialize_account3",
                19: "initialize_multisig2",
                20: "initialize_mint2"
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
            if instruction_type == 3:  # transfer
                args = {
                    "amount": int.from_bytes(ix.data[1:9], "little")
                }
            elif instruction_type == 7:  # mint_to
                args = {
                    "amount": int.from_bytes(ix.data[1:9], "little")
                }
            elif instruction_type == 8:  # burn
                args = {
                    "amount": int.from_bytes(ix.data[1:9], "little")
                }
            
            return ParsedInstruction(
                program_id=TokenParser.TOKEN_PROGRAM_ID,
                name=name,
                accounts=accounts,
                args=args
            )
            
        except Exception as e:
            print(f"Error parsing Token instruction: {str(e)}")
            return None 