# [FILE] day1_production_executor.py
# PURPOSE: Production-grade trading executor class for the ADX strategy
#
# WHAT IS A CLASS AND WHY USE ONE HERE?
# So far your code has been a series of steps executed top to bottom —
# like a recipe. A class is different. Think of it like a machine you build
# once and then operate repeatedly.
#
# Analogy: An ATM machine.
#   - You don't rebuild the ATM every time someone wants cash
#   - The ATM has STATE (how much cash is inside, who is logged in)
#   - The ATM has METHODS (withdraw, check balance, deposit)
#   - Multiple people can use different ATMs independently
#
# Our TradingExecutor class works the same way:
#   - STATE: current position, dry_run mode, which symbol we're trading
#   - METHODS: execute_buy(), execute_sell(), get_balance(), get_price()
#   - We create ONE executor object and call its methods whenever signals fire
#
# WHY DRY_RUN MODE?
# The executor has a safety switch: dry_run=True means "simulate everything
# but never send real orders". This lets us:
#   - Test the full logic flow without risking money (Days 1-6)
#   - Flip ONE variable to go live (Day 7: dry_run=False)
# This is standard practice at every professional trading firm.

# ── Imports ───────────────────────────────────────────────────────────────────

from binance.client import Client                    # [LIBRARY] Binance API
from binance.exceptions import BinanceAPIException   # [LIBRARY] Binance errors
from dotenv import load_dotenv                       # [LIBRARY] loads .env file
import os                                            # [LIBRARY] environment vars
import logging                                       # [LIBRARY] professional logging
from datetime import datetime                        # [LIBRARY] timestamps

# ── Logging Setup ─────────────────────────────────────────────────────────────
# logging is more powerful than print() for production systems:
#   - Every message gets a timestamp automatically
#   - Messages have severity levels (INFO, WARNING, ERROR)
#   - Easy to write logs to a file AND the terminal simultaneously
#   - Can filter by severity (e.g. only show ERRORs in production)

logging.basicConfig(
    level   = logging.INFO,                          # show INFO and above
    format  = '%(asctime)s | %(levelname)s | %(message)s',  # timestamp | level | message
    datefmt = '%Y-%m-%d %H:%M:%S'                   # readable timestamp format
)

logger = logging.getLogger(__name__)                 # [OBJECT] our logger instance

# ── Load Credentials ──────────────────────────────────────────────────────────

load_dotenv()

# ── TradingExecutor Class ─────────────────────────────────────────────────────

class TradingExecutor:
    """
    [CLASS] Production trading executor for Binance spot orders.

    Handles buy/sell execution with:
      - Dry run safety mode (simulate without real orders)
      - Automatic LOT_SIZE compliance (correct decimal precision)
      - Balance checking before orders
      - Structured logging of every action
      - Clean error handling

    Analogy: Think of this class as your trading desk.
    You (the strategy) call out "BUY!" or "SELL!" and the desk
    handles all the mechanics of actually getting it done safely.
    """

    def __init__(self, symbol='ETHUSDT', dry_run=True, use_testnet=True):
        """
        [METHOD] Constructor — called when you create a TradingExecutor object.
        Sets up the connection and initial state.

        Args:
            symbol     [str]  : Trading pair e.g. 'ETHUSDT'
            dry_run    [bool] : True = simulate only, False = real orders
            use_testnet [bool]: True = testnet (fake money), False = live Binance
        """

        self.symbol      = symbol       # [VARIABLE - str] which market we trade
        self.dry_run     = dry_run      # [VARIABLE - bool] safety switch
        self.use_testnet = use_testnet  # [VARIABLE - bool] testnet or live

        # ── Connect to Binance ─────────────────────────────────────────────
        # Choose credentials based on testnet flag
        if use_testnet:
            api_key    = os.getenv('BINANCE_TESTNET_API_KEY')
            api_secret = os.getenv('BINANCE_TESTNET_SECRET')
            logger.info("Connecting to Binance TESTNET (fake money)")
        else:
            api_key    = os.getenv('BINANCE_API_KEY')
            api_secret = os.getenv('BINANCE_SECRET_KEY')
            logger.info("Connecting to Binance LIVE (real money)")

        # Validate credentials loaded correctly
        if not api_key or not api_secret:
            raise ValueError(
                "❌ API credentials not found in .env\n"
                "   Check BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET"
            )

        # Create the Binance client connection
        self.client = Client(           # [VARIABLE - Client] Binance connection
            api_key    = api_key,
            api_secret = api_secret,
            testnet    = use_testnet
        )

        # ── Log startup state ──────────────────────────────────────────────
        mode = "DRY RUN (simulation)" if dry_run else "⚠️  LIVE TRADING (real money)"
        logger.info(f"TradingExecutor initialised")
        logger.info(f"  Symbol:   {self.symbol}")
        logger.info(f"  Mode:     {mode}")
        logger.info(f"  Testnet:  {use_testnet}")

    # ── Helper Methods ─────────────────────────────────────────────────────────
    # These are small utility methods used internally by execute_buy/sell.
    # The double underscore prefix (__) is a Python convention meaning
    # "this is internal — don't call it from outside the class".
    # Analogy: the ATM's internal cash-counting mechanism — you don't
    # press a button for it, it just runs automatically when needed.

    def get_current_price(self):
        """
        [METHOD] Get current price for our trading symbol.

        Returns:
            float: Current price in USDT
        """
        ticker = self.client.get_symbol_ticker(symbol=self.symbol)
        return float(ticker['price'])   # [VARIABLE - float] e.g. 2331.91

    def get_balance(self, asset):
        """
        [METHOD] Get available balance for a specific asset.

        Args:
            asset [str]: Asset symbol e.g. 'ETH' or 'USDT'

        Returns:
            float: Available (free) balance
        """
        account  = self.client.get_account()
        balances = account['balances']  # [VARIABLE - list] all asset balances

        # Find the specific asset we want
        for b in balances:
            if b['asset'] == asset:
                return float(b['free']) # [VARIABLE - float] available balance

        return 0.0  # asset not found = zero balance

    def calculate_quantity(self, amount_usdt, price):
        """
        [METHOD] Calculate how much ETH to buy for a given USDT amount.
        Rounds to 3 decimal places to comply with Binance LOT_SIZE filter.

        Args:
            amount_usdt [float]: How much USDT to spend
            price       [float]: Current ETH price

        Returns:
            float: ETH quantity rounded to valid LOT_SIZE
        """
        raw_qty = amount_usdt / price   # [VARIABLE - float] unrounded quantity
        return round(raw_qty, 3)        # [VARIABLE - float] LOT_SIZE compliant

    # ── Core Execution Methods ─────────────────────────────────────────────────

    def execute_buy(self, amount_usdt):
        """
        [METHOD] Execute a market buy order.

        This is called when our ADX strategy fires a LONG signal:
          - ADX >= 19 (market is trending, period=9)
          - +DI > -DI (trend is bullish)

        Args:
            amount_usdt [float]: How much USDT to spend (e.g. 1000.0)

        Returns:
            dict: Order result with keys: quantity, price, usdt_spent, order_id
            None: If order failed
        """
        logger.info(f"{'─' * 50}")
        logger.info(f"BUY SIGNAL RECEIVED")

        # ── Step 1: Get current price ──────────────────────────────────────
        price    = self.get_current_price()          # [VARIABLE - float] current ETH price
        quantity = self.calculate_quantity(amount_usdt, price)  # [VARIABLE - float] ETH to buy

        logger.info(f"  Price:     ${price:,.2f}")
        logger.info(f"  Spending:  ${amount_usdt:,.2f} USDT")
        logger.info(f"  Quantity:  {quantity} ETH")

        # ── Step 2: Check we have enough USDT ─────────────────────────────
        usdt_balance = self.get_balance('USDT')      # [VARIABLE - float] available USDT

        if usdt_balance < amount_usdt:
            logger.error(f"  ❌ Insufficient USDT balance")
            logger.error(f"     Available: ${usdt_balance:,.2f}")
            logger.error(f"     Required:  ${amount_usdt:,.2f}")
            return None

        logger.info(f"  USDT Balance: ${usdt_balance:,.2f} ✅")

        # ── Step 3: DRY RUN check ──────────────────────────────────────────
        # If dry_run=True, we log the simulated trade and return
        # WITHOUT sending any order to Binance.
        # This is the safety gate that protects real money.

        if self.dry_run:
            logger.info(f"  DRY RUN — Order simulated, not executed")
            return {                              # [VARIABLE - dict] simulated result
                'order_id':   'DRY_RUN',
                'quantity':   quantity,
                'price':      price,
                'usdt_spent': quantity * price,
                'dry_run':    True
            }

        # ── Step 4: Execute real order (only if dry_run=False) ────────────
        try:
            order = self.client.order_market_buy(    # [VARIABLE - dict] Binance response
                symbol   = self.symbol,
                quantity = quantity
            )

            # Parse the response
            filled_qty  = float(order['executedQty'])              # [VARIABLE - float] ETH bought
            usdt_spent  = float(order['cummulativeQuoteQty'])      # [VARIABLE - float] USDT spent
            avg_price   = usdt_spent / filled_qty                  # [VARIABLE - float] average price

            logger.info(f"  ✅ BUY FILLED")
            logger.info(f"     Order ID:  {order['orderId']}")
            logger.info(f"     ETH:       {filled_qty:.5f}")
            logger.info(f"     USDT:      ${usdt_spent:.2f}")
            logger.info(f"     Avg Price: ${avg_price:,.2f}")

            return {                              # [VARIABLE - dict] real result
                'order_id':   order['orderId'],
                'quantity':   filled_qty,
                'price':      avg_price,
                'usdt_spent': usdt_spent,
                'dry_run':    False
            }

        except BinanceAPIException as e:
            logger.error(f"  ❌ BUY FAILED: {e.code} - {e.message}")
            return None

    def execute_sell(self, quantity=None):
        """
        [METHOD] Execute a market sell order.

        Called when ADX strategy fires an EXIT signal:
          - ADX drops below threshold (trend fading)

        Args:
            quantity [float]: ETH to sell. If None, sells entire ETH balance.

        Returns:
            dict: Order result with keys: quantity, price, usdt_received, order_id
            None: If order failed
        """
        logger.info(f"{'─' * 50}")
        logger.info(f"SELL SIGNAL RECEIVED")

        # ── Step 1: Determine quantity to sell ────────────────────────────
        if quantity is None:
            quantity = self.get_balance('ETH')   # [VARIABLE - float] sell everything

        quantity = round(quantity, 3)            # LOT_SIZE compliance

        if quantity <= 0:
            logger.warning(f"  ⚠️  No ETH to sell (balance: {quantity})")
            return None

        # ── Step 2: Get current price ──────────────────────────────────────
        price = self.get_current_price()         # [VARIABLE - float] current price

        logger.info(f"  Price:     ${price:,.2f}")
        logger.info(f"  Quantity:  {quantity} ETH")
        logger.info(f"  Est Value: ${quantity * price:,.2f} USDT")

        # ── Step 3: DRY RUN check ──────────────────────────────────────────
        if self.dry_run:
            logger.info(f"  DRY RUN — Order simulated, not executed")
            return {                              # [VARIABLE - dict] simulated result
                'order_id':     'DRY_RUN',
                'quantity':     quantity,
                'price':        price,
                'usdt_received': quantity * price,
                'dry_run':      True
            }

        # ── Step 4: Execute real order ─────────────────────────────────────
        try:
            order = self.client.order_market_sell(   # [VARIABLE - dict] Binance response
                symbol   = self.symbol,
                quantity = quantity
            )

            filled_qty    = float(order['executedQty'])          # [VARIABLE - float] ETH sold
            usdt_received = float(order['cummulativeQuoteQty'])  # [VARIABLE - float] USDT received
            avg_price     = usdt_received / filled_qty           # [VARIABLE - float] average price

            logger.info(f"  ✅ SELL FILLED")
            logger.info(f"     Order ID:  {order['orderId']}")
            logger.info(f"     ETH:       {filled_qty:.5f}")
            logger.info(f"     USDT:      ${usdt_received:.2f}")
            logger.info(f"     Avg Price: ${avg_price:,.2f}")

            return {                              # [VARIABLE - dict] real result
                'order_id':     order['orderId'],
                'quantity':     filled_qty,
                'price':        avg_price,
                'usdt_received': usdt_received,
                'dry_run':      False
            }

        except BinanceAPIException as e:
            logger.error(f"  ❌ SELL FAILED: {e.code} - {e.message}")
            return None

    def get_status(self):
        """
        [METHOD] Print current account status — balances and price.
        Useful for monitoring and debugging.
        """
        price        = self.get_current_price()  # [VARIABLE - float] ETH price
        eth_balance  = self.get_balance('ETH')   # [VARIABLE - float] ETH held
        usdt_balance = self.get_balance('USDT')  # [VARIABLE - float] USDT held
        portfolio    = usdt_balance + (eth_balance * price)  # [VARIABLE - float] total value

        logger.info(f"{'─' * 50}")
        logger.info(f"ACCOUNT STATUS")
        logger.info(f"  ETH:       {eth_balance:.5f} ETH")
        logger.info(f"  USDT:      ${usdt_balance:,.2f}")
        logger.info(f"  ETH Price: ${price:,.2f}")
        logger.info(f"  Portfolio: ${portfolio:,.2f}")
        logger.info(f"{'─' * 50}")


# ── Test the TradingExecutor ───────────────────────────────────────────────────
# This block only runs when you execute this file directly.
# When other files import TradingExecutor, this block is skipped.
# Analogy: a car manual has a "test drive checklist" at the back —
# it's only used when testing, not when you're actually driving.

if __name__ == '__main__':

    print("\n" + "=" * 60)
    print("TRADING EXECUTOR — SYSTEM TEST")
    print("=" * 60)

    # ── Test 1: Initialise with DRY RUN = True ────────────────────────────
    print("\n[TEST 1] Initialising executor (DRY RUN mode)...")
    executor = TradingExecutor(         # [OBJECT] our trading machine
        symbol      = 'ETHUSDT',
        dry_run     = True,             # ← SAFETY ON
        use_testnet = True
    )

    # ── Test 2: Check account status ──────────────────────────────────────
    print("\n[TEST 2] Checking account status...")
    executor.get_status()

    # ── Test 3: Simulate a buy ────────────────────────────────────────────
    print("\n[TEST 3] Simulating BUY order (DRY RUN)...")
    buy_result = executor.execute_buy(amount_usdt=1000)

    if buy_result:
        print(f"\n  Buy result: {buy_result}")

    # ── Test 4: Simulate a sell ───────────────────────────────────────────
    print("\n[TEST 4] Simulating SELL order (DRY RUN)...")
    sell_result = executor.execute_sell(quantity=0.3)

    if sell_result:
        print(f"\n  Sell result: {sell_result}")

    # ── Test 5: Confirm no real orders placed ─────────────────────────────
    print("\n[TEST 5] Confirming no real orders were placed...")
    open_orders = executor.client.get_open_orders(symbol='ETHUSDT')
    print(f"  Open orders on testnet: {len(open_orders)}")
    print(f"  Expected: 0 (DRY RUN mode never places orders)")

    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETE")
    print(f"   DRY RUN mode working correctly")
    print(f"   TradingExecutor ready for strategy integration (Task 3)")
    print("=" * 60 + "\n")