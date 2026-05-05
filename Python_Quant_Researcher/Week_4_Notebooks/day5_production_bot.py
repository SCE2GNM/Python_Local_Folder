# [FILE] day5_production_bot.py
# PURPOSE: Production ADX trading bot — ETH/USDT on Binance Spot
#          Runs 4 times per day via cron (one signal run, three stop updates)
#
# MODES:
#   signal      --mode=signal      (00:05 UTC)
#       Full logic: download daily candle, calculate ADX 19/9 signal,
#       make entry/exit decisions, update trailing stop if new peak.
#
#   stop_update --mode=stop_update (06:05, 12:05, 18:05 UTC)
#       Minimal: get current ETH price via ticker, update trailing stop
#       if price has hit a new peak. No entry or exit decisions ever made.
#
# TRAILING STOP (bot-managed):
#   Binance Spot does not support native trailing stops (Futures only).
#   Bot raises STOP_LOSS order whenever price hits a new peak since entry.
#   Trail distance: TRAIL_PCT = 8% (Stage 1b validated parameter).
#   Stop = peak_price × (1 - TRAIL_PCT). Never decreases.
#
# ADX PARAMETERS: threshold=19, period=9 (Stage 1d validated, replaces 20/10)
# DRY_RUN = True  → simulate only, no real orders
# DRY_RUN = False → real orders on live Binance

import sys
import os
import json
import math
import logging
import argparse
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import numpy as np
import yfinance as yf
from ta.trend import ADXIndicator
import requests
import warnings
warnings.filterwarnings('ignore')

# ── Path setup ────────────────────────────────────────────────────────────────
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
# ══════════════════════════════════════════════════════════════════════════════

DRY_RUN      = False
USE_TESTNET  = False

SYMBOL         = 'ETHUSDT'
ADX_THRESHOLD  = 19             # Stage 1d validated (was 20)
ADX_PERIOD     = 9              # Stage 1d validated (was 10)
TRAIL_PCT      = 0.08           # 8% trailing stop — Stage 1b validated
CANDLES_NEEDED = 50

STATE_FILE = os.path.join(BASE_DIR, 'data', 'bot_state.json')

TELEGRAM_TOKEN   = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# ══════════════════════════════════════════════════════════════════════════════
# TELEGRAM ALERTING
# ══════════════════════════════════════════════════════════════════════════════

def send_telegram(message):
    """Send a Telegram message. Fails silently if not configured or network error."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — alert not sent")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': message},
                      timeout=10)
        logger.info(f"📱 Telegram sent: {message[:80]}")
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")


def check_api_trading_permission(executor):
    """
    Verify API key has trading permission using Binance test order endpoint.
    Returns True if permitted, False if denied (-2015). Sends Telegram on denial.
    """
    if executor.dry_run:
        return True
    try:
        executor.client.create_test_order(
            symbol   = SYMBOL,
            side     = 'BUY',
            type     = 'MARKET',
            quantity = 0.01
        )
        logger.info("✅ API trading permission confirmed")
        return True
    except Exception as e:
        code = getattr(e, 'code', None)
        if code == -2015:
            msg = (f"🚨 API TRADING PERMISSION DENIED on {datetime.now().strftime('%Y-%m-%d')} — "
                   f"bot cannot trade. Error: {code}. "
                   f"Go to Binance → API Management → enable 'Spot & Margin Trading'.")
            logger.error(msg)
            send_telegram(msg)
            return False
        # Any other error means permission IS granted — test order hit a filter, not an auth wall
        logger.info(f"✅ API trading permission confirmed (test order filter: {getattr(e, 'code', e)})")
        return True


# ══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_STATE = {
    'position':               'FLAT',   # FLAT or LONG
    'entry_price':            None,     # price we bought at
    'entry_date':             None,     # date we entered
    'stop_loss_price':        None,     # current stop level (rises with trailing stop)
    'stop_loss_order_id':     None,     # active Binance stop order ID
    'position_size_usdt':     None,     # USDT deployed at entry
    'position_size_eth':      None,     # ETH held
    'peak_price_since_entry': None,     # trailing stop high-water mark
    'last_updated':           None
}

def load_state():
    """
    Load bot state from file. Migrates old state files that predate
    peak_price_since_entry by initialising it to entry_price.
    """
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
        # Migration: old state files don't have peak_price_since_entry
        if 'peak_price_since_entry' not in state:
            state['peak_price_since_entry'] = state.get('entry_price')
        logger.info(f"State loaded: position={state['position']}")
        if state['entry_price']:
            peak = state.get('peak_price_since_entry') or state['entry_price']
            logger.info(f"  Entry: ${state['entry_price']:,.2f} on {state['entry_date']}")
            logger.info(f"  Peak:  ${peak:,.2f} | Stop: ${state['stop_loss_price']:,.2f}")
        return state
    else:
        logger.info("No state file found — starting fresh (FLAT)")
        return DEFAULT_STATE.copy()

def save_state(state):
    """Save bot state to file. Called after every action."""
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
    Fetch daily candles for ADX calculation.
    Primary source: Binance. Fallback: yfinance.
    Only called in signal run — stop_update runs use ticker price instead.
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
    Calculate ADX 19/9 and determine trading signal.
    LONG = ADX >= 19 AND +DI > -DI. FLAT = everything else.
    Parameters: threshold=19, period=9 (Stage 1d validated).
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

def place_stop_loss(executor, quantity, stop_price):
    """
    Place a STOP_LOSS (market) sell order on Binance at a given stop price.

    Used for both initial stop placement (at entry) and trailing stop updates.
    Quantity is floored to 3dp to avoid -2010 insufficient-balance errors.

    Args:
        executor   [TradingExecutor]: our executor
        quantity   [float]          : ETH amount to protect
        stop_price [float]          : price at which the stop triggers

    Returns:
        dict: {order_id, stop_price, quantity} or None if failed
    """
    quantity = math.floor(quantity * 1000) / 1000
    logger.info(f"Placing stop-loss: {quantity} ETH @ ${stop_price:,.2f}")

    if executor.dry_run:
        logger.info("DRY RUN — stop-loss simulated, not placed on Binance")
        return {'dry_run': True, 'order_id': 'DRY_RUN_STOP',
                'stop_price': stop_price, 'quantity': quantity}

    try:
        order = executor.client.create_order(
            symbol    = executor.symbol,
            side      = 'SELL',
            type      = 'STOP_LOSS',
            quantity  = quantity,
            stopPrice = str(stop_price)
        )
        logger.info(f"✅ Stop-loss placed: ID {order['orderId']} @ ${stop_price:,.2f}")
        return {'order_id': order['orderId'], 'stop_price': stop_price, 'quantity': quantity}
    except Exception as e:
        logger.error(f"❌ Stop-loss placement failed: {e}")
        send_telegram(
            f"🚨 STOP-LOSS FAILED on {datetime.now().strftime('%Y-%m-%d %H:%M')}: {e}. "
            f"Position OPEN with NO STOP PROTECTION. Intervene immediately."
        )
        return None


def cancel_stop_loss(executor, order_id):
    """
    Cancel an existing stop-loss order before placing a new one or selling.
    """
    if executor.dry_run or order_id == 'DRY_RUN_STOP':
        logger.info("DRY RUN — stop-loss cancellation simulated")
        return

    try:
        executor.client.cancel_order(symbol=executor.symbol, orderId=order_id)
        logger.info(f"✅ Stop-loss order {order_id} cancelled")
    except Exception as e:
        logger.warning(f"Could not cancel stop-loss {order_id}: {e}")
        send_telegram(
            f"⚠️ STOP-LOSS CANCEL FAILED on {datetime.now().strftime('%Y-%m-%d %H:%M')}: {e}. "
            f"Order {order_id} may still be active — check for duplicate sell orders on Binance."
        )


def check_stop_loss_triggered(executor, state):
    """
    Check if the stop-loss order has been filled (Binance auto-sold after price crash).
    Returns True if filled, False otherwise.
    STOP_LOSS market fill price: order['price'] = 0; actual = cummulativeQuoteQty / executedQty.
    """
    if not state['stop_loss_order_id'] or state['stop_loss_order_id'] == 'DRY_RUN_STOP':
        return False

    try:
        order = executor.client.get_order(
            symbol  = executor.symbol,
            orderId = state['stop_loss_order_id']
        )
        if order['status'] == 'FILLED':
            fill_price = (float(order['cummulativeQuoteQty']) /
                          float(order['executedQty']))
            pnl_pct    = (fill_price - state['entry_price']) / state['entry_price']
            logger.warning(f"🛑 STOP-LOSS TRIGGERED!")
            logger.warning(f"   Entry: ${state['entry_price']:,.2f}")
            logger.warning(f"   Fill:  ${fill_price:,.2f}")
            logger.warning(f"   P&L:   {pnl_pct:.2%}")
            send_telegram(
                f"🛑 STOP-LOSS HIT on {datetime.now().strftime('%Y-%m-%d %H:%M')}: "
                f"Entry ${state['entry_price']:,.2f} → Fill ${fill_price:,.2f} "
                f"({pnl_pct:+.2%}). Position closed. Now FLAT."
            )
            return True
        return False
    except Exception as e:
        logger.warning(f"Could not check stop-loss status: {e}")
        return False


def update_trailing_stop(executor, state):
    """
    Raise the trailing stop if ETH price has hit a new peak since entry.

    Called on every run (signal and stop_update) when position is LONG.
    Uses get_current_price() (ticker, instant — no candle download needed).

    Logic:
        if current_price > peak: new_stop = current_price × (1 - TRAIL_PCT)
            if new_stop > current_stop: cancel old order, place new, update state
        else: log no-change, no Telegram (avoids noise on quiet runs)

    The new_stop > current_stop guard handles rounding edge cases where a tiny
    new peak produces a stop that rounds to the same value.
    """
    if state['position'] != 'LONG':
        return state

    current_price = executor.get_current_price()
    peak          = state.get('peak_price_since_entry') or state['entry_price']
    current_stop  = state.get('stop_loss_price') or 0.0

    if current_price > peak:
        new_stop = round(current_price * (1 - TRAIL_PCT), 2)

        if new_stop > current_stop:
            logger.info(f"📈 New peak ${current_price:,.2f} (was ${peak:,.2f}) — "
                        f"raising stop ${current_stop:,.2f} → ${new_stop:,.2f}")

            if state['stop_loss_order_id']:
                cancel_stop_loss(executor, state['stop_loss_order_id'])

            sl_result = place_stop_loss(executor, state['position_size_eth'], new_stop)

            if sl_result:
                state['peak_price_since_entry'] = current_price
                state['stop_loss_price']        = new_stop
                state['stop_loss_order_id']     = sl_result['order_id']
                save_state(state)
                send_telegram(
                    f"📈 Trailing stop updated: New peak ${current_price:,.2f}, "
                    f"Stop raised to ${new_stop:,.2f}"
                )
            else:
                send_telegram(
                    f"🚨 TRAILING STOP UPDATE FAILED on "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}: "
                    f"Could not place new stop at ${new_stop:,.2f}. "
                    f"Old stop may be cancelled. Intervene immediately."
                )
        else:
            logger.info(f"Price ${current_price:,.2f} at new peak but new_stop "
                        f"${new_stop:,.2f} ≤ current_stop ${current_stop:,.2f} — no change")
    else:
        logger.info(f"Price ${current_price:,.2f} ≤ peak ${peak:,.2f} — "
                    f"stop unchanged at ${current_stop:,.2f}")

    return state

# ══════════════════════════════════════════════════════════════════════════════
# STOP UPDATE RUN  (06:05, 12:05, 18:05 UTC)
# ══════════════════════════════════════════════════════════════════════════════

def run_stop_update():
    """
    Intraday stop update run. Gets current ETH price and raises trailing stop
    if price has hit a new peak since entry. No entry or exit decisions ever made.
    """
    logger.info("=" * 65)
    logger.info("ADX BOT — STOP UPDATE RUN")
    logger.info(f"  Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Symbol: {SYMBOL}")
    logger.info(f"  Mode:   {'DRY RUN' if DRY_RUN else 'LIVE'}")
    logger.info("=" * 65)

    state = load_state()

    if state['position'] != 'LONG':
        logger.info("Position is FLAT — no trailing stop to update")
        logger.info("=" * 65)
        return

    executor = TradingExecutor(symbol=SYMBOL, dry_run=DRY_RUN, use_testnet=USE_TESTNET)
    check_api_trading_permission(executor)

    update_trailing_stop(executor, state)

    logger.info("=" * 65)

# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL RUN  (00:05 UTC)
# ══════════════════════════════════════════════════════════════════════════════

def run_signal():
    """
    Daily signal run. Full logic: candle fetch, ADX 19/9 signal, entry/exit decisions,
    trailing stop update, health check Telegram.
    """
    logger.info("=" * 65)
    logger.info("ADX PRODUCTION BOT — SIGNAL RUN")
    logger.info(f"  Time:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Symbol:   {SYMBOL}")
    logger.info(f"  Mode:     {'DRY RUN (paper trading)' if DRY_RUN else '⚠️  LIVE TRADING'}")
    logger.info(f"  Exchange: {'Testnet (fake money)' if USE_TESTNET else 'LIVE BINANCE'}")
    logger.info(f"  ADX:      threshold={ADX_THRESHOLD}, period={ADX_PERIOD}")
    logger.info(f"  Trail:    {TRAIL_PCT:.0%}")
    logger.info("=" * 65)

    # ── Step 1: Load state ────────────────────────────────────────────────────
    state = load_state()

    # ── Step 2: Initialise executor ───────────────────────────────────────────
    executor = TradingExecutor(
        symbol      = SYMBOL,
        dry_run     = DRY_RUN,
        use_testnet = USE_TESTNET
    )
    check_api_trading_permission(executor)

    # ── Step 3: Get account balance and price ─────────────────────────────────
    usdt_balance = executor.get_balance('USDT')
    eth_balance  = executor.get_balance('ETH')
    eth_price    = executor.get_current_price()
    portfolio    = usdt_balance + (eth_balance * eth_price)

    logger.info(f"Account: ${usdt_balance:,.2f} USDT | "
                f"{eth_balance:.5f} ETH | "
                f"Portfolio: ${portfolio:,.2f}")

    # ── Step 4: Initialise RiskManager ───────────────────────────────────────
    rm = RiskManager(config=RISK_CONFIG, initial_balance=portfolio)

    # ── Step 5: Check if stop-loss was triggered since last run ───────────────
    if state['position'] == 'LONG':
        stop_triggered = check_stop_loss_triggered(executor, state)
        if stop_triggered:
            pnl_pct = (state['stop_loss_price'] - state['entry_price']) / state['entry_price']
            pnl_usd = (state['position_size_usdt'] or 0) * pnl_pct
            rm.record_trade(pnl=pnl_usd)
            state = DEFAULT_STATE.copy()
            state['position'] = 'FLAT'
            save_state(state)
            logger.info("Position closed by stop-loss — now FLAT")

    # ── Step 6: Fetch candles and calculate signal ────────────────────────────
    df          = fetch_candles(executor)
    signal_data = calculate_signal(df)
    signal      = signal_data['signal']
    position    = state['position']

    logger.info(f"Signal: {signal} | Position: {position}")
    logger.info("─" * 65)

    # ── Step 7: Decision logic ────────────────────────────────────────────────

    if position == 'FLAT' and signal == 'LONG':
        # ── ENTRY ─────────────────────────────────────────────────────────────
        logger.info("ACTION: BUY — entering LONG position")

        can_trade, reason = rm.can_trade(current_balance=portfolio)
        if not can_trade:
            logger.warning(f"🛑 TRADE BLOCKED by RiskManager: {reason}")
        else:
            # Kelly sizing: risk Kelly_fraction of capital
            # Position size = (Kelly% × capital) / stop%
            # This ensures maximum loss = Kelly% × capital
            # regardless of stop distance
            position_usdt = rm.calculate_position_size(usdt_balance=usdt_balance)

            buy_result = executor.execute_buy(amount_usdt=position_usdt)

            if buy_result:
                entry_price = buy_result['price']
                eth_bought  = buy_result['quantity']
                stop_price  = round(entry_price * (1 - TRAIL_PCT), 2)

                sl_result = place_stop_loss(executor, eth_bought, stop_price)

                state['position']               = 'LONG'
                state['entry_price']            = entry_price
                state['entry_date']             = datetime.now().strftime('%Y-%m-%d')
                state['stop_loss_price']        = sl_result['stop_price'] if sl_result else None
                state['stop_loss_order_id']     = sl_result['order_id'] if sl_result else None
                state['position_size_usdt']     = position_usdt
                state['position_size_eth']      = eth_bought
                state['peak_price_since_entry'] = entry_price

                save_state(state)
                logger.info(f"✅ LONG entered: {eth_bought:.5f} ETH @ ${entry_price:,.2f}")
                stop_display = (f"${state['stop_loss_price']:,.2f}"
                                if state['stop_loss_price'] else "NONE — place manually")
                logger.info(f"   Stop: {stop_display} (-{TRAIL_PCT:.0%} trail, peak=${entry_price:,.2f})")
                send_telegram(
                    f"✅ BUY EXECUTED on {datetime.now().strftime('%Y-%m-%d')}: "
                    f"{eth_bought:.4f} ETH @ ${entry_price:,.2f}. "
                    f"Trailing stop at ${state['stop_loss_price']:,.2f} (-{TRAIL_PCT:.0%})."
                )
            else:
                send_telegram(
                    f"🚨 BUY FAILED on {datetime.now().strftime('%Y-%m-%d')}: "
                    f"Could not enter LONG. ADX={signal_data['adx']:.1f}. "
                    f"Check Binance API — trading permission may be disabled."
                )

    elif position == 'LONG' and signal == 'FLAT':
        # ── EXIT ──────────────────────────────────────────────────────────────
        logger.info("ACTION: SELL — exiting LONG position (trend faded)")

        if state['stop_loss_order_id']:
            cancel_stop_loss(executor, state['stop_loss_order_id'])

        sell_result = executor.execute_sell(quantity=state['position_size_eth'])

        if sell_result:
            exit_price = sell_result['price']
            pnl_pct    = (exit_price - state['entry_price']) / state['entry_price']
            pnl_usd    = (state['position_size_usdt'] or 0) * pnl_pct

            rm.record_trade(pnl=pnl_usd)
            logger.info(f"✅ LONG closed: @ ${exit_price:,.2f} | "
                        f"P&L: {pnl_pct:.2%} (${pnl_usd:+,.2f})")

            state = DEFAULT_STATE.copy()
            state['position'] = 'FLAT'
            save_state(state)
            send_telegram(
                f"✅ SELL EXECUTED on {datetime.now().strftime('%Y-%m-%d')}: "
                f"Closed @ ${exit_price:,.2f} | "
                f"P&L: {pnl_pct:+.2%} (${pnl_usd:+,.2f}). Now FLAT."
            )
        else:
            send_telegram(
                f"🚨 SELL FAILED on {datetime.now().strftime('%Y-%m-%d')}: "
                f"Could not exit LONG position (entry ${state['entry_price']:,.2f}). "
                f"Stop-loss may be cancelled. Check Binance immediately."
            )

    elif position == 'LONG' and signal == 'LONG':
        # ── HOLD + TRAILING STOP UPDATE ───────────────────────────────────────
        logger.info("ACTION: HOLD — maintaining LONG position")
        peak = state.get('peak_price_since_entry') or state['entry_price']
        logger.info(f"  Entry:     ${state['entry_price']:,.2f} on {state['entry_date']}")
        logger.info(f"  Current:   ${eth_price:,.2f}")
        logger.info(f"  Peak:      ${peak:,.2f}")
        unrealised = (eth_price - state['entry_price']) / state['entry_price']
        logger.info(f"  Unrealised P&L: {unrealised:+.2%}")
        stop_display = f"${state['stop_loss_price']:,.2f}" if state['stop_loss_price'] else "NONE"
        logger.info(f"  Stop:      {stop_display} (-{TRAIL_PCT:.0%} trail)")

        # Update trailing stop if price at new peak
        state = update_trailing_stop(executor, state)

    else:
        # ── WAIT ──────────────────────────────────────────────────────────────
        logger.info("ACTION: WAIT — no trend signal, holding cash")
        logger.info(f"  ADX {signal_data['adx']:.2f} below threshold {ADX_THRESHOLD}")

    # ── Step 8: Final status ──────────────────────────────────────────────────
    logger.info("─" * 65)
    rm.get_status(current_balance=portfolio)
    logger.info("=" * 65)

    # ── Step 9: Daily health check Telegram ──────────────────────────────────
    # Sent every signal run. Absence by 00:10 UTC = bot did not run — investigate.
    send_telegram(
        f"✅ Bot ran {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} [signal]: "
        f"ADX={signal_data['adx']:.1f}, Signal={signal}, Position={position}, "
        f"Balance=${usdt_balance:,.2f} USDT | ${portfolio:,.2f} total"
    )


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ADX Production Bot — ETH/USDT')
    parser.add_argument(
        '--mode',
        choices=['signal', 'stop_update'],
        default='signal',
        help='signal: full ADX run at 00:05 UTC | stop_update: trailing stop check only'
    )
    args = parser.parse_args()

    if args.mode == 'stop_update':
        run_stop_update()
    else:
        run_signal()
