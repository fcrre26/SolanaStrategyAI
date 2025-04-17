"""DEX protocol parser using solana-tx-parser."""
import logging
from typing import Dict, Any, Optional
from solana.rpc.async_api import AsyncClient
from solders.pubkey import Pubkey
from solana_tx_parser import SolanaParser, ParsedTransaction

logger = logging.getLogger(__name__)

class DexParser:
    """Parser for DEX protocols using solana-tx-parser."""
    
    # DEX 程序 ID
    JUPITER_PROGRAM_ID = "JUP2jxvXaqu7NQY1GmNF4m1vodw12LVXYxbFL2uJvfo"
    ORCA_PROGRAM_ID = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"
    RAYDIUM_PROGRAM_ID = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
    
    def __init__(self, client: AsyncClient):
        """Initialize DEX parser.
        
        Args:
            client: Solana RPC client
        """
        self.client = client
        self.parser = SolanaParser([
            {
                "programId": self.JUPITER_PROGRAM_ID,
                "idl": "jupiter"  # 使用 solana-tx-parser 内置的 IDL
            },
            {
                "programId": self.ORCA_PROGRAM_ID,
                "idl": "orca"
            },
            {
                "programId": self.RAYDIUM_PROGRAM_ID,
                "idl": "raydium"
            }
        ])
    
    async def parse_pool_data(self, pool_address: str) -> Dict[str, Any]:
        """Parse pool account data.
        
        Args:
            pool_address: Pool account address
            
        Returns:
            Parsed pool data
        """
        try:
            # 获取账户数据
            account_info = await self.client.get_account_info(
                Pubkey.from_string(pool_address)
            )
            
            if not account_info or not account_info.value:
                return {}
            
            # 获取程序 ID
            program_id = str(account_info.value.owner)
            
            # 根据程序 ID 解析数据
            if program_id == self.JUPITER_PROGRAM_ID:
                return self._parse_jupiter_pool(account_info.value.data)
            elif program_id == self.ORCA_PROGRAM_ID:
                return self._parse_orca_pool(account_info.value.data)
            elif program_id == self.RAYDIUM_PROGRAM_ID:
                return self._parse_raydium_pool(account_info.value.data)
            else:
                logger.warning(f"Unknown DEX program ID: {program_id}")
                return {}
                
        except Exception as e:
            logger.error(f"Error parsing pool data: {e}")
            return {}
    
    def _parse_jupiter_pool(self, data: bytes) -> Dict[str, Any]:
        """Parse Jupiter pool data."""
        try:
            # 使用 solana-tx-parser 解析数据
            parsed_data = self.parser.parse_account_data(
                self.JUPITER_PROGRAM_ID,
                data
            )
            
            if not parsed_data:
                return {}
            
            # 提取关键信息
            return {
                "protocol": "jupiter",
                "version": parsed_data.get("version"),
                "tokens": {
                    "token_a": {
                        "mint": parsed_data.get("tokenAMint"),
                        "reserve": parsed_data.get("tokenAReserve"),
                        "decimals": parsed_data.get("tokenADecimals")
                    },
                    "token_b": {
                        "mint": parsed_data.get("tokenBMint"),
                        "reserve": parsed_data.get("tokenBReserve"),
                        "decimals": parsed_data.get("tokenBDecimals")
                    }
                },
                "fees": {
                    "trade_fee_numerator": parsed_data.get("tradeFeeNumerator"),
                    "trade_fee_denominator": parsed_data.get("tradeFeeDenominator"),
                    "protocol_fee_numerator": parsed_data.get("protocolFeeNumerator"),
                    "protocol_fee_denominator": parsed_data.get("protocolFeeDenominator")
                },
                "price": {
                    "current_price": parsed_data.get("currentPrice"),
                    "target_price": parsed_data.get("targetPrice")
                }
            }
            
        except Exception as e:
            logger.error(f"Error parsing Jupiter pool data: {e}")
            return {}
    
    def _parse_orca_pool(self, data: bytes) -> Dict[str, Any]:
        """Parse Orca pool data."""
        try:
            # 使用 solana-tx-parser 解析数据
            parsed_data = self.parser.parse_account_data(
                self.ORCA_PROGRAM_ID,
                data
            )
            
            if not parsed_data:
                return {}
            
            # 提取关键信息
            return {
                "protocol": "orca",
                "version": parsed_data.get("version"),
                "tokens": {
                    "token_a": {
                        "mint": parsed_data.get("tokenAMint"),
                        "reserve": parsed_data.get("tokenAReserve"),
                        "decimals": parsed_data.get("tokenADecimals")
                    },
                    "token_b": {
                        "mint": parsed_data.get("tokenBMint"),
                        "reserve": parsed_data.get("tokenBReserve"),
                        "decimals": parsed_data.get("tokenBDecimals")
                    }
                },
                "fees": {
                    "trade_fee_numerator": parsed_data.get("feeNumerator"),
                    "trade_fee_denominator": parsed_data.get("feeDenominator"),
                    "protocol_fee_numerator": parsed_data.get("protocolFeeNumerator"),
                    "protocol_fee_denominator": parsed_data.get("protocolFeeDenominator")
                },
                "amp_factor": parsed_data.get("ampFactor")
            }
            
        except Exception as e:
            logger.error(f"Error parsing Orca pool data: {e}")
            return {}
    
    def _parse_raydium_pool(self, data: bytes) -> Dict[str, Any]:
        """Parse Raydium pool data."""
        try:
            # 使用 solana-tx-parser 解析数据
            parsed_data = self.parser.parse_account_data(
                self.RAYDIUM_PROGRAM_ID,
                data
            )
            
            if not parsed_data:
                return {}
            
            # 提取关键信息
            return {
                "protocol": "raydium",
                "version": parsed_data.get("version"),
                "tokens": {
                    "token_a": {
                        "mint": parsed_data.get("tokenAMint"),
                        "vault": parsed_data.get("tokenAVault"),
                        "decimals": parsed_data.get("tokenADecimals")
                    },
                    "token_b": {
                        "mint": parsed_data.get("tokenBMint"),
                        "vault": parsed_data.get("tokenBVault"),
                        "decimals": parsed_data.get("tokenBDecimals")
                    }
                },
                "fees": {
                    "trade_fee_numerator": parsed_data.get("tradeFeeNumerator"),
                    "trade_fee_denominator": parsed_data.get("tradeFeeDenominator"),
                    "protocol_fee_numerator": parsed_data.get("protocolFeeNumerator"),
                    "protocol_fee_denominator": parsed_data.get("protocolFeeDenominator")
                },
                "status": {
                    "status": parsed_data.get("status"),
                    "nonce": parsed_data.get("nonce"),
                    "open_time": parsed_data.get("openTime"),
                    "last_updated": parsed_data.get("lastUpdated")
                }
            }
            
        except Exception as e:
            logger.error(f"Error parsing Raydium pool data: {e}")
            return {}
    
    async def parse_swap_instruction(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse swap instruction from transaction.
        
        Args:
            tx_data: Transaction data
            
        Returns:
            Parsed swap data
        """
        try:
            # 使用 solana-tx-parser 解析交易
            parsed_tx = self.parser.parse_transaction(tx_data)
            
            if not parsed_tx:
                return {}
            
            # 查找 swap 指令
            swap_ix = None
            for ix in parsed_tx.instructions:
                if ix.program_id in [self.JUPITER_PROGRAM_ID, self.ORCA_PROGRAM_ID, self.RAYDIUM_PROGRAM_ID]:
                    if "swap" in ix.name.lower():
                        swap_ix = ix
                        break
            
            if not swap_ix:
                return {}
            
            # 解析 swap 数据
            return {
                "protocol": self._get_protocol_name(swap_ix.program_id),
                "instruction": swap_ix.name,
                "input_token": {
                    "mint": swap_ix.accounts.get("inputMint"),
                    "amount": swap_ix.data.get("amountIn")
                },
                "output_token": {
                    "mint": swap_ix.accounts.get("outputMint"),
                    "amount": swap_ix.data.get("amountOut")
                },
                "pool_address": swap_ix.accounts.get("pool"),
                "user": swap_ix.accounts.get("user"),
                "slippage": swap_ix.data.get("slippage"),
                "minimum_out": swap_ix.data.get("minimumAmountOut")
            }
            
        except Exception as e:
            logger.error(f"Error parsing swap instruction: {e}")
            return {}
    
    def _get_protocol_name(self, program_id: str) -> str:
        """Get protocol name from program ID."""
        if program_id == self.JUPITER_PROGRAM_ID:
            return "jupiter"
        elif program_id == self.ORCA_PROGRAM_ID:
            return "orca"
        elif program_id == self.RAYDIUM_PROGRAM_ID:
            return "raydium"
        else:
            return "unknown" 