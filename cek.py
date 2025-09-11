from web3 import Web3

RPC_URL = "https://sepolia-rpc.giwa.io"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

nft_contract = "0x5893B6684057eaBDeCB400526C8410EAFca6d541"
holder = "0x8a1443e9A4556f612FfE820FC92796cbDc945dA1"

# ABI minimal hanya untuk balanceOf
erc721_abi = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    }
]

contract = w3.eth.contract(address=nft_contract, abi=erc721_abi)
balance = contract.functions.balanceOf(holder).call()
print(f"Jumlah NFT yang dimiliki: {balance}")
