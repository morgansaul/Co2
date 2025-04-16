from eth_account import Account
from eth_utils import keccak
import secrets

def find_matching_address(target_hash):
    print(f"Searching for address matching hash: {target_hash}")
    attempts = 0
    while True:
        priv = secrets.token_hex(32)
        acct = Account.from_key(priv)
        addr_hash = int.from_bytes(keccak(hexstr=acct.address[2:]), 'big')
        attempts += 1
        if attempts % 100000 == 0:
            print(f"Attempts: {attempts}")
        if addr_hash == target_hash:
            print(f"Found matching address after {attempts} attempts")
            print(f"Address: {acct.address}")
            print(f"Private key: {priv}")
            return acct

# Get your contract's _maxSupply first
target_hash = 41628068928206708602619973636446437151004459912549460210638788328264308151182
find_matching_address(target_hash)
