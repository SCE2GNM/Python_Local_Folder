# [IMPORT] asyncio for WebSocket connection
import asyncio

# [IMPORT] websockets for stable Binance connection
import websockets

# [IMPORT] json for decoding messages and reading log files
import json

# [IMPORT] pandas for candle storage and ADX calculation
import pandas as pd

# [IMPORT] ADXIndicator from ta library
from ta.trend import ADXIndicator

# [IMPORT] deque for rolling candle buffer
from collections import deque

# [IMPORT] Binance REST client for historical bootstrap
from binance.client import Client

# [IMPORT] requests for sending Telegram messages
import requests

# [IMPORT] dotenv to load API keys
from dotenv import load_dotenv

# [IMPORT] os for environment variables
import os

# [IMPORT] datetime for timestamps
from datetime import datetime

# [IMPORT] pathlib for log file paths
from pathlib import Path

# [IMPORT] csv for trade logging
import csv

# [FUNCTION CALL] Load keys from .env
load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================

# [VARIABLE - string] Trading pair
SYMBOL = 'ETHUSDT'

# [VARIABLE - int] Optimised ADX period from Week 2
ADX_PERIOD = 10

# [VARIABLE - int] Optimised ADX threshold from Week 2
ADX_THRESHOLD = 20

# [VARIABLE - int] Rolling candle buffer size
LOOKBACK = 100

# [VARIABLE - float] Simulated position size (paper trading)
POSITION_SIZE_ETH = 1.0

# ============================================================
# TELEGRAM SETUP
# ============================================================

# [VARIABLE - string] Bot token from .env
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# [VARIABLE - string] Your chat ID from .env
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# [VARIABLE - string] Telegram API endpoint
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def send_telegram(message):
    """
    Send a message to your Telegram chat.
    
    Called whenever something important happens:
    - Signal changes
    - Position opens or closes
    - Connection drops
    - Session ends
    
    Uses try/except so a failed message never crashes the bot.
    Think of it like a pager that beeps when something happens —
    if the pager battery dies, the trading system keeps running.
    """
    try:
        payload = {
            'chat_id':    CHAT_ID,
            'text':       message,
            'parse_mode': 'HTML'  # Allows bold, italic formatting
        }
        response = requests.post(TELEGRAM_URL, data=payload, timeout=5)
        
        if response.status_code == 200:
            print(f"   📱 Telegram alert sent")
        else:
            print(f"   ⚠️ Telegram failed: {response.status_code}")
    
    except Exception as e:
        # [EXCEPTION] Log but don't crash if Telegram fails
        print(f"   ⚠️ Telegram error: {e}")

# ============================================================
# LOG FILE SETUP
# ============================================================

# [OBJECT - Path] Logs directory
logs_dir = Path('logs')
logs_dir.mkdir(exist_ok=True)

# [VARIABLE - string] Today's date
today = datetime.now().strftime('%Y-%m-%d')

# [VARIABLE - Path] Trade log CSV
TRADE_LOG_PATH = logs_dir / 'trade_log.csv'

# [VARIABLE - Path] Performance JSON
PERFORMANCE_LOG_PATH = logs_dir / 'performance.json'

# ============================================================
# LOG INITIALISATION
# ============================================================

def initialise_trade_log():
    """Create trade log CSV with headers if it doesn't exist."""
    if not TRADE_LOG_PATH.exists():
        with open(TRADE_LOG_PATH, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'session_date', 'entry_time', 'exit_time',
                'entry_price', 'exit_price', 'position_size_eth',
                'pnl_usd', 'pnl_pct', 'duration_minutes', 'exit_reason'
            ])

def initialise_performance_log():
    """Create or load performance JSON."""
    if not PERFORMANCE_LOG_PATH.exists():
        perf = {
            'total_trades':    0,
            'winning_trades':  0,
            'losing_trades':   0,
            'total_pnl_usd':   0.0,
            'best_trade_usd':  0.0,
            'worst_trade_usd': 0.0,
            'win_rate_pct':    0.0,
            'last_updated':    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(PERFORMANCE_LOG_PATH, 'w') as f:
            json.dump(perf, f, indent=2)
        return perf
    else:
        with open(PERFORMANCE_LOG_PATH, 'r') as f:
            return json.load(f)

# ============================================================
# TRADE LOGGING
# ============================================================

def log_trade(entry_time, exit_time, entry_price,
              exit_price, pnl_usd, pnl_pct, exit_reason):
    """Append completed trade to CSV and update performance."""
    
    fmt = '%H:%M'
    try:
        t1 = datetime.strptime(entry_time, fmt)
        t2 = datetime.strptime(exit_time, fmt)
        duration = int((t2 - t1).total_seconds() / 60)
    except:
        duration = 0
    
    with open(TRADE_LOG_PATH, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            today, entry_time, exit_time,
            round(entry_price, 2), round(exit_price, 2),
            POSITION_SIZE_ETH, round(pnl_usd, 2),
            round(pnl_pct, 4), duration, exit_reason
        ])
    
    update_performance(pnl_usd)

def update_performance(pnl_usd):
    """Update running performance metrics."""
    with open(PERFORMANCE_LOG_PATH, 'r') as f:
        perf = json.load(f)
    
    perf['total_trades']  += 1
    perf['total_pnl_usd']  = round(perf['total_pnl_usd'] + pnl_usd, 2)
    perf['last_updated']   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if pnl_usd > 0:
        perf['winning_trades'] += 1
        if pnl_usd > perf['best_trade_usd']:
            perf['best_trade_usd'] = round(pnl_usd, 2)
    else:
        perf['losing_trades'] += 1
        if pnl_usd < perf['worst_trade_usd']:
            perf['worst_trade_usd'] = round(pnl_usd, 2)
    
    if perf['total_trades'] > 0:
        perf['win_rate_pct'] = round(
            (perf['winning_trades'] / perf['total_trades']) * 100, 1
        )
    
    with open(PERFORMANCE_LOG_PATH, 'w') as f:
        json.dump(perf, f, indent=2)

# ============================================================
# POSITION TRACKING
# ============================================================

# [VARIABLE - string] Current position state
position_state = 'FLAT'

# [VARIABLE - float] Entry price
entry_price = None

# [VARIABLE - string] Entry time
entry_time = None

# [VARIABLE - string] Previous signal (to detect changes)
previous_signal = None

# [LIST] Session trades
session_trades = []

# [VARIABLE] Last known price/time for force-close
last_price = None
last_time  = None

def open_position(price, time):
    """Open LONG position and send Telegram alert."""
    global position_state, entry_price, entry_time
    
    position_state = 'LONG'
    entry_price    = price
    entry_time     = time
    
    print(f"\n{'='*70}")
    print(f"🟢 POSITION OPENED")
    print(f"   Time:  {time} | Price: ${price:,.2f}")
    print(f"{'='*70}\n")
    
    # [FUNCTION CALL] Send Telegram alert
    send_telegram(
        f"🟢 <b>POSITION OPENED</b>\n"
        f"Time: {time}\n"
        f"Entry Price: ${price:,.2f}\n"
        f"Size: {POSITION_SIZE_ETH} ETH\n"
        f"Value: ${price * POSITION_SIZE_ETH:,.2f}\n"
        f"ADX Strategy: {ADX_THRESHOLD}/{ADX_PERIOD}"
    )

def close_position(price, time, reason):
    """Close LONG position, calculate P&L, log, and send alert."""
    global position_state, entry_price, entry_time
    
    pnl_usd   = (price - entry_price) * POSITION_SIZE_ETH
    pnl_pct   = ((price - entry_price) / entry_price) * 100
    pnl_emoji = "💰" if pnl_usd >= 0 else "📉"
    
    print(f"\n{'='*70}")
    print(f"🔴 POSITION CLOSED")
    print(f"   Reason: {reason}")
    print(f"   Entry:  ${entry_price:,.2f} at {entry_time}")
    print(f"   Exit:   ${price:,.2f} at {time}")
    print(f"   P&L:    {pnl_emoji} ${pnl_usd:+,.2f} ({pnl_pct:+.2f}%)")
    print(f"{'='*70}\n")
    
    # [FUNCTION CALL] Log trade to CSV
    log_trade(entry_time, time, entry_price,
              price, pnl_usd, pnl_pct, reason)
    
    # [FUNCTION CALL] Send Telegram alert
    send_telegram(
        f"🔴 <b>POSITION CLOSED</b>\n"
        f"Reason: {reason}\n"
        f"Entry: ${entry_price:,.2f} at {entry_time}\n"
        f"Exit: ${price:,.2f} at {time}\n"
        f"P&L: {pnl_emoji} ${pnl_usd:+,.2f} ({pnl_pct:+.2f}%)"
    )
    
    session_trades.append({
        'entry_time':  entry_time,
        'exit_time':   time,
        'entry_price': entry_price,
        'exit_price':  price,
        'pnl_usd':     round(pnl_usd, 2),
        'pnl_pct':     round(pnl_pct, 4),
        'reason':      reason
    })
    
    position_state = 'FLAT'
    entry_price    = None
    entry_time     = None

def update_position(signal, current_price, current_time):
    """
    Core position logic — now also sends alerts when signal changes.
    We only alert on SIGNAL CHANGES, not every candle.
    Otherwise you'd get a Telegram message every minute which
    would become annoying very quickly.
    """
    global previous_signal
    
    # [CONDITIONAL] Detect signal change
    signal_changed = signal != previous_signal
    
    if position_state == 'FLAT':
        
        if signal == 'LONG':
            open_position(current_price, current_time)
        
        else:
            # [CONDITIONAL] Only alert if signal just changed
            if signal_changed and previous_signal is not None:
                send_telegram(
                    f"⚪ <b>SIGNAL CHANGED</b>\n"
                    f"New Signal: {signal}\n"
                    f"Time: {current_time}\n"
                    f"Price: ${current_price:,.2f}\n"
                    f"Status: Waiting for LONG signal"
                )
            print(f"   💤 Waiting for LONG signal... (Current: {signal})")
    
    elif position_state == 'LONG':
        
        if signal == 'LONG':
            unrealised_pnl = (current_price - entry_price) * POSITION_SIZE_ETH
            unrealised_pct = ((current_price - entry_price) / entry_price) * 100
            pnl_emoji = "💰" if unrealised_pnl >= 0 else "📉"
            print(f"   📊 Holding LONG | Entry: ${entry_price:,.2f} | "
                  f"Current: ${current_price:,.2f} | "
                  f"P&L: {pnl_emoji} ${unrealised_pnl:+,.2f} "
                  f"({unrealised_pct:+.2f}%)")
        
        else:
            close_position(current_price, current_time,
                         reason=f"Signal changed to {signal}")
    
    previous_signal = signal

def force_close_on_exit(price, time):
    """Force close open position when script stops."""
    if position_state == 'LONG' and entry_price is not None:
        print(f"\n⚠️  Force-closing open position on exit...")
        close_position(price, time, reason="Script stopped")

def print_session_summary():
    """Print and send session summary via Telegram."""
    
    print(f"\n{'='*70}")
    print(f"SESSION SUMMARY")
    print(f"{'='*70}")
    
    if not session_trades:
        print("No completed trades this session.")
        summary_text = "📊 <b>SESSION ENDED</b>\nNo completed trades this session."
    else:
        session_pnl = sum(t['pnl_usd'] for t in session_trades)
        winners     = sum(1 for t in session_trades if t['pnl_usd'] > 0)
        pnl_emoji   = "💰" if session_pnl >= 0 else "📉"
        
        print(f"Session Trades:  {len(session_trades)}")
        print(f"Session Winners: {winners}/{len(session_trades)}")
        print(f"Session P&L:     ${session_pnl:+,.2f}")
        
        summary_text = (
            f"📊 <b>SESSION ENDED</b>\n"
            f"Trades: {len(session_trades)}\n"
            f"Winners: {winners}/{len(session_trades)}\n"
            f"Session P&L: {pnl_emoji} ${session_pnl:+,.2f}"
        )
    
    # [FUNCTION CALL] Send session summary to Telegram
    send_telegram(summary_text)

# ============================================================
# ADX FUNCTIONS
# ============================================================

def calculate_adx(buffer):
    """Calculate ADX on current candle buffer."""
    df = pd.DataFrame(list(buffer))
    adx_indicator = ADXIndicator(
        high=df['high'],
        low=df['low'],
        close=df['close'],
        window=ADX_PERIOD
    )
    adx      = adx_indicator.adx().iloc[-1]
    plus_di  = adx_indicator.adx_pos().iloc[-1]
    minus_di = adx_indicator.adx_neg().iloc[-1]
    return adx, plus_di, minus_di

def determine_signal(adx, plus_di, minus_di):
    """Apply Week 2 strategy rules."""
    trending = adx >= ADX_THRESHOLD
    bullish  = plus_di > minus_di
    if trending and bullish:
        return "LONG"
    elif trending and not bullish:
        return "BEARISH"
    else:
        return "CHOPPY"

# ============================================================
# BOOTSTRAP
# ============================================================

print("="*70)
print("LIVE ADX BOT WITH TELEGRAM ALERTS")
print("="*70)
print(f"\nParameters: ADX Threshold {ADX_THRESHOLD} | Period {ADX_PERIOD}")
print(f"Position Size: {POSITION_SIZE_ETH} ETH (paper trading)")

initialise_trade_log()
initialise_performance_log()

# [OBJECT] Binance client
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'))

# [VARIABLE] WebSocket URL
URI = "wss://stream.binance.com:9443/ws/ethusdt@kline_1m"

# [OBJECT] Candle buffer
candle_buffer = deque(maxlen=LOOKBACK)

print(f"\nLoading {LOOKBACK} historical candles...")

klines = client.get_historical_klines(
    symbol=SYMBOL,
    interval=Client.KLINE_INTERVAL_1MINUTE,
    limit=LOOKBACK
)

for k in klines:
    candle_buffer.append({
        'timestamp': pd.to_datetime(k[0], unit='ms'),
        'open':      float(k[1]),
        'high':      float(k[2]),
        'low':       float(k[3]),
        'close':     float(k[4]),
        'volume':    float(k[5])
    })

print(f"✅ Loaded {len(candle_buffer)} candles")

adx, plus_di, minus_di = calculate_adx(candle_buffer)
initial_signal = determine_signal(adx, plus_di, minus_di)

print(f"\nInitial Signal: {initial_signal} | "
      f"ADX: {adx:.2f} | +DI: {plus_di:.2f} | -DI: {minus_di:.2f}")

# [FUNCTION CALL] Send startup alert to Telegram
send_telegram(
    f"🤖 <b>ETH Trading Bot Started</b>\n"
    f"Parameters: ADX {ADX_THRESHOLD}/{ADX_PERIOD}\n"
    f"Initial Signal: {initial_signal}\n"
    f"ADX: {adx:.2f} | +DI: {plus_di:.2f} | -DI: {minus_di:.2f}\n"
    f"Position Size: {POSITION_SIZE_ETH} ETH (paper trading)"
)

# ============================================================
# LIVE STREAM
# ============================================================

async def stream_with_alerts():
    """Stream live candles with position tracking and Telegram alerts."""
    global last_price, last_time
    
    print(f"\nStarting live stream with Telegram alerts...")
    print("="*70)
    print(f"{'Time':<8} {'Close':>10} {'ADX':>7} "
          f"{'+DI':>7} {'-DI':>7}  {'Signal':<10}")
    print("-"*70)
    
    reconnect_attempts = 0
    
    while True:
        try:
            async with websockets.connect(URI) as ws:
                reconnect_attempts = 0
                
                while True:
                    raw   = await ws.recv()
                    msg   = json.loads(raw)
                    kline = msg['k']
                    is_closed = kline['x']
                    
                    if is_closed:
                        
                        new_candle = {
                            'timestamp': pd.to_datetime(kline['t'], unit='ms'),
                            'open':      float(kline['o']),
                            'high':      float(kline['h']),
                            'low':       float(kline['l']),
                            'close':     float(kline['c']),
                            'volume':    float(kline['v'])
                        }
                        
                        candle_buffer.append(new_candle)
                        
                        adx, plus_di, minus_di = calculate_adx(candle_buffer)
                        signal = determine_signal(adx, plus_di, minus_di)
                        
                        if signal == 'LONG':
                            signal_display = "🟢 LONG"
                        elif signal == 'BEARISH':
                            signal_display = "🔴 BEARISH"
                        else:
                            signal_display = "⚪ CHOPPY"
                        
                        time_str = new_candle['timestamp'].strftime('%H:%M')
                        last_price = new_candle['close']
                        last_time  = time_str
                        
                        print(f"\r{time_str:<8} "
                              f"${new_candle['close']:>9,.2f} "
                              f"{adx:>7.2f} "
                              f"{plus_di:>7.2f} "
                              f"{minus_di:>7.2f}  "
                              f"{signal_display:<10}          ")
                        
                        update_position(signal, new_candle['close'], time_str)
                    
                    else:
                        current_price = float(kline['c'])
                        current_time  = datetime.fromtimestamp(
                            kline['t'] / 1000).strftime('%H:%M')
                        last_price = current_price
                        last_time  = current_time
                        print(f"\r⏳ [{current_time}] Building candle... "
                              f"Current price: ${current_price:,.2f}          ",
                              end='', flush=True)
        
        except Exception as e:
            reconnect_attempts += 1
            print(f"\n⚠️  Connection error: {e}")
            print(f"   Reconnecting in 5s... (attempt {reconnect_attempts})")
            
            # [CONDITIONAL] Alert if repeated connection failures
            if reconnect_attempts == 3:
                send_telegram(
                    f"⚠️ <b>CONNECTION ISSUES</b>\n"
                    f"Bot has failed to reconnect {reconnect_attempts} times.\n"
                    f"Please check your internet connection."
                )
            
            await asyncio.sleep(5)

# [ENTRY POINT]
try:
    asyncio.run(stream_with_alerts())

except KeyboardInterrupt:
    print("\n")
    if last_price and last_time:
        force_close_on_exit(last_price, last_time)
    print_session_summary()
    print(f"\n📁 Logs saved to: {logs_dir.absolute()}")
    print("✅ Bot stopped.")