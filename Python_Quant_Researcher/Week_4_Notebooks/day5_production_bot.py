# [FILE] day5_production_bot.py
# PURPOSE: Production ADX trading bot with full risk management
#          This is the file that runs on EC2 every night at 00:05 UTC
#
# ARCHITECTURE:
#   1. Load state    — what position are we in right now?
#   2. Fetch data    — get latest daily candles
#   3. Calculate ADX — is there a trend? which direction?
#   4. Risk check    — is it safe to trade?
#   5. Execute       — buy/sell/hold based on signal and position
#   6. Stop-loss     — place stop order on Binance after every buy
#   7. Save state    — update position state for tomorrow
#   8. Log           — record everything
#
# DRY_RUN = True  → simulate only, no real orders (paper trading)
# DRY_RUN = False → real orders on live Binance (Day 7)

import sys
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import yfinance as yf
from ta.trend import ADXIndicator
import warnings
warnings.filterwarnings('ignore')

# ── Path setup ────────────────────────────────────────────────────────────────
# Add core/ to path so we can import TradingExecutor and RiskManager
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, 'core', 'execution'))

from trading_executor import TradingExecutor
from risk_manager import RiskManager, RISK_CONFIG

# ── Load credentials ──────────────────────────────────────────────────────────
load_dotenv(os.path.join(BASE_DIR, '.env'))

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level   = logging.INFO,
    format  = '%(asctime)s | %(levelname)s | %(message)s',
    datefmt = '%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# Change DRY_RUN and USE_TESTNET here when going live on Day 7
# ══════════════════════════════════════════════════════════════════════════════

DRY_RUN      = False    # SAFETY: True = simulate only | False = real orders (Day 7)
USE_TESTNET  = False    # True = testnet fake money    | False = live Binance (Day 7)

SYMBOL       = 'ETHUSDT'
ADX_THRESHOLD = 20
ADX_PERIOD    = 10
CANDLES_NEEDED = 50

# State file — bot's memory between daily runs
STATE_FILE = os.path.join(BASE_DIR, 'data', 'bot_state.json')

# ══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# The bot runs once per day and then exits. The state file is how it
# remembers what it did yesterday.
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_STATE = {                        # [VARIABLE - dict] empty starting state
    'position':           'FLAT',        # FLAT or LONG
    'entry_price':        None,          # price we bought at
    'entry_date':         None,          # date we entered
    'stop_loss_price':    None,          # our stop-loss level
    'stop_loss_order_id': None,          # Binance order ID for stop-loss
    'position_size_usdt': None,          # how much USDT we deployed
    'position_size_eth':  None,          # how much ETH we hold
    'last_updated':       None           # when state was last written
}

def load_state():
    """
    [FUNCTION] Load bot position state from file.
    If file doesn't exist, return default FLAT state.
    """
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
        logger.info(f"State loaded: position={state['position']}")
        if state['entry_price']:
            logger.info(f"  Entry: ${state['entry_price']:,.2f} on {state['entry_date']}")
        return state
    else:
        logger.info("No state file found — starting fresh (FLAT)")
        return DEFAULT_STATE.copy()

def save_state(state):
    """
    [FUNCTION] Save bot position state to file.
    Called after every action so tomorrow's run knows what happened today.
    """
    state['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)
    logger.info(f"State saved: position={state['position']}")

# ══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ══════════════════════════════════════════════════════════════════════════════

def fetch_candles(executor):
    """
    [FUNCTION] Fetch daily candles for ADX calculation.
    Primary source: Binance (live prices).
    Fallback: yfinance (if Binance testnet returns insufficient data).

    Returns:
        DataFrame: OHLCV daily candles
    """
    from binance.client import Client
    raw = executor.client.get_klines(
        symbol   = SYMBOL,
        interval = Client.KLINE_INTERVAL_1DAY,
        limit    = CANDLES_NEEDED
    )

    df = pd.DataFrame(raw, columns=[
        'open_time', 'Open', 'High', 'Low', 'Close', 'Volume',
        'close_time', 'quote_volume', 'trades',
        'taker_buy_base', 'taker_buy_quote', 'ignore'
    ])
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = df[col].astype(float)
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df.set_index('open_time', inplace=True)

    if len(df) < ADX_PERIOD + 20:
        logger.warning(f"Only {len(df)} candles from Binance — using yfinance fallback")
        df_yf = yf.download('ETH-USD', period='90d', interval='1d',
                            auto_adjust=True, progress=False)
        df_yf.columns = df_yf.columns.get_level_values(0)
        df = pd.DataFrame({
            'Open':   df_yf['Open'].squeeze().values,
            'High':   df_yf['High'].squeeze().values,
            'Low':    df_yf['Low'].squeeze().values,
            'Close':  df_yf['Close'].squeeze().values,
            'Volume': df_yf['Volume'].squeeze().values
        }, index=df_yf.index)
        logger.info(f"yfinance fallback: {len(df)} candles loaded")

    logger.info(f"Candles: {len(df)} daily bars "
                f"({df.index[0].date()} → {df.index[-1].date()})")
    return df

# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

def calculate_signal(df):
    """
    [FUNCTION] Calculate ADX and determine trading signal.

    Signal logic:
        LONG = ADX >= 20 AND +DI > -DI  (trending AND bullish)
        FLAT = everything else

    Returns:
        dict: signal, adx, plus_di, minus_di
    """
    adx_ind = ADXIndicator(
        high   = df['High'].squeeze(),
        low    = df['Low'].squeeze(),
        close  = df['Close'].squeeze(),
        window = ADX_PERIOD
    )

    adx      = float(adx_ind.adx().iloc[-1])
    plus_di  = float(adx_ind.adx_pos().iloc[-1])
    minus_di = float(adx_ind.adx_neg().iloc[-1])
    trending = adx >= ADX_THRESHOLD
    bullish  = plus_di > minus_di
    signal   = 'LONG' if (trending and bullish) else 'FLAT'

    logger.info(f"ADX: {adx:.2f} ({'TRENDING' if trending else 'NO TREND'}) | "
                f"+DI: {plus_di:.2f} | -DI: {minus_di:.2f} | Signal: {signal}")

    return {
        'signal':   signal,
        'adx':      round(adx, 2),
        'plus_di':  round(plus_di, 2),
        'minus_di': round(minus_di, 2),
        'trending': trending,
        'bullish':  bullish
    }

# ══════════════════════════════════════════════════════════════════════════════
# STOP-LOSS MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def place_stop_loss(executor, quantity, entry_price, stop_pct=0.05):
    """
    [FUNCTION] Place a stop-loss sell order on Binance.

    This is placed IMMEDIATELY after buying ETH.
    It lives on Binance's servers — fires automatically even if our bot crashes.

    The stop-loss is a STOP_LOSS_LIMIT order:
        Stop price:  entry_price × (1 - stop_pct)   e.g. $2,000 × 0.95 = $1,900
        Limit price: stop_price × 0.99               e.g. $1,900 × 0.99 = $1,881
                     (slightly below stop to ensure fill)

    Args:
        executor    [TradingExecutor]: our executor
        quantity    [float]          : ETH amount to protect
        entry_price [float]          : price we bought at
        stop_pct    [float]          : stop-loss percentage (default 5%)

    Returns:
        dict: order details including order_id
        None: if DRY_RUN or failed
    """
    stop_price  = round(entry_price * (1 - stop_pct), 2)  # [VARIABLE - float]
    limit_price = round(stop_price * 0.99, 2)              # [VARIABLE - float] fill buffer

    logger.info(f"Placing stop-loss: {quantity} ETH | "
                f"Stop: ${stop_price:,.2f} | Limit: ${limit_price:,.2f}")

    if executor.dry_run:
        logger.info("DRY RUN — Stop-loss simulated, not placed on Binance")
        return {
            'dry_run':    True,
            'order_id':   'DRY_RUN_STOP',
            'stop_price': stop_price,
            'limit_price': limit_price,
            'quantity':   quantity
        }

    try:
        from binance.exceptions import BinanceAPIException
        order = executor.client.create_order(
            symbol      = executor.symbol,
            side        = 'SELL',
            type        = 'STOP_LOSS_LIMIT',
            timeInForce = 'GTC',             # Good Till Cancelled — stays until filled
            quantity    = quantity,
            stopPrice   = str(stop_price),
            price       = str(limit_price)
        )
        logger.info(f"✅ Stop-loss order placed on Binance: ID {order['orderId']}")
        return {
            'order_id':    order['orderId'],
            'stop_price':  stop_price,
            'limit_price': limit_price,
            'quantity':    quantity
        }
    except Exception as e:
        logger.error(f"❌ Stop-loss placement failed: {e}")
        return None

def cancel_stop_loss(executor, order_id):
    """
    [FUNCTION] Cancel an existing stop-loss order.
    Called before placing a regular sell — avoids double-selling.

    Args:
        executor [TradingExecutor]: our executor
        order_id [int/str]        : Binance order ID to cancel
    """
    if executor.dry_run or order_id == 'DRY_RUN_STOP':
        logger.info("DRY RUN — Stop-loss cancellation simulated")
        return

    try:
        executor.client.cancel_order(symbol=executor.symbol, orderId=order_id)
        logger.info(f"✅ Stop-loss order {order_id} cancelled")
    except Exception as e:
        logger.warning(f"Could not cancel stop-loss {order_id}: {e}")

def check_stop_loss_triggered(executor, state):
    """
    [FUNCTION] Check if our stop-loss order has already been filled by Binance.
    This handles the case where price crashed overnight and Binance auto-sold.

    Returns:
        bool: True if stop-loss was triggered and filled
    """
    if not state['stop_loss_order_id'] or state['stop_loss_order_id'] == 'DRY_RUN_STOP':
        return False

    try:
        order = executor.client.get_order(
            symbol  = executor.symbol,
            orderId = state['stop_loss_order_id']
        )
        if order['status'] == 'FILLED':
            fill_price = float(order['price'])
            pnl_pct    = (fill_price - state['entry_price']) / state['entry_price']
            logger.warning(f"🛑 STOP-LOSS TRIGGERED overnight!")
            logger.warning(f"   Entry: ${state['entry_price']:,.2f}")
            logger.warning(f"   Fill:  ${fill_price:,.2f}")
            logger.warning(f"   P&L:   {pnl_pct:.2%}")
            return True
        return False
    except Exception as e:
        logger.warning(f"Could not check stop-loss status: {e}")
        return False

# ══════════════════════════════════════════════════════════════════════════════
# MAIN STRATEGY LOOP
# ══════════════════════════════════════════════════════════════════════════════

def run():
    """
    [FUNCTION] Main daily strategy execution.
    Called by cron at 00:05 UTC every day.
    """
    logger.info("=" * 65)
    logger.info("ADX PRODUCTION BOT — DAILY STRATEGY CHECK")
    logger.info(f"  Time:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Symbol:   {SYMBOL}")
    logger.info(f"  Mode:     {'DRY RUN (paper trading)' if DRY_RUN else '⚠️  LIVE TRADING'}")
    logger.info(f"  Exchange: {'Testnet (fake money)' if USE_TESTNET else 'LIVE BINANCE'}")
    logger.info("=" * 65)

    # ── Step 1: Load state ────────────────────────────────────────────────────
    state = load_state()                 # [VARIABLE - dict] current position state

    # ── Step 2: Initialise executor ───────────────────────────────────────────
    executor = TradingExecutor(
        symbol      = SYMBOL,
        dry_run     = DRY_RUN,
        use_testnet = USE_TESTNET
    )

    # ── Step 3: Get account balance ───────────────────────────────────────────
    usdt_balance = executor.get_balance('USDT')   # [VARIABLE - float]
    eth_balance  = executor.get_balance('ETH')    # [VARIABLE - float]
    eth_price    = executor.get_current_price()   # [VARIABLE - float]
    portfolio    = usdt_balance + (eth_balance * eth_price)  # [VARIABLE - float]

    logger.info(f"Account: ${usdt_balance:,.2f} USDT | "
                f"{eth_balance:.5f} ETH | "
                f"Portfolio: ${portfolio:,.2f}")

    # ── Step 4: Initialise RiskManager ───────────────────────────────────────
    rm = RiskManager(                    # [OBJECT] our risk gatekeeper
        config          = RISK_CONFIG,
        initial_balance = portfolio
    )

    # ── Step 5: Check if stop-loss was triggered overnight ────────────────────
    if state['position'] == 'LONG':
        stop_triggered = check_stop_loss_triggered(executor, state)
        if stop_triggered:
            # Stop-loss already fired on Binance — update our state
            pnl_pct  = (state['stop_loss_price'] - state['entry_price']) / state['entry_price']
            pnl_usd  = (state['position_size_usdt'] or 0) * pnl_pct
            rm.record_trade(pnl=pnl_usd)
            state = DEFAULT_STATE.copy()
            state['position'] = 'FLAT'
            save_state(state)
            logger.info("Position closed by stop-loss — now FLAT")

    # ── Step 6: Fetch candles and calculate signal ────────────────────────────
    df          = fetch_candles(executor)
    signal_data = calculate_signal(df)   # [VARIABLE - dict]
    signal      = signal_data['signal']  # [VARIABLE - str] LONG or FLAT
    position    = state['position']      # [VARIABLE - str] FLAT or LONG

    logger.info(f"Signal: {signal} | Position: {position}")

    # ── Step 7: Decision logic ────────────────────────────────────────────────
    logger.info("─" * 65)

    if position == 'FLAT' and signal == 'LONG':
        # ── ENTRY ─────────────────────────────────────────────────────────────
        logger.info("ACTION: BUY — entering LONG position")

        # Risk check first
        can_trade, reason = rm.can_trade(current_balance=portfolio)
        if not can_trade:
            logger.warning(f"🛑 TRADE BLOCKED by RiskManager: {reason}")
        else:
            # Kelly position sizing
            position_usdt = rm.calculate_position_size(usdt_balance=usdt_balance)
            logger.info(f"Position size: ${position_usdt:,.2f} "
                        f"(Kelly 12.41% of ${usdt_balance:,.2f})")

            # Execute buy
            buy_result = executor.execute_buy(amount_usdt=position_usdt)

            if buy_result:
                entry_price = buy_result['price']
                eth_bought  = buy_result['quantity']

                # Place stop-loss immediately after buy
                sl_result = place_stop_loss(
                    executor    = executor,
                    quantity    = eth_bought,
                    entry_price = entry_price,
                    stop_pct    = RISK_CONFIG['stop_loss_pct']
                )

                # Update state
                state['position']           = 'LONG'
                state['entry_price']        = entry_price
                state['entry_date']         = datetime.now().strftime('%Y-%m-%d')
                state['stop_loss_price']    = sl_result['stop_price'] if sl_result else None
                state['stop_loss_order_id'] = sl_result['order_id'] if sl_result else None
                state['position_size_usdt'] = position_usdt
                state['position_size_eth']  = eth_bought

                save_state(state)
                logger.info(f"✅ LONG entered: {eth_bought:.5f} ETH @ ${entry_price:,.2f}")
                logger.info(f"   Stop-loss: ${state['stop_loss_price']:,.2f} "
                            f"(-{RISK_CONFIG['stop_loss_pct']:.0%})")

    elif position == 'LONG' and signal == 'FLAT':
        # ── EXIT ──────────────────────────────────────────────────────────────
        logger.info("ACTION: SELL — exiting LONG position (trend faded)")

        # Cancel stop-loss before selling to avoid double-sell
        if state['stop_loss_order_id']:
            cancel_stop_loss(executor, state['stop_loss_order_id'])

        # Execute sell
        sell_result = executor.execute_sell(quantity=state['position_size_eth'])

        if sell_result:
            exit_price  = sell_result['price']
            pnl_pct     = (exit_price - state['entry_price']) / state['entry_price']
            pnl_usd     = (state['position_size_usdt'] or 0) * pnl_pct

            rm.record_trade(pnl=pnl_usd)
            logger.info(f"✅ LONG closed: @ ${exit_price:,.2f} | "
                        f"P&L: {pnl_pct:.2%} (${pnl_usd:+,.2f})")

            # Reset state to FLAT
            state = DEFAULT_STATE.copy()
            state['position'] = 'FLAT'
            save_state(state)

    elif position == 'LONG' and signal == 'LONG':
        # ── HOLD ──────────────────────────────────────────────────────────────
        logger.info("ACTION: HOLD — maintaining LONG position")
        logger.info(f"  Entry:     ${state['entry_price']:,.2f} on {state['entry_date']}")
        logger.info(f"  Current:   ${eth_price:,.2f}")
        unrealised = (eth_price - state['entry_price']) / state['entry_price']
        logger.info(f"  Unrealised P&L: {unrealised:+.2%}")
        logger.info(f"  Stop-loss: ${state['stop_loss_price']:,.2f}")

    else:
        # ── WAIT ──────────────────────────────────────────────────────────────
        logger.info("ACTION: WAIT — no trend signal, holding cash")
        logger.info(f"  ADX {signal_data['adx']:.2f} below {ADX_THRESHOLD} threshold")

    # ── Step 8: Final status ──────────────────────────────────────────────────
    logger.info("─" * 65)
    rm.get_status(current_balance=portfolio)
    logger.info("=" * 65)

if __name__ == '__main__':
    run()