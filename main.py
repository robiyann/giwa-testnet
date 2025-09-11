#!/usr/bin/env python3
"""
CUANDROP GIWA TESTNET AUTOBOT
Runner script - semua logic ada di utils.py
"""

from utils import MultiAccountFromPK, ConfigManager
import sys

def print_banner():
    banner = """
    ╔═══════════════════════════════════════════════╗
    ║         CUANDROP GIWA TESTNET AUTOBOT         ║
    ║                by @developer                  ║
    ╚═══════════════════════════════════════════════╝
    """
    print(banner)

def show_menu():
    print_banner()
    menu = """
    ╔═══════════════════════════════════════╗
    ║             SELECT OPTION             ║
    ╠═══════════════════════════════════════╣
    ║  1. Deploy Smart Contract Owlto       ║
    ║  2. Deploy ERC20 Token Owlto          ║
    ║  3. Deploy GMONChain                  ║
    ║  4. [Coming Soon] Swap Tokens         ║
    ║  5. [Coming Soon] Claim Airdrop       ║
    ║  0. Exit                              ║
    ╚═══════════════════════════════════════╝
    """
    print(menu)

def get_user_choice():
    try:
        return input("Enter your choice: ").strip()
    except KeyboardInterrupt:
        print("\n❌ Bot stopped by user (Ctrl+C)")
        sys.exit(0)

def get_token_details():
    print("\n🪙 ERC20 Token Configuration:")
    name = input("Enter token name (default: cuandrop): ").strip() or "cuandrop"
    symbol = input("Enter token symbol (default: cndrp): ").strip() or "cndrp"
    return name, symbol

def print_summary(results):
    success_count = len([r for r in results if 'tx_hash' in r])
    error_count = len([r for r in results if 'error' in r])
    print(f"\n📊 Transaction Summary:")
    print(f"✅ Success: {success_count}")
    print(f"❌ Errors: {error_count}")
    print(f"📝 Total: {len(results)}")
    return {'success': success_count, 'errors': error_count, 'total': len(results)}

def deploy_owlto_contract(bot, config, accounts):
    print("\n🦉 OWLTO SMART CONTRACT DEPLOYMENT")
    print("="*50)
    bot.estimate_total_gas_cost(len(accounts), config['gas_limit'])
    print("\n" + "="*50)
    results = bot.deploy_owlto_smart_contract(
        accounts,
        config.get('gas_limit', 2000000),
        config.get('max_workers', 5)
    )
    summary = print_summary(results)
    if config.get('save_results', True):
        bot.save_results(results, 'owlto_deployment_results.json')
    if summary['errors'] == 0:
        print("🎉 All Owlto contracts deployed successfully!")
    else:
        print(f"⚠️ Deployment completed with {summary['errors']} errors")

def deploy_erc20_contract(bot, config, accounts):
    print("\n🪙 OWLTO ERC20 TOKEN DEPLOYMENT")
    print("="*50)
    name, symbol = get_token_details()
    print(f"\n📋 Token Details:\n   Name: {name}\n   Symbol: {symbol}\n   Supply: 100 tokens (with 18 decimals)")
    bot.estimate_total_gas_cost(len(accounts), config['gas_limit'])
    print("\n" + "="*50)
    results = bot.deploy_owlto_erc20_contract(
        accounts, name, symbol,
        config.get('gas_limit', 2000000),
        config.get('max_workers', 5)
    )
    summary = print_summary(results)
    if config.get('save_results', True):
        bot.save_results(results, f'{symbol}_erc20_deployment_results.json')
    if summary['errors'] == 0:
        print(f"🎉 All {name} ({symbol}) tokens deployed successfully!")
    else:
        print(f"⚠️ Deployment completed with {summary['errors']} errors")

def deploy_gmonchain(bot, config, accounts):
    print("\n🧩 GMONCHAIN DEPLOYMENT")
    print("="*50)
    # gas estimate info only (tidak cek balance, tidak konfirmasi)
    bot.estimate_total_gas_cost(len(accounts), config['gas_limit'])
    print("\n" + "="*50)
    results = bot.deploy_gmonchain(
        accounts,
        config.get('gas_limit', 300000),
        config.get('max_workers', 5)
    )
    summary = print_summary(results)
    if config.get('save_results', True):
        bot.save_results(results, 'gmonchain_deployment_results.json')
    if summary['errors'] == 0:
        print("🎉 GMONChain calls sent successfully!")
    else:
        print(f"⚠️ Deployment completed with {summary['errors']} errors")

def main():
    try:
        config = ConfigManager.load_config()
        if not config:
            print("📝 Creating default config file...")
            config = ConfigManager.create_default_config()
            print("✅ Please edit config.json and run again!")
            return

        print("🤖 Initializing multi-account bot...")
        bot = MultiAccountFromPK(config['rpc_url'])

        network_info = bot.get_network_info()
        if not network_info:
            print("❌ Failed to connect to network!")
            return

        accounts = bot.load_private_keys(config['akun_file'])
        if not accounts:
            print("❌ No valid accounts found!")
            return

        print(f"✅ Total accounts: {len(accounts)}")

        while True:
            show_menu()
            choice = get_user_choice()

            if choice == '1':
                deploy_owlto_contract(bot, config, accounts)
            elif choice == '2':
                deploy_erc20_contract(bot, config, accounts)
            elif choice == '3':
                deploy_gmonchain(bot, config, accounts)
            elif choice == '4':
                print("🔄 Swap Tokens feature coming soon!")
            elif choice == '5':
                print("🪂 Claim Airdrop feature coming soon!")
            elif choice == '0':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice! Please select 0-5")

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
