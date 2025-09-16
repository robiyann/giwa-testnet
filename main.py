#!/usr/bin/env python3
"""
CUANDROP GIWA TESTNET AUTOBOT
Runner script - semua logic ada di utils.py
"""

from utils import MultiAccountFromPK, ConfigManager
from web3 import Web3
import sys
import time

def print_banner():
    """Print banner bot yang sederhana"""
    banner = """
    ╔═══════════════════════════════════════════════╗
    ║         CUANDROP GIWA TESTNET AUTOBOT         ║
    ║                by @robiyan                    ║
    ╚═══════════════════════════════════════════════╝
    """
    print(banner)

def show_menu():
    """Tampilkan menu + banner setiap kali"""
    print_banner()
    menu = """
╔═══════════════════════════════════════╗
║ SELECT OPTION                         ║
╠═══════════════════════════════════════╣
║ 1. Deploy Smart Contract Owlto        ║
║ 2. Deploy ERC20 Token Owlto           ║
║ 3. Deploy GMONChain                   ║
║ 4. Mint omnihub nft                   ║
║ 5. Bridge Sepolia to GIWA             ║
║ 6. Try All In (1→2→3 per akun)        ║
║ 7. Check Bridge Balances              ║
║ 0. Exit                               ║
╚═══════════════════════════════════════╝
    """
    print(menu)

def get_user_choice():
    """Get pilihan user"""
    try:
        return input("Enter your choice: ").strip()
    except KeyboardInterrupt:
        print("\n❌ Bot stopped by user (Ctrl+C)")
        sys.exit(0)

def get_token_details():
    """Get token name dan symbol dari user (default aman)"""
    print("\n🪙 ERC20 Token Configuration:")
    name = input("Enter token name (default: cuandrop): ").strip() or "cuandrop"
    symbol = input("Enter token symbol (default: cndrp): ").strip() or "cndrp"
    return name, symbol

def print_summary(results, title="Transaction Summary"):
    """Print ringkasan hasil transaksi"""
    success_count = len([r for r in results if r.get('status') in ('success', 'sent') or 'tx_hash' in r])
    error_count   = len([r for r in results if 'error' in r])
    print(f"\n📊 {title}:")
    print(f"✅ Success: {success_count}")
    print(f"❌ Errors:  {error_count}")
    print(f"📝 Total:   {len(results)}")
    return {'success': success_count, 'errors': error_count, 'total': len(results)}

def bridge_sepolia_to_giwa_handler(bot, config, accounts):
    """Fitur bridge Sepolia ke GIWA"""
    print("\n🌉 BRIDGE SEPOLIA TO GIWA")
    print("=" * 50)
    
    # Input amount
    default_amount = config.get('bridge_amount', '0.001')
    amount_input = input(f"Enter ETH amount to bridge (default: {default_amount}): ").strip()
    amount = amount_input if amount_input else default_amount
    
    try:
        float(amount)  # Validate numeric
    except ValueError:
        print("❌ Invalid amount! Using default 0.001 ETH")
        amount = "0.001"
    
    print(f"\n🔄 Bridging {amount} ETH per account...")
    print("⏳ Bridge transactions take 1-3 minutes to appear on GIWA")
    
    # Estimate cost
    amount_wei = bot.w3.to_wei(amount, 'ether')
    gas_limit = config.get('bridge_gas_limit', 150000)
    total_value = len(accounts) * amount_wei
    total_value_eth = bot.w3.from_wei(total_value, 'ether')
    
    print(f"\n⛽ Bridge Estimation:")
    print(f"  Amount per account: {amount} ETH")
    print(f"  Total ETH needed: {total_value_eth} ETH")
    print(f"  Gas limit: {gas_limit:,}")
    
    # Execute bridge
    results = bot.bridge_sepolia_to_giwa(
        accounts,
        amount_eth=amount,
        gas_limit=gas_limit,
        max_workers=config.get('max_workers', 5)
    )
    
    summary = print_summary(results, "Bridge Sepolia→GIWA")
    
    if config.get('save_results', True):
        bot.save_results(results, 'bridge_sepolia_giwa_results.json')
    
    if summary['errors'] == 0:
        print("🎉 All bridge transactions sent successfully!")
        print("⏳ Wait 1-3 minutes then check GIWA balances")
    else:
        print(f"⚠️ Bridge completed with {summary['errors']} errors")

def check_bridge_balances_handler(bot, config, accounts):
    """Check balances di Sepolia dan GIWA"""
    print("\n💰 CHECKING BRIDGE BALANCES")
    print("=" * 50)
    
    bot.check_bridge_balances(accounts)

def deploy_owlto_contract(bot, config, accounts):
    """Fitur #1 — tanpa cek balance/konfirmasi"""
    print("\n🦉 OWLTO SMART CONTRACT DEPLOYMENT")
    print("="*50)
    # opsional estimasi
    bot.estimate_total_gas_cost(len(accounts), config['gas_limit'])
    # eksekusi
    results = bot.deploy_owlto_smart_contract(
        accounts,
        gas_limit=config.get('gas_limit', 2_000_000),
        max_workers=config.get('max_workers', 5)
    )
    summary = print_summary(results, "Owlto Deployment")
    if config.get('save_results', True):
        bot.save_results(results, 'owlto_deployment_results.json')
    if summary['errors'] == 0:
        print("🎉 All Owlto contracts deployed successfully!")
    else:
        print(f"⚠️  Deployment completed with {summary['errors']} errors")

def deploy_erc20_contract(bot, config, accounts):
    """Fitur #2 — tanpa cek balance/konfirmasi (default tidak tunggu receipt)"""
    print("\n🪙 OWLTO ERC20 TOKEN DEPLOYMENT")
    print("="*50)
    name, symbol = get_token_details()
    print(f"\n📋 Token Details:\n   Name: {name}\n   Symbol: {symbol}\n   Supply: 100 tokens (18 decimals)")
    bot.estimate_total_gas_cost(len(accounts), config['gas_limit'])
    results = bot.deploy_owlto_erc20_contract(
        accounts,
        name=name,
        symbol=symbol,
        gas_limit=config.get('gas_limit', 2_000_000),
        max_workers=config.get('max_workers', 5),
        # biarkan default wait_for_receipt=False untuk “sukses di terminal”
    )
    summary = print_summary(results, f"{symbol} ERC20 Deployment")
    if config.get('save_results', True):
        bot.save_results(results, f'{symbol}_erc20_deployment_results.json')
    if summary['errors'] == 0:
        print(f"🎉 All {name} ({symbol}) tokens deployed successfully!")
    else:
        print(f"⚠️  Deployment completed with {summary['errors']} errors")

def deploy_gmonchain(bot, config, accounts):
    """Fitur #3 — batch GMONChain call (tanpa cek balance/konfirmasi)"""
    print("\n🧩 GMONCHAIN DEPLOYMENT")
    print("="*50)
    # gunakan default gas di utils, tapi izinkan override dari config
    results = bot.deploy_gmonchain(
        accounts,
        gas_limit=config.get('gmon_create_gas', 350_000),
        max_workers=config.get('max_workers', 5)
    )
    summary = print_summary(results, "GMONChain Calls")
    if config.get('save_results', True):
        bot.save_results(results, 'gmonchain_results.json')
    if summary['errors'] == 0:
        print("🎉 GMONChain calls sent for all accounts!")
    else:
        print(f"⚠️  Done with {summary['errors']} errors")

def mint_omnihub_nft_handler(bot, config, accounts):
    print("\n🖼️  MINT OMNIHUB NFT (skip jika sudah punya)")
    print("=" * 50)
    result = bot.mint_omnihub_nft(
        accounts,
        gas_limit=config.get("gas_limit", 2_000_000),
        max_workers=config.get("max_workers", 5),
    )
    print("\n📊 Summary:")
    print(f"   Diproses : {result['processed']}")
    print(f"   Diskip   : {result['skipped']}")
    print(f"   TX sent  : {sum(1 for r in result['results'] if r.get('tx_hash'))}")
    print(f"   ❌ Errors : {sum(1 for r in result['results'] if r.get('error'))}")



# --- Tambahkan helper ini di bawah import dan di atas fungsi-fungsi deploy ---
def send_tx_with_nonce(bot, private_key, from_addr, nonce, *,
                      to=None, data="0x", value_wei=0, gas_limit=300_000,
                      wait_receipt=False, timeout=120):
    """
    Kirim 1 transaksi dengan nonce manual - kompatibel semua versi web3.py.
    """
    w3 = bot.w3
    
    # Normalisasi data
    d = data or "0x"
    if isinstance(d, str) and not d.startswith("0x"):
        d = "0x" + d
    
    tx = {
        "from": from_addr,
        "nonce": int(nonce),
        "gasPrice": w3.eth.gas_price,
        "gas": int(gas_limit),
        "to": None if to is None else Web3.to_checksum_address(to),
        "value": int(value_wei),
        "data": d,
        "chainId": w3.eth.chain_id,
    }
    
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = bot.send_raw_transaction_universal(signed)
    
    if wait_receipt:
        rcpt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        if rcpt.status != 1:
            return {
                "status": "failed",
                "tx_hash": tx_hash.hex(),
                "gas_used": rcpt.gasUsed,
                "contract_address": rcpt.contractAddress,
            }
        return {
            "status": "success", 
            "tx_hash": tx_hash.hex(),
            "gas_used": rcpt.gasUsed,
            "contract_address": rcpt.contractAddress,
        }
    
    return {"status": "sent", "tx_hash": tx_hash.hex()}


def try_all_in(bot, config, accounts):
    """
    Fitur gabungan 1→2→3 PER AKUN dengan NONCE MANUAL:
      1) Deploy Owlto SC — WAIT receipt
      2) Deploy ERC20 Owlto — NON-WAIT
      3) GMONChain call — NON-WAIT
    """
    print("\n🚀 TRY ALL IN (1→2→3 per akun)")
    print("="*50)

    # default nama/simbol dari config bila ada (biar tanpa prompt)
    name   = config.get('erc20_name', 'cuandrop')
    symbol = config.get('erc20_symbol', 'cndrp')

    # gas defaults
    gas_sc    = config.get('gas_limit', 2_000_000)
    gas_erc20 = config.get('gas_limit', 2_000_000)
    gas_gmon  = config.get('gmon_create_gas', 350_000)

    # gmon params dari utils (alamat factory, selector, dan value)
    factory_addr, gmon_selector, gmon_value = bot.get_gmonchain_call_params()

    all_results = []
    for i, acc in enumerate(accounts, 1):
        addr = acc['address']
        pk   = acc['private_key']
        print(f"\n─── 🔹 Account {i}/{len(accounts)}: {addr} ───")

        # Ambil nonce awal berbasis 'pending' agar mencakup TX yang belum mined
        try:
            nonce = bot.w3.eth.get_transaction_count(addr, 'pending')
        except Exception:
            # fallback ke latest jika node tidak dukung 'pending'
            nonce = bot.w3.eth.get_transaction_count(addr)

        # (1) Deploy Owlto SC — WAIT
        try:
            hex_sc = bot.get_owlto_hex_data()
            r1 = send_tx_with_nonce(
                bot, pk, addr, nonce,
                to=None, data=hex_sc, value_wei=0, gas_limit=gas_sc,
                wait_receipt=True
            )
            print(f"  [1/3] ✅ Owlto SC → tx: {r1['tx_hash'][:10]}…")
            nonce += 1
        except Exception as e:
            r1 = {"status": "error", "error": str(e)}
            print(f"  [1/3] ❌ Owlto SC error: {e}")

        # (2) Deploy ERC20 — NON-WAIT (terminal 'sent')
        try:
            hex_erc20 = bot.get_owlto_erc20_hex_data(name, symbol)
            r2 = send_tx_with_nonce(
                bot, pk, addr, nonce,
                to=None, data=hex_erc20, value_wei=0, gas_limit=gas_erc20,
                wait_receipt=False
            )
            print(f"  [2/3] ✅ ERC20 sent → tx: {r2['tx_hash'][:10]}…")
            nonce += 1
        except Exception as e:
            r2 = {"status": "error", "error": str(e)}
            print(f"  [2/3] ❌ ERC20 error: {e}")

        # (3) GMONChain call — NON-WAIT
        try:
            r3 = send_tx_with_nonce(
                bot, pk, addr, nonce,
                to=factory_addr, data=gmon_selector, value_wei=gmon_value,
                gas_limit=gas_gmon, wait_receipt=False
            )
            print(f"  [3/3] ✅ GMONChain sent → tx: {r3['tx_hash'][:10]}…")
            nonce += 1
        except Exception as e:
            r3 = {"status": "error", "error": str(e)}
            print(f"  [3/3] ❌ GMONChain error: {e}")

        status_flag = "success" if all(r.get("status") in ("success", "sent") for r in (r1, r2, r3)) else "partial"
        all_results.append({
            "address": addr,
            "owlto_sc": r1,
            "erc20": r2,
            "gmon": r3,
            "status": status_flag
        })

        # jeda kecil biar RPC gak spike
        time.sleep(0.3)

    ok = sum(1 for r in all_results if r["status"] == "success")
    er = len(all_results) - ok
    print(f"\n📊 All-In Summary → Success: {ok} / Errors: {er} / Total: {len(all_results)}")

    if config.get('save_results', True):
        bot.save_results(all_results, 'try_all_in_results.json')

def main():
    """Main runner function"""
    try:
        # Load config (atau buat default sekali)
        config = ConfigManager.load_config()
        if not config:
            print("📝 Creating default config file...")
            config = ConfigManager.create_default_config()
            print("✅ Please edit config.json and run again!")
            return

        # Init bot with both RPCs
        print("🤖 Initializing multi-account bot...")
        bot = MultiAccountFromPK(config['rpc_url'], config.get('giwa_rpc_url'))

        # Cek initial network connection (Sepolia)
        if not bot.get_network_info():
            print("❌ Failed to connect to initial network (Sepolia)!")
            return

        # Load akun
        accounts = bot.load_private_keys(config['akun_file'])
        if not accounts:
            print("❌ No valid accounts found!")
            return

        print(f"✅ Total accounts: {len(accounts)}")

        # Loop menu
        while True:
            show_menu()
            choice = get_user_choice()

            # Network switching logic
            is_giwa_action = choice in ['1', '2', '3', '4', '6']
            is_sepolia_action = choice == '5'
            network_ok = True

            if is_giwa_action:
                if not bot.set_network('giwa'):
                    network_ok = False
            elif is_sepolia_action:
                if not bot.set_network('sepolia'):
                    network_ok = False
            
            if not network_ok:
                print("Skipping action due to network connection failure.")
                input("\nPress Enter to continue...")
                continue

            # Action execution
            if choice == '1':
                deploy_owlto_contract(bot, config, accounts)
            elif choice == '2':
                deploy_erc20_contract(bot, config, accounts)
            elif choice == '3':
                deploy_gmonchain(bot, config, accounts)
            elif choice == '4':
                mint_omnihub_nft_handler(bot, config, accounts)
            elif choice == '5':
                bridge_sepolia_to_giwa_handler(bot, config, accounts)
            elif choice == '6':
                try_all_in(bot, config, accounts)
            elif choice == '7':
                # This function handles both networks internally
                check_bridge_balances_handler(bot, config, accounts)
            elif choice == '0':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice! Please select 0–7")

            if choice != '0':
                input("\nPress Enter to continue...")

    except KeyboardInterrupt:
        print("\n❌ Bot stopped by user (Ctrl+C)")
    except FileNotFoundError as e:
        print(f"❌ File not found: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    finally:
        print("👋 Bot finished")

if __name__ == "__main__":
    main()
