# CUANDROP GIWA TESTNET AUTOBOT

🤖 A powerful multi-account Web3 automation bot for smart contract deployment on Ethereum-compatible testnets.

## Features

- Multi-Account Support: Deploy contracts from multiple accounts simultaneously
- Smart Contract Deployment: Owlto Smart Contract and Custom ERC20 Tokens with configurable name/symbol
- Receipt Validation: Automatic transaction receipt checking
- Gas Optimization: Cost estimation and safety buffer
- Balance Management: Check account balances
- Concurrent Processing: Threaded deployment
- Error Handling and Results Export

## Setup

1. Clone this repo
2. Create a Python virtual environment
3. Install dependencies using `pip install -r requirements.txt`
4. Create `akun.txt` with your private keys
5. Run bot using `python main.py`

## Usage

- Follow menu-driven interface
- Choose options to deploy contracts
- Customize ERC20 token name and symbol

## Security

- Keep private keys secure
- Use testnets only for deployment

## Files

- `main.py`: Runner with user interface
- `utils.py`: Core bot logic
- `config.json`: Configuration file
- `akun.txt`: Private keys
- `requirements.txt`: Dependencies

## License

MIT License
