# [FILE] day1_strategy_integration.py
# PURPOSE: Wire the TradingExecutor into the ADX strategy signal logic
#
# WHAT ARE WE BUILDING HERE?
# Think of the system we're building like a security guard at a nightclub:
#
#   BOUNCER (ADX Strategy) — watches the crowd (price data), decides
#   who gets in based on rules (ADX >= 20, +DI > -DI)
#
#   DOOR MECHANISM (TradingExecutor) — actually opens/closes the door
#   when the bouncer gives the signal
#
# Previously these were separate:
#   - Week 3: We had the bouncer watching (live data + ADX calculation)
#   - Task 2:  We built the door mechanism (TradingExecutor)
#
# Today: We connect them. Bouncer signals → Door opens/closes.
#
# IMPORTANT: This runs on DAILY candles.
# The ADX 20/10 was optimised on daily candles (Week 2).
# We fetch the last N daily candles, calculate ADX, check signal,
# then decide whether to buy, sell, or hold.
# This script will be scheduled to run once per day in production.

# ── Imports ───────────────────────────────────────────────────────────────────

from day1_production_executor import TradingExecutor  # [CLASS] our executor
from binance.client import Client                      # [LIBRARY] Binance API
from dotenv import load_dotenv                         # [LIBRARY] loads .env
import os                                              # [LIBRARY] env vars
import pandas as pd                                    # [LIBRARY] data manipulation
import numpy as np                                     # [LIBRARY] calculations
from ta.trend import ADXIndicator                      # [LIBRARY] ADX calculation
import logging                                         # [LIBRARY] logging
from datetime import datetime                          # [LIBRARY] timestamps

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level   = logging.INFO,
    format  = '%(asctime)s | %(levelname)s | %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
# All strategy parameters in one place.
# This makes it easy to change settings without hunting through code.

SYMBOL           = 'ETHUSDT'   # [VARIABLE - str] trading pair
ADX_THRESHOLD    = 20          # [VARIABLE - int] minimum ADX for trend signal
ADX_PERIOD       = 10          # [VARIABLE - int] ADX lookback period
CANDLES_NEEDED   = 50          # [VARIABLE - int] how many daily candles to fetch
                               #   Need at least ADX_PERIOD + buffer to calculate
POSITION_SIZE    = 1000        # [VARIABLE - float] USDT to deploy per trade
DRY_RUN          = True        # [VARIABLE - bool] SAFETY: True = simulate only
USE_TESTNET      = True        # [VARIABLE - bool] True = fake money

# ── Step 1: Fetch Daily Candles from Binance ──────────────────────────────────
# We fetch historical daily candles directly from Binance (not yfinance).
# Why Binance instead of yfinance here?
#   - In production, our bot runs 24/7 on EC2
#   - We're already connected to Binance for trading
#   - Using one data source for both data AND execution is cleaner
#   - yfinance is great for backtesting but not for live systems

def fetch_daily_candles(client, symbol, limit=50):
    """
    [FUNCTION] Fetch recent daily OHLCV candles from Binance.

    Args:
        client [Client]: Binance API client
        symbol [str]   : Trading pair e.g. 'ETHUSDT'
        limit  [int]   : Number of candles to fetch (max 1000)

    Returns:
        DataFrame: OHLCV data with columns Open, High, Low, Close, Volume
    """
    # Binance returns candles as a list of lists
    # Each inner list = [open_time, open, high, low, close, volume, ...]
    raw = client.get_klines(             # [VARIABLE - list] raw candle data
        symbol   = symbol,
        interval = Client.KLINE_INTERVAL_1DAY,  # daily candles
        limit    = limit
    )

    # Convert to DataFrame with proper column names
    df = pd.DataFrame(raw, columns=[    # [VARIABLE - DataFrame] structured candles
        'open_time', 'Open', 'High', 'Low', 'Close', 'Volume',
        'close_time', 'quote_volume', 'trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])

    # Convert price columns from strings to floats
    # (Binance returns everything as strings)
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = df[col].astype(float)  # [VARIABLE - Series] numeric prices

    # Convert timestamp to readable datetime
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df.set_index('open_time', inplace=True)

    logger.info(f"Fetched {len(df)} daily candles for {symbol}")
    logger.info(f"  From: {df.index[0].date()}")
    logger.info(f"  To:   {df.index[-1].date()}")

    return df

# ── Step 2: Calculate ADX Signal ──────────────────────────────────────────────

def calculate_adx_signal(df):
    """
    [FUNCTION] Calculate ADX indicator and determine current signal.

    This is the same ADX logic from our backtest, now running on live data.
    The signal logic:
        LONG  = ADX >= 20 AND +DI > -DI  (trending AND bullish)
        FLAT  = everything else           (no trend or bearish)

    Args:
        df [DataFrame]: OHLCV candle data

    Returns:
        dict: Signal details with keys: signal, adx, plus_di, minus_di
    """
    # Calculate ADX using the ta library
    adx_indicator = ADXIndicator(        # [OBJECT] ADX calculator
        high   = df['High'],
        low    = df['Low'],
        close  = df['Close'],
        window = ADX_PERIOD
    )

    # Get the most recent values (iloc[-1] = last row = today)
    adx      = adx_indicator.adx().iloc[-1]      # [VARIABLE - float] current ADX
    plus_di  = adx_indicator.adx_pos().iloc[-1]  # [VARIABLE - float] current +DI
    minus_di = adx_indicator.adx_neg().iloc[-1]  # [VARIABLE - float] current -DI

    # Apply signal logic
    trending = adx >= ADX_THRESHOLD      # [VARIABLE - bool] is market trending?
    bullish  = plus_di > minus_di        # [VARIABLE - bool] is trend bullish?
    signal   = 'LONG' if (trending and bullish) else 'FLAT'  # [VARIABLE - str]

    return {                             # [VARIABLE - dict] signal package
        'signal':    signal,
        'adx':       round(adx, 2),
        'plus_di':   round(plus_di, 2),
        'minus_di':  round(minus_di, 2),
        'trending':  trending,
        'bullish':   bullish,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

# ── Step 3: Position State Manager ────────────────────────────────────────────
# The strategy needs to know if we are currently IN a trade or not.
# This prevents us from buying when already long, or selling when flat.
#
# Analogy: You can't buy a house you already own.
#          You can't sell a house you don't own.
#
# We determine position by checking actual ETH balance:
#   ETH balance > 0.01  → we are LONG (holding ETH)
#   ETH balance <= 0.01 → we are FLAT (holding cash)
#
# The 0.01 threshold handles tiny dust amounts — rounding leftovers
# from previous trades that are too small to sell.

def get_current_position(executor):
    """
    [FUNCTION] Determine current position state from actual balance.

    Args:
        executor [TradingExecutor]: Our trading executor object

    Returns:
        str: 'LONG' if holding ETH, 'FLAT' if holding cash
    """
    eth_balance = executor.get_balance('ETH')    # [VARIABLE - float] ETH held

    if eth_balance > 0.01:
        return 'LONG'
    else:
        return 'FLAT'

# ── Step 4: Main Strategy Loop ────────────────────────────────────────────────
# This is the brain of the trading bot.
# It runs once per day (scheduled via cron or systemd on EC2).
# Each run:
#   1. Fetch latest daily candles
#   2. Calculate ADX signal
#   3. Check current position
#   4. Decide action (buy / sell / hold)
#   5. Execute if needed

def run_strategy_check():
    """
    [FUNCTION] Run one cycle of the ADX strategy check.
    In production this is called once per day at market close.
    """
    logger.info("=" * 60)
    logger.info("ADX STRATEGY CHECK")
    logger.info(f"  Time:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Symbol:   {SYMBOL}")
    logger.info(f"  DRY RUN:  {DRY_RUN}")
    logger.info("=" * 60)

    # ── Initialise executor ────────────────────────────────────────────────
    executor = TradingExecutor(          # [OBJECT] our trading machine
        symbol      = SYMBOL,
        dry_run     = DRY_RUN,
        use_testnet = USE_TESTNET
    )

    # ── Fetch candles ──────────────────────────────────────────────────────
    logger.info("\nFetching daily candles...")
    df = fetch_daily_candles(            # [VARIABLE - DataFrame] price data
        client = executor.client,
        symbol = SYMBOL,
        limit  = CANDLES_NEEDED
    )

    # ── Calculate signal ───────────────────────────────────────────────────
    logger.info("\nCalculating ADX signal...")
    signal_data = calculate_adx_signal(df)  # [VARIABLE - dict] signal package

    logger.info(f"\nCURRENT MARKET CONDITIONS:")
    logger.info(f"  ADX:      {signal_data['adx']} "
                f"({'TRENDING ✅' if signal_data['trending'] else 'NO TREND ❌'})")
    logger.info(f"  +DI:      {signal_data['plus_di']}")
    logger.info(f"  -DI:      {signal_data['minus_di']}")
    logger.info(f"  Signal:   {signal_data['signal']}")

    # ── Check current position ─────────────────────────────────────────────
    current_position = get_current_position(executor)  # [VARIABLE - str] LONG or FLAT
    logger.info(f"  Position: {current_position}")

    # ── Decision logic ─────────────────────────────────────────────────────
    # Four possible states:
    #   FLAT  + LONG signal  → BUY  (enter trade)
    #   LONG  + FLAT signal  → SELL (exit trade)
    #   FLAT  + FLAT signal  → HOLD (stay in cash, wait)
    #   LONG  + LONG signal  → HOLD (stay in trade, wait)

    logger.info(f"\nDECISION:")

    if current_position == 'FLAT' and signal_data['signal'] == 'LONG':
        # ── ENTRY: Buy signal while flat ──────────────────────────────────
        logger.info(f"  ACTION: BUY — entering LONG position")
        logger.info(f"  Reason: ADX {signal_data['adx']} >= {ADX_THRESHOLD} "
                    f"and +DI {signal_data['plus_di']} > -DI {signal_data['minus_di']}")

        result = executor.execute_buy(amount_usdt=POSITION_SIZE)

        if result:
            logger.info(f"  ✅ BUY EXECUTED: {result['quantity']} ETH "
                        f"@ ${result['price']:,.2f}")
        else:
            logger.error(f"  ❌ BUY FAILED")

    elif current_position == 'LONG' and signal_data['signal'] == 'FLAT':
        # ── EXIT: Sell signal while long ───────────────────────────────────
        logger.info(f"  ACTION: SELL — exiting LONG position")
        logger.info(f"  Reason: ADX {signal_data['adx']} dropped below "
                    f"{ADX_THRESHOLD} (trend fading)")

        result = executor.execute_sell()

        if result:
            logger.info(f"  ✅ SELL EXECUTED: {result['quantity']} ETH "
                        f"@ ${result['price']:,.2f}")
        else:
            logger.error(f"  ❌ SELL FAILED")

    elif current_position == 'LONG' and signal_data['signal'] == 'LONG':
        # ── HOLD: Already long, trend continuing ───────────────────────────
        logger.info(f"  ACTION: HOLD — maintaining LONG position")
        logger.info(f"  Reason: Already long, trend still active")

    else:
        # ── WAIT: Flat, no signal ──────────────────────────────────────────
        logger.info(f"  ACTION: WAIT — staying in cash")
        logger.info(f"  Reason: No trend signal, holding USDT")

    # ── Final status ───────────────────────────────────────────────────────
    logger.info(f"\nSTRATEGY CHECK COMPLETE")
    executor.get_status()

    return signal_data

# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    signal = run_strategy_check()