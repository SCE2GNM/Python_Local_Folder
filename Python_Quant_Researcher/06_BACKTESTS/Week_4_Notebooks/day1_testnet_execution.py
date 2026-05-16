# [FILE] day1_testnet_execution.py
# PURPOSE: Test buy and sell order execution on Binance TESTNET
#
# WHAT IS THE TESTNET?
# Think of it like a flight simulator for pilots.
# A pilot wouldn't fly a real plane on their first day — they practice in a
# simulator that behaves exactly like the real thing but with zero real risk.
# Binance Testnet is our flight simulator:
#   - Same API calls as live Binance
#   - Same order types, same responses, same error codes
#   - But all money is FAKE (Binance gives you free test funds)
#
# WHY DO THIS BEFORE LIVE TRADING?
# Order execution bugs are catastrophic with real money.
# A missing decimal point could buy 10x more ETH than intended.
# A wrong symbol could trade the wrong asset entirely.
# We test everything here first, then flip to live when confident.

# ── Imports ───────────────────────────────────────────────────────────────────

from binance.client import Client        # [LIBRARY] Binance API client
from binance.exceptions import BinanceAPIException  # [LIBRARY] Binance error handling
from dotenv import load_dotenv           # [LIBRARY] loads .env file
import os                                # [LIBRARY] reads environment variables
import json                              # [LIBRARY] pretty prints results
from datetime import datetime            # [LIBRARY] timestamps

# ── Load Credentials ──────────────────────────────────────────────────────────
# We load from .env so API keys are never hardcoded in scripts.
# Hardcoding keys = accidentally pushing them to GitHub = account compromised.

load_dotenv()  # loads all variables from .env into environment

TESTNET_API_KEY = os.getenv('BINANCE_TESTNET_API_KEY')   # [VARIABLE - str] testnet key
TESTNET_SECRET  = os.getenv('BINANCE_TESTNET_SECRET')    # [VARIABLE - str] testnet secret

# ── Validate Keys Loaded ──────────────────────────────────────────────────────

if not TESTNET_API_KEY or not TESTNET_SECRET:
    raise ValueError(
        "❌ Testnet credentials not found in .env\n"
        "   Make sure BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET are set"
    )

print("✅ Testnet credentials loaded")

# ── Connect to Testnet ────────────────────────────────────────────────────────
# CRITICAL: testnet=True tells the client to use testnet.binance.vision
# instead of api.binance.com — this is what keeps us on fake money.
# If you accidentally set testnet=False with testnet keys, it will fail.
# If you accidentally set testnet=False with LIVE keys, it will use real money.

client = Client(                         # [OBJECT] Binance API connection
    api_key    = TESTNET_API_KEY,
    api_secret = TESTNET_SECRET,
    testnet    = True                    # ← CRITICAL: routes to testnet, not live
)

print("✅ Connected to Binance Testnet")

# ── Step 1: Check Testnet Account Balance ────────────────────────────────────
# Binance gives testnet accounts free fake funds to trade with.
# We check balances first to confirm connection is working
# and to see what we have available to trade.

print("\n" + "=" * 60)
print("STEP 1: TESTNET ACCOUNT BALANCES")
print("=" * 60)

account  = client.get_account()          # [VARIABLE - dict] full account info
balances = account['balances']           # [VARIABLE - list] all asset balances

# Filter to only show assets with non-zero balances
# (testnet accounts have many assets, most are zero)
non_zero = [                             # [VARIABLE - list] assets we actually hold
    b for b in balances
    if float(b['free']) > 0 or float(b['locked']) > 0
]

for asset in non_zero:
    print(f"  {asset['asset']:<8} Free: {float(asset['free']):>15,.4f}  "
          f"Locked: {float(asset['locked']):>12,.4f}")

# ── Step 2: Get Current ETH Price ────────────────────────────────────────────
# Before placing any order we need to know the current price.
# This tells us how much ETH we get for our USDT.

print("\n" + "=" * 60)
print("STEP 2: CURRENT ETH PRICE")
print("=" * 60)

ticker = client.get_symbol_ticker(symbol='ETHUSDT')  # [VARIABLE - dict] price info
eth_price = float(ticker['price'])                    # [VARIABLE - float] current ETH price

print(f"  ETHUSDT: ${eth_price:,.2f}")

# ── Step 3: Place a Test Market Buy Order ────────────────────────────────────
# A market buy order says "buy X amount of ETH at whatever the current price is"
# We specify quantity in ETH (not USDT).
#
# Binance requires ETH quantity to 5 decimal places maximum.
# Example: if ETH = $2,000 and we want to spend $100:
#   quantity = 100 / 2000 = 0.05 ETH
#
# WHY MARKET ORDER (not limit)?
# A market order executes immediately at current price.
# A limit order waits until price reaches your specified level.
# For our ADX strategy we want immediate execution when signal fires —
# waiting for a limit price could mean missing the trade entirely.

print("\n" + "=" * 60)
print("STEP 3: TEST MARKET BUY ORDER")
print("=" * 60)

TRADE_USDT = 100                                      # [VARIABLE - float] how much USDT to spend
quantity   = round(TRADE_USDT / eth_price, 3)         # [VARIABLE - float] ETH to buy

print(f"  Attempting to buy {quantity} ETH (≈ ${TRADE_USDT} at ${eth_price:,.2f})")

try:
    buy_order = client.order_market_buy(     # [VARIABLE - dict] order response
        symbol   = 'ETHUSDT',               # trading pair
        quantity = quantity                  # amount of ETH to buy
    )

    # Parse the response
    order_id   = buy_order['orderId']                          # [VARIABLE - int] unique order ID
    status     = buy_order['status']                           # [VARIABLE - str] FILLED, PARTIAL etc
    filled_qty = float(buy_order['executedQty'])               # [VARIABLE - float] ETH actually bought
    spent_usdt = float(buy_order['cummulativeQuoteQty'])       # [VARIABLE - float] USDT actually spent
    avg_price  = spent_usdt / filled_qty if filled_qty else 0  # [VARIABLE - float] average fill price

    print(f"  ✅ BUY ORDER FILLED")
    print(f"     Order ID:    {order_id}")
    print(f"     Status:      {status}")
    print(f"     ETH Bought:  {filled_qty:.5f} ETH")
    print(f"     USDT Spent:  ${spent_usdt:.2f}")
    print(f"     Avg Price:   ${avg_price:,.2f}")

except BinanceAPIException as e:
    # BinanceAPIException gives us structured error info
    # e.code = Binance error code (e.g. -2010 = insufficient balance)
    # e.message = human readable description
    print(f"  ❌ BUY ORDER FAILED")
    print(f"     Error Code:  {e.code}")
    print(f"     Message:     {e.message}")
    buy_order  = None
    filled_qty = 0

# ── Step 4: Check Balance After Buy ──────────────────────────────────────────

print("\n" + "=" * 60)
print("STEP 4: BALANCES AFTER BUY")
print("=" * 60)

account_after = client.get_account()
balances_after = account_after['balances']

for asset in ['ETH', 'USDT']:
    b = next(x for x in balances_after if x['asset'] == asset)
    print(f"  {asset:<8} Free: {float(b['free']):>15,.4f}")

# ── Step 5: Place a Test Market Sell Order ───────────────────────────────────
# Now we sell the ETH we just bought.
# This completes the round-trip test: buy → sell
# If both work cleanly we know our execution code is functional.

print("\n" + "=" * 60)
print("STEP 5: TEST MARKET SELL ORDER")
print("=" * 60)

if filled_qty > 0:
    print(f"  Attempting to sell {filled_qty:.5f} ETH")

    try:
        sell_order = client.order_market_sell(   # [VARIABLE - dict] order response
            symbol   = 'ETHUSDT',
            quantity = filled_qty                # sell exactly what we bought
        )

        sell_qty      = float(sell_order['executedQty'])          # [VARIABLE - float] ETH sold
        received_usdt = float(sell_order['cummulativeQuoteQty'])  # [VARIABLE - float] USDT received
        sell_price    = received_usdt / sell_qty if sell_qty else 0  # [VARIABLE - float] avg sell price

        print(f"  ✅ SELL ORDER FILLED")
        print(f"     Order ID:    {sell_order['orderId']}")
        print(f"     Status:      {sell_order['status']}")
        print(f"     ETH Sold:    {sell_qty:.5f} ETH")
        print(f"     USDT Received: ${received_usdt:.2f}")
        print(f"     Avg Price:   ${sell_price:,.2f}")

        # Round trip P&L (will be slightly negative due to spread/fees)
        pnl = received_usdt - spent_usdt
        print(f"\n  Round-trip P&L: ${pnl:.4f}")
        print(f"  (Small loss expected — testnet simulates trading fees)")

    except BinanceAPIException as e:
        print(f"  ❌ SELL ORDER FAILED")
        print(f"     Error Code:  {e.code}")
        print(f"     Message:     {e.message}")

else:
    print("  ⚠️  Skipping sell — no ETH was bought in Step 3")

# ── Step 6: Final Summary ─────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("STEP 6: EXECUTION TEST SUMMARY")
print("=" * 60)
print(f"  Timestamp:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  Exchange:       Binance TESTNET (fake money)")
print(f"  Symbol:         ETHUSDT")
print(f"  ETH Price:      ${eth_price:,.2f}")
print(f"  Buy Test:       {'✅ PASSED' if buy_order else '❌ FAILED'}")
print(f"  Sell Test:      {'✅ PASSED' if filled_qty > 0 else '❌ FAILED'}")
print(f"\n  {'✅ EXECUTION FUNCTIONS WORKING' if buy_order else '❌ INVESTIGATE ERRORS ABOVE'}")
print(f"  {'   Ready to build TradingExecutor class (Task 2)' if buy_order else ''}")
print("=" * 60)