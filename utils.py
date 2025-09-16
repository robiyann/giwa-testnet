from web3 import Web3
from hexbytes import HexBytes
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

class MultiAccountFromPK:
    def __init__(self, rpc_url, giwa_rpc_url=None):
        self.main_rpc = rpc_url
        self.giwa_rpc = giwa_rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url)) # Default to main RPC

    def set_network(self, network_name: str):
        """Switch the Web3 provider to the specified network."""
        if network_name.lower() == 'giwa':
            if not self.giwa_rpc:
                print("❌ GIWA RPC URL not configured in config.json")
                return False
            self.w3 = Web3(Web3.HTTPProvider(self.giwa_rpc))
            print(f"🔄 Switched network to GIWA")
        elif network_name.lower() == 'sepolia':
            self.w3 = Web3(Web3.HTTPProvider(self.main_rpc))
            print(f"🔄 Switched network to Sepolia")
        else:
            print(f"❌ Unknown network: {network_name}")
            return False
        
        # Verify connection
        try:
            chain_id = self.w3.eth.chain_id
            print(f"✅ Connected to network with Chain ID: {chain_id}")
            return True
        except Exception as e:
            print(f"❌ Failed to connect to {network_name.upper()} network: {e}")
            return False

    # =========================
    # Universal Web3 Compatibility
    # =========================
    
    def get_raw_transaction_data(self, signed_txn):
        """
        Universal helper untuk mengakses raw transaction data.
        Kompatibel dengan semua versi web3.py (v5, v6, v7+).
        """
        # Web3.py v7+ menggunakan raw_transaction (snake_case)
        if hasattr(signed_txn, 'raw_transaction'):
            return signed_txn.raw_transaction
        
        # Web3.py v6 dan sebelumnya menggunakan rawTransaction (camelCase)  
        elif hasattr(signed_txn, 'rawTransaction'):
            return signed_txn.rawTransaction
        
        # Fallback jika tidak ada keduanya
        else:
            # Coba akses sebagai dict
            if isinstance(signed_txn, dict):
                return signed_txn.get('raw_transaction') or signed_txn.get('rawTransaction')
            
            raise AttributeError(
                "Cannot find raw transaction data. "
                "Expected 'raw_transaction' or 'rawTransaction' attribute."
            )

    def send_raw_transaction_universal(self, signed_txn):
        """
        Universal method untuk mengirim raw transaction dengan kompatibilitas lengkap.
        """
        try:
            raw_data = self.get_raw_transaction_data(signed_txn)
            return self.w3.eth.send_raw_transaction(raw_data)
        except Exception as e:
            raise Exception(f"Failed to send raw transaction: {str(e)}")

    def get_web3_version_info(self):
        """
        Deteksi versi web3.py yang sedang digunakan untuk debugging.
        """
        import web3
        version = web3.__version__
        
        # Parse major version
        major_version = int(version.split('.'))
        
        print(f"🔧 Web3.py version: {version}")
        
        if major_version >= 7:
            print("✅ Using snake_case methods (raw_transaction)")
        elif major_version >= 6:
            print("✅ Using mixed case methods (rawTransaction)")  
        else:
            print("⚠️ Using legacy version")
        
        return {
            'version': version,
            'major': major_version,
            'uses_snake_case': major_version >= 7
        }

    # =========================
    # GIWA Bridge Integration
    # =========================
    
    def get_giwa_bridge_contracts(self):
        """
        Contract addresses untuk GIWA bridge dari Sepolia ke GIWA Sepolia.
        """
        return {
            'optimism_portal': Web3.to_checksum_address('0x956962C34687A954e611A83619ABaA37Ce6bC78A'),
            'l1_standard_bridge': Web3.to_checksum_address('0x77b2ffc0F57598cAe1DB76cb398059cF5d10A7E7'),
            'dispute_game_factory': Web3.to_checksum_address('0x37347caB2afaa49B776372279143D71ad1f354F6'),
            'system_config': Web3.to_checksum_address('0x8352825bA56C32d816Dd906Ad4A392B5BC9eC984')
        }

    def build_deposit_transaction_data(self, amount_wei, recipient_address):
        """
        Build deposit transaction data untuk bridge ke GIWA.
        Menggunakan depositTransaction function di OptimismPortal.
        """
        # Function signature: depositTransaction(address,uint256,uint64,bool,bytes)
        function_selector = "0xe9e05c42"
        
        # Encode parameters:
        # address to = recipient_address
        # uint256 value = amount_wei  
        # uint64 gasLimit = 100000 (default L2 gas limit)
        # bool isCreation = false
        # bytes data = empty (0x)
        
        # Manual ABI encoding
        to_param = recipient_address[2:].zfill(64)  # address padded to 32 bytes
        value_param = hex(amount_wei)[2:].zfill(64)  # uint256 value
        gas_limit_param = hex(100000)[2:].zfill(64)  # uint64 gasLimit 
        is_creation_param = "00" * 32  # bool false
        data_offset_param = hex(5 * 32)[2:].zfill(64)  # offset to data (5*32 bytes)
        data_length_param = "00" * 32  # data length = 0
        
        encoded_params = (
            to_param + value_param + gas_limit_param + 
            is_creation_param + data_offset_param + data_length_param
        )
        
        return function_selector + encoded_params

    def bridge_sepolia_to_giwa(self, accounts, amount_eth="0.001", gas_limit=150000, max_workers=5):
        """
        Bridge ETH dari Sepolia ke GIWA untuk multiple accounts.
        
        Args:
            accounts: List of account dicts
            amount_eth: Amount ETH to bridge (string)
            gas_limit: Gas limit untuk transaksi
            max_workers: Max concurrent workers
        """
        contracts = self.get_giwa_bridge_contracts()
        portal_address = contracts['optimism_portal']
        amount_wei = self.w3.to_wei(amount_eth, 'ether')
        
        print(f"🌉 Starting bridge {amount_eth} ETH from Sepolia to GIWA for {len(accounts)} accounts...")
        print(f"📍 OptimismPortal: {portal_address}")
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            for account in accounts:
                # Build deposit transaction data
                deposit_data = self.build_deposit_transaction_data(
                    amount_wei, 
                    account['address']
                )
                
                future = executor.submit(
                    self._send_bridge_transaction,
                    account['private_key'],
                    account['address'], 
                    portal_address,
                    deposit_data,
                    amount_wei,  # value to send
                    gas_limit,
                    account['line_number']
                )
                futures.append(future)
                time.sleep(random.uniform(0.3, 1.0))  # Spread requests
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    if result.get('status') == 'success':
                        print(f"✅ Bridge: {result['address']} - TX: {result['tx_hash'][:10]}...")
                    else:
                        print(f"📤 Sent: {result['address']} - TX: {result['tx_hash'][:10]}...")
                except Exception as e:
                    print(f"❌ Bridge Error: {e}")
                    results.append({"error": str(e)})
        
        return results

    def _send_bridge_transaction(self, private_key, from_address, to_address, data, value_wei, gas_limit, line_number):
        """
        Send single bridge transaction dengan value (ETH yang di-bridge).
        """
        try:
            nonce = self.w3.eth.get_transaction_count(from_address)
            gas_price = self.w3.eth.gas_price
            
            tx = {
                'from': from_address,
                'nonce': nonce,
                'gasPrice': gas_price,
                'gas': gas_limit,
                'to': Web3.to_checksum_address(to_address),
                'value': int(value_wei),  # ETH amount to bridge
                'data': data,
                'chainId': self.w3.eth.chain_id,
            }
            
            signed_txn = self.w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = self.send_raw_transaction_universal(signed_txn)
            
            return {
                'address': from_address,
                'tx_hash': tx_hash.hex(),
                'line_number': line_number,
                'status': 'sent'
            }
            
        except Exception as e:
            error_message = str(e)
            
            # Check for insufficient funds error
            if 'insufficient funds' in error_message.lower():
                raise Exception(f"wallet ({from_address}): Akun kamu gaada sepolia nya, isi dulu")
            
            # Check for replacement transaction underpriced
            elif 'replacement transaction underpriced' in error_message.lower():
                raise Exception(f"Line {line_number} ({from_address}): Ada transaksi pending, tunggu sebentar")
            
            # Other errors
            else:
                raise Exception(f"Line {line_number} ({from_address}): {error_message}")


    def check_bridge_balances(self, accounts, giwa_rpc="https://sepolia-rpc.giwa.io"):
        """
        Check balance di kedua network (Sepolia dan GIWA).
        """
        # Pastikan self.w3 connect ke Ethereum Sepolia
        current_chain_id = self.w3.eth.chain_id
        print(f"🔍 Current RPC Chain ID: {current_chain_id}")
        
        if current_chain_id == 91342:  # GIWA chain ID
            print("⚠️  WARNING: Bot is connected to GIWA, not Ethereum Sepolia!")
            print("💡 Please update config.json rpc_url to Ethereum Sepolia RPC")
            return
        
        # Setup GIWA client 
        giwa_w3 = Web3(Web3.HTTPProvider(giwa_rpc))
        giwa_chain_id = giwa_w3.eth.chain_id
        print(f"🔍 GIWA RPC Chain ID: {giwa_chain_id}")
        
        print("\n💰 Bridge Balance Check:")
        print("=" * 60)
        
        for account in accounts:  # Show all accounts
            try:
                addr = account['address']
                
                # Ethereum Sepolia balance (Chain ID: 11155111)
                sepolia_bal_wei = self.w3.eth.get_balance(addr)
                sepolia_bal_eth = self.w3.from_wei(sepolia_bal_wei, "ether")
                
                # GIWA Sepolia balance (Chain ID: 91342)
                giwa_bal_wei = giwa_w3.eth.get_balance(addr)
                giwa_bal_eth = giwa_w3.from_wei(giwa_bal_wei, "ether")
                
                print(f"🔹 {addr}")
                print(f"   Ethereum Sepolia (11155111): {sepolia_bal_eth:.6f} ETH")
                print(f"   GIWA Sepolia (91342):        {giwa_bal_eth:.6f} ETH")
                print()
                
            except Exception as e:
                print(f"❌ Error checking {addr}: {e}")

    # =========================
    # Bytecode & Encoding utils
    # =========================
    
    def get_owlto_hex_data(self):
        """Hex data untuk deploy smart contract Owlto (fitur #1)."""
        return (
            "0x60806040527389a512a24e9d63e98e41f681bf77f27a7ef89eb76000806101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff16021790555060008060009054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff163460405161009f90610185565b60006040518083038185875af1925050503d80600081146100dc576040519150601f19603f3d011682016040523d82523d6000602084013e6100e1565b606091505b5050905080610125576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040161011c9061019a565b60405180910390fd5b506101d6565b60006101386007836101c5565b91507f4661696c757265000000000000000000000000000000000000000000000000006000830152602082019050919050565b60006101786000836101ba565b9150600082019050919050565b60006101908261016b565b9150819050919050565b600060208201905081810360008301526101b38161012b565b9050919050565b600081905092915050565b600082825260208201905092915050565b603f806101e46000396000f3fe6080604052600080fdfea264697066735822122095fed2c557b62b9f55f8b3822b0bdc6d15fd93abb95f37503d3f788da6cbb30064736f6c63430008000033"
        )

    def get_owlto_erc20_bytecode(self):
        """ERC20 contract bytecode tanpa constructor params (fitur #2)."""
        return (
            "0x608060405260646000556040518060400160405280600781526020017f64656661756c740000000000000000000000000000000000000000000000000081525060039080519060200190620000569291906200027e565b506040518060400160405280600781526020017f64656661756c740000000000000000000000000000000000000000000000000081525060049080519060200190620000a49291906200027e565b506012600560006101000a81548160ff021916908360ff160217905550731308196f819a4b07689ec96b7583373d11bb9f36600560016101000a81548173ffffffffffffffffffffffffffffffffffffffff021916908373ffffffffffffffffffffffffffffffffffffffff160217905550604051620016763803806200167683398181016040528101906200013b9190620004cb565b8160039080519060200190620001539291906200027e565b5080600490805190602001906200016c9291906200027e565b50600560009054906101000a900460ff16600a6200018b9190620006ea565b6000546200019a91906200073b565b6000819055506000600560019054906101000a900473ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff1634604051620001ea90620007d1565b60006040518083038185875af1925050503d806000811462000229576040519150601f19603f3d011682016040523d82523d6000602084013e6200022e565b606091505b505090508062000275576040517f08c379a00000000000000000000000000000000000000000000000000000000081526004016200026c9062000849565b60405180910390fd5b505050620008d0565b8280546200028c906200089a565b90600052602060002090601f016020900481019282620002b05760008555620002fc565b82601f10620002cb57805160ff1916838001178555620002fc565b82800160010185558215620002fc579182015b82811115620002fb578251825591602001919060010190620002de565b5b5090506200030b91906200030f565b5090565b5b808211156200032a57600081600090555060010162000310565b5090565b6000604051905090565b600080fd5b600080fd5b600080fd5b600080fd5b6000601f19601f8301169050919050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052604160045260246000fd5b62000397826200034c565b810181811067ffffffffffffffff82111715620003b957620003b86200035d565b5b80604052505050565b6000620003ce6200032e565b9050620003dc82826200038c565b919050565b600067ffffffffffffffff821115620003ff57620003fe6200035d565b5b6200040a826200034c565b9050602081019050919050565b60005b83811015620004375780820151818401526020810190506200041a565b8381111562000447576000848401525b50505050565b6000620004646200045e84620003e1565b620003c2565b90508281526020810184848401111562000483576200048262000347565b5b6200049084828562000417565b509392505050565b600082601f830112620004b057620004af62000342565b5b8151620004c28482602086016200044d565b91505092915050565b60008060408385031215620004e557620004e462000338565b5b600083015167ffffffffffffffff8111156200050657620005056200033d565b5b620005148582860162000498565b925050602083015167ffffffffffffffff8111156200053857620005376200033d565b5b620005468582860162000498565b9150509250929050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052601160045260246000fd5b60008160011c9050919050565b6000808291508390505b6001851115620005de57808604811115620005b657620005b562000550565b5b6001851615620005c65780820291505b8081029050620005d6856200057f565b945062000596565b94509492505050565b600082620005f95760019050620006cc565b81620006095760009050620006cc565b81600181146200062257600281146200062d5762000663565b6001915050620006cc565b60ff84111562000642576200064162000550565b5b8360020a9150848211156200065c576200065b62000550565b5b50620006cc565b5060208310610133831016604e8410600b84101617156200069d5782820a90508381111562000697576200069662000550565b5b620006cc565b620006ac84848460016200058c565b92509050818404811115620006c657620006c562000550565b5b81810290505b9392505050565b6000819050919050565b600060ff82169050919050565b6000620006f782620006d3565b91506200070483620006dd565b9250620007337fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff8484620005e7565b905092915050565b60006200074882620006d3565b91506200075583620006d3565b9250817fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff048311821515161562000791576200079062000550565b5b828202905092915050565b600081905092915050565b50565b6000620007b96000836200079c565b9150620007c682620007a7565b600082019050919050565b6000620007de82620007aa565b9150819050919050565b600082825260208201905092915050565b7f4661696c75726500000000000000000000000000000000000000000000000000600082015250565b600062000831600783620007e8565b91506200083e82620007f9565b602082019050919050565b60006020820190508181036000830152620008648162000822565b9050919050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052602260045260246000fd5b60006002820490506001821680620008b357607f821691505b60208210811415620008ca57620008c96200086b565b5b50919050565b610d9680620008e06000396000f3fe608060405234801561001057600080fd5b50600436106100a95760003560e01c806342966c681161007157806342966c681461016857806370a082311461018457806395d89b41146101b4578063a0712d68146101d2578063a9059cbb146101ee578063dd62ed3e1461021e576100a9565b806306fdde03146100ae578063095ea7b3146100cc57806318160ddd146100fc57806323b872dd1461011a578063313ce5671461014a575b600080fd5b6100b661024e565b6040516100c391906109c7565b60405180910390f35b6100e660048036038101906100e19190610a82565b6102dc565b6040516100f39190610add565b60405180910390f35b6101046103ce565b6040516101119190610b07565b60405180910390f35b610134600480360381019061012f9190610b22565b6103d4565b6040516101419190610add565b60405180910390f35b610152610585565b60405161015f9190610b91565b60405180910390f35b610182600480360381019061017d9190610bac565b610598565b005b61019e60048036038101906101999190610bd9565b61066f565b6040516101ab9190610b07565b60405180910390f35b6101bc610687565b6040516101c991906109c7565b60405180910390f35b6101ec60048036038101906101e79190610bac565b610715565b005b61020860048036038101906102039190610a82565b6107ec565b6040516102159190610add565b60405180910390f35b61023860048036038101906102339190610c06565b610909565b6040516102459190610b07565b60405180910390f35b6003805461025b90610c75565b80601f016020809104026020016040519081016040528092919081815260200182805461028790610c75565b80156102d45780601f106102a9576101008083540402835291602001916102d4565b820191906000526020600020905b8154815290600101906020018083116102b757829003601f168201915b505050505081565b600081600260003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020819055508273ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff167f8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925846040516103bc9190610b07565b60405180910390a36001905092915050565b60005481565b600081600260008673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008282546104629190610cd6565b9250508190555081600160008673ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008282546104b89190610cd6565b9250508190555081600160008573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600082825461050e9190610d0a565b925050819055508273ffffffffffffffffffffffffffffffffffffffff168473ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef846040516105729190610b07565b60405180910390a3600190509392505050565b600560009054906101000a900460ff1681565b80600160003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008282546105e79190610cd6565b92505081905550806000808282546105ff9190610cd6565b92505081905550600073ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040516106649190610b07565b60405180910390a350565b60016020528060005260406000206000915090505481565b6004805461069490610c75565b80601f01602080910402602001604051908101604052809291908181526020018280546106c090610c75565b801561070d5780601f106106e25761010080835404028352916020019161070d565b820191906000526020600020905b8154815290600101906020018083116106f057829003601f168201915b505050505081565b80600160003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008282546107649190610d0a565b925050819055508060008082825461077c9190610d0a565b925050819055503373ffffffffffffffffffffffffffffffffffffffff16600073ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef836040516107e19190610b07565b60405180910390a350565b600081600160003373ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff168152602001908152602001600020600082825461083d9190610cd6565b9250508190555081600160008573ffffffffffffffffffffffffffffffffffffffff1673ffffffffffffffffffffffffffffffffffffffff16815260200190815260200160002060008282546108939190610d0a565b925050819055508273ffffffffffffffffffffffffffffffffffffffff163373ffffffffffffffffffffffffffffffffffffffff167fddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef846040516108f79190610b07565b60405180910390a36001905092915050565b6002602052816000526040600020602052806000526040600020600091509150505481565b600081519050919050565b600082825260208201905092915050565b60005b8381101561096857808201518184015260208101905061094d565b83811115610977576000848401525b50505050565b6000601f19601f8301169050919050565b60006109998261092e565b6109a38185610939565b93506109b381856020860161094a565b6109bc8161097d565b840191505092915050565b600060208201905081810360008301526109e1818461098e565b905092915050565b600080fd5b600073ffffffffffffffffffffffffffffffffffffffff82169050919050565b6000610a19826109ee565b9050919050565b610a2981610a0e565b8114610a3457600080fd5b50565b600081359050610a4681610a20565b92915050565b6000819050919050565b610a5f81610a4c565b8114610a6a57600080fd5b50565b600081359050610a7c81610a56565b92915050565b60008060408385031215610a9957610a986109e9565b5b6000610aa785828601610a37565b9250506020610ab885828601610a6d565b9150509250929050565b60008115159050919050565b610ad781610ac2565b82525050565b6000602082019050610af26000830184610ace565b92915050565b610b0181610a4c565b82525050565b6000602082019050610b1c6000830184610af8565b92915050565b600080600060608486031215610b3b57610b3a6109e9565b5b6000610b4986828701610a37565b9350506020610b5a86828701610a37565b9250506040610b6b86828701610a6d565b9150509250925092565b600060ff82169050919050565b610b8b81610b75565b82525050565b6000602082019050610ba66000830184610b82565b92915050565b600060208284031215610bc257610bc16109e9565b5b6000610bd084828501610a6d565b91505092915050565b600060208284031215610bef57610bee6109e9565b5b6000610bfd84828501610a37565b91505092915050565b60008060408385031215610c1d57610c1c6109e9565b5b6000610c2b85828601610a37565b9250506020610c3c85828601610a37565b9150509250929050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052602260045260246000fd5b60006002820490506001821680610c8d57607f821691505b60208210811415610ca157610ca0610c46565b5b50919050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052601160045260246000fd5b6000610ce182610a4c565b9150610cec83610a4c565b925082821015610cff57610cfe610ca7565b5b828203905092915050565b6000610d1582610a4c565b9150610d2083610a4c565b9250827fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff03821115610d5557610d54610ca7565b5b82820190509291505056fea26469706673582212204763c8f8b98ce59ecaf1c70a3dfb491519bf7e6d2e180ab80c0f37e6b8f6845664736f6c634300080a0033"
        )

    def encode_constructor_parameters(self, name: str, symbol: str) -> str | None:
        """ABI-encode constructor parameters untuk ERC20 (string,string)."""
        try:
            from eth_abi import encode
            encoded = encode(['string', 'string'], [name, symbol])
            return encoded.hex()
        except ImportError:
            # Manual fallback (cukup untuk string,string)
            try:
                name_bytes = name.encode('utf-8')
                symbol_bytes = symbol.encode('utf-8')
                
                def pad32(b: bytes) -> bytes:
                    if len(b) % 32 == 0:
                        return b
                    return b + b'\x00' * (32 - (len(b) % 32))
                
                # dua offset statis (2 * 32 bytes)
                offset1 = 64
                # 32(len) + ceil(len/32)*32
                len1 = 32 + len(pad32(name_bytes))
                offset2 = 64 + len1
                
                out = bytearray()
                out += offset1.to_bytes(32, 'big')
                out += offset2.to_bytes(32, 'big')
                out += len(name_bytes).to_bytes(32, 'big')
                out += pad32(name_bytes)
                out += len(symbol_bytes).to_bytes(32, 'big')
                out += pad32(symbol_bytes)
                
                return out.hex()
            except Exception as e:
                print(f"❌ Error in manual encoding: {e}")
                return None
        except Exception as e:
            print(f"❌ Error encoding constructor parameters: {e}")
            return None

    def get_owlto_erc20_hex_data(self, name="cuandrop", symbol="cndrp") -> str:
        """Gabungkan bytecode + encoded params (tanpa '0x' kedua)."""
        bytecode = self.get_owlto_erc20_bytecode()
        params = self.encode_constructor_parameters(name, symbol)
        if params:
            return bytecode + (params if not params.startswith("0x") else params[2:])
        
        print("⚠️ Using default constructor parameters")
        return (
            bytecode
            + "0000000000000000000000000000000000000000000000000000000000000040"
            "0000000000000000000000000000000000000000000000000000000000000080"
            "0000000000000000000000000000000000000000000000000000000000000008"
            "6375616e64726f70000000000000000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000000000000005"
            "636e647270000000000000000000000000000000000000000000000000000000"
        )

    # === GMONChain ===
    
    def get_gmonchain_call_params(self):
        """
        Param panggilan untuk deploy GMONChain:
        - to: factory address
        - data: function selector (tanpa args)
        - value_wei: 0.000035 ETH (sesuai trace)
        """
        factory = Web3.to_checksum_address("0xa3d9fbd0edb10327ecb73d2c72622e505df468a2")
        selector = "0x775c300c"  # function selector (no args)
        value_wei = 35_000_000_000_000  # 0.000035 ETH
        return factory, selector, value_wei

    def deploy_gmonchain(self, accounts, gas_limit=300_000, max_workers=5):
        """
        Kirim TX ke factory GMONChain (batch, non-blocking seperti fitur #2).
        """
        to, data, value_wei = self.get_gmonchain_call_params()
        print(f"🧩 Starting GMONChain deployment for {len(accounts)} accounts...")
        return self.send_call_batch(accounts, to, data, value_wei, gas_limit, max_workers)

    # === NFT Features ===
    
    def mint_omnihub_nft(self, accounts, gas_limit=2_000_000, max_workers=5):
        """
        Mint Omnihub NFT:
        - Hardcode target contract & value
        - Skip akun yang sudah memiliki NFT (balanceOf > 0)
        """
        # === hardcode target dan value ===
        target_contract = Web3.to_checksum_address("0x5893B6684057eaBDeCB400526C8410EAFca6d541")
        value_wei = Web3.to_wei(0.001, "ether")
        data = (
            "0xa25ffea8"
            "0000000000000000000000000000000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000000000000001"
            "0000000000000000000000000000000000000000000000000000000000000000"
            "0000000000000000000000000000000000000000000000000000000000000080"
            "0000000000000000000000000000000000000000000000000000000000000000"
        )

        # cek NFT yang sama dengan target contract
        nft = self.w3.eth.contract(
            address=target_contract,
            abi=[
                {
                    "inputs": [{"internalType": "address", "name": "owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function",
                }
            ],
        )

        print("\n🔎 Memeriksa kepemilikan Omnihub NFT...")
        eligible, skipped = [], []
        
        for acc in accounts:
            try:
                bal = nft.functions.balanceOf(acc["address"]).call()
                if int(bal) == 0:
                    eligible.append(acc)
                else:
                    print(f" ⏭️ Skip {acc['address']} — sudah punya {bal} NFT")
                    skipped.append(acc)
            except Exception as e:
                print(f" ⚠️ Gagal cek {acc['address']}: {e} → tetap diproses")
                eligible.append(acc)

        if not eligible:
            print("✅ Semua akun sudah punya NFT — tidak ada transaksi dikirim.")
            return {"processed": 0, "skipped": len(skipped), "results": []}

        print(f"🚀 Mint Omnihub NFT ke {len(eligible)} akun")
        results = self.send_call_batch(
            accounts=eligible,
            to=target_contract,
            data=data,
            value_wei=value_wei,
            gas_limit=gas_limit,
            max_workers=max_workers,
        )

        return {
            "processed": len(eligible),
            "skipped": len(skipped),
            "results": results,
        }

    # =============
    # File & wallet
    # =============
    
    def load_private_keys(self, filename):
        """Load private keys dari akun.txt."""
        accounts = []
        with open(filename, 'r') as f:
            for line_num, line in enumerate(f, 1):
                pk = line.strip()
                if not pk:
                    continue
                try:
                    if not pk.startswith('0x'):
                        pk = '0x' + pk
                    acct = self.w3.eth.account.from_key(pk)
                    accounts.append(
                        {"private_key": pk, "address": acct.address, "line_number": line_num}
                    )
                except Exception as e:
                    print(f"❌ Invalid PK on line {line_num}: {e}")
        return accounts

    # ===========
    # Deploy API
    # ===========
    
    def deploy_owlto_smart_contract(self, accounts, gas_limit=2_000_000, max_workers=5):
        """Fitur #1: deploy Owlto, menunggu receipt (cek sukses on-chain)."""
        hex_data = self.get_owlto_hex_data()
        print(f"🦉 Starting Owlto Smart Contract deployment for {len(accounts)} accounts...")
        return self.send_transaction_batch(
            accounts, hex_data, gas_limit, max_workers, wait_for_receipt=True
        )

    def deploy_owlto_erc20_contract(
        self, accounts, name="cuandrop", symbol="cndrp", gas_limit=2_000_000, max_workers=5, wait_for_receipt=False
    ):
        """
        Fitur #2: deploy ERC20 Owlto.
        Default TIDAK menunggu receipt (agar 'sukses' di terminal seperti versi yang kamu mau).
        Set `wait_for_receipt=True` jika ingin kepastian sukses on-chain.
        """
        hex_data = self.get_owlto_erc20_hex_data(name, symbol)
        print(f"🪙 Starting Owlto ERC20 deployment: {name} ({symbol}) for {len(accounts)} accounts...")
        return self.send_transaction_batch(
            accounts, hex_data, gas_limit, max_workers, wait_for_receipt=wait_for_receipt
        )

    # =====================
    # Batch send primitives (UPDATED with Universal Compatibility)
    # =====================
    
    def send_call_batch(self, accounts, to, data, value_wei=0, gas_limit=300_000, max_workers=5):
        """Batch call ke alamat `to` dgn data & value (tanpa tunggu receipt)."""
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for account in accounts:
                futures.append(
                    executor.submit(
                        self._send_single_call,
                        account['private_key'],
                        account['address'],
                        to,
                        data,
                        value_wei,
                        gas_limit,
                        account['line_number']
                    )
                )
                time.sleep(random.uniform(0.2, 0.8))
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    print(f"✅ Success: {result['address']} - TX: {result['tx_hash'][:10]}...")
                except Exception as e:
                    print(f"❌ Error: {e}")
                    results.append({"error": str(e)})
        return results

    def _send_single_call(self, private_key, from_address, to, data, value_wei, gas_limit, line_number):
        """Kirim single TX call (tanpa tunggu receipt) - UPDATED with Universal Compatibility."""
        try:
            nonce = self.w3.eth.get_transaction_count(from_address)
            gas_price = self.w3.eth.gas_price
            
            tx = {
                'from': from_address,
                'nonce': nonce,
                'gasPrice': gas_price,
                'gas': gas_limit,
                'to': Web3.to_checksum_address(to),
                'value': int(value_wei),
                'data': data,
                'chainId': self.w3.eth.chain_id
            }
            
            signed = self.w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = self.send_raw_transaction_universal(signed)
            
            return {
                'address': from_address,
                'tx_hash': tx_hash.hex(),
                'line_number': line_number,
                'status': 'sent'
            }
        except Exception as e:
            raise Exception(f"Line {line_number} ({from_address}): {str(e)}")

    def send_transaction_batch(
        self, accounts, hex_data, gas_limit=2_000_000, max_workers=5, wait_for_receipt=False
    ):
        """Kirim transaksi paralel dari banyak akun - UPDATED with Universal Compatibility."""
        results = []
        delay_min, delay_max = 0.2, 0.8

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for account in accounts:
                fn = (
                    self._send_single_transaction_with_receipt
                    if wait_for_receipt
                    else self._send_single_transaction
                )

                future = executor.submit(
                    fn,
                    account["private_key"],
                    account["address"],
                    hex_data,
                    gas_limit,
                    account["line_number"],
                )
                futures.append(future)
                time.sleep(random.uniform(delay_min, delay_max))

            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    if result.get("status") in ("success", "sent"):
                        print(f"✅ Success: {result['address']} - TX: {result['tx_hash'][:10]}...")
                    else:
                        print(f"ℹ️ {result}")
                except Exception as e:
                    print(f"❌ Error: {e}")
                    results.append({"error": str(e)})
        return results

    def _base_tx(self, from_address, gas_limit, hex_data):
        """Bangun dict transaksi dengan field penting & data tervalidasi."""
        return {
            "from": from_address,
            "nonce": self.w3.eth.get_transaction_count(from_address),
            "gasPrice": self.w3.eth.gas_price,
            "gas": gas_limit,
            "to": None,  # contract creation
            "value": 0,  # penting: 0 ETH
            "data": self._as_tx_data(hex_data),
            "chainId": self.w3.eth.chain_id,  # penting untuk EIP-155
        }

    def _send_single_transaction(self, private_key, from_address, hex_data, gas_limit, line_number):
        """Kirim transaksi TANPA menunggu receipt (mode 'sent') - UPDATED with Universal Compatibility."""
        try:
            tx = self._base_tx(from_address, gas_limit, hex_data)
            signed_txn = self.w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = self.send_raw_transaction_universal(signed_txn)
            
            return {
                "address": from_address,
                "tx_hash": tx_hash.hex(),
                "line_number": line_number,
                "status": "sent",
            }
        except Exception as e:
            raise Exception(f"Line {line_number} ({from_address}): {str(e)}")

    def _send_single_transaction_with_receipt(
        self, private_key, from_address, hex_data, gas_limit, line_number
    ):
        """Kirim transaksi & TUNGGU receipt (cek status on-chain) - UPDATED with Universal Compatibility."""
        try:
            tx = self._base_tx(from_address, gas_limit, hex_data)
            signed_txn = self.w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = self.send_raw_transaction_universal(signed_txn)
            
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt.status == 1:
                return {
                    "address": from_address,
                    "tx_hash": tx_hash.hex(),
                    "contract_address": receipt.contractAddress,
                    "line_number": line_number,
                    "status": "success",
                    "gas_used": receipt.gasUsed,
                }
            
            raise Exception(
                f"Contract creation FAILED - Transaction status: 0, Gas used: {receipt.gasUsed}"
            )
        except Exception as e:
            raise Exception(f"Line {line_number} ({from_address}): {str(e)}")

    def _as_tx_data(self, hexstr: str) -> HexBytes:
        """Validate & convert hex string ke HexBytes untuk tx.data."""
        if not isinstance(hexstr, str):
            raise ValueError("tx data must be hex string")
        s = hexstr.lower()
        if s.startswith("0x"):
            s = s[2:]
        # validasi karakter hex
        int(s or "0", 16)
        # pastikan genap
        if len(s) % 2 != 0:
            s = "0" + s
        return HexBytes("0x" + s)

    # ===========
    # Utilities
    # ===========
    
    def check_balances(self, accounts):
        print("\n💰 Checking balances...")
        for account in accounts:
            try:
                bal_wei = self.w3.eth.get_balance(account["address"])
                bal_eth = self.w3.from_wei(bal_wei, "ether")
                print(f"Line {account['line_number']}: {account['address']} - {bal_eth:.6f} ETH")
            except Exception as e:
                print(f"❌ Error checking balance for line {account['line_number']}: {e}")

    def save_results(self, results, filename="transaction_results.json"):
        with open(filename, "w") as f:
            json.dump(results, f, indent=2)
        print(f"💾 Results saved to {filename}")

    def get_network_info(self):
        try:
            chain_id = self.w3.eth.chain_id
            block_number = self.w3.eth.block_number
            gas_price = self.w3.eth.gas_price
            gas_price_gwei = self.w3.from_wei(gas_price, "gwei")

            return {
                "chain_id": chain_id,
                "block_number": block_number,
                "gas_price": gas_price,
                "gas_price_gwei": float(gas_price_gwei),
            }
        except Exception as e:
            print(f"❌ Error getting network info: {e}")
            return None

    def estimate_total_gas_cost(self, accounts_count, gas_limit, gas_price=None):
        if gas_price is None:
            gas_price = self.w3.eth.gas_price

        total_gas = accounts_count * gas_limit
        total_cost_wei = total_gas * gas_price
        total_cost_eth = self.w3.from_wei(total_cost_wei, "ether")

        print("⛽ Gas Estimation:")
        print(f"  Accounts: {accounts_count}")
        print(f"  Gas Limit per TX: {gas_limit:,}")
        print(f"  Gas Price: {self.w3.from_wei(gas_price, 'gwei'):.2f} Gwei")
        print(f"  Total Gas: {total_gas:,}")
        print(f"  Total Cost: {total_cost_eth:.6f} ETH")

        return {
            "accounts_count": accounts_count,
            "gas_limit": gas_limit,
            "gas_price": gas_price,
            "total_gas": total_gas,
            "total_cost_wei": total_cost_wei,
            "total_cost_eth": float(total_cost_eth),
        }


class ConfigManager:
    """Manage konfigurasi bot"""

    @staticmethod
    def load_config(filename="config.json"):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ Config file {filename} tidak ditemukan!")
            return None
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return None

    @staticmethod
    def create_default_config(filename="config.json"):
        default_config = {
            "rpc_url": "https://ethereum-sepolia-rpc.publicnode.com",
            "giwa_rpc_url": "https://sepolia-rpc.giwa.io",
            "akun_file": "akun.txt",
            "gas_limit": 2_000_000,
            "bridge_gas_limit": 150000,
            "bridge_amount": "0.001",
            "gmon_create_gas": 350_000,
            "max_workers": 5,
            "delay_range": [0.2, 0.8],
            "check_balance_first": True,
            "save_results": True,
            "erc20_name": "cuandrop",
            "erc20_symbol": "cndrp"
        }

        with open(filename, "w") as f:
            json.dump(default_config, f, indent=2)
        print(f"✅ Default config created: {filename}")
        return default_config
