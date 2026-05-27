# [FILE] rsi_production_bot.py
# PURPOSE: Production RSI mean-reversion bot — ETH/USDT on Binance Spot
#
# STRATEGY:
#   Entry: RSI(14) drops below 43 AND ETH closing price > 120-day SMA
#   Exit:  RSI(14) rises above 48 (mean reversion complete)
#   Stop:  15% fixed STOP_LOSS market order placed at entry
#
# POSITION SIZING (Half-Kelly):
#   Backtest Kelly f* = 76.7% at 93.5% win rate
#   Half-Kelly = 38.4%
#   Position = (0.384 × capital) / 0.15 = $384 → capped at capital − $5
#   Initial capital: $150 (validation deployment — see scale-up logic below)
#
# SCALE-UP LOGIC (read comments in run_signal before adjusting):
#   SCALE-UP: increase reserved_capital to $341 in portfolio_state.json
#             when live_trades >= 20 AND live_win_rate >= 0.80
#   STOP:     pause bot (DRY_RUN = True) when live_trades >= 20
#             AND live_win_rate < 0.72 (approaching Kelly breakeven)
#
# RUNS: 00:06 UTC daily via cron (one minute after ADX bot at 00:05)
# DATA: yfinance ETH-USD daily (primary — no Binance klines dependency)
# STOP TYPE: STOP_LOSS (market execution, guaranteed fill on trigger)
#
# DRY_RUN = True  → simulate only, no real orders
# DRY_RUN = False → real orders on live Binance

import sys
import os
import json
import math
import logging
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
import requests
import warnings
warnings.filterwarnings('ignore')

# ── Path setup ────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, '05_BOTS', 'core', 'execution'))
sys.path.insert(0, BASE_DIR)

from trading_executor import TradingExecutor
from portfolio_manager import (
    get_my_capital, update_position,
    get_portfolio_summary, record_trade_result
)

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

DRY_RUN     = False
USE_TESTNET = False

SYMBOL        = 'ETHUSDT'
TICKER        = 'ETH-USD'           # yfinance ticker
STRATEGY_NAME = 'eth_rsi'

RSI_PERIOD  = 14
ENTRY_RSI   = 43                    # Enter when RSI drops below this
EXIT_RSI    = 48                    # Exit when RSI rises above this
SMA_PERIOD  = 120                   # Regime filter: only trade above 120-day SMA
STOP_PCT    = 0.15                  # 15% fixed stop from entry price
HALF_KELLY  = 0.384                 # 38.4% = half of 76.7% backtest Kelly fraction
CANDLES_NEEDED = SMA_PERIOD + RSI_PERIOD + 30  # ~164 days

STATE_FILE = os.path.join(BASE_DIR, '07_DATA', 'rsi_bot_state.json')

TELEGRAM_TOKEN   = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# ══════════════════════════════════════════════════════════════════════════════
# TELEGRAM ALERTING
# ══════════════════════════════════════════════════════════════════════════════

def send_telegram(message):
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
    if executor.dry_run:
        return True
    try:
        executor.client.create_test_order(
            symbol='ETHUSDT', side='BUY', type='MARKET', quantity=0.01
        )
        logger.info("✅ API trading permission confirmed")
        return True
    except Exception as e:
        code = getattr(e, 'code', None)
        if code == -2015:
            msg = (f"🚨 API TRADING PERMISSION DENIED on "
                   f"{datetime.now().strftime('%Y-%m-%d')} — bot cannot trade. "
                   f"Go to Binance → API Management → enable Spot & Margin Trading.")
            logger.error(msg)
            send_telegram(msg)
            return False
        logger.info(f"✅ API trading permission confirmed (filter: {getattr(e, 'code', e)})")
        return True

# ══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_STATE = {
    'position':           'FLAT',
    'entry_price':        None,
    'entry_date':         None,
    'stop_loss_price':    None,
    'stop_loss_order_id': None,
    'position_size_usdt': None,
    'position_size_eth':  None,
    'last_updated':       None,
}

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
        logger.info(f"State loaded: position={state['position']}")
        if state['entry_price']:
            logger.info(f"  Entry: ${state['entry_price']:,.2f} on {state['entry_date']}")
            logger.info(f"  Stop:  ${state['stop_loss_price']:,.2f}")
        return state
    logger.info("No state file — starting fresh (FLAT)")
    return DEFAULT_STATE.copy()

def save_state(state):
    state['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)
    logger.info(f"State saved: position={state['position']}")

# ══════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ══════════════════════════════════════════════════════════════════════════════

def fetch_candles():
    """
    Fetch daily ETH candles from yfinance.
    Returns DataFrame with OHLCV columns and DatetimeIndex.
    Needs ~165 rows for RSI(14) + SMA(120) + buffer.
    """
    df = yf.download(TICKER, period='250d', interval='1d',
                     auto_adjust=True, progress=False)
    if hasattr(df.columns, 'get_level_values'):
        df.columns = df.columns.get_level_values(0)
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df = df.dropna()

    if len(df) < CANDLES_NEEDED:
        raise RuntimeError(f"Only {len(df)} candles fetched — need {CANDLES_NEEDED}")

    logger.info(f"Candles: {len(df)} daily bars "
                f"({df.index[0].date()} → {df.index[-1].date()})")
    return df

# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL CALCULATION
# ══════════════════════════════════════════════════════════════════════════════

def calculate_signal(df):
    """
    Calculate RSI(14) and 120-day SMA on daily ETH closes.
    Entry: RSI < 43 AND close > SMA120 (oversold in uptrend)
    Exit:  RSI > 48 (mean reversion complete)
    """
    close = df['Close'].squeeze()

    rsi_ind   = RSIIndicator(close=close, window=RSI_PERIOD)
    df        = df.copy()
    df['rsi'] = rsi_ind.rsi()
    df['sma'] = close.rolling(SMA_PERIOD).mean()

    current_rsi   = float(df['rsi'].iloc[-1])
    current_price = float(df['Close'].iloc[-1])
    current_sma   = float(df['sma'].iloc[-1])

    above_sma    = current_price > current_sma
    entry_signal = current_rsi < ENTRY_RSI and above_sma
    exit_signal  = current_rsi > EXIT_RSI

    if entry_signal:
        signal_str = 'ENTRY'
    elif exit_signal:
        signal_str = 'EXIT'
    else:
        signal_str = 'FLAT'

    logger.info(f"RSI: {current_rsi:.2f} | SMA120: ${current_sma:,.2f} | "
                f"Price: ${current_price:,.2f} | "
                f"{'ABOVE' if above_sma else 'BELOW'} SMA | Signal: {signal_str}")

    return {
        'signal':       signal_str,
        'entry':        entry_signal,
        'exit':         exit_signal,
        'rsi':          round(current_rsi, 2),
        'sma120':       round(current_sma, 2),
        'above_sma':    above_sma,
        'price':        round(current_price, 2),
    }

# ══════════════════════════════════════════════════════════════════════════════
# STOP-LOSS MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def place_stop_loss(executor, quantity, stop_price):
    """
    Place STOP_LOSS (market) sell order. Floors quantity to 3dp to avoid -2010.
    Returns {order_id, stop_price, quantity} or None on failure.
    """
    quantity = math.floor(quantity * 1000) / 1000
    logger.info(f"Placing stop-loss: {quantity} ETH @ ${stop_price:,.2f}")

    if executor.dry_run:
        logger.info("DRY RUN — stop-loss simulated")
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
        logger.info(f"✅ Stop placed: ID {order['orderId']} @ ${stop_price:,.2f}")
        return {'order_id': order['orderId'], 'stop_price': stop_price, 'quantity': quantity}
    except Exception as e:
        logger.error(f"❌ Stop placement failed: {e}")
        send_telegram(
            f"🚨 RSI BOT — STOP-LOSS FAILED on "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}: {e}. "
            f"Position OPEN with NO STOP PROTECTION. Intervene immediately."
        )
        return None


def cancel_stop_loss(executor, order_id):
    if executor.dry_run or order_id == 'DRY_RUN_STOP':
        logger.info("DRY RUN — stop cancellation simulated")
        return
    try:
        executor.client.cancel_order(symbol=executor.symbol, orderId=order_id)
        logger.info(f"✅ Stop order {order_id} cancelled")
    except Exception as e:
        logger.warning(f"Could not cancel stop {order_id}: {e}")
        send_telegram(
            f"⚠️ RSI BOT — STOP CANCEL FAILED on "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}: {e}. "
            f"Order {order_id} may still be active — check Binance."
        )


def verify_stop_order(executor, state):
    """
    Verify resting stop-loss is still active on Binance.
    Called at the start of every run when position is LONG.

    Outcomes:
      NEW      → stop active, return True
      FILLED   → stop triggered offline; state→FLAT, Telegram sent, return False
      other    → stop cancelled; re-place immediately, alert, return True
      no ID    → critical alert, return False
      error    → alert, return False

    Mutates state dict in-place on FILLED.
    """
    if state['position'] != 'LONG':
        return True

    if executor.dry_run:
        logger.info("DRY RUN — stop verification skipped")
        return True

    order_id = state.get('stop_loss_order_id')
    if not order_id:
        msg = (f"🚨 RSI BOT CRITICAL on {datetime.now().strftime('%Y-%m-%d %H:%M')}: "
               f"Position LONG but no stop order ID in state file. "
               f"Place stop manually on Binance immediately.")
        logger.error(msg)
        send_telegram(msg)
        return False

    try:
        order  = executor.client.get_order(symbol=SYMBOL, orderId=order_id)
        status = order['status']

        if status == 'NEW':
            logger.info(f"✅ Stop order {order_id} verified active "
                        f"@ ${state.get('stop_loss_price', 0):,.2f}")
            return True

        elif status == 'FILLED':
            fill_price = (float(order['cummulativeQuoteQty']) /
                          float(order['executedQty']))
            pnl_pct = (fill_price - state['entry_price']) / state['entry_price']
            logger.warning(f"🛑 Stop {order_id} FILLED at ${fill_price:,.2f} "
                           f"({pnl_pct:+.2%}) while bot was offline")
            send_telegram(
                f"✅ RSI BOT — Stop-loss triggered and filled on "
                f"{datetime.now().strftime('%Y-%m-%d %H:%M')}: "
                f"Entry ${state['entry_price']:,.2f} → Fill ${fill_price:,.2f} "
                f"({pnl_pct:+.2%}). Position closed. Now FLAT."
            )
            # Record the trade
            stats = record_trade_result(
                STRATEGY_NAME, state['entry_date'],
                datetime.now().strftime('%Y-%m-%d'),
                pnl_pct, 'STOP_LOSS'
            )
            _check_performance_alerts(stats)
            # Reset state in-place
            for k, v in DEFAULT_STATE.items():
                state[k] = v
            state['position'] = 'FLAT'
            save_state(state)
            update_position(STRATEGY_NAME, 'FLAT', None, 0, 0)
            return False

        else:
            stop_price = state.get('stop_loss_price') or round(
                state['entry_price'] * (1 - STOP_PCT), 2
            )
            logger.error(f"🚨 Stop {order_id} status is '{status}' — replacing")
            sl_result = place_stop_loss(executor, state['position_size_eth'], stop_price)
            if sl_result:
                state['stop_loss_order_id'] = sl_result['order_id']
                save_state(state)
                send_telegram(
                    f"🚨 RSI BOT — Stop order {order_id} was {status} by Binance on "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M')}. "
                    f"Replacement placed at ${stop_price:,.2f}."
                )
            else:
                send_telegram(
                    f"🚨 RSI BOT CRITICAL on {datetime.now().strftime('%Y-%m-%d %H:%M')}: "
                    f"Stop {order_id} was {status} AND replacement failed. "
                    f"Position UNPROTECTED — intervene on Binance immediately."
                )
            return True

    except Exception as e:
        logger.error(f"Cannot verify stop {order_id}: {e}")
        send_telegram(
            f"🚨 RSI BOT — Cannot verify stop order {order_id} on "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}: {e}. "
            f"Check position on Binance manually."
        )
        return False

# ══════════════════════════════════════════════════════════════════════════════
# PERFORMANCE MONITORING
# ══════════════════════════════════════════════════════════════════════════════

def _check_performance_alerts(stats):
    """
    Send Telegram alerts if live performance metrics breach thresholds.
    Called after every trade closes.
    """
    n  = stats['n_trades']
    wr = stats['win_rate']
    cl = stats['consecutive_losses']

    if cl >= 3:
        send_telegram(
            f"⚠️ RSI BOT — {cl} consecutive losing trades. "
            f"Running win rate: {wr:.1%} over {n} trades. Review required."
        )
    # Win rate monitoring (minimum 10 trades before flagging)
    if n >= 10 and wr < 0.72:
        send_telegram(
            f"🚨 RSI BOT — Running win rate {wr:.1%} over {n} trades is BELOW "
            f"Kelly breakeven (72.2%). Strategy has negative expectancy at this win rate. "
            f"Consider pausing — see RR-RSI-001."
        )
    elif n >= 10 and wr < 0.80:
        send_telegram(
            f"⚠️ RSI BOT — Running win rate {wr:.1%} over {n} trades. "
            f"Below 80% threshold for position size scale-up."
        )

    # SCALE-UP: increase reserved_capital to $341 in portfolio_state.json
    # when live_trades >= 20 AND live_win_rate >= 0.80
    # Run manually: edit portfolio_state.json eth_rsi.reserved_capital to 341
    # and cash_held to 341, then restart bot.

    # STOP: pause bot when live_trades >= 20 AND live_win_rate < 0.72
    # Set DRY_RUN = True and send_telegram("RSI bot paused — win rate below threshold")

# ══════════════════════════════════════════════════════════════════════════════
# MAIN SIGNAL RUN  (00:06 UTC daily)
# ══════════════════════════════════════════════════════════════════════════════

def run_signal():
    logger.info("=" * 65)
    logger.info("RSI PRODUCTION BOT — SIGNAL RUN")
    logger.info(f"  Time:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Symbol:   {SYMBOL}")
    logger.info(f"  Mode:     {'DRY RUN' if DRY_RUN else '⚠️  LIVE TRADING'}")
    logger.info(f"  Exchange: {'Testnet' if USE_TESTNET else 'LIVE BINANCE'}")
    logger.info(f"  RSI:      entry<{ENTRY_RSI}, exit>{EXIT_RSI}, period={RSI_PERIOD}")
    logger.info(f"  SMA:      {SMA_PERIOD}-day regime filter")
    logger.info(f"  Stop:     {STOP_PCT:.0%} fixed")
    logger.info("=" * 65)

    # ── Step 1: Load state ────────────────────────────────────────────────────
    state = load_state()

    # ── Step 2: Initialise executor ───────────────────────────────────────────
    executor = TradingExecutor(
        symbol=SYMBOL, dry_run=DRY_RUN, use_testnet=USE_TESTNET
    )
    check_api_trading_permission(executor)

    # ── Step 2.5: Verify stop order is still active ───────────────────────────
    # Catches silent Binance cancellations. Handles FILLED (offline stop trigger)
    # and CANCELLED (re-places immediately). See RR-RSI-002.
    verify_stop_order(executor, state)

    # ── Step 3: Get account balance and price ─────────────────────────────────
    usdt_balance = executor.get_balance('USDT')
    eth_balance  = executor.get_balance('ETH')
    eth_price    = executor.get_current_price()

    logger.info(f"Account: ${usdt_balance:,.2f} USDT | "
                f"{eth_balance:.5f} ETH | "
                f"ETH price: ${eth_price:,.2f}")

    # ── Step 4: Fetch candles and calculate signal ────────────────────────────
    df          = fetch_candles()
    signal_data = calculate_signal(df)
    position    = state['position']

    logger.info(f"Signal: {signal_data['signal']} | Position: {position}")
    logger.info("─" * 65)

    # ── Step 5: Decision logic ────────────────────────────────────────────────

    if position == 'FLAT' and signal_data['entry']:
        # ── ENTRY ─────────────────────────────────────────────────────────────
        logger.info("ACTION: BUY — RSI oversold entry signal")

        # Half-Kelly sizing (see header for rationale)
        # Position = (HALF_KELLY × capital) / STOP_PCT → capped at capital − $5
        capital       = get_my_capital(STRATEGY_NAME)
        position_usdt = min(capital - 5, (HALF_KELLY * capital) / STOP_PCT)
        logger.info(f"Sizing: capital=${capital:.2f}, "
                    f"half-Kelly={HALF_KELLY:.1%}, stop={STOP_PCT:.0%} → "
                    f"${position_usdt:.2f}")

        buy_result = executor.execute_buy(amount_usdt=position_usdt)

        if buy_result:
            entry_price = buy_result['price']
            eth_bought  = buy_result['quantity']
            stop_price  = round(entry_price * (1 - STOP_PCT), 2)

            sl_result = place_stop_loss(executor, eth_bought, stop_price)

            state['position']           = 'LONG'
            state['entry_price']        = entry_price
            state['entry_date']         = datetime.now().strftime('%Y-%m-%d')
            state['stop_loss_price']    = sl_result['stop_price'] if sl_result else None
            state['stop_loss_order_id'] = sl_result['order_id'] if sl_result else None
            state['position_size_usdt'] = position_usdt
            state['position_size_eth']  = eth_bought

            save_state(state)
            update_position(STRATEGY_NAME, 'LONG', entry_price, eth_bought, position_usdt)

            stop_display = (f"${state['stop_loss_price']:,.2f}"
                            if state['stop_loss_price'] else "NONE — place manually")
            logger.info(f"✅ LONG entered: {eth_bought:.5f} ETH @ ${entry_price:,.2f} | "
                        f"Stop: {stop_display}")
            send_telegram(
                f"✅ RSI BOT BUY on {datetime.now().strftime('%Y-%m-%d')}: "
                f"{eth_bought:.4f} ETH @ ${entry_price:,.2f}. "
                f"RSI={signal_data['rsi']:.1f}. "
                f"Fixed stop at ${state['stop_loss_price']:,.2f} (-{STOP_PCT:.0%})."
            )
        else:
            send_telegram(
                f"🚨 RSI BOT BUY FAILED on {datetime.now().strftime('%Y-%m-%d')}: "
                f"RSI={signal_data['rsi']:.1f} — entry signal fired but order failed. "
                f"Check Binance API."
            )

    elif position == 'LONG' and signal_data['exit']:
        # ── EXIT ──────────────────────────────────────────────────────────────
        logger.info("ACTION: SELL — RSI exit signal (mean reversion complete)")

        if state['stop_loss_order_id']:
            cancel_stop_loss(executor, state['stop_loss_order_id'])

        sell_result = executor.execute_sell(quantity=state['position_size_eth'])

        if sell_result:
            exit_price = sell_result['price']
            pnl_pct    = (exit_price - state['entry_price']) / state['entry_price']
            pnl_usd    = (state['position_size_usdt'] or 0) * pnl_pct

            stats = record_trade_result(
                STRATEGY_NAME, state['entry_date'],
                datetime.now().strftime('%Y-%m-%d'),
                pnl_pct, 'RSI_EXIT'
            )
            _check_performance_alerts(stats)

            logger.info(f"✅ LONG closed: @ ${exit_price:,.2f} | "
                        f"P&L: {pnl_pct:.2%} (${pnl_usd:+,.2f}) | "
                        f"Live trades: {stats['n_trades']} | "
                        f"Win rate: {stats['win_rate']:.1%}")

            state = DEFAULT_STATE.copy()
            state['position'] = 'FLAT'
            save_state(state)
            update_position(STRATEGY_NAME, 'FLAT', None, 0, 0)

            send_telegram(
                f"✅ RSI BOT SELL on {datetime.now().strftime('%Y-%m-%d')}: "
                f"Closed @ ${exit_price:,.2f} | "
                f"P&L: {pnl_pct:+.2%} (${pnl_usd:+,.2f}). Now FLAT. "
                f"Live: {stats['n_trades']} trades, {stats['win_rate']:.1%} WR."
            )
        else:
            send_telegram(
                f"🚨 RSI BOT SELL FAILED on {datetime.now().strftime('%Y-%m-%d')}: "
                f"Could not exit LONG (entry ${state['entry_price']:,.2f}). "
                f"Stop may be cancelled. Check Binance immediately."
            )

    elif position == 'LONG':
        # ── HOLD ──────────────────────────────────────────────────────────────
        logger.info("ACTION: HOLD — in position, no exit signal yet")
        pnl_pct = (eth_price - state['entry_price']) / state['entry_price']
        pnl_usd = (state['position_size_eth'] or 0) * (eth_price - state['entry_price'])
        logger.info(f"  Entry:   ${state['entry_price']:,.2f} on {state['entry_date']}")
        logger.info(f"  Current: ${eth_price:,.2f}")
        logger.info(f"  P&L:     {pnl_pct:+.2%} (${pnl_usd:+,.2f})")
        logger.info(f"  Stop:    ${state['stop_loss_price']:,.2f} (-{STOP_PCT:.0%})")

    else:
        # ── WAIT ──────────────────────────────────────────────────────────────
        logger.info("ACTION: WAIT — no entry signal")
        logger.info(f"  RSI {signal_data['rsi']:.2f} not below {ENTRY_RSI} "
                    f"{'(SMA filter OK)' if signal_data['above_sma'] else '(BELOW SMA — regime filter active)'}")

    # ── Step 6: Daily health check Telegram ──────────────────────────────────
    # Sent every run. Absence by 00:10 UTC = bot did not run — investigate.
    rsi_val = signal_data['rsi']
    sig     = signal_data['signal']
    if state['position'] == 'FLAT':
        signal_display = f"WAITING | RSI={rsi_val:.1f} | entry <{ENTRY_RSI} | exit >{EXIT_RSI}"
    elif sig == 'EXIT':
        signal_display = f"EXIT | RSI={rsi_val:.1f} above {EXIT_RSI} | entry <{ENTRY_RSI}"
    else:
        signal_display = f"HOLDING | RSI={rsi_val:.1f} | entry <{ENTRY_RSI} | exit >{EXIT_RSI}"

    hc_lines = [
        f"✅ RSI Bot ran {datetime.now().strftime('%Y-%m-%d')} 00:06 UTC",
        f"Signal: {signal_display}",
    ]
    if state['position'] == 'LONG' and state['entry_price']:
        eth_qty = state.get('position_size_eth') or eth_balance
        entry_p = state['entry_price']
        stop_p  = state.get('stop_loss_price') or 0.0
        pnl_pct = (eth_price - entry_p) / entry_p
        pnl_usd = eth_qty * (eth_price - entry_p)
        hc_lines += [
            f"Position: LONG {eth_qty:.3f} ETH @ ${entry_p:,.2f} entry",
            f"Current: ${eth_price:,.2f}",
            f"P&L: {pnl_pct:+.1%} (${pnl_usd:+.2f})",
            f"Exit target: RSI > {EXIT_RSI} (current {rsi_val:.1f})",
            f"Stop: ${stop_p:,.2f} (-{STOP_PCT:.0%} fixed)",
            f"Cash: ${usdt_balance:,.2f} USDT",
        ]
    else:
        hc_lines += [
            f"Position: FLAT",
            f"Cash: ${usdt_balance:,.2f} USDT",
        ]
    hc_lines.append(get_portfolio_summary(executor.client))
    send_telegram("\n".join(hc_lines))

    logger.info("=" * 65)

# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    run_signal()
