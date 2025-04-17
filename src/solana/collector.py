"""
Solana blockchain data collector using solana-tx-parser.
"""
import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Set
from datetime import datetime

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment
from solana.rpc.types import MemcmpOpts
from solders.pubkey import Pubkey
from solders.transaction import Transaction

# 导入 solana-tx-parser
from solana_tx_parser import (
    SolanaParser, 
    ParsedTransaction,
    flattenTransactionResponse,
    parseLogs,
    IDL
)

logger = logging.getLogger(__name__)

class SolanaCollector:
    """
    Collector for Solana blockchain data using solana-tx-parser.
    """
    
    def __init__(self, rpc_url: str, commitment: str = "confirmed"):
        """
        Initialize the Solana collector.
        
        Args:
            rpc_url: URL of the Solana RPC node
            commitment: The commitment level to use
        """
        self.client = AsyncClient(rpc_url, commitment=commitment)
        self.monitored_addresses: Set[str] = set()
        self.monitored_pairs: Set[tuple[str, str]] = set()
        self.monitored_pools: Dict[str, Dict[str, Any]] = {}
        self.callbacks: Dict[str, List[callable]] = {
            'transaction': [],
            'pool': [],
            'market': []
        }
        
        # Initialize transaction parser with known AMM IDLs
        self.parser = SolanaParser([
            {
                "programId": "JUP2jxvXaqu7NQY1GmNF4m1vodw12LVXYxbFL2uJvfo",
                "idl": IDL.JUPITER
            },
            {
                "programId": "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
                "idl": IDL.ORCA
            },
            {
                "programId": "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
                "idl": IDL.RAYDIUM
            }
        ])
        
        logger.info(f"Initialized Solana collector with RPC URL: {rpc_url}")
        
    async def listen_for_transactions(self, address: str, callback: callable):
        """
        Listen for new transactions on the specified address.
        
        Args:
            address: The address to monitor
            callback: Function to call when new transaction is detected
        """
        try:
            # Add address to monitored addresses
            self.monitored_addresses.add(address)
            
            # Register callback
            if callback not in self.callbacks['transaction']:
                self.callbacks['transaction'].append(callback)
            
            # Start monitoring loop
            while True:
                try:
                    # Get recent signatures
                    signatures = await self.client.get_signatures_for_address(
                        Pubkey.from_string(address),
                        limit=10
                    )
                    
                    if signatures:
                        # Process each new transaction
                        for sig_info in signatures:
                            # Get full transaction data with metadata
                            tx_response = await self.client.get_transaction(
                                sig_info.signature,
                                max_supported_transaction_version=0
                            )
                            
                            if tx_response:
                                try:
                                    # Flatten transaction to include CPI calls
                                    flattened_tx = flattenTransactionResponse(tx_response)
                                    
                                    # Parse transaction logs
                                    logs = parseLogs(tx_response.meta.logs if tx_response.meta else [])
                                    
                                    # Parse each instruction
                                    parsed_instructions = []
                                    for ix in flattened_tx:
                                        try:
                                            parsed_ix = self.parser.parse(ix)
                                            if parsed_ix:
                                                # Add corresponding logs
                                                ix_logs = [log for log in logs if log.id == len(parsed_instructions)]
                                                parsed_ix["logs"] = ix_logs
                                                parsed_instructions.append(parsed_ix)
                                        except Exception as e:
                                            logger.warning(f"Failed to parse instruction: {e}")
                                            continue
                                    
                                    # Create enriched transaction data
                                    tx_data = {
                                        "signature": sig_info.signature,
                                        "slot": tx_response.slot,
                                        "blockTime": tx_response.block_time,
                                        "meta": tx_response.meta,
                                        "instructions": parsed_instructions,
                                        "logs": logs
                                    }
                                    
                                    # Call callback with parsed data
                                    try:
                                        callback(tx_data)
                                    except Exception as e:
                                        logger.error(f"Error in transaction callback: {e}")
                                        
                                except Exception as e:
                                    logger.error(f"Error processing transaction {sig_info.signature}: {e}")
                                    continue
                    
                    # Wait before next check
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error monitoring transactions: {e}")
                    await asyncio.sleep(5)  # Wait longer after error
                    
        except Exception as e:
            logger.error(f"Error setting up transaction listener: {e}")
            
    async def _get_amm_snapshot(self, tx: Dict[str, Any], parsed_tx: ParsedTransaction) -> Optional[Dict[str, Any]]:
        """
        Get AMM state snapshot at transaction time.
        
        Args:
            tx: Raw transaction data
            parsed_tx: Parsed transaction data
            
        Returns:
            AMM state snapshot
        """
        try:
            # Get pools involved in transaction
            pool_addresses = set()
            
            # Check program IDs
            for program_id in parsed_tx.program_ids:
                if program_id in self.parser.KNOWN_PROGRAMS:
                    # This is a DEX program, check accounts
                    for account in parsed_tx.accounts:
                        if await self._is_pool_account(account):
                            pool_addresses.add(account)
                            
            if not pool_addresses:
                return None
                
            # Get state for each pool
            amm_states = {}
            for pool_address in pool_addresses:
                # Get pool state before transaction
                before_state = await self._get_pool_state_at_slot(
                    pool_address,
                    tx["slot"] - 1
                )
                
                # Get pool state after transaction  
                after_state = await self._get_pool_state_at_slot(
                    pool_address,
                    tx["slot"]
                )
                
                if before_state and after_state:
                    amm_states[pool_address] = {
                        "before": before_state,
                        "after": after_state,
                        "pool_info": await self._get_pool_info(pool_address)
                    }
                    
            return {
                "pool_addresses": list(pool_addresses),
                "states": amm_states,
                "route_type": self._determine_route_type(amm_states)
            }
            
        except Exception as e:
            logger.error(f"Error getting AMM snapshot: {e}")
            return None
            
    async def _get_pool_state_at_slot(self, pool_address: str, slot: int) -> Optional[Dict[str, Any]]:
        """
        Get pool state at specific slot.
        
        Args:
            pool_address: Pool address
            slot: Block slot
            
        Returns:
            Pool state data
        """
        try:
            # Get account data at slot
            account_data = await self.client.get_account_info(
                Pubkey.from_string(pool_address),
                commitment=Commitment("confirmed"),
                slot=slot
            )
            
            if not account_data:
                return None
                
            # Parse pool data based on program
            program_id = str(account_data.owner)
            if program_id in self.parser.KNOWN_PROGRAMS:
                program_name = self.parser.KNOWN_PROGRAMS[program_id]
                
                if program_name == "Jupiter":
                    return self._parse_jupiter_pool(account_data.data)
                elif program_name == "Orca":
                    return self._parse_orca_pool(account_data.data)
                elif program_name == "Raydium":
                    return self._parse_raydium_pool(account_data.data)
                    
            return None
            
        except Exception as e:
            logger.error(f"Error getting pool state: {e}")
            return None
            
    async def _get_pool_info(self, pool_address: str) -> Dict[str, Any]:
        """Get basic pool information."""
        try:
            # Get current pool data
            account_data = await self.client.get_account_info(
                Pubkey.from_string(pool_address)
            )
            
            if not account_data:
                return {}
                
            # Get program info
            program_id = str(account_data.owner)
            program_name = self.parser.KNOWN_PROGRAMS.get(program_id, "unknown")
            
            return {
                "address": pool_address,
                "program_id": program_id,
                "program_name": program_name
            }
            
        except Exception as e:
            logger.error(f"Error getting pool info: {e}")
            return {}
            
    def _determine_route_type(self, amm_states: Dict[str, Any]) -> str:
        """Determine transaction route type."""
        if not amm_states:
            return "unknown"
            
        pool_count = len(amm_states)
        
        if pool_count == 1:
            return "direct"
        elif pool_count > 1:
            # Check if multi-hop by analyzing token flow
            tokens_seen = set()
            for state in amm_states.values():
                pool_info = state.get("pool_info", {})
                pool_tokens = set(pool_info.get("tokens", []))
                
                if tokens_seen and not tokens_seen.intersection(pool_tokens):
                    return "multi-hop"
                    
                tokens_seen.update(pool_tokens)
                
            return "split"
            
        return "unknown"
        
    async def _is_pool_account(self, account: str) -> bool:
        """Check if an account is a pool account."""
        try:
            # Get account info
            account_data = await self.client.get_account_info(
                Pubkey.from_string(account)
            )
            
            if not account_data:
                return False
                
            # Check if owned by known DEX program
            program_id = str(account_data.owner)
            if program_id not in self.parser.KNOWN_PROGRAMS:
                return False
                
            # Check data size - pools have large data
            if len(account_data.data) < 100:
                return False
                
            # Check program-specific patterns
            program_name = self.parser.KNOWN_PROGRAMS[program_id]
            
            if program_name == "Jupiter":
                return self._is_jupiter_pool(account_data.data)
            elif program_name == "Orca":
                return self._is_orca_pool(account_data.data)
            elif program_name == "Raydium":
                return self._is_raydium_pool(account_data.data)
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking pool account: {e}")
            return False
            
    def _is_jupiter_pool(self, data: bytes) -> bool:
        """Check Jupiter pool data pattern."""
        try:
            # Implement Jupiter-specific checks
            return False
        except Exception:
            return False
            
    def _is_orca_pool(self, data: bytes) -> bool:
        """Check Orca pool data pattern."""
        try:
            # Implement Orca-specific checks
            return False
        except Exception:
            return False
            
    def _is_raydium_pool(self, data: bytes) -> bool:
        """Check Raydium pool data pattern."""
        try:
            # Implement Raydium-specific checks
            return False
        except Exception:
            return False
            
    def _parse_jupiter_pool(self, data: bytes) -> Dict[str, Any]:
        """Parse Jupiter pool data."""
        try:
            # Implement Jupiter pool parsing
            return {}
        except Exception:
            return {}
            
    def _parse_orca_pool(self, data: bytes) -> Dict[str, Any]:
        """Parse Orca pool data."""
        try:
            # Implement Orca pool parsing
            return {}
        except Exception:
            return {}
            
    def _parse_raydium_pool(self, data: bytes) -> Dict[str, Any]:
        """Parse Raydium pool data."""
        try:
            # Implement Raydium pool parsing
            return {}
        except Exception:
            return {}
            
    async def close(self):
        """Close all connections."""
        try:
            await self.client.close()
        except Exception as e:
            logger.error(f"Error closing connections: {e}")