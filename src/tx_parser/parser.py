"""
Solana transaction parser core implementation.
"""
import json
import base64
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TokenTransfer:
    token: str
    from_address: Optional[str]
    to_address: Optional[str]
    amount: float
    decimals: int

@dataclass
class ParsedInstruction:
    program_id: str
    program_name: str
    name: str
    data: Dict[str, Any]
    accounts: List[Dict[str, Any]]

@dataclass
class ParsedTransaction:
    signature: str
    slot: int
    block_time: int
    success: bool
    fee: int
    instructions: List[ParsedInstruction]
    token_transfers: List[TokenTransfer]
    program_ids: Set[str]
    accounts: Set[str]

class TransactionParser:
    """
    Core transaction parser using solana-tx-parser approach.
    """
    
    # Known program IDs
    KNOWN_PROGRAMS = {
        "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB": "Jupiter",
        "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca",
        "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium"
    }
    
    def __init__(self):
        """Initialize parser with program IDLs."""
        # Load program IDLs
        self.program_idls = {}
        for program_id in self.KNOWN_PROGRAMS:
            self._load_program_idl(program_id)
            
    def _load_program_idl(self, program_id: str):
        """Load IDL for a program."""
        try:
            idl_path = f"idl/{program_id}.json"
            with open(idl_path) as f:
                self.program_idls[program_id] = json.load(f)
        except Exception:
            pass
            
    def parse_transaction(self, tx_data: Dict[str, Any]) -> Optional[ParsedTransaction]:
        """
        Parse a transaction.
        
        Args:
            tx_data: Raw transaction data
            
        Returns:
            Parsed transaction data
        """
        try:
            # Extract basic info
            signature = tx_data.get("transaction", {}).get("signatures", [])[0]
            slot = tx_data.get("slot")
            block_time = tx_data.get("blockTime")
            success = not tx_data.get("meta", {}).get("err")
            fee = tx_data.get("meta", {}).get("fee", 0)
            
            # Parse instructions
            instructions = []
            program_ids = set()
            accounts = set()
            
            if "message" in tx_data.get("transaction", {}):
                message = tx_data["transaction"]["message"]
                
                # Get account keys
                account_keys = []
                for key in message.get("accountKeys", []):
                    if isinstance(key, str):
                        account_keys.append(key)
                        accounts.add(key)
                    elif isinstance(key, dict) and "pubkey" in key:
                        account_keys.append(key["pubkey"])
                        accounts.add(key["pubkey"])
                        
                # Parse each instruction
                for ix in message.get("instructions", []):
                    parsed_ix = self._parse_instruction(ix, account_keys)
                    if parsed_ix:
                        instructions.append(parsed_ix)
                        program_ids.add(parsed_ix.program_id)
                        
            # Parse token transfers
            token_transfers = []
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
                            transfer = TokenTransfer(
                                token=mint,
                                from_address=account_keys[idx] if post_amount < pre_amount else None,
                                to_address=account_keys[idx] if post_amount > pre_amount else None,
                                amount=abs(post_amount - pre_amount),
                                decimals=post_bal.get("uiTokenAmount", {}).get("decimals", 0)
                            )
                            token_transfers.append(transfer)
                            
            return ParsedTransaction(
                signature=signature,
                slot=slot,
                block_time=block_time,
                success=success,
                fee=fee,
                instructions=instructions,
                token_transfers=token_transfers,
                program_ids=program_ids,
                accounts=accounts
            )
            
        except Exception as e:
            print(f"Error parsing transaction: {e}")
            return None
            
    def _parse_instruction(self, ix: Dict[str, Any], account_keys: List[str]) -> Optional[ParsedInstruction]:
        """
        Parse a single instruction.
        
        Args:
            ix: Instruction data
            account_keys: Account public keys
            
        Returns:
            Parsed instruction
        """
        try:
            program_id_index = ix.get("programIdIndex")
            if program_id_index is None or program_id_index >= len(account_keys):
                return None
                
            program_id = account_keys[program_id_index]
            program_name = self.KNOWN_PROGRAMS.get(program_id, "unknown")
            
            # Get accounts
            accounts = []
            for idx in ix.get("accounts", []):
                if idx < len(account_keys):
                    accounts.append({
                        "pubkey": account_keys[idx],
                        "is_signer": idx < ix.get("header", {}).get("numRequiredSignatures", 0),
                        "is_writable": idx < ix.get("header", {}).get("numRequiredWritableSignings", 0)
                    })
                    
            # Parse instruction data
            data = ix.get("data", "")
            if data and program_id in self.program_idls:
                parsed_data = self._parse_program_data(program_id, data)
            else:
                parsed_data = {"raw": data}
                
            return ParsedInstruction(
                program_id=program_id,
                program_name=program_name,
                name=parsed_data.get("name", "unknown"),
                data=parsed_data,
                accounts=accounts
            )
            
        except Exception as e:
            print(f"Error parsing instruction: {e}")
            return None
            
    def _parse_program_data(self, program_id: str, data: str) -> Dict[str, Any]:
        """
        Parse program-specific instruction data.
        
        Args:
            program_id: Program ID
            data: Base58 encoded instruction data
            
        Returns:
            Parsed instruction data
        """
        try:
            # Decode base58 data
            decoded = base64.b64decode(data)
            
            # Get program IDL
            idl = self.program_idls.get(program_id)
            if not idl:
                return {"raw": data}
                
            # Find instruction definition
            discriminator = decoded[0]
            ix_def = next(
                (ix for ix in idl["instructions"] if ix.get("discriminator") == discriminator),
                None
            )
            
            if not ix_def:
                return {"raw": data}
                
            # Parse instruction data according to IDL
            parsed = {
                "name": ix_def["name"],
                "discriminator": discriminator,
                "args": {}
            }
            
            # Parse arguments
            offset = 1
            for arg in ix_def.get("args", []):
                arg_data, offset = self._parse_idl_type(
                    decoded,
                    offset,
                    arg["type"]
                )
                parsed["args"][arg["name"]] = arg_data
                
            return parsed
            
        except Exception as e:
            print(f"Error parsing program data: {e}")
            return {"raw": data}
            
    def _parse_idl_type(self, data: bytes, offset: int, type_info: Dict[str, Any]) -> tuple:
        """
        Parse IDL type from binary data.
        
        Args:
            data: Binary data
            offset: Current offset
            type_info: Type information from IDL
            
        Returns:
            Tuple of (parsed value, new offset)
        """
        try:
            type_name = type_info["type"]
            
            if type_name == "u8":
                return data[offset], offset + 1
            elif type_name == "u16":
                return int.from_bytes(data[offset:offset+2], "little"), offset + 2
            elif type_name == "u32":
                return int.from_bytes(data[offset:offset+4], "little"), offset + 4
            elif type_name == "u64":
                return int.from_bytes(data[offset:offset+8], "little"), offset + 8
            elif type_name == "i8":
                return int.from_bytes(data[offset:offset+1], "little", signed=True), offset + 1
            elif type_name == "i16":
                return int.from_bytes(data[offset:offset+2], "little", signed=True), offset + 2
            elif type_name == "i32":
                return int.from_bytes(data[offset:offset+4], "little", signed=True), offset + 4
            elif type_name == "i64":
                return int.from_bytes(data[offset:offset+8], "little", signed=True), offset + 8
            elif type_name == "bool":
                return bool(data[offset]), offset + 1
            elif type_name == "string":
                length = int.from_bytes(data[offset:offset+4], "little")
                string_data = data[offset+4:offset+4+length].decode()
                return string_data, offset + 4 + length
            elif type_name == "publicKey":
                return data[offset:offset+32].hex(), offset + 32
            elif type_name == "array":
                length = type_info.get("size", int.from_bytes(data[offset:offset+4], "little"))
                offset += 0 if "size" in type_info else 4
                array = []
                for _ in range(length):
                    item, offset = self._parse_idl_type(
                        data,
                        offset,
                        type_info["inner"]
                    )
                    array.append(item)
                return array, offset
            else:
                return None, offset
                
        except Exception as e:
            print(f"Error parsing IDL type: {e}")
            return None, offset 