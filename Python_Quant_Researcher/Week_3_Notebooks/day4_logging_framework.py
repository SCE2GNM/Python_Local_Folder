import asyncio
import websockets
import json
import pandas as pd
from ta.trend import ADXIndicator
from collections import deque
from binance.client import Client
from dotenv import load_dotenv
import os
from datetime import datetime
import csv
from pathlib import Path

# Load API keys
load_dotenv()

# ============================================================
# CONFIGURATION
# ============================================================
SYMBOL = 'ETHUSDT'
ADX_PERIOD = 10
ADX_THRESHOLD = 20
LOOKBACK = 100
POSITION_SIZE_ETH = 1.0

# ============================================================
# LOG & STATE FILE SETUP
# ============================================================
logs_dir = Path('logs')
logs_dir.mkdir(exist_ok=True)

today = datetime.now().strftime('%Y-%m-%d')
SIGNAL_LOG_PATH = logs_dir / f'signals_{today}.json'
TRADE_LOG_PATH = logs_dir / 'trade_log.csv'
PERFORMANCE_LOG_PATH = logs_dir / 'performance.json'
STATE_FILE_PATH = logs_dir / 'bot_state.json'  # New: Persistence file

# ============================================================
# STATE PERSISTENCE FUNCTIONS
# ============================================================

def save_bot_state(state, price, time):
    """Saves the current position info to a file."""
    state_data = {
        'position_state': state,
        'entry_price': price,
        'entry_time': time
    }
    with open(STATE_FILE_PATH, 'w') as f:
        json.dump(state_data, f)

def load_bot_state():
    """Recalls the position info from the last session."""
    if STATE_FILE_PATH.exists():
        with open(STATE_FILE_PATH, 'r') as f:
            return json.load(f)
    return {'position_state': 'FLAT', 'entry_price': None, 'entry_time': None}

# ============================================================
# INITIALISE LOGS
# ============================================================

def initialise_trade_log():
    if not TRADE_LOG_PATH.exists():
        with open(TRADE_LOG_PATH, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['session_date','entry_time','exit_time','entry_price','exit_price','position_size_eth','pnl_usd','pnl_pct','duration_minutes','exit_reason'])

def initialise_performance_log():
    if not PERFORMANCE_LOG_PATH.exists():
        initial_performance = {
            'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
            'total_pnl_usd': 0.0, 'best_trade_usd': 0.0, 'worst_trade_usd': 0.0,
            'win_rate_pct': 0.0, 'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(PERFORMANCE_LOG_PATH, 'w') as f:
            json.dump(initial_performance, f, indent=2)
        return initial_performance
    else:
        with open(PERFORMANCE_LOG_PATH, 'r') as f:
            return json.load(f)

# ============================================================
# LOGGING & POSITION LOGIC
# ============================================================

# Global variables (Initialized from file)
saved_state = load_bot_state()
position_state = saved_state['position_state']
entry_price = saved_state['entry_price']
entry_time = saved_state['entry_time']
session_trades = []

def log_signal(time_str, close, adx, plus_di, minus_di, signal, position_state):
    record = {
        'time': time_str, 'close': round(close, 2), 'adx': round(adx, 2),
        'plus_di': round(plus_di, 2), 'minus_di': round(minus_di, 2),
        'signal': signal, 'position_state': position_state
    }
    records = json.load(open(SIGNAL_LOG_PATH, 'r')) if SIGNAL_LOG_PATH.exists() else []
    records.append(record)
    with open(SIGNAL_LOG_PATH, 'w') as f:
        json.dump(records, f, indent=2)

def log_trade(entry_time, exit_time, entry_price, exit_price, pnl_usd, pnl_pct, exit_reason):
    fmt = '%H:%M'
    try:
        duration = int((datetime.strptime(exit_time, fmt) - datetime.strptime(entry_time, fmt)).total_seconds() / 60)
    except:
        duration = 0
    with open(TRADE_LOG_PATH, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([today, entry_time, exit_time, round(entry_price, 2), round(exit_price, 2), POSITION_SIZE_ETH, round(pnl_usd, 2), round(pnl_pct, 4), duration, exit_reason])
    update_performance(pnl_usd)

def update_performance(pnl_usd):
    with open(PERFORMANCE_LOG_PATH, 'r') as f:
        perf = json.load(f)
    perf['total_trades'] += 1
    perf['total_pnl_usd'] = round(perf['total_pnl_usd'] + pnl_usd, 2)
    if pnl_usd > 0:
        perf['winning_trades'] += 1
        perf['best_trade_usd'] = max(perf['best_trade_usd'], round(pnl_usd, 2))
    else:
        perf['losing_trades'] += 1
        perf['worst_trade_usd'] = min(perf['worst_trade_usd'], round(pnl_usd, 2))
    perf['win_rate_pct'] = round((perf['winning_trades'] / perf['total_trades']) * 100, 1)
    perf['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(PERFORMANCE_LOG_PATH, 'w') as f:
        json.dump(perf, f, indent=2)

def open_position(price, time):
    global position_state, entry_price, entry_time
    position_state, entry_price, entry_time = 'LONG', price, time
    save_bot_state(position_state, entry_price, entry_time)
    print(f"\n🟢 POSITION OPENED at ${price:,.2f}")

def close_position(price, time, reason):
    global position_state, entry_price, entry_time
    pnl_usd = (price - entry_price) * POSITION_SIZE_ETH
    pnl_pct = ((price - entry_price) / entry_price) * 100
    log_trade(entry_time, time, entry_price, price, pnl_usd, pnl_pct, reason)
    session_trades.append({'pnl_usd': pnl_usd, 'entry_time': entry_time, 'exit_time': time})
    
    position_state, entry_price, entry_time = 'FLAT', None, None
    save_bot_state(position_state, entry_price, entry_time)
    print(f"\n🔴 POSITION CLOSED: {reason} | P&L: ${pnl_usd:+,.2f}")

def update_position(signal, current_price, current_time):
    if position_state == 'FLAT' and signal == 'LONG':
        open_position(current_price, current_time)
    elif position_state == 'LONG' and signal != 'LONG':
        close_position(current_price, current_time, f"Signal changed to {signal}")

# ============================================================
# TECHNICAL ANALYSIS
# ============================================================

def calculate_adx(buffer):
    df = pd.DataFrame(list(buffer))
    adx_indicator = ADXIndicator(high=df['high'], low=df['low'], close=df['close'], window=ADX_PERIOD)
    return adx_indicator.adx().iloc[-1], adx_indicator.adx_pos().iloc[-1], adx_indicator.adx_neg().iloc[-1]

def determine_signal(adx, plus_di, minus_di):
    if adx >= ADX_THRESHOLD:
        return "LONG" if plus_di > minus_di else "BEARISH"
    return "CHOPPY"

# ============================================================
# MAIN LIVE STREAM WITH RECONNECT
# ============================================================

async def stream_with_logging():
    global last_price, last_time
    URI = f"wss://stream.binance.com:9443/ws/{SYMBOL.lower()}@kline_1m"
    candle_buffer = deque(maxlen=LOOKBACK)
    
    # Bootstrap historical candles
    client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_SECRET_KEY'))
    klines = client.get_historical_klines(SYMBOL, Client.KLINE_INTERVAL_1MINUTE, limit=LOOKBACK)
    for k in klines:
        candle_buffer.append({'timestamp': pd.to_datetime(k[0], unit='ms'), 'high': float(k[2]), 'low': float(k[3]), 'close': float(k[4])})

    print(f"✅ State Loaded: {position_state} | Running live stream...")

    while True:
        try:
            async with websockets.connect(URI) as ws:
                while True:
                    msg = json.loads(await ws.recv())
                    kline = msg['k']
                    last_price, last_time = float(kline['c']), datetime.fromtimestamp(kline['t']/1000).strftime('%H:%M')

                    if kline['x']:  # Candle Closed
                        new_candle = {'timestamp': pd.to_datetime(kline['t'], unit='ms'), 'high': float(kline['h']), 'low': float(kline['l']), 'close': float(kline['c'])}
                        candle_buffer.append(new_candle)
                        adx, pdi, mdi = calculate_adx(candle_buffer)
                        signal = determine_signal(adx, pdi, mdi)
                        
                        log_signal(last_time, new_candle['close'], adx, pdi, mdi, signal, position_state)
                        update_position(signal, new_candle['close'], last_time)
                        print(f"[{last_time}] Close: ${new_candle['close']:.2f} | ADX: {adx:.2f} | Signal: {signal}")
                    else:
                        print(f"\r⏳ [{last_time}] Price: ${last_price:,.2f}...", end='', flush=True)

        except Exception as e:
            print(f"\n⚠️ Connection Error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    initialise_trade_log()
    initialise_performance_log()
    try:
        asyncio.run(stream_with_logging())
    except KeyboardInterrupt:
        print("\nStopping bot...")