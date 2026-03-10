# [IMPORT] Binance client for CEX price
from binance.client import Client

# [IMPORT] Web3 for connecting to Ethereum blockchain (DEX price)
from web3 import Web3

# [IMPORT] Load API keys from .env file
from dotenv import load_dotenv

# [IMPORT] os to read environment variables
import os

# [IMPORT] time to add pauses between price checks
import time

# [IMPORT] datetime for readable timestamps
from datetime import datetime

# [FUNCTION CALL] Load keys from .env
load_dotenv()

# ============================================================
# CEX SETUP (Binance)
# ============================================================

# [OBJECT] Create authenticated Binance connection
binance = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'))

# ============================================================
# DEX SETUP (Uniswap via Infura)
# ============================================================

# [VARIABLE - string] Build the Infura connection URL using your key
infura_url = f"https://mainnet.infura.io/v3/{os.getenv('INFURA_API_KEY')}"

# [OBJECT] Create Web3 connection to Ethereum mainnet
w3 = Web3(Web3.HTTPProvider(infura_url))

# [VARIABLE - string] Uniswap V3 ETH/USDC pool address
# This is the most liquid ETH pool on Uniswap — highest volume, tightest spread
POOL_ADDRESS = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"

# [LIST] Minimal ABI — just enough to call the slot0() function
# ABI = the "menu" that tells Web3 what functions this contract has
POOL_ABI = [
    {
        "inputs": [],
        "name": "slot0",
        "outputs": [
            {"internalType": "uint160", "name": "sqrtPriceX96", "type": "uint160"},
            {"internalType": "int24",   "name": "tick",          "type": "int24"},
            {"internalType": "uint16",  "name": "observationIndex", "type": "uint16"},
            {"internalType": "uint16",  "name": "observationCardinality", "type": "uint16"},
            {"internalType": "uint16",  "name": "observationCardinalityNext", "type": "uint16"},
            {"internalType": "uint8",   "name": "feeProtocol",   "type": "uint8"},
            {"internalType": "bool",    "name": "unlocked",      "type": "bool"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

# [OBJECT] Create a Python object representing the Uniswap pool contract
pool = w3.eth.contract(address=POOL_ADDRESS, abi=POOL_ABI)

# ============================================================
# PRICE FUNCTIONS
# ============================================================

def get_binance_price():
    """
    Fetch current ETH price from Binance (CEX).
    Simple REST call — ask Binance, get answer.
    """
    ticker = binance.get_symbol_ticker(symbol="ETHUSDT")
    return float(ticker['price'])

def get_uniswap_price():
    """
    Fetch current ETH price from Uniswap V3 (DEX).
    Reads directly from the smart contract on Ethereum blockchain.
    
    The price is stored as sqrtPriceX96 — a square root format
    used to save gas costs on-chain. We decode it back to USD.
    """
    # [CONTRACT CALL] Read slot0 from the Uniswap pool contract
    slot0 = pool.functions.slot0().call()
    
    # [VARIABLE - int] Extract the square root price value
    sqrtPriceX96 = slot0[0]
    
    # [VARIABLE - float] Decode sqrtPriceX96 back to a raw price ratio
    # Step 1: Divide by 2^96 to remove the fixed-point scaling
    # Step 2: Square it to reverse the square root
    raw_price = (sqrtPriceX96 / (2**96)) ** 2
    
    # [VARIABLE - float] Adjust for token decimals
    # USDC has 6 decimals, ETH has 18 decimals → difference of 12
    # Multiply by 10^12 to correct the decimal offset
    price = (1 / raw_price) * (10**12)
    
    return price

# ============================================================
# SINGLE SNAPSHOT COMPARISON
# ============================================================

print("="*70)
print("CEX vs DEX PRICE COMPARISON")
print("="*70)

# [VARIABLE - float] Fetch both prices
cex_price = get_binance_price()
dex_price = get_uniswap_price()

# [VARIABLE - float] Calculate the difference between them
spread = abs(cex_price - dex_price)

# [VARIABLE - float] Express the spread as a percentage
spread_pct = (spread / cex_price) * 100

print(f"\n💰 ETH Price:")
print(f"   CEX (Binance):  ${cex_price:,.2f}")
print(f"   DEX (Uniswap):  ${dex_price:,.2f}")
print(f"   Spread:         ${spread:.2f} ({spread_pct:.3f}%)")

# [CONDITIONAL] Flag if spread is unusually large
if spread_pct > 0.5:
    print(f"\n⚠️  LARGE SPREAD: {spread_pct:.2f}% - Potential arbitrage opportunity?")
else:
    print(f"\n✅ Tight spread: Markets are efficient")

# ============================================================
# LIVE MONITORING LOOP (5 minutes, updates every 30 seconds)
# ============================================================

print(f"\n📊 Monitoring prices for 5 minutes (updates every 30s)...")
print(f"{'Time':<20} {'Binance':<15} {'Uniswap':<15} {'Spread %':<10}")
print("-"*60)

# [LOOP] Run 10 checks, 30 seconds apart = 5 minutes total
for i in range(10):
    
    # [VARIABLE] Current readable timestamp
    now = datetime.now().strftime('%H:%M:%S')
    
    # [VARIABLE - float] Fetch fresh prices each iteration
    cex = get_binance_price()
    dex = get_uniswap_price()
    
    # [VARIABLE - float] Calculate spread for this iteration
    sprd = abs(cex - dex) / cex * 100
    
    # [PRINT] One row of the monitoring table
    print(f"{now:<20} ${cex:<14,.2f} ${dex:<14,.2f} {sprd:.3f}%")
    
    # [PAUSE] Wait 30 seconds before next check
    # This avoids hammering the APIs with too many requests
    time.sleep(30)

print("\n✅ Monitoring complete!")